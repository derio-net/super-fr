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

    def workspace(self, branch: str) -> OpsTree | None:
        """The ops workspace of *branch*, or None while it is not up."""
        ...


class OpsTree(Protocol):
    path: Path

    def head(self) -> str: ...

    def contains(self, sha: str) -> bool:
        """Whether *sha* is the workspace's HEAD or one of its ancestors."""
        ...

    def fr(self, args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        """This `fr` on the host with the ops workspace as its checkout."""
        ...

    def commit_paths(self, paths: list[str], message: str) -> str | None: ...

    def rebase_onto(self, new_base: str, upstream: str) -> None: ...

    def push(self, branch: str) -> None: ...


class GateForge(Protocol):
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
        entry = JournalEntry(
            kind="decision",
            scope="plan",
            id=f"{STAGE_PREFIX}{n}",
            created=journal_now(),
            title=title,
            body=body,
        )
        append_journal_entry(
            resolve_journal_read_path(self.root, "plan", self.slug), self.slug, entry
        )


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

    def mark(self, n: int, *, head: str | None = None) -> None:
        from fr.ops.trust import _write_private

        data = self._data()
        data["stages"] = sorted(self.stages() | {n})
        if head is not None:
            data["head"] = head
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

    # -- reads ----------------------------------------------------------------

    def view(self, *, fresh: bool = False) -> dict[str, Any]:
        if self._view is None or fresh:
            self._view = self.forge.pr_view(self.target.repo, self.target.pr)
        return self._view

    @property
    def default(self) -> str:
        return str(self.view().get("base_ref") or "main")

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

    def redo_stage_1(self) -> str:
        t = self.target
        return (
            f"re-run stage 1 against the PR's head: `fr isolation down --repo {t.primary} "
            f"--branch {t.ops_branch}`, then `fr ops gate --run {t.run.run} --yes` (it "
            "re-cuts the ops workspace and re-checks trust)"
        )

    def finish(self, tree: OpsTree, n: int, body: str, *, head: str | None = None) -> None:
        """Record stage *n* in the host state (and, for audit, the plan journal) and
        commit the workspace's evidence on the ops branch."""
        name = STAGE_BY_NUMBER[n].name
        self.state.mark(n, head=head)
        self.audit_factory(tree.path, self.target.slug).record(
            n, f"DevOps stage {n} done: {name}", body
        )
        tree.commit_paths(["docs"], f"chore(ops): {self.target.slug} DevOps stage {n} — {name}")
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


def _unclosed(tree: OpsTree, slug: str, ops: Sequence[LoadedOp]) -> list[str]:
    """Each op the RECORDED evidence does not close, with its recorded state."""
    from fr.ops.evidence import JournalEvidence, recorded_close, recorded_state

    journal = JournalEvidence(tree.path, slug)
    out = []
    for lo in ops:
        ev = journal.latest(lo.op.id, runbook=False)
        if recorded_close(lo, ev) is None:
            out.append(f"{lo.op.id}: {recorded_state(lo, ev)}")
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
    from fr.ops.evidence import JournalEvidence, recorded_close

    t = gate.target
    tree = gate.tree()
    gate.trust(tree)
    ops = _ops(tree, t.plan_rel, phase)
    gate.say(f"{phase} ops of {t.slug}: {len(ops)}")
    rows = _status_rows(gate, phase)
    journal = JournalEvidence(tree.path, t.slug)
    for lo in ops:
        op = lo.op
        if recorded_close(lo, journal.latest(op.id, runbook=False)) is not None:
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
    left = _unclosed(tree, t.slug, ops)
    if left:
        attest = " ".join(shlex.quote(a) for a in gate.exec_args(
            "ops", "attest", "<op>", "--plan", t.plan_rel, "--note", "<what you did>"))  # fmt: skip
        raise StageFailed(
            f"{phase} ops not closed by recorded evidence: {'; '.join(left)} — an op with no "
            f"check closes by attestation (`fr {attest}`), any other by a passing check"
        )


# ------------------------------------------------------------------------ stages


def stage_1(gate: Gate) -> None:
    """Bring up (or reuse) the ops workspace, cut from the PR head; pre-merge ops."""
    t = gate.target
    head = valid_sha(str(gate.view(fresh=True).get("head_oid") or ""), f"PR #{t.pr}'s head")
    reused = gate.host.workspace(t.ops_branch)
    if reused is not None and not reused.contains(head):
        raise StageFailed(
            f"the ops workspace {t.ops_branch} was not cut from PR #{t.pr}'s head {head}; "
            + gate.redo_stage_1()
        )
    if reused is None:
        gate.host.fetch(t.feature)
        code, _ = gate.host.fr(["isolation", "up", "--repo", str(t.primary), "--profile",
                                t.profile, "--branch", t.ops_branch, "--base", head])  # fmt: skip
        if code != 0 or gate.host.workspace(t.ops_branch) is None:
            raise StageFailed(f"`fr isolation up --branch {t.ops_branch}` exited {code}")
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
    head = gate.verified_head(tree)
    live = str(view.get("head_oid") or "")
    if live != head:
        raise StageFailed(
            f"PR #{t.pr}'s head moved from {head} (verified in stage 1) to {live or 'unknown'}; "
            f"nothing merged: {gate.redo_stage_1()}",
            code=2,
        )
    pre = _ops(tree, t.plan_rel, "pre-merge")
    left = _unclosed(tree, t.slug, pre)
    if left:
        raise StageFailed("pre-merge ops are still open: " + "; ".join(left))
    _checks_green(gate)
    lines = [f"  {lo.op.id}: closed" for lo in pre] or ["  (no pre-merge op)"]
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
    for step, kind in gated_steps(tree.path, t.run, "devops"):
        if kind is not None:
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
        code, out = tree.fr(["closeout", "outcome", "--run", t.run.run, "--step", str(step.n),
                             flag[0], flag[1], text])  # fmt: skip
        if code != 0:
            raise StageFailed(f"`fr closeout outcome --step {step.n}` exited {code}: {out}")
    gate.finish(tree, 5, "devops Test Plan steps recorded")


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
        raise StageFailed(f"`fr gate pass --gate devops --run {t.run.run}` exited {code}")
    gate.finish(tree, 6, "gate:devops passed")


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
    """`fr archive --branch <feature>`, then the ops branch as the housekeeping PR."""
    t = gate.target
    tree = gate.tree()
    if (tree.path / t.plan_rel).is_dir():
        code, out = tree.fr(["archive", "--branch", t.feature])
        if out.strip():
            gate.say(out.rstrip())
        if code != 0:
            raise StageFailed(f"`fr archive --branch {t.feature}` exited {code}")
        tree.commit_paths(["docs"], f"chore(ops): archive {t.slug}")
    try:
        tree.push(t.ops_branch)
        if gate.forge.open_pr_for_head(t.repo, t.ops_branch) is None:
            title = f"chore: DevOps stage of {t.slug} (run {t.run.run})"
            body = (
                f"The DevOps stage's evidence and archive for PR #{t.pr} (run {t.run.run}): "
                f"the op evidence, the gate-stage decisions and `fr archive --branch "
                f"{t.feature}`."
            )
            number = gate.forge.pr_create(t.repo, head=t.ops_branch, base=gate.default,
                                          title=title, body=body)  # fmt: skip
            gate.say(f"housekeeping PR #{number} opened from {t.ops_branch}")
    except Exception as exc:  # noqa: BLE001 — git's or the forge's own words
        raise StageFailed(f"cannot publish {t.ops_branch}: {exc}") from exc
    gate.finish(tree, 8, f"archived; housekeeping PR from {t.ops_branch}")
    try:
        tree.push(t.ops_branch)
    except Exception as exc:  # noqa: BLE001
        raise StageFailed(f"cannot push the stage-8 record to {t.ops_branch}: {exc}") from exc


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


def _merged(gate: Gate, recorded: set[int]) -> bool:
    return 2 in recorded or str(gate.view().get("state") or "") == "MERGED"


def _passed(gate: Gate, recorded: set[int]) -> bool:
    return 6 in recorded or "gate:devops-passed" in {
        str(n) for n in gate.view().get("labels") or []
    }


STAGES: tuple[Stage, ...] = (
    Stage(1, "pre-merge ops", "bring up or reuse the ops workspace from the PR head; "
          "trust; pre-merge status and apply", _recorded(1), stage_1),
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
