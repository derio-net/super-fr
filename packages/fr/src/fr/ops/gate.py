"""The DevOps stage: `fr ops gate --run <id>` (spec 2026-10-22-fr-ops R15, §I).

A sequencer in the collected close-out's style (`fr.triage.batch_closeout`): it decides
the next stage and runs nothing itself. Its ports run everything:

- `GateHost` runs THIS `fr` on the harness host, in the base checkout (`fr isolation
  up/exec/verify-merge`), and fetches;
- `OpsTree` is the ops workspace `chore/ops-<slug>` (`fr.triage.gitseam.Worktree`): git
  there, and this `fr` with the workspace as its checkout (`fr ops trust`, `fr closeout
  outcome`, `fr gate pass`, `fr archive`);
- `GateForge` is the `GhClient` adapter (another forge's merge raises
  `UnsupportedForgeOperation`, which names the manual merge);
- `GatePrompt` is the operator's terminal; `GateState` the operator's host-side record of
  the stages done and the head stage 1 verified (`HostGateState`).

The eight stages (`STAGES`) run in order. Each one's completion is recorded host-side,
per operator, outside every checkout (`gate_state_path`), so a rerun resumes at the
first stage that state does not record; a forge-MERGED PR counts as stage 2 done. The
`gate-stage-<n>` decisions in the plan journal are an audit trail and are NEVER read:
the ops workspace is cut from the PR, so whatever it carries is PR-controlled. The
first failure stops the run, naming the stage. Pre-merge evidence is committed on the ops
branch and never pushed to the PR head, so the reviewed head and its checks stay valid.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from fr.ghclient import UnsupportedForgeOperation
from fr.journal.model import (
    JournalEntry,
    append_journal_entry,
    journal_now,
    resolve_journal_read_path,
)

if TYPE_CHECKING:
    from fr.ops.load import LoadedOp
    from fr.run.model import RunState
    from fr.spec import Step as TestPlanStep

STAGE_PREFIX = "gate-stage-"
PROFILES_FILE = ".devcontainer/fr-profiles.yaml"
ARCHIVED_JOURNALS = "docs/superpowers/implemented/journals"
FIRST_PUSHED_STAGE = 3  # the ops branch holds only default-branch code from the rebase on
GATE_DIR_ENV = "FR_OPS_GATE_DIR"
SHA_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
CLOSED_STATES = frozenset({"DONE", "N/A"})
STATUS_OK_CODES = (0, 1, 3)  # every op reported; 2 is a refusal (`fr ops status`, R3)


class StageFailed(Exception):  # noqa: N818 — a stage's stop, not a fault
    """A stage could not complete; `why` is what the operator reads."""

    def __init__(self, why: str, *, code: int = 1) -> None:
        super().__init__(why)
        self.why = why
        self.code = code  # 2: a refusal (the merge head moved), 1: any other stop


# --------------------------------------------------------------------------- ports


class GateHost(Protocol):
    def fr(self, args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        """This `fr` in the base checkout: (exit, stdout). *terminal*: the operator's
        terminal attached and nothing captured (an `interactive: true` op)."""
        ...

    def fetch(self, ref: str) -> None: ...

    def changed_paths(self, base: str, head: str, paths: Sequence[str]) -> list[str]:
        """The *paths* (pathspecs) that differ between *base* and *head*, in the base
        checkout (`git diff --name-only --end-of-options <base> <head> -- <paths>`)."""
        ...

    def origin_head(self) -> str | None:
        """The default branch the base checkout's `origin/HEAD` names, or None."""
        ...

    def workspace(self, branch: str) -> OpsTree | None:
        """The ops workspace of *branch*, or None while it is not up."""
        ...


class OpsTree(Protocol):
    path: Path

    def head(self) -> str: ...

    def show(self, ref: str, path: str) -> str | None:
        """*path*'s text at *ref*, or None when it does not exist there."""
        ...

    def fr(self, args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        """This `fr` on the host with the ops workspace as its checkout."""
        ...

    def commit_paths(self, paths: list[str], message: str) -> str | None: ...

    def rebase_onto(self, new_base: str, upstream: str) -> None: ...

    def push(self, branch: str, lease: str | None = None) -> None:
        """Push HEAD to *branch*: with *lease*, only while the remote is still at that sha
        (`--force-with-lease`); without, only as a new branch (refusing an existing one)."""
        ...


class GateForge(Protocol):
    def default_branch(self, *, cwd: Path, run: Any = None) -> str | None: ...

    def pr_view(self, repo: str, number: int) -> dict[str, Any]: ...

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]: ...

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]: ...

    def repo_merge_methods(self, repo: str) -> dict[str, Any]: ...

    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None: ...

    def open_pr_for_head(self, repo: str, branch: str) -> dict[str, Any] | None: ...

    def pr_create(self, repo: str, *, head: str, base: str, title: str, body: str) -> int: ...


class GatePrompt(Protocol):
    def confirm(self, text: str) -> bool: ...

    def ask(self, text: str) -> str: ...


class AuditLog(Protocol):
    def record(self, n: int, title: str, body: str) -> None: ...


class JournalLedger:
    """The `gate-stage-<n>` decisions written to the ops workspace's plan journal (live, or
    archived once stage 8 moved it). AUDIT ONLY: the workspace is cut from the PR, so
    anything it carries is PR-controlled and is never read back (p4-gate-state-host-side).
    The stage state is `HostGateState`."""

    def __init__(self, root: Path, slug: str) -> None:
        self.root = root
        self.slug = slug

    def record(self, n: int, title: str, body: str) -> None:
        path = resolve_journal_read_path(self.root, "plan", self.slug)
        text = path.read_text() if path.is_file() else ""
        sid, k = f"{STAGE_PREFIX}{n}", 1
        while f"id={sid} " in text:  # a retried stage writes a second audit line
            k += 1
            sid = f"{STAGE_PREFIX}{n}-{k}"
        entry = JournalEntry(
            kind="decision",
            scope="plan",
            id=sid,
            created=journal_now(),
            title=title,
            body=body,
        )
        append_journal_entry(path, self.slug, entry)


def gate_state_dir() -> Path:
    """`$FR_OPS_GATE_DIR`, else `$XDG_STATE_HOME/fr/ops-gate`, else
    `~/.local/state/fr/ops-gate`: beside the trust store, outside every checkout."""
    override = os.environ.get(GATE_DIR_ENV)
    if override:
        return Path(override)
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "fr" / "ops-gate"


def gate_state_path(repo_root: Path, run_id: str) -> Path:
    from fr.ops import trust

    return gate_state_dir() / trust.repo_key(repo_root) / f"{run_id}.json"


class GateState(Protocol):
    def stages(self) -> set[int]: ...

    def head(self) -> str | None: ...

    def cut(self) -> str | None: ...

    def set_cut(self, sha: str) -> None: ...

    def pushed(self) -> str | None: ...

    def set_pushed(self, sha: str) -> None: ...

    def mark(self, n: int, *, head: str | None = None) -> None: ...


class HostGateState:
    """The operator's own record of a run's DevOps stage (R15): the stages done and the PR
    head stage 1 verified, as JSON written atomically 0600 (`fr.ops.trust`'s writer)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _data(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def stages(self) -> set[int]:
        raw = self._data().get("stages") or []
        return {n for n in raw if isinstance(n, int) and not isinstance(n, bool)}

    def head(self) -> str | None:
        head = self._data().get("head")
        return str(head) if head is not None else None

    def cut(self) -> str | None:
        """The PR head the ops workspace was cut from (p4-r5)."""
        cut = self._data().get("cut")
        return str(cut) if cut is not None else None

    def set_cut(self, sha: str) -> None:
        self._write({**self._data(), "cut": sha})

    def pushed(self) -> str | None:
        """The ops branch's sha fr last pushed: the lease of the next push."""
        pushed = self._data().get("pushed")
        return str(pushed) if pushed is not None else None

    def set_pushed(self, sha: str) -> None:
        self._write({**self._data(), "pushed": sha})

    def mark(self, n: int, *, head: str | None = None) -> None:
        data = self._data()
        data["stages"] = sorted(self.stages() | {n})
        if head is not None:
            data["head"] = head
        self._write(data)

    def _write(self, data: dict[str, Any]) -> None:
        from fr.ops.trust import _write_private

        _write_private(self.path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def valid_sha(sha: str, what: str) -> str:
    """*sha* when it is a full hex object id; a refusal (exit 2) otherwise, so nothing a
    forge or a file says reaches git as an option."""
    if not SHA_RE.match(sha or ""):
        raise StageFailed(f"{what} {sha!r} is not a full commit sha; nothing done", code=2)
    return sha


# ------------------------------------------------------------------------- context


@dataclass(frozen=True)
class GateTarget:
    """What the command resolved: the run, its PR, its plan and the ops profile."""

    run: RunState
    repo: str  # OWNER/REPO
    pr: int
    plan_rel: str  # docs/superpowers/plans/<slug>
    profile: str
    primary: Path  # the base checkout `fr isolation …` is told about (`--repo`)
    method: str | None = None

    @property
    def slug(self) -> str:
        return Path(self.plan_rel).name

    @property
    def feature(self) -> str:
        return self.run.branch

    @property
    def ops_branch(self) -> str:
        return f"chore/ops-{self.slug}"


@dataclass
class Gate:
    """One `fr ops gate` invocation: the target, its ports and what it said."""

    target: GateTarget
    host: GateHost
    forge: GateForge
    prompt: GatePrompt
    say: Callable[[str], None]
    state: GateState
    audit_factory: Callable[[Path, str], AuditLog] = JournalLedger
    _view: dict[str, Any] | None = field(default=None, repr=False)
    _default: str | None = field(default=None, repr=False)

    # -- reads ----------------------------------------------------------------

    def view(self, *, fresh: bool = False) -> dict[str, Any]:
        if self._view is None or fresh:
            self._view = self.forge.pr_view(self.target.repo, self.target.pr)
        return self._view

    @property
    def default(self) -> str:
        """The repo's default branch from TRUSTED sources only (p4-r1 addendum): the
        forge's repo metadata, cross-checked with the base checkout's `origin/HEAD`;
        never the PR's own base ref, which its author chooses."""
        if self._default is None:
            forge = self.forge.default_branch(cwd=self.target.primary)
            origin = self.host.origin_head()
            if not forge or not origin:
                raise StageFailed(
                    "cannot establish the default branch (forge: "
                    f"{forge or 'unknown'}, origin/HEAD: {origin or 'unset'}); run "
                    "`git remote set-head origin --auto` in the base clone",
                    code=2,
                )
            if forge != origin:
                raise StageFailed(
                    f"the forge's default branch {forge} is not origin/HEAD's {origin}; "
                    "nothing done",
                    code=2,
                )
            self._default = forge
        return self._default

    def require_default_base(self) -> None:
        """Refuse a PR whose base is not the trusted default branch: a side branch could
        carry the very profile the stage compares against."""
        base = str(self.view().get("base_ref") or "")
        if base != self.default:
            raise StageFailed(
                f"PR #{self.target.pr} is based on {base or 'unknown'}, not the default "
                f"branch {self.default}; the DevOps stage merges only into it",
                code=2,
            )

    def publish(self, tree: OpsTree) -> None:
        """Push the ops branch (only once stage 3 rebased it onto the default branch, so it
        never carries unmerged PR code), leased on the sha fr last pushed."""
        tree.push(self.target.ops_branch, lease=self.state.pushed())
        self.state.set_pushed(tree.head())

    def tree(self) -> OpsTree:
        tree = self.host.workspace(self.target.ops_branch)
        if tree is None:
            raise StageFailed(f"the ops workspace {self.target.ops_branch} is not up")
        return tree

    def recorded(self) -> set[int]:
        """The stages done, by the HOST state only: never by the ops workspace."""
        return self.state.stages()

    # -- helpers the stages share ---------------------------------------------

    def exec_args(self, *argv: str) -> list[str]:
        t = self.target
        return ["isolation", "exec", "--repo", str(t.primary), "--branch", t.ops_branch,
                "--", "fr", *argv]  # fmt: skip

    def trust(self, tree: OpsTree) -> None:
        """R19: the grant is made on the HOST, at the operator's terminal (`fr ops trust`
        says "already trusted" and writes nothing when it holds), never in the container,
        which sees the store read-only."""
        code, _ = tree.fr(["ops", "trust", "--plan", self.target.plan_rel], terminal=True)
        if code != 0:
            raise StageFailed(
                f"the op set is not trusted (`fr ops trust --plan {self.target.plan_rel}` "
                f"exited {code}); no probe ran"
            )

    def verified_head(self, tree: OpsTree) -> str:
        """The PR head stage 1 cut the ops workspace from and verified the pre-merge ops
        on (p4-merge-head-pinned): the only head stage 2 merges and stage 3 rebases from."""
        head = self.state.head()
        if not head:
            raise StageFailed(f"stage 1 recorded no PR head; {self.redo_stage_1()}", code=2)
        return valid_sha(head, "the recorded PR head")

    def pinned_head(self) -> str:
        """The PR head this run of the stage is pinned to: stage 1's recorded head, else
        the head the ops workspace was cut from."""
        head = self.state.cut() or self.state.head()
        if not head:
            raise StageFailed(f"no PR head is recorded; {self.redo_stage_1()}", code=2)
        return valid_sha(head, "the recorded PR head")

    def redo_stage_1(self) -> str:
        t = self.target
        return (
            f"re-run stage 1 against the PR's head: `fr isolation down --repo {t.primary} "
            f"--branch {t.ops_branch}`, then `fr ops gate --run {t.run.run} --yes` (it "
            "re-cuts the ops workspace and re-checks trust)"
        )

    def finish(self, tree: OpsTree, n: int, body: str, *, head: str | None = None) -> None:
        """Write stage *n*'s audit line and commit the workspace's evidence on the ops
        branch; from stage 3 on, push it too (p4-r11 correction: before the stage-3 rebase
        the branch holds the UNMERGED PR head, which must never reach a base-repo branch).
        Only then mark the stage done, so a failed commit or push leaves it to retry."""
        name = STAGE_BY_NUMBER[n].name
        self.audit_factory(tree.path, self.target.slug).record(
            n, f"DevOps stage {n} done: {name}", body
        )
        try:
            tree.commit_paths(["docs"], f"chore(ops): {self.target.slug} DevOps stage {n} — {name}")
            if n >= FIRST_PUSHED_STAGE:
                self.publish(tree)
        except Exception as exc:  # noqa: BLE001 — git's own words
            raise StageFailed(
                f"cannot commit and push stage {n}'s record to {self.target.ops_branch}: {exc}"
            ) from exc
        self.state.mark(n, head=head)
        self.say(f"stage {n} ({name}): done")


# --------------------------------------------------------------------- op stages


def _ops(tree: OpsTree, plan_rel: str, phase: str) -> list[LoadedOp]:
    from fr.ops.engine import OrderError, order
    from fr.ops.load import OpsLoadError, load_ops

    try:
        every = load_ops(tree.path / plan_rel, tree.path).ops
        chosen = [lo for lo in every if lo.op.phase == phase]
        return order(chosen, known={lo.op.id for lo in every})
    except (OpsLoadError, OrderError) as exc:
        raise StageFailed(f"the plan's ops cannot be read: {exc}") from exc


def head_entry_ids(tree: OpsTree, head: str, scope: str, slug: str) -> set[str]:
    """The ids of the journal entries the PR head itself carries: PR-controlled, so none
    of them closes anything inside the stage (p4-r2)."""
    from fr.journal.model import JournalParseError, journal_read_candidates, parse_journal

    ids: set[str] = set()
    # every location the evidence readers resolve, never only the live one (p4-r2 addendum)
    for path in journal_read_candidates(Path("."), scope, slug):  # type: ignore[arg-type]
        rel = path.as_posix()
        text = tree.show(head, rel)
        if not text:
            continue
        try:
            ids |= {e.id for e in parse_journal(text)}
        except JournalParseError as exc:  # never an empty exclusion: a refusal
            raise StageFailed(
                f"the PR head's journal {rel} cannot be read ({exc}); nothing it carries "
                "can be told apart from the ops branch's own evidence",
                code=2,
            ) from exc
    return ids


def _closed(
    lo: LoadedOp,
    row: Mapping[str, Any] | None,
    tree: OpsTree,
    slug: str,
    at_head: set[str],
) -> str | None:
    """The op's closing label, or None (R15, p4-r2): its LIVE status row must read DONE or
    N/A; a closure that comes from the journal (an attestation, a proof, a recorded n/a)
    counts only when its entry was added on the ops branch, never one the PR carries."""
    from fr.ops.evidence import JournalEvidence

    if row is None or str(row.get("state")) not in CLOSED_STATES:
        return None
    label = str(row.get("label") or row.get("state"))
    how = str(row.get("how") or "")
    from_journal = how in ("attested", "proof") or "recorded" in label
    if from_journal:
        ev = JournalEvidence(tree.path, slug).latest(lo.op.id, runbook=False)
        if ev is None or ev.entry_id in at_head:
            return None
    return label


def _unclosed(
    gate: Gate, tree: OpsTree, ops: Sequence[LoadedOp], rows: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    """Each op the live status and the ops branch's own evidence do not close."""
    at_head = head_entry_ids(tree, gate.pinned_head(), "plan", gate.target.slug)
    out = []
    for lo in ops:
        row = rows.get(lo.op.id)
        if _closed(lo, row, tree, gate.target.slug, at_head) is None:
            live = str(row.get("label") or row.get("state")) if row else "not reported"
            out.append(f"{lo.op.id}: {live}")
    return out


def _status_rows(gate: Gate, phase: str) -> dict[str, Mapping[str, Any]]:
    code, out = gate.host.fr(
        gate.exec_args("ops", "status", "--plan", gate.target.plan_rel, "--phase", phase, "--json")
    )
    if code not in STATUS_OK_CODES:
        raise StageFailed(f"`fr ops status --phase {phase}` in the ops workspace exited {code}")
    try:
        rows = json.loads(out or "[]")
    except json.JSONDecodeError as exc:
        raise StageFailed(f"`fr ops status --phase {phase}` printed no readable report") from exc
    for r in rows:
        who = f" (as {r['identity']})" if r.get("identity") else ""
        gate.say(f"  {r['label']}  {r['op']}  {r.get('reason') or r.get('summary') or ''}{who}")
    return {str(r["op"]): r for r in rows}


def apply_phase(gate: Gate, phase: str) -> None:
    """Status, then each op not closed by recorded evidence: confirmed on the host,
    applied through `fr isolation exec … fr ops apply <id> --yes [--yes-mutating]`."""
    from fr.ops.apply import confirmation_text

    t = gate.target
    tree = gate.tree()
    gate.trust(tree)
    ops = _ops(tree, t.plan_rel, phase)
    gate.say(f"{phase} ops of {t.slug}: {len(ops)}")
    rows = _status_rows(gate, phase)
    at_head = head_entry_ids(tree, gate.pinned_head(), "plan", t.slug)
    for lo in ops:
        op = lo.op
        if _closed(lo, rows.get(op.id), tree, t.slug, at_head) is not None:
            continue
        state = str(rows.get(op.id, {}).get("state") or "")
        flags = ["--yes"]
        if state not in CLOSED_STATES:  # it will run: the operator confirms it here
            if not gate.prompt.confirm(confirmation_text(lo)):
                raise StageFailed(f"op {op.id} declined; nothing applied")
            flags += ["--yes-mutating"] if op.mutating else []
        argv = gate.exec_args("ops", "apply", op.id, "--plan", t.plan_rel, *flags)
        code, out = gate.host.fr(argv, terminal=op.interactive)
        if out.strip():
            gate.say(out.rstrip())
        if code != 0:
            raise StageFailed(f"op {op.id}: `fr ops apply {op.id}` exited {code}")
    left = _unclosed(gate, tree, ops, _status_rows(gate, phase))
    if left:
        attest = " ".join(shlex.quote(a) for a in gate.exec_args(
            "ops", "attest", "<op>", "--plan", t.plan_rel, "--note", "<what you did>"))  # fmt: skip
        raise StageFailed(
            f"{phase} ops not closed: {'; '.join(left)} — an op with no "
            f"check closes by attestation (`fr {attest}`), any other by a passing check"
        )


# ------------------------------------------------------------------------ stages


def stage_1(gate: Gate) -> None:
    """Bring up (or reuse) the ops workspace, cut from the PR head; pre-merge ops."""
    t = gate.target
    head = valid_sha(str(gate.view(fresh=True).get("head_oid") or ""), f"PR #{t.pr}'s head")
    gate.require_default_base()
    gate.host.fetch(t.feature)
    gate.host.fetch(gate.default)
    archived = gate.host.changed_paths(f"origin/{gate.default}", head, [ARCHIVED_JOURNALS])
    if archived:  # p4-r2 addendum: a feature PR has no business in the archive
        raise StageFailed(
            f"PR #{t.pr} adds or changes archived journals ({', '.join(archived)}); "
            "nothing was brought up",
            code=2,
        )
    pinned = [f".devcontainer/{t.profile}", PROFILES_FILE]
    changed = gate.host.changed_paths(f"origin/{gate.default}", head, pinned)
    if changed:  # p4-r1: never bring up a privileged profile the PR itself rewrote
        raise StageFailed(
            f"PR #{t.pr} changes the ops profile ({', '.join(changed)}); its devcontainer "
            "runs with the ops credentials, so a profile change must merge in its own PR "
            "first. Nothing was brought up",
            code=2,
        )
    reused = gate.host.workspace(t.ops_branch)
    if reused is not None and gate.state.cut() != head:  # p4-r5: exactly the PR head
        raise StageFailed(
            f"the ops workspace {t.ops_branch} was cut from {gate.state.cut() or 'unknown'}, "
            f"not PR #{t.pr}'s head {head}; " + gate.redo_stage_1()
        )
    if reused is None:
        code, _ = gate.host.fr(["isolation", "up", "--repo", str(t.primary), "--profile",
                                t.profile, "--branch", t.ops_branch, "--base", head])  # fmt: skip
        if code != 0 or gate.host.workspace(t.ops_branch) is None:
            raise StageFailed(f"`fr isolation up --branch {t.ops_branch}` exited {code}")
        gate.state.set_cut(head)
        gate.say(f"ops workspace {t.ops_branch} up on profile {t.profile}, from {head[:12]}")
    apply_phase(gate, "pre-merge")
    gate.finish(gate.tree(), 1, f"head: {head}\npre-merge ops closed on {t.ops_branch}", head=head)


def _checks_green(gate: Gate) -> None:
    from fr.triage.batch_drive import checks_verdict

    t = gate.target
    every = gate.forge.pr_checks(t.repo, t.pr)
    counts = {"pass": 0, "fail": 0, "pending": 0}
    for c in every:
        bucket = str(c.get("bucket") or "")
        key = "pass" if bucket in ("pass", "skipping") else bucket
        key = "fail" if key == "cancel" else key
        if key in counts:
            counts[key] += 1
    verdict, names = checks_verdict(gate.forge.pr_required_checks(t.repo, t.pr), counts,
                                    ci_none=False)  # fmt: skip
    if verdict != "green":
        raise StageFailed(f"PR #{t.pr}'s checks are {verdict}: {', '.join(names)}")


def stage_2(gate: Gate) -> None:
    """The merge: no open pre-merge op, green required checks, an explicit confirmation."""
    from fr.triage.batch_merge import choose_method

    t = gate.target
    tree = gate.tree()
    view = gate.view(fresh=True)
    state = str(view.get("state") or "")
    if state != "OPEN":
        raise StageFailed(f"PR #{t.pr} is {state or 'UNKNOWN'}, not open: nothing to merge")
    gate.require_default_base()  # a base retargeted since stage 1
    head = gate.verified_head(tree)
    live = str(view.get("head_oid") or "")
    if live != head:
        raise StageFailed(
            f"PR #{t.pr}'s head moved from {head} (verified in stage 1) to {live or 'unknown'}; "
            f"nothing merged: {gate.redo_stage_1()}",
            code=2,
        )
    pre = _ops(tree, t.plan_rel, "pre-merge")
    gate.trust(tree)
    rows = _status_rows(gate, "pre-merge")  # live, never the PR-controlled journal (p4-r2)
    left = _unclosed(gate, tree, pre, rows)
    if left:
        raise StageFailed("pre-merge ops are still open: " + "; ".join(left))
    _checks_green(gate)
    lines = [f"  {lo.op.id}: {rows[lo.op.id].get('label')}" for lo in pre] or [
        "  (no pre-merge op)"
    ]
    text = f"MERGE PR #{t.pr} of {t.repo} at head {head}\npre-merge state:\n" + "\n".join(lines)
    if not gate.prompt.confirm(text):  # its own confirmation, --yes or not
        raise StageFailed(f"the merge of PR #{t.pr} was not confirmed; nothing merged")
    try:
        method = choose_method(t.method, gate.forge.repo_merge_methods(t.repo))
        gate.forge.pr_merge(t.repo, t.pr, head_sha=head, method=method)
    except UnsupportedForgeOperation as exc:
        raise StageFailed(
            f"{exc}: merge PR #{t.pr} by hand in the forge at head {head}, then re-run "
            "`fr ops gate` (a merged PR counts as this stage done)"
        ) from exc
    except Exception as exc:  # noqa: BLE001 — the forge's refusal is the operator's to read
        raise StageFailed(f"the forge refused the merge of PR #{t.pr}: {exc}") from exc
    gate.finish(tree, 2, f"merged PR #{t.pr} at {head}")


def stage_3(gate: Gate) -> None:
    """verify-merge, rebase the ops workspace onto the default branch, every `ready:`."""
    t = gate.target
    code, _ = gate.host.fr(["isolation", "verify-merge", "--repo", str(t.primary), "--branch",
                            t.feature, "--default-branch", gate.default])  # fmt: skip
    if code != 0:
        raise StageFailed(f"`fr isolation verify-merge --branch {t.feature}` exited {code}")
    tree = gate.tree()
    head = gate.verified_head(tree)
    merged = str(gate.view(fresh=True).get("head_oid") or "")
    if merged != head:
        raise StageFailed(
            f"the merged PR #{t.pr}'s head {merged or 'unknown'} is not the head stage 1 "
            f"verified ({head}); nothing rebased",
            code=2,
        )
    try:
        tree.rebase_onto(f"origin/{gate.default}", head)
    except Exception as exc:  # noqa: BLE001 — git's own words
        raise StageFailed(f"cannot rebase {t.ops_branch} onto {gate.default}: {exc}") from exc
    gate.trust(tree)  # the tree moved: the grant must cover the merged revision
    code, out = gate.host.fr(
        gate.exec_args("ops", "status", "--plan", t.plan_rel, "--phase", "post-merge", "--ready")
    )
    if out.strip():
        gate.say(out.rstrip())
    if code == 2:  # p4-r10: a refusal (an untrusted set, a bad carrier), not "not ready"
        raise StageFailed(
            "`fr ops status --ready` refused (exit 2; its reason is printed above); "
            "no ready probe ran",
            code=2,
        )
    if code != 0:
        raise StageFailed("a post-merge op's `ready:` does not pass yet; re-run once it does")
    gate.finish(tree, 3, f"merge verified; {t.ops_branch} rebased onto {gate.default}; ready")


def stage_4(gate: Gate) -> None:
    apply_phase(gate, "post-merge")
    gate.finish(gate.tree(), 4, "post-merge ops closed")


_ANSWER = re.compile(r"^\s*(ran|na|n/a|owed)\s+(\S.*)$", re.I)


def stage_5(gate: Gate) -> None:
    """Each Test Plan step whose effective gate is devops, recorded with `fr closeout
    outcome` (ran, n/a, or owed — which stage 6 then refuses)."""
    from fr.ops.holds import gated_steps

    t = gate.target
    tree = gate.tree()
    spec_slug = _spec_slug(t.run)
    at_head = head_entry_ids(tree, gate.pinned_head(), "spec", spec_slug) if spec_slug else set()
    every = gated_steps(tree.path, t.run, "devops")
    trusted = gated_steps(tree.path, t.run, "devops", exclude=at_head)
    for (step, kind), (_, mine) in zip(every, trusted, strict=True):
        if mine is not None:
            continue
        answer = gate.prompt.ask(
            f"Test Plan step {step.n} (devops): {step.text}\n"
            "Walk it, then answer `ran <evidence>`, `na <reason>` or `owed <why>`:"
        )
        m = _ANSWER.match(answer or "")
        if m is None:
            raise StageFailed(f"Test Plan step {step.n} has no outcome; walk it and re-run")
        how, text = m.group(1).lower(), m.group(2).strip()
        flag = {"ran": ("--ran", "--evidence"), "owed": ("--owed", "--why")}.get(
            how, ("--na", "--reason")
        )
        argv = ["closeout", "outcome", "--run", t.run.run, "--step", str(step.n),
                flag[0], flag[1], text]  # fmt: skip
        if kind is not None:  # an outcome the PR carries, or an owed one: record over it
            argv.append("--supersede")
        code, out = tree.fr(argv)
        if code != 0:
            raise StageFailed(f"`fr closeout outcome --step {step.n}` exited {code}: {out}")
    gate.finish(tree, 5, "devops Test Plan steps recorded")


def _spec_slug(run: RunState) -> str | None:
    from fr.archive import spec_slug_of
    from fr.requirements import run_spec

    spec = run_spec(run)
    return spec_slug_of(Path(spec)) if spec else None


def tester_steps(gate: Gate, tree: OpsTree) -> list[TestPlanStep]:
    from fr.ops.holds import gated_steps

    return [s for s, kind in gated_steps(tree.path, gate.target.run, "tester") if kind is None]


def stage_6(gate: Gate) -> None:
    """`fr gate pass --gate devops --run <id>` from the ops workspace; the comment lists
    the steps the Tester gate still owns."""
    t = gate.target
    tree = gate.tree()
    notes = f"DevOps stage of run {t.run.run}: ops and devops steps recorded on {t.ops_branch}"
    owed = tester_steps(gate, tree)
    if owed:
        notes += "; the Tester gate owns: " + "; ".join(f"step {s.n}: {s.text}" for s in owed)
    code, out = tree.fr(["gate", "pass", "--repo", t.repo, "--pr", str(t.pr), "--gate",
                         "devops", "--run", t.run.run, "--notes", notes, "--yes"])  # fmt: skip
    if out.strip():
        gate.say(out.rstrip())
    if code != 0:
        raise StageFailed(
            f"`fr gate pass --gate devops --run {t.run.run}` exited {code}" + _recovery(gate, tree)
        )
    gate.finish(tree, 6, "gate:devops passed")


def _recovery(gate: Gate, tree: OpsTree) -> str:
    """p4-r3: for each devops step that is not closed, the command that records it in the
    ops workspace; a rerun then retries the gate pass."""
    from fr.ops.holds import gated_steps

    t = gate.target
    open_steps = [
        (s, kind) for s, kind in gated_steps(tree.path, t.run, "devops") if kind != "discovery"
    ]
    if not open_steps:
        return ""
    # A step already recorded (owed) is recorded over only with --supersede: an owed
    # outcome may already be filed as an fr:owed issue, so it is never overwritten silently.
    lines = [
        f"  fr isolation exec --repo {t.primary} --branch {t.ops_branch} -- fr closeout "
        f"outcome --run {t.run.run} --step {s.n} --ran --evidence '<what it showed>'"
        + (" --supersede" if kind is not None else "")
        for s, kind in open_steps
    ]
    return (
        "; record each devops step that is not closed (or `--na --reason …`), then re-run "
        "`fr ops gate`:\n" + "\n".join(lines)
    )


def stage_7(gate: Gate) -> None:
    """The tester hand-off: gate:tester is kept while tester steps remain."""
    tree = gate.tree()
    owed = tester_steps(gate, tree)
    if owed:
        gate.say(f"gate:tester stays on PR #{gate.target.pr}; the Tester gate owns:")
        for s in owed:
            gate.say(f"  step {s.n}: {s.text}")
        body = "tester steps handed off: " + ", ".join(str(s.n) for s in owed)
    else:
        body = "no tester step remains"
    gate.finish(tree, 7, body)


def stage_8(gate: Gate) -> None:
    """`fr archive --branch <feature>` filing the run's out-of-scope findings as the
    close-out brief would (p4-r4), then the ops branch as the housekeeping PR."""
    from fr.run.closeout import archive_issue_args

    t = gate.target
    tree = gate.tree()
    if (tree.path / t.plan_rel).is_dir():
        argv = ["archive", "--branch", t.feature, *archive_issue_args(tree.path, t.run)]
        code, out = tree.fr(argv)
        if out.strip():
            gate.say(out.rstrip())
        if code != 0:
            raise StageFailed(f"`fr {shlex.join(argv)}` exited {code}")
        tree.commit_paths(["docs"], f"chore(ops): archive {t.slug}")
    try:
        gate.publish(tree)
        if gate.forge.open_pr_for_head(t.repo, t.ops_branch) is None:
            title = f"chore: DevOps stage of {t.slug} (run {t.run.run})"
            body = (
                f"The DevOps stage's evidence and archive for PR #{t.pr} (run {t.run.run}): "
                f"the op evidence, the gate-stage audit decisions and `fr archive --branch "
                f"{t.feature}`."
            )
            number = gate.forge.pr_create(t.repo, head=t.ops_branch, base=gate.default,
                                          title=title, body=body)  # fmt: skip
            gate.say(f"housekeeping PR #{number} opened from {t.ops_branch}")
    except Exception as exc:  # noqa: BLE001 — git's or the forge's own words
        raise StageFailed(f"cannot publish {t.ops_branch}: {exc}") from exc
    gate.finish(tree, 8, f"archived; housekeeping PR from {t.ops_branch}")


# ------------------------------------------------------------------- the table


@dataclass(frozen=True)
class Stage:
    number: int
    name: str
    what: str
    done: Callable[[Gate, set[int]], bool]
    act: Callable[[Gate], None]


def _recorded(n: int) -> Callable[[Gate, set[int]], bool]:
    return lambda gate, recorded: n in recorded


def _cut(gate: Gate, recorded: set[int]) -> bool:
    """Stage 1 is done while its record stands AND its workspace does: an operator who
    took the workspace down to re-cut it from a moved head (`redo_stage_1`) gets stage 1
    again, as long as nothing was merged yet."""
    if 1 not in recorded:
        return False
    if 2 in recorded or str(gate.view().get("state") or "") == "MERGED":
        return True
    return gate.host.workspace(gate.target.ops_branch) is not None


def _merged(gate: Gate, recorded: set[int]) -> bool:
    return 2 in recorded or str(gate.view().get("state") or "") == "MERGED"


def _passed(gate: Gate, recorded: set[int]) -> bool:
    return 6 in recorded or "gate:devops-passed" in {
        str(n) for n in gate.view().get("labels") or []
    }


STAGES: tuple[Stage, ...] = (
    Stage(1, "pre-merge ops", "bring up or reuse the ops workspace from the PR head; "
          "trust; pre-merge status and apply", _cut, stage_1),
    Stage(2, "merge", "merge the PR after a terminal confirmation naming it, its head "
          "and the pre-merge state (no open pre-merge op, required checks green)",
          _merged, stage_2),
    Stage(3, "verify-merge, rebase, ready", "fr isolation verify-merge; rebase the ops "
          "workspace onto the default branch; every `ready:`", _recorded(3), stage_3),
    Stage(4, "post-merge ops", "post-merge status and apply", _recorded(4), stage_4),
    Stage(5, "devops steps", "record each devops Test Plan step with fr closeout outcome",
          _recorded(5), stage_5),
    Stage(6, "gate pass", "fr gate pass --gate devops --run <id>", _passed, stage_6),
    Stage(7, "tester hand-off", "keep gate:tester for the steps the Tester gate owns",
          _recorded(7), stage_7),
    Stage(8, "archive and housekeeping PR", "fr archive --branch <feature>; open the ops "
          "branch as the housekeeping PR", _recorded(8), stage_8),
)  # fmt: skip
STAGE_BY_NUMBER = {s.number: s for s in STAGES}


@dataclass(frozen=True)
class GateResult:
    ok: bool
    ran: tuple[int, ...] = ()
    failed: int | None = None
    why: str = ""
    code: int = 0  # the command's exit: 0, 1 (a stage stopped) or 2 (a refusal)


def preview(gate: Gate) -> list[str]:
    """The eight stages and which are done; changes nothing."""
    t = gate.target
    recorded = gate.recorded()
    lines = [f"DevOps stage of run {t.run.run}: PR #{t.pr} of {t.repo}, ops workspace "
             f"{t.ops_branch} on profile {t.profile}"]  # fmt: skip
    nxt = True
    for s in STAGES:
        done = s.done(gate, recorded)
        mark = "done" if done else ("next" if nxt else "    ")
        nxt = nxt and done
        lines.append(f"  [{mark}] {s.number}. {s.name}: {s.what}")
    lines.append("nothing done; re-run with --yes to act")
    return lines


def run(gate: Gate) -> GateResult:
    """Every stage not yet done, in order; stop at the first failure, naming it."""
    ran: list[int] = []
    for s in STAGES:
        if s.done(gate, gate.recorded()):
            continue
        gate.say(f"stage {s.number} ({s.name}) …")
        try:
            s.act(gate)
        except StageFailed as exc:
            why = f"stage {s.number} ({s.name}) failed: {exc.why}"
            gate.say(why)
            return GateResult(False, tuple(ran), s.number, why, exc.code)
        ran.append(s.number)
    gate.say("the DevOps stage is complete" if ran else "every stage is already done; nothing ran")
    return GateResult(True, tuple(ran))


def pr_number(ref: str | None) -> int | None:
    """The PR number a run's emitted `pr` names (a URL or a bare number)."""
    m = re.search(r"(\d+)/?$", ref or "")
    return int(m.group(1)) if m else None
