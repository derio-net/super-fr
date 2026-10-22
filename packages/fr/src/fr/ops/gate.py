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
- `GatePrompt` is the operator's terminal, and `Ledger` the ops workspace's plan journal.

The eight stages (`STAGES`) run in order. Each one's completion is a `gate-stage-<n>`
decision in the plan journal, committed on the ops branch, so a rerun resumes at the
first unrecorded stage; a forge-MERGED PR counts as stage 2 done even without one. The
first failure stops the run, naming the stage. Pre-merge evidence is committed on the ops
branch and never pushed to the PR head, so the reviewed head and its checks stay valid.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from fr.ghclient import UnsupportedForgeOperation
from fr.journal.model import (
    JournalEntry,
    JournalParseError,
    append_journal_entry,
    journal_now,
    parse_journal,
    resolve_journal_read_path,
)

if TYPE_CHECKING:
    from fr.ops.load import LoadedOp
    from fr.run.model import RunState
    from fr.spec import Step as TestPlanStep

STAGE_PREFIX = "gate-stage-"
CLOSED_STATES = frozenset({"DONE", "N/A"})
STATUS_OK_CODES = (0, 1, 3)  # every op reported; 2 is a refusal (`fr ops status`, R3)


class StageFailed(Exception):  # noqa: N818 — a stage's stop, not a fault
    """A stage could not complete; `why` is what the operator reads."""

    def __init__(self, why: str) -> None:
        super().__init__(why)
        self.why = why


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


class Ledger(Protocol):
    def stages(self) -> set[int]: ...

    def record(self, n: int, title: str, body: str) -> None: ...


class JournalLedger:
    """The `gate-stage-<n>` decisions in the ops workspace's plan journal (live, or
    archived once stage 8 moved it)."""

    def __init__(self, root: Path, slug: str) -> None:
        self.root = root
        self.slug = slug

    def _path(self) -> Path:
        return resolve_journal_read_path(self.root, "plan", self.slug)

    def stages(self) -> set[int]:
        path = self._path()
        if not path.is_file():
            return set()
        try:
            entries = parse_journal(path.read_text())
        except JournalParseError:
            return set()
        return {
            int(e.id.removeprefix(STAGE_PREFIX))
            for e in entries
            if e.kind == "decision" and re.fullmatch(rf"{STAGE_PREFIX}\d+", e.id)
        }

    def record(self, n: int, title: str, body: str) -> None:
        entry = JournalEntry(
            kind="decision",
            scope="plan",
            id=f"{STAGE_PREFIX}{n}",
            created=journal_now(),
            title=title,
            body=body,
        )
        append_journal_entry(self._path(), self.slug, entry)


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
    ledger_factory: Callable[[Path, str], Ledger] = JournalLedger
    _view: dict[str, Any] | None = field(default=None, repr=False)

    def ledger_for(self, tree: OpsTree) -> Ledger:
        return self.ledger_factory(tree.path, self.target.slug)

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
        tree = self.host.workspace(self.target.ops_branch)
        return self.ledger_for(tree).stages() if tree is not None else set()

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

    def finish(self, tree: OpsTree, n: int, body: str) -> None:
        """Record stage *n* and commit the workspace's evidence on the ops branch."""
        name = STAGE_BY_NUMBER[n].name
        self.ledger_for(tree).record(n, f"DevOps stage {n} done: {name}", body)
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
    if gate.host.workspace(t.ops_branch) is None:
        head = str(gate.view().get("head_oid") or "")
        if not head:
            raise StageFailed(f"PR #{t.pr} reports no head commit")
        gate.host.fetch(t.feature)
        code, _ = gate.host.fr(["isolation", "up", "--repo", str(t.primary), "--profile",
                                t.profile, "--branch", t.ops_branch, "--base", head])  # fmt: skip
        if code != 0 or gate.host.workspace(t.ops_branch) is None:
            raise StageFailed(f"`fr isolation up --branch {t.ops_branch}` exited {code}")
        gate.say(f"ops workspace {t.ops_branch} up on profile {t.profile}, from {head[:12]}")
    apply_phase(gate, "pre-merge")
    gate.finish(gate.tree(), 1, f"pre-merge ops closed on {t.ops_branch}")


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
    pre = _ops(tree, t.plan_rel, "pre-merge")
    left = _unclosed(tree, t.slug, pre)
    if left:
        raise StageFailed("pre-merge ops are still open: " + "; ".join(left))
    _checks_green(gate)
    head = str(view.get("head_oid") or "")
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
    head = str(gate.view().get("head_oid") or "")
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
            return GateResult(False, tuple(ran), s.number, why)
        ran.append(s.number)
    gate.say("the DevOps stage is complete" if ran else "every stage is already done; nothing ran")
    return GateResult(True, tuple(ran))


def pr_number(ref: str | None) -> int | None:
    """The PR number a run's emitted `pr` names (a URL or a bare number)."""
    m = re.search(r"(\d+)/?$", ref or "")
    return int(m.group(1)) if m else None
