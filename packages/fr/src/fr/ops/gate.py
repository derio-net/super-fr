"""The DevOps stage: `fr ops gate --run <id>` (spec 2026-10-22-fr-ops R15, §I).

A sequencer in the collected close-out's style (`fr.triage.batch_closeout`): it decides
the next stage and runs nothing itself. Its ports run everything:

- `GateHost` runs THIS `fr` on the harness host, in the base checkout (`fr isolation
  up/exec/verify-merge`), and fetches;
- `OpsTree` is the ops workspace `chore/ops-<slug>` (`fr.triage.gitseam.Worktree`): git
  there, and this `fr` with the workspace as its checkout (`fr ops trust`, `fr closeout
  outcome`, `fr gate pass`, `fr archive`);
- `GateForge` is the `GhClient` adapter (another forge's label write raises
  `UnsupportedForgeOperation`, which names the manual label);
- `GatePrompt` is the operator's terminal; `GateState` the operator's host-side record of
  the stages done and the head stage 1 verified (`HostGateState`).

The eight stages (`STAGES`) run in order. Each one's completion is recorded host-side,
per operator, outside every checkout (`gate_state_path`), so a rerun resumes at the
first stage that state does not record; stage 2 is done only when the forge reads the PR
MERGED, which the wave merge queue brings about (stage 2 adds `fr-queue:release` and the run
stops until then, R26; stage 4 adds `fr-queue:postmerge-done`). The
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
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from fr.artifacts.paths import KIND_DIRS
from fr.config.space import LEGACY_PROFILES, PROFILES, SPACE_DIR, rel
from fr.ghclient import UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS
from fr.journal.model import (
    JournalEntry,
    append_journal_entry,
    journal_now,
    resolve_journal_read_path,
)
from fr.labels import QUEUE_POSTMERGE_DONE, QUEUE_RELEASE, LabelDef

if TYPE_CHECKING:
    from fr.acceptance.model import Row, Walk
    from fr.ops.holds import GateItem
    from fr.ops.load import LoadedOp
    from fr.run.model import RunState
    from fr.spec import Step as TestPlanStep
    from fr.spec import StepGate
    from fr.verification.exit import Exit

STAGE_PREFIX = "gate-stage-"
PROFILES_FILES = (LEGACY_PROFILES, rel(PROFILES))
"""The profile declarations at both their paths (S1 R9, R13): a PR rewriting either never
brings a privileged profile up."""
ARCHIVED_JOURNALS = KIND_DIRS["journal-archived"]
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


class Restart(Exception):  # noqa: N818 — a signal to `run`, not a fault
    """A stage forgot later stages (a refresh reopened ops): `run` goes back to the first
    stage the host state does not record (spec 2026-11-27-ops-gate-truth R6)."""

    def __init__(self, why: str) -> None:
        super().__init__(why)
        self.why = why


class MergeConflict(Exception):  # noqa: N818 — git's verdict, carried to the stage
    """A merge into the ops branch conflicted and was aborted: the conflicted paths."""

    def __init__(self, paths: Sequence[str]) -> None:
        super().__init__(", ".join(paths))
        self.paths = tuple(paths)


class GateHost(Protocol):
    def materialise(self, ref: str, paths: Sequence[str]) -> Path:
        """A fresh temporary directory holding *paths* as *ref* carries them (`git archive
        <ref> -- <paths>`), paths absent at *ref* skipped. The caller removes it."""
        ...

    def fr(self, args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        """This `fr` in the base checkout: (exit, stdout). *terminal*: the operator's
        terminal attached and nothing captured (an `interactive: true` op)."""
        ...

    def fetch(self, ref: str) -> None: ...

    def changed_paths(self, base: str, head: str, paths: Sequence[str]) -> list[str]:
        """The *paths* (pathspecs) *head* changed since it forked from *base*, in the base
        checkout (`git diff --name-only --merge-base --end-of-options <base> <head> --
        <paths>`). The merge base, never *base*'s tip: what the default branch gained
        after the PR forked is not the PR's change (gh#1266)."""
        ...

    def differing_paths(self, base: str, head: str, paths: Sequence[str]) -> list[str]:
        """The *paths* whose content differs between *base*'s tip and *head* (`git diff
        --name-only --end-of-options <base> <head> -- <paths>`): whether the profile a
        workspace cut from *head* would run is the default branch's own (gh#1266)."""
        ...

    def rev_parse(self, ref: str) -> str | None:
        """The commit *ref* names in the base checkout, or None."""
        ...

    def origin_head(self) -> str | None:
        """The default branch the base checkout's `origin/HEAD` names, or None."""
        ...

    def workspace(self, branch: str) -> OpsTree | None:
        """The ops workspace of *branch*, or None while it is not up."""
        ...

    def patch_id(self, head: str, default: str) -> str | None:
        """*head*'s patch-id against `origin/<default>` in the base checkout (the one the
        merge queue pins a release to), or None when git cannot say."""
        ...

    def queue_configured(self, default: str) -> bool:
        """Whether `.fr/triage.yaml` at the freshly fetched `origin/<default>` declares a
        `queue:` block, so the wave merge queue serves this repo. A read that fails raises
        `StageFailed` with the error: unreadable is not "not configured"."""
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

    def is_ancestor(self, sha: str) -> bool:
        """Whether the commit *sha* is already in the ops branch (`git merge-base
        --is-ancestor`): merging it again would change nothing (review p1-r5)."""
        ...

    def merge_commit(self, sha: str, message: str) -> str:
        """Merge exactly the commit *sha* (a full object id, the one the refresh diffed and
        the operator confirmed; never a ref a later fetch could move, review p1-sec-r1) into
        the ops branch with a merge commit; the new head. Never a rebase: the pushed ops
        branch moves forward only, so its lease holds (spec 2026-11-27-ops-gate-truth R3).
        A conflict is aborted, leaving HEAD and the working tree as they were, and raised
        as `MergeConflict`."""
        ...

    def push(self, branch: str, lease: str | None = None) -> None:
        """Push HEAD to *branch*: with *lease*, only while the remote is still at that sha
        (`--force-with-lease`); without, only as a new branch (refusing an existing one)."""
        ...


class GateForge(Protocol):
    def default_branch(self, *, cwd: Path, run: Any = None) -> str | None: ...

    def pr_view(self, repo: str, number: int) -> dict[str, Any]: ...

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]: ...

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]: ...

    def ensure_labels(self, repo: str, labels: list[Any]) -> None: ...

    def edit_pr_labels(
        self, repo: str, pr: int, *, add: frozenset[str], remove: frozenset[str]
    ) -> None: ...

    def open_pr_for_head(self, repo: str, branch: str) -> dict[str, Any] | None: ...

    def pr_create(self, repo: str, *, head: str, base: str, title: str, body: str) -> int: ...

    def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]: ...

    def comment_pr(self, repo: str, pr: int, body: str) -> None: ...

    def edit_issue_comment(self, repo: str, comment_id: int, body: str) -> None: ...


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

    def reopened(self) -> tuple[frozenset[str], frozenset[str]]: ...

    def set_reopened(self, ops: Iterable[str], before: Iterable[str]) -> None: ...

    def clear_reopened(self) -> None: ...

    def forget(self, from_stage: int) -> None: ...

    def forgotten(self) -> set[int]: ...


class HostGateState:
    """The operator's own record of a run's DevOps stage (R15): the stages done and the PR
    head stage 1 verified, as JSON written atomically 0600 (`fr.ops.trust`'s writer)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _data(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text())
        except OSError, ValueError:
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
        data["forgotten"] = sorted(self.forgotten() - {n})
        if head is not None:
            data["head"] = head
        self._write(data)

    def reopened(self) -> tuple[frozenset[str], frozenset[str]]:
        """The ops a refresh reopened, and the plan-journal entry ids present at that
        refresh: none of those closes a reopened op (spec 2026-11-27-ops-gate-truth R6)."""
        raw = self._data().get("reopened")
        raw = raw if isinstance(raw, dict) else {}

        def ids(key: str) -> frozenset[str]:
            value = raw.get(key)
            return frozenset(str(i) for i in value) if isinstance(value, list) else frozenset()

        return ids("ops"), ids("before")

    def set_reopened(self, ops: Iterable[str], before: Iterable[str]) -> None:
        self._write({**self._data(), "reopened": {"ops": sorted(ops), "before": sorted(before)}})

    def clear_reopened(self) -> None:
        data = self._data()
        data.pop("reopened", None)
        self._write(data)

    def forget(self, from_stage: int) -> None:
        """Drop stages *from_stage* and later; the heads, the lease and the reopened ops
        stay, so the same run goes back to *from_stage* (R6)."""
        data = self._data()
        data["stages"] = sorted(n for n in self.stages() if n < from_stage)
        dropped = set(range(from_stage, max(STAGE_BY_NUMBER) + 1))
        data["forgotten"] = sorted(self.forgotten() | dropped)
        self._write(data)

    def forgotten(self) -> set[int]:
        """The stages a refresh forgot that have not been done again since (review p1-r1):
        while stage 6 is one, a `gate:devops-passed` label on the PR predates the refresh."""
        raw = self._data().get("forgotten") or []
        return {n for n in raw if isinstance(n, int) and not isinstance(n, bool)}

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

    def refreshed(self) -> Gate:
        """This gate with the PR re-read from the forge on its next `view`."""
        self.view(fresh=True)
        return self

    @property
    def default(self) -> str:
        """The repo's default branch from TRUSTED sources only (p4-r1 addendum): the
        forge's repo metadata, cross-checked with the base checkout's `origin/HEAD`;
        never the PR's own base ref, which its author chooses."""
        if self._default is None:
            # A forge error (a login page the adapter re-raises, gh#1554; a refused
            # host) is the gate's refusal, naming it — never a traceback (R7).
            try:
                forge = self.forge.default_branch(cwd=self.target.primary)
            except FORGE_ERRORS as exc:
                raise StageFailed(
                    f"cannot read the default branch from the forge: {exc}", code=2
                ) from exc
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


def _recorded_here(lo: LoadedOp, tree: OpsTree, slug: str, at_head: set[str]) -> bool:
    """Whether the op's closure is already recorded on the ops branch. A closure the live
    status observed but nobody recorded (a check that passes on its own) still goes through
    `fr ops apply --yes`, which records it once (R7) and runs nothing: otherwise the gate
    pass reads the op as 'never checked' and refuses (gh#1293)."""
    from fr.ops.evidence import JournalEvidence, recorded_close

    ev = JournalEvidence(tree.path, slug).latest(lo.op.id, runbook=False)
    return ev is not None and ev.entry_id not in at_head and recorded_close(lo, ev) is not None


def _excluded(gate: Gate, tree: OpsTree) -> Callable[[str], set[str]]:
    """The plan-journal entry ids that close nothing, per op: the PR head's own, and for an
    op a refresh reopened, every entry from before that refresh (R6)."""
    from fr.ops.refresh import closure_exclusions

    at_head = head_entry_ids(tree, gate.pinned_head(), "plan", gate.target.slug)
    return closure_exclusions(gate.state, at_head)


def _unclosed(
    gate: Gate, tree: OpsTree, ops: Sequence[LoadedOp], rows: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    """Each op the live status and the ops branch's own evidence do not close."""
    excluded = _excluded(gate, tree)
    out = []
    for lo in ops:
        row = rows.get(lo.op.id)
        if _closed(lo, row, tree, gate.target.slug, excluded(lo.op.id)) is None:
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
    excluded = _excluded(gate, tree)
    for lo in ops:
        op = lo.op
        skip = excluded(op.id)
        closed = _closed(lo, rows.get(op.id), tree, t.slug, skip) is not None
        if closed and _recorded_here(lo, tree, t.slug, skip):
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


def _head_paths(t: GateTarget, spec_rel: str) -> list[str]:
    """What the ops-gap check reads at the PR head (spec 2026-11-01-ops-gate-probes §A),
    plus the run's own spec when it lives elsewhere."""
    paths = [KIND_DIRS["spec"], t.plan_rel, KIND_DIRS["acceptance-fragment"], SPACE_DIR]
    return paths if spec_rel.startswith(f"{KIND_DIRS['spec']}/") else [*paths, spec_rel]


def _refuse_an_ops_gap(gate: Gate, ref: str, *, merged: bool) -> None:
    """R5: refuse, before any workspace exists, a run with an ops gap. It is decided on a
    scratch tree materialised from *ref*, removed afterwards: the PR head while the PR is
    open, the default branch's tip once it merged (review p1-r1, the gh#1266 family): a
    merged PR gains no commits, so only a fix landed on the default branch can clear it. A head
    whose Verification section, matrix or ops carriers cannot be read is not decided here:
    the stages that read them report it."""
    import shutil

    from fr.acceptance.model import AcceptanceError
    from fr.ops.gap import gap_message, ops_gap
    from fr.ops.load import OpsLoadError
    from fr.requirements import run_spec
    from fr.spec import TestPlanHeadingError
    from fr.triage.gitseam import GitError
    from fr.verification.exit import exit_for_spec

    t = gate.target
    spec_rel = run_spec(t.run)
    if spec_rel is None:
        return
    where = f"{gate.default} at {ref[:12]} (PR #{t.pr} merged)" if merged else f"PR #{t.pr}'s head"
    scratch: Path | None = None
    try:
        scratch = gate.host.materialise(ref, _head_paths(t, spec_rel))
        gates = exit_for_spec(scratch, spec_rel, repo=t.repo.rsplit("/", 1)[-1]).gates
        gap = ops_gap(scratch, spec_rel, scratch / t.plan_rel, gates)
    except TestPlanHeadingError as e:
        # A near-miss heading hides every devops step: refuse, never "not checked" (#1315).
        raise StageFailed(f"{where}: {e}", code=2) from e
    except (ValueError, OSError, AcceptanceError, OpsLoadError, GitError) as e:
        gate.say(f"the ops-gap check could not read {where} ({e}); not checked")
        gap = []
    finally:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)
    if gap:
        fix = (
            f"The PR has merged, so land the fix on {gate.default} (a follow-up PR)"
            if merged
            else "Fix it on the PR branch"
        )
        raise StageFailed(
            f"{where} has an ops gap. {gap_message(gap, has_plan=True)} "
            f"{fix}, then re-run `fr ops gate`. Nothing was brought up",
            code=2,
        )


def stage_1(gate: Gate) -> None:
    """Bring up (or reuse) the ops workspace, cut from the PR head (from the default
    branch once the PR merged); pre-merge ops."""
    t = gate.target
    view = gate.view(fresh=True)
    head = valid_sha(str(view.get("head_oid") or ""), f"PR #{t.pr}'s head")
    merged = str(view.get("state") or "") == "MERGED"
    gate.require_default_base()
    gate.host.fetch(t.feature)
    gate.host.fetch(gate.default)
    default_ref = f"origin/{gate.default}"
    archived = gate.host.changed_paths(default_ref, head, [ARCHIVED_JOURNALS])
    if archived:  # p4-r2 addendum: a feature PR has no business in the archive
        raise StageFailed(
            f"PR #{t.pr} adds or changes archived journals ({', '.join(archived)}); "
            "nothing was brought up",
            code=2,
        )
    pinned = [f".devcontainer/{t.profile}", *PROFILES_FILES]
    changed = gate.host.changed_paths(default_ref, head, pinned)  # the PR's own diff
    if changed:  # p4-r1: never bring up a privileged profile the PR itself rewrote
        raise StageFailed(
            f"PR #{t.pr} changes the ops profile ({', '.join(changed)}); its devcontainer "
            "runs with the ops credentials, so a profile change must merge in its own PR "
            "first. Nothing was brought up",
            code=2,
        )
    # The workspace runs the profile it was cut with. An open PR is cut from its head
    # (p4-r5); a merged one cannot be rebased, so it is cut from the default branch,
    # which already holds it (gh#1266).
    if merged:
        tip = gate.host.rev_parse(default_ref)
        base = valid_sha(tip or "", f"{default_ref}'s tip")
    else:
        base = head
    reused = gate.host.workspace(t.ops_branch)
    cut = gate.state.cut()
    if reused is not None and not merged and cut != head:  # p4-r5: exactly the PR head
        raise StageFailed(
            f"the ops workspace {t.ops_branch} was cut from {cut or 'unknown'}, "
            f"not PR #{t.pr}'s head {head}; " + gate.redo_stage_1()
        )
    if reused is not None and merged and not cut:
        raise StageFailed(
            f"the ops workspace {t.ops_branch} was cut from unknown; " + gate.redo_stage_1()
        )
    run_from = valid_sha(cut or "", "the recorded cut") if reused is not None else base
    stale = gate.host.differing_paths(default_ref, run_from, pinned)
    if stale:  # never run a profile other than the default branch's own (gh#1266)
        fix = (
            gate.redo_stage_1()
            if merged
            else f"rebase PR #{t.pr} onto {gate.default} (or merge {gate.default} into it), "
            "then re-run `fr ops gate`"
        )
        raise StageFailed(
            f"the ops profile on {gate.default} changed since {run_from[:12]} "
            f"({', '.join(stale)}); an ops workspace from there would run an older profile "
            f"with the ops credentials. Nothing was brought up: {fix}",
            code=2,
        )
    _refuse_an_ops_gap(gate, base, merged=merged)
    if reused is None:
        code, _ = gate.host.fr(["isolation", "up", "--repo", str(t.primary), "--profile",
                                t.profile, "--branch", t.ops_branch, "--base", base])  # fmt: skip
        if code != 0 or gate.host.workspace(t.ops_branch) is None:
            raise StageFailed(f"`fr isolation up --branch {t.ops_branch}` exited {code}")
        gate.state.set_cut(base)
        origin = f"{gate.default} at {base[:12]} (PR #{t.pr} merged)" if merged else base[:12]
        gate.say(f"ops workspace {t.ops_branch} up on profile {t.profile}, from {origin}")
    apply_phase(gate, "pre-merge")
    gate.finish(gate.tree(), 1, f"head: {head}\npre-merge ops closed on {t.ops_branch}", head=head)


def _checks_green(gate: Gate) -> None:
    from fr.checkstate import bucket_verdict
    from fr.triage.batch_drive import checks_verdict

    t = gate.target
    every = gate.forge.pr_checks(t.repo, t.pr)
    counts = {"pass": 0, "fail": 0, "pending": 0}
    for c in every:  # a cancelled check is pending (spec 2026-11-24-ci-economy R3)
        counts[bucket_verdict(str(c.get("bucket") or ""))] += 1
    required = gate.forge.pr_required_checks(t.repo, t.pr)
    verdict, names = checks_verdict(required, counts, ci_none=False)
    if verdict == "pending":
        # Counted apart: a cancelled check no newer run replaced, with nothing still
        # running, is owed a re-run, not a wait (review #1647).
        read = required or every
        waiting = [c for c in read if bucket_verdict(str(c.get("bucket") or "")) == "pending"]
        if waiting and all(c.get("bucket") == "cancel" for c in waiting):
            cancelled = sorted({str(c.get("name")) for c in waiting})
            raise StageFailed(
                f"PR #{t.pr}'s checks were cancelled with no newer run: "
                f"{', '.join(cancelled)}; re-run the workflow"
            )
    if verdict != "green":
        raise StageFailed(f"PR #{t.pr}'s checks are {verdict}: {', '.join(names)}")


def add_queue_label(gate: Gate, label: LabelDef) -> None:
    """Say a word to the wave merge queue (R26): create *label* on the repo when it is
    missing, then add it to the PR. The DevOps stage reads no triage state and calls no
    merge; the driver settles the label into a queue event on its next pass."""
    from fr.settings import SettingsError, ledger_block

    t = gate.target
    try:
        off = ledger_block(t.primary, "labels")  # R9: only `forge.labels` decides the ledger
    except SettingsError as exc:
        off = str(exc)
    if off is not None:
        raise StageFailed(
            f"the queue is told by the label {label.name} on PR #{t.pr}, and {off}: add it by "
            "hand if the queue is to act on this PR"
        )
    try:
        gate.forge.ensure_labels(t.repo, [label])
        gate.forge.edit_pr_labels(t.repo, t.pr, add=frozenset({label.name}), remove=frozenset())
    except UnsupportedForgeOperation as exc:
        raise StageFailed(
            f"{exc}: add the label {label.name} to PR #{t.pr} by hand in the forge"
        ) from exc
    except Exception as exc:  # noqa: BLE001 — the forge's refusal is the operator's to read
        raise StageFailed(f"the forge refused the label {label.name} on PR #{t.pr}: {exc}") from exc


def write_release_marker(gate: Gate, head: str, patch_id: str) -> None:
    """Write (or update in place) the marker comment on the PR naming what stage 2 verified
    (R26): the head and patch-id the driver records the release at."""
    from fr.triage.approval import RELEASE_MARKER_PREFIX, release_marker

    _write_marker(gate, RELEASE_MARKER_PREFIX, release_marker(head, patch_id))


def write_postmerge_marker(gate: Gate, head: str) -> None:
    """Write the marker comment stage 4 leaves on the merged PR (R26, l-security-r2): the
    driver lifts the barrier only with it and the label together."""
    from fr.triage.approval import POSTMERGE_MARKER_PREFIX, postmerge_marker

    _write_marker(gate, POSTMERGE_MARKER_PREFIX, postmerge_marker(head))


def _write_marker(gate: Gate, prefix: str, body: str) -> None:
    """Post *body*, or edit in place the last comment that is its own form (it starts with
    *prefix*) AND from a trusted author (l-security-r3: never overwrite a stranger's
    comment). The ledger's `comments` setting decides, as it does for the label."""
    from fr.settings import SettingsError, ledger_block
    from fr.triage.claims import trusted_author

    t = gate.target
    try:
        off = ledger_block(t.primary, "comments")
    except SettingsError as exc:
        off = str(exc)
    if off is not None:
        raise StageFailed(
            f"the queue reads what the stage verified from a comment on PR #{t.pr}, and {off}: "
            f"post `{body}` on it by hand if the queue is to act"
        )
    try:
        mine = [
            c for c in gate.forge.list_issue_comments(t.repo, t.pr)
            if str(c.get("body") or "").lstrip().startswith(prefix) and c.get("id")
            and trusted_author(c, frozenset())
        ]  # fmt: skip
        if mine:
            try:
                gate.forge.edit_issue_comment(t.repo, int(mine[-1]["id"]), body)
                return
            except Exception:  # noqa: BLE001 — not ours to edit: post a new, later one
                pass
        gate.forge.comment_pr(t.repo, t.pr, body)
    except UnsupportedForgeOperation as exc:
        raise StageFailed(f"{exc}: post `{body}` on PR #{t.pr} by hand") from exc
    except Exception as exc:  # noqa: BLE001 — the forge's refusal is the operator's to read
        raise StageFailed(f"the forge refused the marker on PR #{t.pr}: {exc}") from exc


def _release_marker_now(gate: Gate) -> tuple[str, str] | None:
    from fr.triage.approval import read_release_marker

    t = gate.target
    try:
        return read_release_marker(gate.forge.list_issue_comments(t.repo, t.pr))
    except Exception:  # noqa: BLE001 — unreadable: not marked
        return None


NO_QUEUE = (
    "the wave merge queue does not serve {repo} (no `queue:` in .fr/triage.yaml on "
    "{default}): merge PR #{pr} by hand; stage 2 is done once the forge reads it merged"
)


def stage_2(gate: Gate) -> None:
    """The release to the merge queue (R26): no open pre-merge op, green required checks, an
    explicit confirmation, then the marker comment naming the verified head and patch-id and
    the label `fr-queue:release`. It never merges and records nothing: the stage is done
    when the forge reads the PR MERGED, which the queue brings about (a repo with no queue
    merges by hand, and `run` stops here until then)."""
    t = gate.target
    tree = gate.tree()
    view = gate.view(fresh=True)
    state = str(view.get("state") or "")
    if state != "OPEN":
        raise StageFailed(f"PR #{t.pr} is {state or 'UNKNOWN'}, not open: nothing to release")
    gate.require_default_base()  # a base retargeted since stage 1
    head = gate.verified_head(tree)
    live = str(view.get("head_oid") or "")
    if live != head:
        raise StageFailed(
            f"PR #{t.pr}'s head moved from {head} (verified in stage 1) to {live or 'unknown'}; "
            f"nothing released: {gate.redo_stage_1()}",
            code=2,
        )
    pre = _ops(tree, t.plan_rel, "pre-merge")
    gate.trust(tree)
    rows = _status_rows(gate, "pre-merge")  # live, never the PR-controlled journal (p4-r2)
    left = _unclosed(gate, tree, pre, rows)
    if left:
        raise StageFailed("pre-merge ops are still open: " + "; ".join(left))
    _checks_green(gate)
    if not gate.host.queue_configured(gate.default):
        gate.say(NO_QUEUE.format(repo=t.repo, default=gate.default, pr=t.pr))
        return
    patch_id = gate.host.patch_id(head, gate.default)
    if patch_id is None:
        raise StageFailed(
            f"cannot read the patch-id of PR #{t.pr}'s head {head[:12]} in the base checkout; "
            "nothing released"
        )
    has_label = QUEUE_RELEASE.name in {str(n) for n in view.get("labels") or ()}
    if has_label and _release_marker_now(gate) == (head, patch_id):
        return  # already released: the queue has it, or has not read the label yet
    lines = [f"  {lo.op.id}: {rows[lo.op.id].get('label')}" for lo in pre] or [
        "  (no pre-merge op)"
    ]
    text = (
        f"RELEASE PR #{t.pr} of {t.repo} at head {head} to the merge queue, which lands it "
        "as the last entry of its push\npre-merge state:\n" + "\n".join(lines)
    )
    if not gate.prompt.confirm(text):  # its own confirmation, --yes or not
        raise StageFailed(f"the release of PR #{t.pr} was not confirmed; nothing released")
    write_release_marker(gate, head, patch_id)  # first: the label then implies a marker
    if not has_label:
        add_queue_label(gate, QUEUE_RELEASE)
    gate.say(
        f"PR #{t.pr} released to the merge queue ({QUEUE_RELEASE.name} at {head[:12]}): the "
        "driver lands it as the last entry of its push, then `fr ops gate --run "
        f"{t.run.run}` resumes at stage 3"
    )


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
    # Replay only the ops branch's own commits: they sit on the cut, which is the PR
    # head, or the default branch's tip when stage 1 ran after the merge (gh#1266).
    upstream = gate.pinned_head()
    try:
        tree.rebase_onto(f"origin/{gate.default}", upstream)
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


def _refresh(gate: Gate, n: int) -> None:
    """Stages 4–7 first bring the ops workspace up to date with the default branch
    (spec 2026-11-27-ops-gate-truth R1, `fr.ops.refresh`)."""
    from fr.ops.refresh import refresh

    refresh(gate, gate.tree(), n)


def stage_4(gate: Gate) -> None:
    """Post-merge ops. Their completion lifts the queue's barrier (R26): the label
    `fr-queue:postmerge-done`, which the driver settles into `queue_postmerge_done`."""
    _refresh(gate, 4)
    apply_phase(gate, "post-merge")
    view = gate.view(fresh=True)
    write_postmerge_marker(gate, str(view.get("head_oid") or ""))  # first: label implies marker
    labels = {str(n) for n in view.get("labels") or ()}
    if QUEUE_POSTMERGE_DONE.name not in labels:  # added by hand under `forge.labels: off`
        add_queue_label(gate, QUEUE_POSTMERGE_DONE)
    gate.finish(gate.tree(), 4, "post-merge ops closed")
    gate.state.clear_reopened()  # applied again: a later refresh decides afresh (R6)


_KEYWORD = re.compile(
    r"^\s*(ran|n/a|na|owed|retry)(?=$|\s|:|-\s)\s*(?:(?::|-(?=\s))\s*)?(.*?)\s*$", re.I | re.S
)
_GRAMMAR = {
    "ran": "`ran <evidence>`",
    "na": "`na <reason>`",
    "owed": "`owed <why>`",
    "retry": "`retry`",
}
MAX_ANSWERS = 3


def _ask_outcome(gate: Gate, text: str, allowed: Sequence[str]) -> tuple[str, str]:
    """Ask until the answer is `<keyword>[:|-] <argument>` for an allowed keyword (R10):
    `retry` takes no argument and the others need one. A miss is echoed with the grammar
    and re-asked; the third in a row fails the stage with that same echo."""
    expected = ", ".join(_GRAMMAR[k] for k in allowed)
    shown = text
    for attempt in range(MAX_ANSWERS):
        answer = gate.prompt.ask(shown) or ""
        m = _KEYWORD.match(answer)
        if m is not None:
            how = "na" if m.group(1).lower() == "n/a" else m.group(1).lower()
            arg = m.group(2).strip()
            if how in allowed and bool(arg) == (how != "retry"):
                return how, arg
        echo = f"Not understood: {answer!r}. Expected {expected}."
        if attempt == MAX_ANSWERS - 1:
            raise StageFailed(f"{echo} Three answers in a row did not match.")
        shown = f"{echo}\n{text}"
    raise AssertionError("unreachable")  # pragma: no cover


def _record_outcome(
    gate: Gate,
    tree: OpsTree,
    step: Any,
    kind: str | None,
    how: str,
    text: str,
    *,
    walker: tuple[str, str] | None = None,
) -> None:
    """Record *step*'s outcome with `fr closeout outcome`. *walker* `(harness, model)`
    names who walked the rows a `ran` step names (ops-gate-truth R9: a passing probe is
    `fr-ops-probe` / `op:<id>`, since nobody walked it); otherwise the operator did."""
    flag = {"ran": ("--ran", "--evidence"), "owed": ("--owed", "--why")}.get(
        how, ("--na", "--reason")
    )
    argv = ["closeout", "outcome", "--run", gate.target.run.run, "--step", str(step.n),
            flag[0], flag[1], text]  # fmt: skip
    if walker is not None:
        argv += ["--harness", walker[0], "--model", walker[1]]
    if how == "ran":  # R12: a walk it writes counts owed harnesses over head-free walks
        argv += ["--pr-head", gate.pinned_head()]
    if kind is not None:  # an outcome the PR carries, or an owed one: record over it
        argv.append("--supersede")
    code, out = tree.fr(argv)
    if code != 0:
        raise StageFailed(f"`fr closeout outcome --step {step.n}` exited {code}: {out}")


def _ask_step(gate: Gate, tree: OpsTree, step: Any, kind: str | None) -> None:
    """A step with no pointer: walk it, then answer."""
    how, text = _ask_outcome(
        gate,
        f"Test Plan step {step.n} (devops): {step.text}\n"
        "Walk it, then answer `ran <evidence>`, `na <reason>` or `owed <why>`:",
        ("ran", "na", "owed"),
    )
    _record_outcome(gate, tree, step, kind, how, text)


def _step_row(gate: Gate, op_id: str) -> Mapping[str, Any]:
    plan = gate.target.plan_rel
    code, out = gate.host.fr(gate.exec_args("ops", "status", op_id, "--plan", plan, "--json"))
    if code not in STATUS_OK_CODES:
        raise StageFailed(f"`fr ops status {op_id}` in the ops workspace exited {code}: {out}")
    try:
        rows = json.loads(out or "[]")
    except json.JSONDecodeError as exc:
        raise StageFailed(f"`fr ops status {op_id}` printed no readable report: {out}") from exc
    for r in rows:
        if str(r.get("op")) == op_id:
            return r  # type: ignore[no-any-return]
    raise StageFailed(f"`fr ops status {op_id}` did not report the op the step points at")


def _probe_step(gate: Gate, tree: OpsTree, step: Any, kind: str | None) -> None:
    """A step that points at an op (R8): run its probe; a pass is recorded as `ran` with
    no question, anything else asks what to do about it."""
    op_id = step.op
    while True:
        row = _step_row(gate, op_id)
        state, how = str(row.get("state")), row.get("how")
        gate.say(
            f"  step {step.n}: {row.get('label') or state}  {op_id}  {row.get('reason') or ''}"
        )
        if row.get("output"):
            gate.say(str(row["output"]))
        if state == "DONE" and how == "checked":
            evidence = row.get("evidence") or "no output"
            _record_outcome(gate, tree, step, kind, "ran", f"{op_id}: check passed — {evidence}",
                            walker=("fr-ops-probe", f"op:{op_id}"))  # fmt: skip
            return
        head = f"Test Plan step {step.n} (devops): {step.text}\n"
        if state in ("OPEN", "UNVERIFIABLE", "CANNOT-VERIFY", "ESCALATE"):
            what, allowed = "`retry`, `na <reason>` or `owed <why>`", ("retry", "na", "owed")
        else:  # N/A, or a DONE that ran no check: no probe ran, so fr records no `ran`
            what, allowed = "`ran <evidence>`, `na <reason>` or `owed <why>`", ("ran", "na", "owed")
        answer, text = _ask_outcome(
            gate, f"{head}{op_id} is {row.get('label') or state}. Answer {what}:", allowed
        )
        if answer == "retry":
            continue
        _record_outcome(gate, tree, step, kind, answer, text)
        return


def stage_5(gate: Gate) -> None:
    """Each Test Plan step whose effective gate is devops: a pointed step is probed (R8),
    any other asked (R10); recorded with `fr closeout outcome` (ran, n/a, or owed — which
    stage 6 then refuses)."""
    from fr.ops.holds import gated_steps

    _refresh(gate, 5)
    t = gate.target
    tree = gate.tree()
    spec_slug = _spec_slug(t.run)
    at_head = head_entry_ids(tree, gate.pinned_head(), "spec", spec_slug) if spec_slug else set()
    every = gated_steps(tree.path, t.run, "devops")
    trusted = gated_steps(tree.path, t.run, "devops", exclude=at_head)
    probed = False
    for (step, kind), (_, mine) in zip(every, trusted, strict=True):
        if mine is not None:
            continue
        if step.op is None:
            _ask_step(gate, tree, step, kind)
            continue
        if not probed:
            gate.trust(tree)
            probed = True
        _probe_step(gate, tree, step, kind)
    asked = _ask_rows(gate, tree)
    body = "devops Test Plan steps recorded"
    gate.finish(tree, 5, body + (f"; rows {', '.join(asked)} answered" if asked else ""))


def _feature(run: RunState) -> str | None:
    """The fragment slug of the run's spec: the feature its row amendments go to."""
    from fr.acceptance.fragment import fragment_slug_for_spec
    from fr.requirements import run_spec

    spec = run_spec(run)
    return fragment_slug_for_spec(spec) if spec else None


def head_walks(tree: OpsTree, head: str) -> dict[str, set[Walk]]:
    """Row id -> the walks the PR head carries, read from every acceptance fragment there,
    since a row citing the spec may live in another feature's fragment: PR-controlled, so
    none of them walks a row inside the stage (ops-gate-truth R12). An unreadable fragment
    is a refusal, never an empty exclusion."""
    from fr.acceptance.fragment import FRAGMENTS_DIR
    from fr.acceptance.model import AcceptanceError
    from fr.acceptance.walks import fragment_walks
    from fr.artifacts.paths import artifact_root

    texts: list[tuple[str, str]] = []
    for path in sorted((artifact_root(tree.path) / FRAGMENTS_DIR).glob("*.yaml")):
        if not path.is_relative_to(tree.path):  # not in the product: the head cannot carry it
            continue
        rel = path.relative_to(tree.path).as_posix()
        text = tree.show(head, rel)
        if text:
            texts.append((rel, text))
    try:
        return fragment_walks(texts)
    except AcceptanceError as exc:
        raise StageFailed(
            f"the PR head's acceptance fragments cannot be read ({exc}); their walks cannot "
            "be told apart from the ops branch's own",
            code=2,
        ) from exc


def _gate_exit(tree: OpsTree, run: RunState) -> Exit:
    from fr.acceptance.model import AcceptanceError
    from fr.settings import SettingsError
    from fr.verification.exit import run_exit
    from fr.verification.spec_section import SectionError

    try:
        return run_exit(tree.path, run)
    except (AcceptanceError, SectionError, SettingsError, OSError) as exc:
        raise StageFailed(f"the run's exit cannot be read: {exc}") from exc


def row_walk_argv(
    run: RunState,
    row: Row,
    strategy: str,
    evidence: str,
    *,
    walks: Sequence[Walk] | None = None,
    harness: str = "operator",
    model: str = "human",
) -> list[str]:
    """`fr acceptance set-status --walk` recording a walk of *row* on *harness* in the
    DevOps stage (ops-gate-truth R13): `walked` when no other harness is still owed over
    *walks* (the head-free walks, R12), else its current status."""
    from fr.acceptance.walks import owed_harnesses

    status = row.status if set(owed_harnesses(row, walks)) - {harness} else "walked"
    return ["acceptance", "set-status", "--id", row.id, "--status", status, "--walk", evidence,
            "--harness", harness, "--model", model, "--strategy", strategy,
            "--notes", f"walked in the DevOps stage of run {run.run}",
            "--feature", _feature(run) or ""]  # fmt: skip


def recovery_argvs(
    run: RunState, row: Row, strategy: str, walks: Sequence[Walk]
) -> list[list[str]]:
    """R14: the walk commands that discharge *row*, one per harness it still owes over
    the head-free *walks*; the last one moves it to `walked`."""
    from fr.acceptance.walks import owed_harnesses

    owed = owed_harnesses(row, walks) if row.harnesses else ["operator"]
    out: list[list[str]] = []
    for i, h in enumerate(owed):
        later = owed[i + 1 :]
        argv = row_walk_argv(run, row, strategy, "<what it showed>", walks=walks, harness=h,
                             model="human" if h == "operator" else "<model>")  # fmt: skip
        if later:  # an earlier command keeps the status: the later harnesses still owe it
            argv[argv.index("--status") + 1] = row.status
        out.append(argv)
    return out


def _ask_rows(gate: Gate, tree: OpsTree) -> list[str]:
    """R13: each devops row that is not walked, judged head-free (R12), is asked about
    after the steps; a walk this stage's own `fr closeout outcome` wrote has already
    discharged it when it is walked. `ran <evidence>` walks it, `owed <why>` sets
    `walk-owed`. Returns the rows asked about."""
    from fr.acceptance.walks import head_free_walks, row_walked
    from fr.ops.holds import gated_rows

    t = gate.target
    rows = gated_rows(tree.path, _gate_exit(tree, t.run), "devops")
    if not rows:
        return []
    head = head_walks(tree, gate.pinned_head())
    asked: list[str] = []
    for r, strategy in rows:
        skip = head.get(r.id, set())
        if row_walked(r, skip):
            continue
        how, text = _ask_outcome(
            gate,
            f"Acceptance row {r.id} (devops): {r.acceptance}\n"
            "No walk this stage recorded discharges it. Walk it, then answer "
            "`ran <evidence>` or `owed <why>`:",
            ("ran", "owed"),
        )
        if how == "ran":
            argv = row_walk_argv(t.run, r, strategy, text, walks=head_free_walks(r, skip))
        else:
            argv = ["acceptance", "set-status", "--id", r.id, "--status", "walk-owed",
                    "--notes", text, "--feature", _feature(t.run) or ""]  # fmt: skip
        code, out = tree.fr(argv)
        if code != 0:
            raise StageFailed(f"`fr acceptance set-status --id {r.id}` exited {code}: {out}")
        asked.append(r.id)
    return asked


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
    _refresh(gate, 6)
    t = gate.target
    tree = gate.tree()
    if _pass_labelled(gate.refreshed()):
        _existing_pass(gate, tree)
        return
    if owed_now := _say_owed(gate, tree, "devops"):  # R14: never a pass on head-only evidence
        raise StageFailed(
            f"the devops gate of run {t.run.run} still owes, with the PR head's own walks and "
            f"outcomes excluded ({'; '.join(i.line for i in owed_now)}); `fr gate pass` was "
            "not run" + _recovery(gate, tree)
        )
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


def _owed_items(gate: Gate, tree: OpsTree, gate_name: StepGate) -> list[GateItem]:
    """What *gate_name* still owes in the ops workspace (`gate_items`), the PR head's own
    outcomes and walks excluded (R12)."""
    from fr.acceptance.model import AcceptanceError
    from fr.ops.holds import gate_items
    from fr.ops.load import OpsLoadError
    from fr.settings import SettingsError
    from fr.spec import TestPlanHeadingError
    from fr.verification.spec_section import SectionError

    t = gate.target
    at_head, excluded = _head_exclusions(gate, tree)
    try:
        items = gate_items(tree.path, t.run, gate_name, exclude_walks=excluded,
                           exclude_outcomes=at_head)  # fmt: skip
    except OpsLoadError as exc:
        raise StageFailed(f"the plan's ops cannot be read: {exc}") from exc
    except TestPlanHeadingError as exc:
        raise StageFailed(str(exc)) from exc
    except (AcceptanceError, SectionError, SettingsError, OSError) as exc:  # p2-r4
        raise StageFailed(f"the run's exit cannot be read: {exc}") from exc
    return [i for i in items if not i.discharged]


def _head_exclusions(gate: Gate, tree: OpsTree) -> tuple[set[str], dict[str, set[Walk]]]:
    """The spec-journal entry ids and the walks the pinned PR head carries: PR-controlled,
    so none of them counts inside the stage (R12)."""
    head = gate.pinned_head()
    spec_slug = _spec_slug(gate.target.run)
    at_head = head_entry_ids(tree, head, "spec", spec_slug) if spec_slug else set()
    return at_head, head_walks(tree, head)


def head_manual_ticks(tree: OpsTree, head: str, run: RunState, plan_rel: str) -> set[int]:
    """The `[manual]` phases whose tick the pinned PR head itself carries (R20): complete in
    the head's own phase file, with the same step and completion state there as in the ops
    workspace. PR-controlled, so such a tick counts as not there inside the stage; one the
    ops branch makes (or re-records) after the head changes the state and counts."""
    import yaml

    from fr.verification.exit import run_plan_dir

    plan_dir = run_plan_dir(tree.path, run)  # live, or archived by stage 8
    if plan_dir is None:
        return set()
    out: set[int] = set()
    for local in sorted(plan_dir.glob("[0-9][0-9].yaml")):
        text = tree.show(head, f"{plan_rel}/{local.name}")
        if not text:
            continue
        try:
            at_head, here = yaml.safe_load(text), yaml.safe_load(local.read_text())
        except yaml.YAMLError as exc:  # never an empty exclusion: a refusal
            raise StageFailed(
                f"the PR head's {plan_rel}/{local.name} cannot be read ({exc})", code=2
            ) from exc
        phase = (at_head or {}).get("phase") or {}
        state = (at_head or {}).get("state")
        if phase.get("tag") == "manual" and _ticked(state) and state == (here or {}).get("state"):
            out.add(int(phase.get("number", 0)))
    return out


def _ticked(state: Any) -> bool:
    """`plan_locally_complete` over a raw phase file's `state` block."""
    if not isinstance(state, dict):
        return False
    if (state.get("completion") or {}).get("at"):
        return True
    steps = state.get("steps") or {}
    return bool(steps) and all(
        isinstance(v, dict) and v.get("state") in ("x", "-") for v in steps.values()
    )


def _say_done(gate: Gate) -> None:
    """R20: the stage is complete only while the run's Definition of Done, read on the ops
    workspace with the PR head's own evidence excluded, is discharged; otherwise every item
    still owed, from every group."""
    from fr.run.dod import DodError, definition_of_done

    t = gate.target
    try:
        tree = gate.tree()
        at_head, excluded = _head_exclusions(gate, tree)
        head = gate.pinned_head()
        dod = definition_of_done(
            tree.path,
            t.run,
            exclude_walks=excluded,
            exclude_outcomes=at_head,
            exclude_entries={"spec": at_head, "plan": head_entry_ids(tree, head, "plan", t.slug)},
            exclude_manual_ticks=head_manual_ticks(tree, head, t.run, t.plan_rel),
        )
    except (DodError, StageFailed) as exc:
        why = exc.why if isinstance(exc, StageFailed) else str(exc)
        gate.say(f"every stage ran; the Definition of Done cannot be read: {why}")
        return
    if dod.discharged:
        gate.say("the DevOps stage is complete")
        return
    gate.say("every stage ran; still owed:")
    for line in dod.owed():
        gate.say(f"  {line}")


def _say_owed(gate: Gate, tree: OpsTree, gate_name: StepGate) -> list[GateItem]:
    """R14: before the pass, what the gate still owes by `gate_blockers`, judged
    head-free (R12); the owed items."""
    owed = _owed_items(gate, tree, gate_name)
    if owed:
        gate.say(f"stage 6: the {gate_name} gate still owes:")
        for item in owed:
            gate.say(f"  {item.line}")
    return owed


def _existing_pass(gate: Gate, tree: OpsTree) -> None:
    """The PR already carries `gate:devops-passed` from before a refresh (review p1-r1):
    `fr gate pass` would only re-close trackers, so the blockers are read here, on the
    refreshed workspace. The label is never removed by fr."""
    from fr.ops.holds import devops_blockers
    from fr.ops.load import OpsLoadError

    try:
        blockers = devops_blockers(tree.path, gate.target.run)
    except OpsLoadError as exc:
        raise StageFailed(f"the plan's ops cannot be read: {exc}") from exc
    if blockers:
        raise StageFailed(
            f"PR #{gate.target.pr}'s gate:devops-passed predates the refresh, and the "
            f"refreshed workspace is still held: {'; '.join(blockers)}" + _recovery(gate, tree)
        )
    gate.say("stage 6: the existing pass still holds after the refresh")
    gate.finish(tree, 6, "gate:devops-passed still holds after the refresh")


def _recovery(gate: Gate, tree: OpsTree) -> str:
    """p4-r3: for each devops step that is not closed, the command that records it in the
    ops workspace; a rerun then retries the gate pass."""
    from fr.acceptance.walks import head_free_walks, row_walked
    from fr.ops.holds import gated_rows, gated_steps

    t = gate.target
    open_steps = [
        (s, kind) for s, kind in gated_steps(tree.path, t.run, "devops") if kind != "discovery"
    ]
    head = head_walks(tree, gate.pinned_head())
    rows = [(r, k, head_free_walks(r, head.get(r.id, set())))
            for r, k in gated_rows(tree.path, _gate_exit(tree, t.run), "devops")
            if not row_walked(r, head.get(r.id, set()))]  # fmt: skip
    if not open_steps and not rows:
        return ""
    exec_ = f"  fr isolation exec --repo {t.primary} --branch {t.ops_branch} -- fr "
    # A step already recorded (owed) is recorded over only with --supersede: an owed
    # outcome may already be filed as an fr:owed issue, so it is never overwritten silently.
    lines = [
        f"{exec_}closeout outcome --run {t.run.run} --step {s.n} --ran --evidence "
        "'<what it showed>'" + (" --supersede" if kind is not None else "")
        for s, kind in open_steps
    ]
    # R14: each unwalked devops row, one command per harness it still owes (head-free)
    lines += [exec_ + shlex.join(a) for r, k, w in rows for a in recovery_argvs(t.run, r, k, w)]
    return (
        "; record each devops step that is not closed (or `--na --reason …`) and walk each "
        "devops row that is not walked, then re-run `fr ops gate`:\n" + "\n".join(lines)
    )


def stage_7(gate: Gate) -> None:
    """The tester hand-off: gate:tester is kept while the Tester gate owns something (a
    tester step with no outcome, an unwalked tester row, a declared run gate). A
    gate:tester that owns nothing is passed with a generated note (gh#1275), as stage 6
    passes devops, so the PR does not wait on a gate nobody owes."""
    from fr.labels import held_gates

    _refresh(gate, 7)
    t = gate.target
    tree = gate.tree()
    owed = _owed_items(gate, tree, "tester")
    declared = _gate_exit(tree, t.run).run_gate == "tester"  # a run gate passes explicitly
    if owed or declared:
        gate.say(f"gate:tester stays on PR #{t.pr}; the Tester gate owns:")
        for item in owed:
            gate.say(f"  {item.line}")
        if declared:
            gate.say("  the run itself: its spec declares `gate: tester`")
        body = "tester work handed off: " + ", ".join(
            [*(i.what for i in owed), *(["the run"] if declared else [])]
        )
    elif "tester" in held_gates(
        str(n) for n in gate.forge.pr_view(t.repo, t.pr).get("labels") or []
    ):
        notes = (
            f"DevOps stage of run {t.run.run}: no Test Plan step or unwalked row belongs to "
            "the Tester gate"
        )
        code, out = tree.fr(["gate", "pass", "--repo", t.repo, "--pr", str(t.pr), "--gate",
                             "tester", "--run", t.run.run, "--notes", notes,
                             "--yes"])  # fmt: skip
        if out.strip():
            gate.say(out.rstrip())
        if code != 0:
            raise StageFailed(f"`fr gate pass --gate tester` exited {code}")
        body = "gate:tester passed: the Tester gate owns nothing"
    else:
        body = "no tester step remains"
    gate.finish(tree, 7, body)


def stage_8(gate: Gate) -> None:
    """`fr archive --branch <feature>` filing the run's out-of-scope findings as the
    close-out brief would (p4-r4), then the ops branch as the housekeeping PR."""
    from fr.run.closeout import archive_issue_args

    t = gate.target
    tree = gate.tree()
    held: list[str] = []
    if (tree.path / t.plan_rel).is_dir():
        argv = ["archive", "--branch", t.feature, *archive_issue_args(tree.path, t.run)]
        code, out = tree.fr(argv)
        if out.strip():
            gate.say(out.rstrip())
        if code != 0:
            raise StageFailed(f"`fr {shlex.join(argv)}` exited {code}")
        tree.commit_paths(["docs"], f"chore(ops): archive {t.slug}")
        if (tree.path / t.plan_rel).is_dir():  # R15: `fr archive` exits 0 on a hold
            held = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("held:")]
            held = held or ["held: the plan directory is still in place"]
            gate.say("stage 8: archive held")
            for line in held:
                gate.say(f"  {line}")
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
    archived = "archive held (" + "; ".join(held) + ")" if held else "archived"
    gate.finish(tree, 8, f"{archived}; housekeeping PR from {t.ops_branch}")


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
    if _merged(gate, recorded):
        return True
    return gate.host.workspace(gate.target.ops_branch) is not None


def _merged(gate: Gate, recorded: set[int]) -> bool:
    """Stage 2 is done only when the forge reads the PR MERGED (R26): the queue owns every
    merge of the repo, so stage 3 never runs on an unmerged PR. Nothing records stage 2."""
    return str(gate.view().get("state") or "") == "MERGED"


def _passed(gate: Gate, recorded: set[int]) -> bool:
    """Stage 6 is done by the host state, or by the PR's `gate:devops-passed` label, but
    the label only while no refresh reopened an op or forgot stage 6 since (review p1-r1):
    a pass from before the refresh is re-checked by stage 6 itself."""
    if 6 in recorded:
        return True
    if gate.state.reopened()[0] or 6 in gate.state.forgotten():
        return False
    return _pass_labelled(gate)


def _pass_labelled(gate: Gate) -> bool:
    return "gate:devops-passed" in {str(n) for n in gate.view().get("labels") or []}


STAGES: tuple[Stage, ...] = (
    Stage(1, "pre-merge ops", "bring up or reuse the ops workspace from the PR head; "
          "trust; pre-merge status and apply", _cut, stage_1),
    Stage(2, "release to the merge queue", "add fr-queue:release to the PR after a terminal "
          "confirmation naming it, its head and the pre-merge state (no open pre-merge op, "
          "required checks green); the queue lands it as the last entry of its push (a repo "
          "with no queue merges by hand) and the stage is done when the forge reads the PR "
          "merged", _merged, stage_2),
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
    waiting: bool = False  # stage 2 released the PR to the merge queue, which has not landed it


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


MAX_RESTARTS = 2  # a refresh merges the default branch, so a second one is a moving target


def run(gate: Gate) -> GateResult:
    """Every stage not yet done, in order; stop at the first failure, naming it."""
    from fr.spec import TestPlanHeadingError

    ran: list[int] = []
    restarts = 0
    i = 0
    while i < len(STAGES):
        s = STAGES[i]
        i += 1
        if s.done(gate, gate.recorded()):
            continue
        gate.say(f"stage {s.number} ({s.name}) …")
        try:
            try:
                s.act(gate)
            except TestPlanHeadingError as exc:
                # The spec's Test Plan heading is a near-miss: its steps cannot be read,
                # so no stage may decide them (super-fr#1315). A refusal, not a traceback.
                raise StageFailed(str(exc), code=2) from exc
            except Restart as exc:
                restarts += 1
                if restarts > MAX_RESTARTS:
                    raise StageFailed(
                        f"{exc.why}, again: the default branch keeps moving; re-run later"
                    ) from exc
                gate.say(f"stage {s.number} ({s.name}): {exc.why}")
                i = 0  # the first stage the host state does not record (R6)
                continue
        except StageFailed as exc:
            why = f"stage {s.number} ({s.name}) failed: {exc.why}"
            gate.say(why)
            return GateResult(False, tuple(ran), s.number, why, exc.code)
        ran.append(s.number)
        # the queue merges it (R26): read the forge afresh, a quick queue may have landed it
        if s.number == 2 and not s.done(gate.refreshed(), gate.recorded()):
            gate.say(
                "stage 2 waits for the PR to be merged (by the merge queue, or by hand where no "
                "queue serves the repo); re-run once it has"
            )
            return GateResult(False, tuple(ran), waiting=True)
    if not ran:
        gate.say("every stage is already done; nothing ran")
    _say_done(gate)
    return GateResult(True, tuple(ran))


def pr_number(ref: str | None) -> int | None:
    """The PR number a run's emitted `pr` names (a URL or a bare number)."""
    m = re.search(r"(\d+)/?$", ref or "")
    return int(m.group(1)) if m else None
