"""`fr run start / status / advance / resolve / check` — spec §4.B, Phase 7.

`fr run advance` is the one place this package could be tempted to shell
out to a model, and it structurally cannot: a `kind: cli` step is executed
directly (`subprocess.run`, exit code + stdout captured into the step
record); a `kind: agent` step is NEVER executed here — it produces a brief
(the shape a harness dispatches, e.g. the `fr-phase-executor` agent) and
marks itself `running`. This is the structural half of the
`no-claude-p-batch` rule, not merely compliance with it — there is nothing
in this module that could invoke an LLM even by mistake.

`fr run resolve` is the other half of that split (spec §4.B, added in the
Phase 7 review — the original four-command CLI was a dead end: nothing
could ever move an `agent` step past `running`, so a real run wedges on its
first one). The harness calls `resolve` when a dispatched agent returns;
it shares `_complete_step` with `advance`'s `cli` branch rather than
forking the done/failed cursor asymmetry a second time.
"""

from __future__ import annotations

import datetime as _dt
import functools
import json
import os
import re
import shlex
import subprocess
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NoReturn, TypeVar, cast

import typer
from rich.console import Console
from rich.markup import escape

from fr.artifacts.commit import CommitOutcome
from fr.commands.common import resolve_repo_root
from fr.git import GitUnavailableError, git_answer
from fr.harness import HARNESSES, load_matrix
from fr.harness.detect import detect_harness
from fr.harness.long_commands import long_command_rule
from fr.harness.model import HarnessError
from fr.isolation import sessions as _sessions
from fr.isolation.types import IsolationError
from fr.journal.model import (
    JournalEntry,
    JournalParseError,
    effective_finding_states,
    journal_now,
    journal_stamp_as_utc,
    parse_journal,
    phase_finding_states,
    resolve_journal_read_path,
    reviews_phase,
    spec_journal_slug,
    unauthorized_fixes,
)
from fr.records_commit import commit_records
from fr.run import liveness as _liveness
from fr.run import units
from fr.run.adopt import MANUAL_ITEM, AdoptError, Superseded, adopt_run, plan_phase_tags
from fr.run.historical import (
    HISTORICAL_HEADING,
    HISTORICAL_REVIEWER,
    findings_witness,
    historical_review_lines,
    historical_reviews,
    historical_sentence,
)
from fr.run.liveness import gate_pending as _gate_pending
from fr.run.liveness import hold_on as _hold_on
from fr.run.liveness import next_step_id as _next_step_id
from fr.run.model import (
    RUN_ID_MAX_LENGTH,
    RUNS_REL,
    AnsweredBy,
    DispatchOutcome,
    RunState,
    RunStateError,
    StepRecord,
    current_run_schema_version,
    existing_run_id_colliding_with,
    load_run_state,
    parse_run_state,
    run_path,
    save_run_state,
    validate_run_id,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fr.record.model import QuestionRounds, VisualEvidence
    from fr.run.telemetry import Round
    from fr.verification.walk import WalkOwed
from fr.run.provenance import cleared_gates, gates
from fr.run.reshape import ReshapeError, diff_ids, reshape
from fr.run.units import UnitAttempt
from fr.run.workspace import RunWorkspaceError, ensure_run_workspace
from fr.types import PHASE_TIERS
from fr.workflow.artifacts import DERIVED_EVIDENCE, REPO_TRACKED_ARTIFACTS, emitted_artifacts
from fr.workflow.check import check_workflow
from fr.workflow.model import Step, WorkflowError, WorkflowManifest
from fr.workflow.resolve import resolve_workflow

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

run_app = typer.Typer(
    help="Durable workflow-run cursor: start / status / advance / resolve / check.",
    no_args_is_help=True,
)

_TEMPLATE_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}")


@run_app.callback()
def _run_group() -> None:
    """Durable workflow-run cursor. Runs on the harness host (spec 2026-09-25
    §5.B.6): refused from inside a devcontainer-mode workspace."""
    from fr.isolation.where import HostSideError, require_harness_host

    try:
        require_harness_host(resolve_repo_root(), "run")
    except HostSideError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2) from e


# --- gh#610 §3.C: fr commits its own record writes ---------------------------
#
# Every mutating command (start/adopt/advance/resolve/claim) is wrapped in
# `_commits_run_writes`: while it runs, each cursor save and each journal
# append it makes is noted here, and on the way out — success, refusal or
# traceback alike, since a write that landed must not be lost to an exit path —
# every noted path is committed ONCE, per repo root, through `commit_records`,
# which never fails the command. `save_run_state` and `adopt_run` stay pure.


@dataclass
class ResolveGuard:
    """What the step-record engine needs to undo a `resolve` it drove (p3-r3).

    `originals` holds the bytes of every path this command wrote — the cursor,
    the usage capture, the spec journal a `--no-questions` clears into, the PR
    render — remembered BEFORE the write, so a refusal or a crash can put each
    one back. `landed` turns true once any commit landed: from then on the
    tree must stay equal to HEAD, never be restored behind it.
    `before_commit` runs once, immediately before the first commit, and names
    extra paths to record in it (the engine's tracked record file, deleted).
    """

    originals: dict[Path, bytes | None] = field(default_factory=dict)
    landed: bool = False
    before_commit: Callable[[], list[Path]] | None = None
    prepared: bool = False


@dataclass
class _RunWrites:
    verb: str
    step: str | None = None
    item: str | None = None
    # The state word the subject ends in, when the command knows it better
    # than the cursor does (p3-r1): a member resolve/claim has no record of its
    # own in `steps`, and a cleared cli gate is `pending` again on disk.
    outcome: str | None = None
    loaded_cursor: str | None = None
    last: RunState | None = None
    paths: dict[Path, list[Path]] = field(default_factory=dict)
    # The outcome of the last commit this command made — the step-record
    # engine reports it in its one line (spec 2026-09-25 §5.C.2.4).
    last_outcome: CommitOutcome | None = None
    guard: ResolveGuard | None = None
    # p3-r10: the step-record engine prints its own one line naming the
    # commit, so `commit_records`' "fr: committed …" echo would be a second.
    quiet: bool = False
    # `adopt --supersede`: the run this command replaced. Its subject names it
    # (spec 2026-10-05-run-upgrade-midflight §C), so the replaced cursor is
    # findable in history.
    supersedes: str | None = None

    def remember(self, path: Path) -> None:
        """Keep `path`'s bytes as they are now, before this command writes it."""
        if self.guard is not None and path not in self.guard.originals:
            self.guard.originals[path] = path.read_bytes() if path.is_file() else None

    def note(self, repo_root: Path, path: Path) -> None:
        self.paths.setdefault(repo_root, []).append(path)

    def message(self) -> str:
        run = self.last.run if self.last is not None else "?"
        if self.supersedes is not None:
            return f"chore(fr): run {run} — adopt, supersedes {self.supersedes}"
        step = self.step or self.loaded_cursor or (self.last.cursor if self.last else None)
        parts = [self.verb]
        if step:
            parts.append(step)
        if self.item:
            parts.append(self.item)
        record = self.last.steps.get(step) if (self.last is not None and step) else None
        if self.outcome is not None:
            parts.append(self.outcome)
        elif record is not None:
            parts.append(record.state)
        return f"chore(fr): run {run} — {' '.join(parts)}"

    def commit(self) -> CommitOutcome | None:
        """Commit what has been noted so far, once per repo root, and forget it.

        Returns the last root's `CommitOutcome`, or `None` when nothing was
        pending — a caller deciding whether to print "push it" (p4-r1) must
        tell "nothing to commit" from "committed" from "refused".
        """
        guard = self.guard
        if guard is not None and not guard.prepared and self.paths:
            guard.prepared = True
            if guard.before_commit is not None:
                root = next(iter(self.paths))
                for path in guard.before_commit():
                    self.note(root, path)
        pending, self.paths = self.paths, {}
        outcome: CommitOutcome | None = None
        for root, paths in pending.items():
            outcome = commit_records(root, paths, self.message(), quiet=self.quiet)
            if guard is not None and outcome.committed:
                guard.landed = True
        if outcome is not None:
            self.last_outcome = outcome
        return outcome


_RUN_WRITES: ContextVar[_RunWrites | None] = ContextVar("fr_run_writes", default=None)


# --- spec 2026-09-25 §5.B.7: transcript gates stop degrading silently ---------
#
# A gate that cannot observe (no harness detected, no readable transcript)
# notes itself here and prints a warning; the resolve then records the names
# under the unit's `unobserved` evidence, so the gap is in the cursor, not
# only in a stderr nobody keeps.

_UNOBSERVED: ContextVar[list[str] | None] = ContextVar("fr_unobserved", default=None)


def _note_unobserved(gate: str) -> None:
    found = _UNOBSERVED.get()
    if found is None:
        found = []
        _UNOBSERVED.set(found)
    if gate not in found:
        found.append(gate)


def _why_unobservable(what: str) -> str:
    """Why a gate could not observe `what` — the thing it reads from the
    transcript (`questions`, `subagent dispatches`, `commands`), so a gate
    never borrows another gate's noun (#815)."""
    from fr.run.observed import why_unobservable

    try:
        harness = detect_harness(os.environ)
    except HarnessError:
        harness = None
    return why_unobservable(harness, os.environ, what)


TESTS_PROVENANCE_SURFACE = "deliver-tests-provenance"
"""The parity row declaring where `tests=<log>` provenance is verified."""


def _why_tests_unobservable() -> str:
    """Why `tests=<log>` could not be tied to a command. Hermes is declared
    `unsupported` for this check (operator decision 2026-09-26, gh#638): say
    so by name rather than implying a reader is merely missing."""
    try:
        harness = detect_harness(os.environ)
    except HarnessError:
        harness = None
    if harness == "hermes":
        return f"tests= provenance is unsupported on hermes (parity row {TESTS_PROVENANCE_SURFACE})"
    if harness == "opencode":
        return "the OpenCode session database could not be read"
    return _why_unobservable("commands")


def _take_unobserved() -> dict[str, str]:
    """`{"unobserved": "<gate>,…"}` for every gate noted so far, and forget them."""
    from fr.run.telemetry import UNOBSERVED

    found = _UNOBSERVED.get() or []
    _UNOBSERVED.set(None)
    return {UNOBSERVED: ",".join(found)} if found else {}


def _note_record_write(repo_root: Path, path: Path, state: RunState | None = None) -> None:
    """Record that this command wrote `path` (a no-op outside a wrapped command)."""
    writes = _RUN_WRITES.get()
    if writes is None:
        return
    writes.note(repo_root, path)
    if state is not None:
        writes.last = state


def _remember(path: Path) -> None:
    """Keep `path`'s current bytes for the step-record engine's restore
    (a no-op unless the engine drives this command)."""
    writes = _RUN_WRITES.get()
    if writes is not None:
        writes.remember(path)


def _save_run_state(repo_root: Path, state: RunState) -> Path:
    """`save_run_state`, noted for the command's closing commit."""
    _remember(run_path(repo_root, state.run))
    path = save_run_state(repo_root, state)
    _note_record_write(repo_root, path, state)
    return path


def _note_subject(*, step: str, item: str | None, outcome: str) -> None:
    """Name the unit this command acted on in its commit subject (p3-r1)."""
    writes = _RUN_WRITES.get()
    if writes is not None:
        writes.step, writes.item, writes.outcome = step, item, outcome


def _commit_run_writes_now() -> CommitOutcome | None:
    """Commit this command's writes BEFORE it prints a dispatch brief.

    The brief is the line a naive `tail -1` parses (see `_print_member_dispatch`),
    so `commit_records`' stderr report must not land after it — in a harness
    that merges stdout and stderr it would become the last line.

    Returns the `CommitOutcome` (or `None` if nothing was pending) so a caller
    that goes on to print a "push it" line knows whether this invocation's
    commit actually landed (p4-r1).
    """
    writes = _RUN_WRITES.get()
    if writes is not None:
        return writes.commit()
    return None


def _note_loaded(state: RunState) -> None:
    """The cursor as the command found it — the step `advance` acted on."""
    writes = _RUN_WRITES.get()
    if writes is not None and writes.loaded_cursor is None:
        writes.loaded_cursor = state.cursor


def _closeout_handoff_lines(repo_root: Path, run_id: str, *, committed: bool) -> list[str]:
    """The handoff toward `fr pickup --run` (spec 2026-09-25-fr-goal-closeout-
    defects §3.D.2) — printed once `deliver` resolves `done`, and again on
    every `advance` of an already-finished run.

    `committed` is THIS invocation's own commit outcome (p4-r1) — the caller's
    `_commit_run_writes_now()` result, `True` when nothing was pending. Names
    the sha of HEAD as it stands when this prints; for the `deliver` call site
    that must be AFTER `_commit_run_writes_now()` has run (p3-m4): the
    wrapping decorator commits in `finally`, which runs after the command's
    own prints, so a sha read any earlier would not exist yet. When the commit
    was refused (default branch, stuck lock, detached HEAD, …), printing that
    sha would be false assurance that the cursor reached the PR — so this
    prints a NOT-committed line instead, never the sha.

    The closeout pair comes LAST (#814): the push line is an instruction the
    orchestrator acts on, and printed after the closeout it became the last
    thing acted on while the closeout line went unrelayed.
    """
    from fr.run.closeout import primary_checkout

    base = primary_checkout(repo_root)
    closeout = [
        f"closeout: after the PR merges, start a NEW session in {base} and run",
        f"  fr pickup --run {run_id}",
    ]
    if not committed:
        return [
            "cursor NOT committed (see the `fr: not committed` line above) — "
            "commit and push it before merging",
            *closeout,
        ]
    try:
        sha = git_answer(repo_root, "rev-parse", "--short", "HEAD").stdout.strip()
    except GitUnavailableError:
        sha = None
    if sha:
        return [f"cursor committed as {sha} — push it (git push) so the PR carries it", *closeout]
    return closeout


_Cmd = TypeVar("_Cmd", bound=Callable[..., None])


def _commits_run_writes(
    verb: str,
    outcome: Callable[[dict[str, Any]], str | None] | None = None,
    after: Callable[[_RunWrites, dict[str, Any]], None] | None = None,
) -> Callable[[_Cmd], _Cmd]:
    """Commit every record the wrapped command wrote, once, on every exit path.

    `outcome` reads the subject's closing state word off the command's own
    arguments (`resolve --state`, `claim --abandoned`) — the state the command
    was asked to record, which the cursor alone cannot always say (p3-r1).
    `after` runs only when the command RETURNED (not on a refusal), before the
    commit, so whatever it writes lands in the same commit.
    """

    def decorate(fn: _Cmd) -> _Cmd:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> None:
            writes = _RunWrites(
                verb=verb,
                step=kwargs.get("step_id"),
                item=kwargs.get("item"),
                outcome=outcome(kwargs) if outcome is not None else None,
            )
            token = _RUN_WRITES.set(writes)
            try:
                fn(*args, **kwargs)
                if after is not None:
                    after(writes, kwargs)
            finally:
                _RUN_WRITES.reset(token)
                writes.commit()

        return cast(_Cmd, wrapper)

    return decorate


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat()


# --- usage capture (spec 2026-09-25-lean-cost-aware-process §5.B.3) ----------


def _capture_usage(
    repo_root: Path, state: RunState, at: str, *, require_sessions: bool = False
) -> None:
    """Write this host's usage capture and note it for the command's commit.
    Never raises (`fr.usage.capture.capture`)."""
    from fr.usage.capture import capture
    from fr.usage.file import usage_path

    _remember(usage_path(repo_root, state.run))
    # `ambient=True`: a step resolve's caller is the run's orchestrator, so its
    # own session is evidence (spec 2026-10-02-opencode-observe-2 §C).
    path = capture(
        repo_root, state, at, os.environ, ambient=True, require_sessions=require_sessions
    )
    if path is not None:
        _note_record_write(repo_root, path)


def _capture_on_new_host(writes: _RunWrites, kwargs: dict[str, Any]) -> None:
    """A resolve on a host with no capture of this run yet captures its
    sessions — runners, pods, a cross-machine resume (§5.B.3 row 3)."""
    from fr.usage.capture import needs_capture

    state = writes.last
    if state is None:
        return
    try:
        repo_root = resolve_repo_root()
    except Exception:  # noqa: BLE001 — capture never fails its step
        return
    if needs_capture(repo_root, state, os.environ):
        step = kwargs.get("step_id") or state.cursor
        _capture_usage(repo_root, state, f"resolve:{step}", require_sessions=True)


_UNSAFE_IN_RUN_ID = re.compile(r"[^A-Za-z0-9._-]+")


def derive_run_id(branch: str, *, today: _dt.date | None = None) -> str:
    """Derive a run id from `branch` when `--run-id` is not given.

    Must satisfy `validate_run_id` — and therefore
    `fr_dispatch.work_item.run_item_id` — because it FEEDS them: a single
    segment of `[A-Za-z0-9._-]`, starting with an alphanumeric. `branch`
    routinely contains `/` (e.g. `feat/ticket-polling`), so it is flattened;
    the date prefix mirrors the plan-slug shape spec §4.B's own example
    (`2026-08-14-ticket-polling`) uses, keeping a run id visually consistent
    with the plan slug a `unit: run` shape will go on to create.

    **Every unsafe run collapses, not just `/`** (review r5-e1). Git branch
    names admit far more than this: `feat/../x`, `-weird`, `wip #3`, a
    non-ASCII word. Replacing only `/` produced ids that `validate_run_id`
    then rejected — turning a legal branch into a `fr run start` that could
    not run at all — or, worse, an id starting with `-`. The date prefix
    guarantees the leading character, so only the tail needs sanitising, and
    a branch that sanitises to nothing still yields the bare date.
    """
    day = today or _dt.date.today()
    sanitized = _UNSAFE_IN_RUN_ID.sub("-", branch.strip("/")).strip("-.")
    derived = f"{day.isoformat()}-{sanitized}" if sanitized else day.isoformat()
    return derived[:RUN_ID_MAX_LENGTH].rstrip("-.") or day.isoformat()


def _step_by_id(manifest: WorkflowManifest, step_id: str) -> Step:
    step, _parent = _find_step(manifest, step_id)
    return step


def _split_member_id(manifest: WorkflowManifest, step_id: str) -> tuple[str, str] | None:
    """`(item, member_id)` if `step_id` is a grouped fan-out's COMPOSITE key
    (`phase/1/implement-phase`), else `None`.

    The composite is the display id and the `items`-map key — what `fr run
    status` and `advance` both show — but it is deliberately NOT accepted in
    `--step` (spec §3.B, journal `d2`). Accepting it and splitting it
    internally was the issue's own option 2 and was declined: it would leave
    two spellings of one id, and it would hide the `--item` flag from the
    operator at the exact moment they need to learn it. So this function
    exists to *recognise* the composite in order to teach the two flags —
    never to resolve it.

    Recognition is manifest-driven, not shape-of-string: the tail after the
    last `/` must name a member of some `for_each` group. An id that merely
    contains a slash is an ordinary not-found id and gets the ordinary
    message.
    """
    if "/" not in step_id:
        return None
    item, _, tail = step_id.rpartition("/")
    for step in manifest.steps:
        if step.for_each and any(member.id == tail for member in step.steps):
            return item, tail
    return None


def _find_step(manifest: WorkflowManifest, step_id: str) -> tuple[Step, Step | None]:
    """`(step, parent-group)` for a top-level OR member id — members share the
    flattened id space `check_workflow` validates, so resolving one must find
    them too. Parent is `None` for a top-level step."""
    for step in manifest.steps:
        if step.id == step_id:
            return step, None
        for member in step.steps:
            if member.id == step_id:
                return member, step
    not_found = f"step {step_id!r} not found in workflow {manifest.workflow!r}"
    split = _split_member_id(manifest, step_id)
    if split is not None:
        item, member_id = split
        raise RunStateError(
            f"{not_found}.\n"
            "It is a grouped `for_each` member, which takes two flags:\n"
            f"  --step {member_id} --item {item}"
        )
    raise RunStateError(not_found)


def _unit_key(
    repo_root: Path,
    state: RunState,
    step: Step,
    parent: Step | None,
    item: str | None,
) -> str:
    """The UNIT key a `(--step, --item)` pair names (`fr.run.units`) —
    spec §4.B's two key spaces (`phase/<n>/<member-id>` for a grouped member,
    `step/<step-id>` for a flat one) computed in exactly ONE place, so
    `claim`, `_resolve_member` and `advance`'s own flat-step key can never
    drift apart (P3.T1.S3). `step`/`parent` are `_find_step`'s own return
    shape — `parent` is `None` for a top-level step, the group for a member.

    Exits 2 (printing to `err_console`) for every input shape that cannot
    name a unit: a member given no `--item`, a non-member given one, or an
    `--item` naming a phase this run's recorded plan does not have.
    """
    if parent is not None:
        if item is None:
            err_console.print(
                f"[red]{step.id}: a member outcome must address a phase item — "
                "pass --item phase/<n>[/red]"
            )
            raise typer.Exit(2)
        try:
            # (agentic, manual) since gh#496 — a `tag: manual` phase is never
            # dispatched, so only the agentic list can name a unit key.
            agentic, manual = _group_phases(repo_root, state)
        except (RunStateError, AdoptError) as e:
            err_console.print(f"[red]{parent.id}: {escape(str(e))}[/red]", soft_wrap=True)
            raise typer.Exit(2) from e
        expected = _expected_group_items(parent, agentic)
        key = f"{item}/{step.id}"
        if key not in expected:
            # #496 (spec §3.D.3): a manual phase gets its own message BEFORE
            # the generic one. "not a phase member — expected phase/<n> for
            # phases [1,2,3]" reads as a bug in the phase list when phase 4
            # plainly exists in the plan; the reason it is absent is a
            # deliberate omission, and the refusal has to say so. It lives
            # HERE because this is the one place a unit key is validated: it
            # used to sit in `_resolve_member` behind a call to this function,
            # which refused first with the generic text — dead on arrival,
            # and `claim` never had it at all.
            if _item_phase(item) in manual:
                err_console.print(
                    f"[red]{key}: phase {_item_phase(item)} is `tag: manual` and is "
                    "deliberately never dispatched, so there is no outcome to "
                    "record.[/red]\n"
                    "  Its record is the plan's own steps plus the PR's "
                    '"unimplemented — operator pushes to this PR".',
                    soft_wrap=True,
                )
                raise typer.Exit(2)
            err_console.print(
                f"[red]{key}: not a phase member of {parent.id!r} — expected "
                f"phase/<n> for phases {agentic} (from the recorded plan)[/red]"
            )
            raise typer.Exit(2)
        return key
    if item is not None:
        if step.steps:
            members = ", ".join(m.id for m in step.steps)
            err_console.print(
                f"[red]{step.id}: a group outcome must address a member step "
                f"({members}) — pass --step <member> --item phase/<n>[/red]"
            )
        else:
            err_console.print(
                f"[red]{step.id}: --item is only for members of a grouped "
                f"`for_each` step — {step.id!r} has no members[/red]"
            )
        raise typer.Exit(2)
    return _liveness.flat_unit_key(step.id)


def _emitted_plan(state: RunState) -> str | None:
    """The recorded repo-relative plan path, wherever the shape put it."""
    for record in state.steps.values():
        if record.emitted and "plan" in record.emitted:
            return record.emitted["plan"]
    return None


def _group_phases(repo_root: Path, state: RunState) -> tuple[list[int], list[int]]:
    """`(agentic, manual)` phase numbers, from the plan on disk — the one
    source of which phases exist.

    **The filter lives here, above everything else** (#496, spec §3.D.3).
    `_expected_group_items` is the single place that decides which units
    exist, and BOTH of `_advance_group`'s refusals read that list: filter a
    manual phase out any later and a `tag: manual` phase can still be the
    `running` key an ALREADY RUNNING refusal names, or the unit a
    `--redispatch` re-briefs.

    The split keys on `tag` alone and never on completion. A ticked
    front-loaded manual phase waits on nobody (review `r4-f1`) but is still
    not work this run did, so it is recorded as skipped rather than done —
    and keeping the predicate completion-free is what lets `advance` and
    `fr run adopt` write identical markers without either parsing state.

    Fail-closed: a group advanced before its plan is recorded (or against an
    unparseable plan) names what is missing instead of dispatching against a
    guessed phase list.
    """
    plan_rel = _emitted_plan(state)
    if plan_rel is None:
        raise RunStateError(
            "cannot dispatch per-phase members — no plan recorded yet "
            "(resolve the step that emits `plan` first)"
        )
    tags = plan_phase_tags(repo_root, plan_rel)
    agentic = sorted(n for n, tag in tags.items() if tag != "manual")
    manual = sorted(n for n, tag in tags.items() if tag == "manual")
    return agentic, manual


def _manual_items(manual: list[int]) -> dict[str, str]:
    """The `phase/<n>: manual` markers for every phase the fan-out skipped.

    Item granularity, in the group's own map, so a deliberate omission is
    visible in `fr run status` beside everything that WAS dispatched — the
    alternative (leave them out entirely) is how a skipped phase becomes
    indistinguishable from a phase nobody noticed.
    """
    return {f"phase/{n}": MANUAL_ITEM for n in manual}


def _item_phase(item: str) -> int | None:
    """The phase number a `phase/<n>` item names, or None when it names
    something else. Structural, not a cast: `--item` is operator input, so
    `phase/four` and `spec/1` must fall through to the generic refusal rather
    than raise."""
    head, _, tail = item.partition("/")
    return int(tail) if head == "phase" and tail.isdigit() else None


def _group_done_line(step_id: str, expected: list[str], manual: list[int]) -> str:
    """The one completion line for a grouped fan-out.

    Printed from both places a group can complete — `_advance_group` (nothing
    left to dispatch) and `_resolve_member` (the last member's outcome) — so
    the count and the manual phases it names cannot drift between them.

    The manual phases are named rather than merely counted: "6 members done"
    over a 4-phase plan reads as an arithmetic bug until the line says which
    phase was never dispatched and why. It does NOT say "trailing", though
    the common case is: after review `r4-f1` a manual phase may legitimately
    be front-loaded-and-already-complete instead, and deciding which from
    here would be a second definition of "trailing" beside
    `fr.plan_ops._trailing_manual_block`.
    """
    line = f"{step_id}: done ({len(expected)} members done"
    if manual:
        phases = ", ".join(f"phase {n}" for n in manual)
        line += (
            f"; {phases} `tag: manual`, never dispatched — the plan's own "
            "steps and the PR are its record"
        )
    return line + ")"


def _phase_tier(repo_root: Path, state: RunState, phase_n: int) -> str | None:
    """The tier phase `phase_n` declares in its header on the plan this run
    recorded, or `None` when it declares none, no plan is recorded yet, or
    the plan is unparseable.

    Fail-soft by design (unlike `_group_phases`, which fails closed): this is
    an observability field, not a dispatch precondition, and refusing to
    dispatch over an unreadable OPTIONAL tier would be a new failure mode for
    a field whose whole point is that a phase may legitimately not set it.
    "Observability must not break execution", rather than `_group_phases`'s
    stance.
    """
    plan_rel = _emitted_plan(state)
    if plan_rel is None:
        return None
    from fr.parser import PlanSchemaError, parse

    try:
        plan = parse(repo_root / plan_rel)
    except (PlanSchemaError, OSError):
        return None
    return next((p.phase.tier for p in plan.phases if p.phase.number == phase_n), None)


def _expected_group_items(group: Step, phases: list[int]) -> list[str]:
    """Every `phase/<n>/<member>` key of a grouped fan-out, in dispatch
    order: phase-major, then member order — implement before review, per
    phase, never the reverse.

    `phases` is `_group_phases`'s AGENTIC list: a manual phase produces no
    expected key at all, so it is neither dispatchable, resolvable, nor
    countable towards the group's completion.
    """
    return [f"phase/{n}/{m.id}" for n in phases for m in group.steps]


class _StepDriftError(RunStateError):
    """The step list a cursor recorded differs from the manifest's — the one
    refusal a read-only command downgrades to a warning (`_resolve_manifest_for_read`)."""


def _resolve_manifest_for_state(repo_root: Path, state: RunState) -> WorkflowManifest:
    """The manifest this run was started against — name AND schema version.

    `state.workflow` is `"<name>@<schema>"`. The suffix used to be sliced off
    and thrown away (review r5-e3), so a run started against `fr-goal@1` would
    happily keep advancing after the shape was rewritten as `schema: 2` — with
    a step graph the cursor was never computed for. The suffix is a version
    stamp; a version stamp nobody checks is decoration.
    """
    manifest = _resolve_manifest_checked_schema(repo_root, state)
    _check_step_drift(state, manifest)
    return manifest


def _resolve_manifest_checked_schema(repo_root: Path, state: RunState) -> WorkflowManifest:
    name, _, recorded_schema = state.workflow.partition("@")
    manifest = resolve_workflow(name, repo_root)
    if recorded_schema and str(manifest.schema_version) != recorded_schema:
        raise RunStateError(
            f"run {state.run!r} was started against {state.workflow!r}, but "
            f"{name!r} now declares schema {manifest.schema_version}. A shape's "
            "schema version changes its step grammar; start a new run rather "
            "than advancing this one against a different one."
        )
    return manifest


def _resolve_manifest_for_read(repo_root: Path, state: RunState) -> WorkflowManifest:
    """`_resolve_manifest_for_state` for a command that only READS the cursor
    (spec 2026-10-05-run-upgrade-midflight §B).

    A step-list drift is printed as ONE warning and the manifest returned
    anyway: refusing to say who cleared a gate because a later step was added
    helps nobody. A schema-version mismatch still refuses — a different grammar
    is not safe to read with. Mutating commands keep the strict resolver.
    """
    manifest = _resolve_manifest_checked_schema(repo_root, state)
    try:
        _check_step_drift(state, manifest)
    except _StepDriftError as e:
        err_console.print(f"[yellow]warning: {escape(str(e))}[/yellow]", soft_wrap=True)
    return manifest


def _reshape_hint(state: RunState) -> str:
    return (
        f" `fr run reshape {state.run}` moves the cursor onto the current list "
        "when that loses nothing it recorded."
    )


def _check_step_drift(state: RunState, manifest: WorkflowManifest) -> None:
    """Refuse when the shape's STEPS have changed since `fr run start`.

    A step added, removed or renamed makes every recorded position suspect:
    the cursor may name a step that no longer exists, a new step silently
    never runs, and `_next_step_id` moves the run somewhere the operator never
    reviewed. Each of those used to surface as a `KeyError` or a `ValueError`
    from `list.index` deep inside `advance` (review r5-e3) — or, for an added
    step, as nothing at all.

    Reported as a DIFF, because "the workflow changed" is not actionable and
    "added: verify; removed: spec-review" is.
    """
    added, removed = diff_ids(state.steps, (s.id for s in manifest.steps))
    if added or removed:
        parts = []
        if added:
            parts.append(f"added: {', '.join(added)}")
        if removed:
            parts.append(f"removed: {', '.join(removed)}")
        raise _StepDriftError(
            f"run {state.run!r} was started against a different version of "
            f"{state.workflow!r} ({'; '.join(parts)}). A run's cursor is a position in "
            "a step list; start a new run rather than advancing this one against a "
            "list it was never computed for." + _reshape_hint(state)
        )
    for step in manifest.steps:
        if not step.steps:
            continue
        record = state.steps.get(step.id)
        recorded_members = record.members if record is not None else None
        if recorded_members is None:
            continue  # pre-nesting run file: top-level ids match, members unknowable
        current_members = [m.id for m in step.steps]
        if recorded_members != current_members:
            added, removed = diff_ids(recorded_members, current_members)
            parts = []
            if added:
                parts.append(f"added: {', '.join(added)}")
            if removed:
                parts.append(f"removed: {', '.join(removed)}")
            raise _StepDriftError(
                f"run {state.run!r} was started against a different version of "
                f"{state.workflow!r} (step {step.id!r} members changed: {'; '.join(parts)}). "
                "A run's cursor is a position in a step list; start a new run rather "
                "than advancing this one against a list it was never computed for."
                + _reshape_hint(state)
            )


def _rebind_shape(
    state: RunState,
    manifest: WorkflowManifest,
    step_id: str,
    target: str,
    repo_root: Path,
) -> WorkflowManifest | None:
    """The manifest a record's `shape: <target>` rebinds the run onto, `None`
    for a same-shape no-op — or `RunStateError` naming the rule it broke.

    2026-09-29-fr-goal-light-path §A (R1). A run's cursor is a position in a
    step list, so moving it onto another list is safe only before it has
    moved at all, and only onto a list that shares the position it is at:

    1. the step being resolved is the run's first step, and no other step has
       left `pending`;
    2. `resolve_workflow(target)` finds the shape, and its first step has the
       same id as the step being resolved;
    3. the target is not the run's current shape — that declaration is a
       no-op, so a re-applied record is idempotent.

    Pure: it validates, and `_rebound` builds the new state. `apply_record`
    calls it before any write, and `resolve` again where it rewrites.
    """
    current = state.workflow.partition("@")[0]
    if target == current:
        return None
    first = manifest.steps[0].id
    if step_id != first:
        raise RunStateError(
            f"shape: {target!r} refused — only the run's first step ({first!r}) may "
            f"rebind it, and {step_id!r} is not that step. Start a new run with "
            f"`fr run start {target}` instead."
        )
    moved = sorted(
        sid for sid, rec in state.steps.items() if sid != step_id and rec.state != "pending"
    )
    if moved:
        raise RunStateError(
            f"shape: {target!r} refused — step(s) {', '.join(moved)} already left "
            "`pending`, so the run has moved on its current shape. Start a new run "
            f"with `fr run start {target}` instead."
        )
    try:
        rebound = resolve_workflow(target, repo_root)
    except WorkflowError as e:
        raise RunStateError(f"shape: {target!r} refused — {e}") from e
    if not rebound.steps or rebound.steps[0].id != step_id:
        begins = rebound.steps[0].id if rebound.steps else "nothing"
        raise RunStateError(
            f"shape: {target!r} refused — it begins with {begins!r}, not {step_id!r}; "
            "a run rebinds only onto a shape that begins with the step being resolved."
        )
    errors = check_workflow(rebound, repo_root)
    if errors:
        raise RunStateError(f"shape: {target!r} refused — not a valid workflow: {errors[0]}")
    return rebound


def _rebound(state: RunState, rebound: WorkflowManifest, step_id: str) -> RunState:
    """`state` on `rebound`'s step list: `workflow` rewritten, every step
    fresh and `pending` as `fr run start` builds them, bar `step_id`'s own
    record, which is carried over. The cursor stays on `step_id`, so the
    caller's `_complete_step` moves it along the NEW list."""
    steps = {
        s.id: StepRecord(state="pending", members=[m.id for m in s.steps] or None)
        for s in rebound.steps
    }
    steps[step_id] = state.steps[step_id]
    return state.model_copy(
        update={"workflow": f"{rebound.workflow}@{rebound.schema_version}", "steps": steps}
    )


def _with_step(state: RunState, step_id: str, record: StepRecord) -> RunState:
    new_steps = dict(state.steps)
    new_steps[step_id] = record
    return state.model_copy(update={"steps": new_steps})


def _complete_step(
    state: RunState,
    manifest: WorkflowManifest,
    step_id: str,
    outcome: Literal["done", "failed"],
    *,
    exit_code: int | None = None,
    stdout: str | None = None,
    emitted: Mapping[str, str] | None = None,
    answered_by: AnsweredBy | None = None,
) -> RunState:
    """Record `step_id`'s outcome and move the cursor — the ONE place that
    implements the done/failed cursor asymmetry, shared by `advance`'s
    `cli` branch and `resolve` (an `agent` step's outcome) rather than
    forked between them: the cursor advances to the next step on `done`,
    and stays exactly where it is on `failed` — a stalled step must stay
    the loudest thing `status`/`check` report, never slide past silently.

    **The cursor moves off the CURSOR, never relative to `step_id`** (review
    fix r2-f8). Assigning `_next_step_id(manifest, step_id)` unconditionally
    meant completing any step *behind* the cursor rewound the run to just
    after that step — a silent state corruption. Only a step that IS the
    cursor can move it; anything else records its outcome and leaves the
    cursor alone. That is correct however many steps are `running` at once,
    so it stays correct if a shape ever dispatches steps concurrently —
    which enforcing "one running step" as an invariant would have foreclosed.

    The prior record's `gate` is carried forward on `done`, and on `failed`
    it is deliberately not — which is narrower than "an operator authorizes a
    step once" (corrected in review r5-b6). `StepRecord.gate` is only ever set
    to `"cleared"` by `resolve`'s **cli** branch, which returns the step to
    `pending`; the `agent` branch below records `done`/`failed` and writes no
    `gate` at all. So a *failed* gated agent step keeps `gate: None` and
    `_gate_pending` re-asks on the next `advance`. That re-ask is correct — a
    step that failed after its gate was answered is a new question, not a
    resumption — but the claim that the gate is answered once for the life of
    the run was not true of it.

    `answered_by` is the gated **agent** branch's half of that story: those
    steps never acquire `gate: cleared` at all, so provenance is the only
    record that a gate was cleared there, and it is passed in by `resolve`.
    Absent an explicit value the prior record's is carried forward — exactly
    like `gate`, so a cleared `cli` gate's provenance survives the `advance`
    that finally executes the step.
    """
    prior = state.steps.get(step_id)
    # The successor is the PRIOR record with the fields completion decides
    # overwritten — never a record rebuilt from a list of fields to keep.
    # Finding f7 is why: this used to be `StepRecord(state=…, gate=prior.gate,
    # members=prior.members, …)`, a hand-maintained carry-forward list, so any
    # durable field added later was DROPPED at completion by default. The
    # dispatch history was the one that got caught: the trail gh-503 asked for
    # ("who was holding this phase, and when") was deleted by the very act of
    # FINISHING — silently, because only `status`/`check` ever read it — and an
    # adopted flat fan-out went blind the same way (`_fan_out_items` scans
    # every record for exactly this). Now `gate`, `members`, `units` and
    # whatever comes next survive unless a line below says otherwise.
    completion: dict[str, object] = {
        "state": outcome,
        "at": _now(),
        "answered_by": answered_by or (prior.answered_by if prior is not None else None),
        "exit": exit_code,
        "stdout": stdout,
        "emitted": dict(emitted) if emitted else None,
    }
    new_record = (
        prior.model_copy(update=completion)
        if prior is not None
        else StepRecord.model_validate(completion)
    )
    new_state = _with_step(state, step_id, new_record)
    if outcome == "done" and step_id == state.cursor:
        next_id = _next_step_id(manifest, step_id)
        if next_id is not None:
            new_state = new_state.model_copy(update={"cursor": next_id})
    return new_state


def _gate_degradation_notice() -> str | None:
    """The loud degradation notice for a blocked `gate: operator` step (spec
    §3.D.1), or `None` when fr can observe who answers it here (Claude Code
    with a readable transcript, OpenCode with an exported, readable session).

    Reads `os.environ` through `detect_harness` (never a hardcoded harness
    name) and the shipped matrix's `operator-gate` row through `load_matrix`
    — the notice text is built from that row's `scope_note`, so a stale or
    hand-typed string here can never drift from what `fr harness parity`
    itself declares. An UNRECOGNISED environment (`detect_harness` returns
    `None`) is treated as degraded too — fail loud, the same posture as the
    isolation gate: a wrong notice costs a confusing paragraph, a missing one
    costs a silently skipped gate.

    Raises `HarnessError` when `FR_HARNESS` is set to something outside
    `fr.harness.HARNESSES` — a typo must not silently become an inference,
    so the caller surfaces it as a command error rather than guessing.
    """
    from fr.run.observed import why_unobservable
    from fr.run.telemetry import operator_answered_since

    harness = detect_harness(os.environ)
    matrix = load_matrix()
    surface = next(s for s in matrix.surfaces if s.id == "operator-gate")
    if harness is not None:
        hstate = surface.harnesses[harness]
        # Observed is a claim about a MECHANISM — `resolve` reading answered
        # questions in the session (Claude Code's transcript, OpenCode's
        # `question` parts) — so the notice is silent exactly where that read
        # works, whatever the row's state. Before 2026-09-21 (debug journal C1)
        # it was a claim about a TOOL existing, nothing checked it, and an early
        # return spared the one harness that skipped its gate the only warning.
        epoch = "1970-01-01T00:00:00+00:00"
        if operator_answered_since(os.environ, epoch) is not None:
            return None
        if hstate.state in ("enforced", "partial"):
            # fr HAS a reader here, so the row's scope_note (which describes
            # the verification) would be false — say why the read failed.
            detail = (
                f"your harness ({harness}) is verified by reading the session, but "
                f"{why_unobservable(harness, os.environ, 'questions')} — so this gate "
                "is advisory now"
            )
        else:
            detail = f"your harness ({harness}) does not enforce this gate (state: {hstate.state})"
            if hstate.scope_note:
                detail += f" — {hstate.scope_note}"
    else:
        detail = (
            "your harness could not be detected (set FR_HARNESS to one of "
            f"{', '.join(HARNESSES)}) — treating this gate as advisory to be safe"
        )
    return (
        f"gate: {detail}.\n"
        "      Put the questions to the operator (with your harness's question tool where "
        "it has one) and STOP until they answer.\n"
        "      fr cannot verify who answered this gate, so its resolve must say: "
        "`answered_by: operator` (the operator answered) or `answered_by: agent` "
        "(cleared without asking) — `--answered-by` on the flag form, an "
        "`answered_by` evidence key in a record. There is no default."
        # No braces in this notice: it precedes the JSON brief, which a harness
        # finds by its first `{`.
    )


def _refuse_gate_flags(step_id: str) -> NoReturn:
    """Gate flags on a resolve that clears no gate — refused, because silently
    ignored flags read as honoured ones (review r1-7)."""
    err_console.print(
        f"[red]{step_id}: --no-questions/--reason and question rounds only apply to a "
        "resolve that clears an operator gate, and this one clears none.[/red]",
        soft_wrap=True,
    )
    raise typer.Exit(2)


def _clears_gate(step: Step, record: StepRecord, outcome: str) -> bool:
    """Does this `resolve` CLEAR an operator gate (rather than decline it, or
    resolve a step that never had one)?

    The condition provenance is recorded under, and deliberately narrow:
    `answered_by` must not claim an authorization for a step nobody gated, and
    a *declined* gate (`--state failed`) was not cleared. It reads the
    record's own state rather than `_gate_pending`, because by the time this
    runs the step is `blocked` — which is what "waiting on its gate" looks
    like once `advance` has seen it.
    """
    return step.gate == "operator" and record.state == "blocked" and outcome == "done"


ANNOUNCEMENTS = ("a 2nd round may follow", "round 1 of 2")
"""What a design-risk second round's first round must say, case-insensitively,
in one of its question texts (spec 2026-09-26 §3.C): the operator is told a
second round may follow before answering the first. The first is the label fr-goal
prints (gh#766: a round's total is a forecast, so the label no longer counts it);
the second is the pre-gh#766 label, still accepted so a session that asked round 1
under the old prose is not refused by the fr it upgraded to."""


def question_rounds_refusal(
    rounds: Sequence[Round], questions: QuestionRounds | None
) -> str | None:
    """The §3.C verdict table: `None` when the observed ANSWERED rounds agree
    with the declaration (absent ≡ `rounds: 1`), else why they do not.

    Pure — the gate calls it with the transcript's rounds, the tests with
    hand-built ones. Zero rounds is not this table's case: that is the
    existing "no answered question" refusal, decided before it.
    """
    n = len(rounds)
    declared = questions.rounds if questions is not None else 1
    if n > 2:
        return (
            f"the transcript shows {n} answered question rounds since the gate blocked — "
            "there is never a round 3. A gate asked in three rounds is not one fr records "
            "as answered: decline it (`--state failed`) and re-run the step, asking at "
            "most two rounds."
        )
    if n != declared:
        plural = "round" if n == 1 else "rounds"
        fix = (
            "Declare the second round: `questions: {rounds: 2, trigger: "
            'design-risk|operator-request, reason: "…"}` in the record, or '
            '`--question-rounds 2 --round-two-trigger … --round-two-reason "…"`.'
            if n == 2
            else "The transcript shows only one round: drop the `questions: {rounds: 2, …}` "
            "declaration (or `--question-rounds 2`)."
        )
        return (
            f"the transcript shows {n} answered question {plural} since the gate blocked, "
            f"but this resolve declares {declared}. {fix}"
        )
    if (
        questions is not None
        and questions.rounds == 2
        and questions.trigger == "design-risk"
        and not any(
            announcement in text.lower()
            for text in rounds[0].question_texts
            for announcement in ANNOUNCEMENTS
        )
    ):
        return (
            "the operator was not told a second round would follow: no round-1 question "
            "says `a 2nd round may follow`. A design-risk second round is announced in round 1, "
            "before the operator answers it."
        )
    return None


# gh#690: a gate DECIDES in `_gate_provenance` but its spec-journal decision
# is only QUEUED there, and written by `_flush_gate_decisions` immediately
# before the resolve saves the cursor — after every refusal point. Written at
# decision time, a later refusal left the entry behind, and the command's
# closing commit (which keeps every noted write, on every exit path) recorded a
# decision the cursor never did.

_GATE_DECISIONS: ContextVar[list[tuple[Path, str, JournalEntry]] | None] = ContextVar(
    "fr_gate_decisions", default=None
)


def _queue_gate_decision(
    repo_root: Path, spec: str, entry_id: str, *, title: str, body: str
) -> None:
    """Queue one spec-journal `decision` about a cleared operator gate — once:
    a retry after a later refusal must not log it twice (review r1-6).

    A retry that would write a DIFFERENT body under the same id is refused
    (exit 2) here, at decision time (review p2-r6): keeping the first body
    silently would leave the journal — and the PR body read from it —
    describing a trigger or reason this resolve no longer declares."""
    from fr.journal.model import journal_path

    slug = spec_journal_slug(Path(spec).name[: -len(".md")])
    target = journal_path(repo_root, "spec", slug)
    try:
        existing = (
            next((e for e in parse_journal(target.read_text()) if e.id == entry_id), None)
            if target.is_file()
            else None
        )
    except JournalParseError:
        existing = None
    if existing is not None:
        if existing.body.strip() == body.strip():
            return
        shown = (
            target.relative_to(repo_root).as_posix()
            if target.is_relative_to(repo_root)
            else str(target)
        )
        err_console.print(
            f"journal entry `{entry_id}` in {shown} already records a different body "
            f"({existing.body.strip()!r}) than this resolve would write ({body.strip()!r}). "
            "Resolve again with what that entry says, or correct the entry first if it is "
            "the one that is wrong — nothing applied.",
            style="red",
            markup=False,
            soft_wrap=True,
        )
        raise typer.Exit(2)
    queued = _GATE_DECISIONS.get()
    if queued is None:
        queued = []
        _GATE_DECISIONS.set(queued)
    entry = JournalEntry(
        kind="decision",
        scope="spec",
        id=entry_id,
        # `fr journal add`'s own stamp (UTC with its offset, second precision).
        created=journal_now(),
        title=title,
        body=body,
    )
    queued.append((target, slug, entry))


def _flush_gate_decisions(repo_root: Path) -> None:
    """Write every queued gate decision — called by each `resolve` branch
    immediately before it saves the cursor, so nothing after it can refuse."""
    from fr.journal.model import append_journal_entry

    queued = _GATE_DECISIONS.get() or []
    _GATE_DECISIONS.set(None)
    for target, slug, entry in queued:
        _remember(target)
        append_journal_entry(target, slug, entry)
        _note_record_write(repo_root, target)


def _gate_provenance(
    repo_root: Path,
    step_id: str,
    record: StepRecord,
    *,
    claimed: AnsweredBy | None,
    no_questions: bool,
    reason: str | None,
    questions: QuestionRounds | None = None,
    emitted: Mapping[str, str],
    state: RunState,
) -> AnsweredBy:
    """Who cleared this operator gate — OBSERVED where fr can see it, refused
    where the observation contradicts the resolve (2026-09-21 debug journal C1).

    The first fr-goal run after #508 cleared its brainstorm gate on Claude Code
    without asking anything; `resolve` recorded `answered_by: agent` and let it
    through, while `parity.yaml` declared the gate `enforced` — which also
    suppressed the one warning OpenCode and Hermes get. Enforced now means what
    it says, read from the session transcript (`operator_answered_since`):

    - an answered question since the gate blocked → `operator`, whatever was
      claimed: provenance is derived, not asserted;
    - observed, none answered → REFUSED (exit 2), unless the bypass is explicit
      and on the record: `--no-questions --reason "…"` → `agent`, the reason
      written to the spec journal this resolve emits (when it emits one);
    - not observable (Hermes, no harness, an unreadable Claude Code transcript,
      OpenCode without a session export or with an unreadable store) → a
      stated claim is recorded as claimed, unverified, and says so out loud;
      no claim is REFUSED (R10 — there is no default).

    `questions` is the declared round count (spec 2026-09-26 §3.C): observed
    answered rounds are checked against it by `question_rounds_refusal`, and a
    verified or claimed `rounds: 2` appends `gate-question-rounds-<step>` to
    the same spec journal the bypass writes to.
    """
    from fr.run.telemetry import answered_rounds_since

    if no_questions and not (reason and reason.strip()):
        err_console.print(
            f'[red]{step_id}: --no-questions needs --reason "…" — clearing an operator '
            "gate without asking is allowed, but only on the record.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    # Review r1-5: "on the record" means a journal the PR body reads — the spec
    # this resolve emits, else one an earlier step already emitted. With
    # neither there is nowhere durable for the reason, so the bypass is refused
    # rather than printed to a stderr nobody keeps.
    spec_for_reason = emitted.get("spec") or next(
        (r.emitted["spec"] for r in state.steps.values() if r.emitted and "spec" in r.emitted),
        None,
    )
    if no_questions and not (spec_for_reason and spec_for_reason.endswith(".md")):
        err_console.print(
            f"[red]{step_id}: --no-questions has nowhere to record its reason — this "
            "resolve emits no spec and the run has none yet. Pass the spec with "
            "`--emitted spec=<path>`, or ask the operator.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    round_two = questions is not None and questions.rounds == 2
    if round_two and not (spec_for_reason and spec_for_reason.endswith(".md")):
        err_console.print(
            f"[red]{step_id}: a second question round has nowhere to record its reason — "
            "this resolve emits no spec and the run has none yet. Pass the spec with "
            "`--emitted spec=<path>` (or `emitted: {spec: <path>}` in the record).[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    rounds = answered_rounds_since(os.environ, record.at) if record.at else None
    observed = None if rounds is None else bool(rounds)
    if observed is True and not no_questions:
        assert rounds is not None
        # gh#761: standalone fr-brainstorming asks one question per turn, so
        # every question is a round to the transcript; the cap is fr-goal's.
        refusal = (
            None if state.driver == "standalone" else question_rounds_refusal(rounds, questions)
        )
        if refusal is not None:
            err_console.print(f"{step_id}: {refusal}", style="red", markup=False, soft_wrap=True)
            raise typer.Exit(2)
        _record_round_two(repo_root, step_id, questions, spec_for_reason)
        return "operator"
    if observed is False and not no_questions:
        err_console.print(
            f"[red]{step_id}: no answered question in this session's transcript since the "
            f"gate blocked at {record.at}. Put the questions to the operator with your "
            "harness's question tool (AskUserQuestion on Claude Code) and resolve again "
            "once they answer — or clear it without asking, on the record: "
            f'`--no-questions --reason "<why no operator decision was needed>"`.[/red]',
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if no_questions:
        assert spec_for_reason is not None  # refused above otherwise
        _queue_gate_decision(
            repo_root,
            spec_for_reason,
            f"gate-no-questions-{step_id}",
            title=f"Operator gate `{step_id}` cleared without asking",
            body=reason or "",
        )
        err_console.print(
            f"[yellow]{step_id}: operator gate cleared WITHOUT asking (answered_by: "
            f"agent). Reason: {reason}[/yellow]",
            soft_wrap=True,
        )
        return "agent"
    if claimed is None:
        # R10 (spec 2026-10-02 §F): there is no default. An unobserved gate with
        # no claim is a question fr cannot answer for the caller, so it asks.
        err_console.print(
            f"[red]{step_id}: could not verify who answered this gate "
            f"({_why_unobservable('questions')}) — pass `answered_by: operator` "
            "(the operator answered) or `answered_by: agent` (cleared without asking): "
            "`--answered-by operator|agent` on the flag form, "
            "`evidence: {answered_by: …}` in a record.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    # Wherever the gate cannot observe — no harness, an unreadable Claude Code
    # transcript, OpenCode without a session export (FR_OPENCODE_SESSION_ID)
    # or with an unreadable store, or Hermes, which has no question reader —
    # it says so on the record (§5.B.7, p2-r28); `advance` already printed the
    # degradation notice there, which is no reason to be quiet now.
    _note_unobserved("operator-gate")
    _record_round_two(repo_root, step_id, questions, spec_for_reason)
    # p2-r2: only `rounds: 2` writes anything (`_record_round_two`); `rounds: 1`
    # is the default and is merely accepted.
    if questions is None:
        declared = ""
    elif questions.rounds == 2:
        declared = " The declared `questions: {rounds: 2}` is recorded as claimed too."
    else:
        declared = (
            f" The declared `questions: {{rounds: {questions.rounds}}}` is accepted, unverified."
        )
    err_console.print(
        f"[yellow]{step_id}: could not verify this gate — {_why_unobservable('questions')}, "
        f"so `answered_by: {claimed}` is recorded as claimed, unverified "
        f"(evidence: unobserved=operator-gate).{declared}[/yellow]",
        soft_wrap=True,
    )
    return claimed


def _record_round_two(
    repo_root: Path, step_id: str, questions: QuestionRounds | None, spec: str | None
) -> None:
    """A cleared gate that took two question rounds says so on the spec journal
    (spec 2026-09-26 §3.C) — where the PR body reads it. `rounds: 1` is the
    default and writes nothing."""
    if questions is None or questions.rounds != 2:
        return
    assert spec is not None  # refused before observation otherwise
    _queue_gate_decision(
        repo_root,
        spec,
        f"gate-question-rounds-{step_id}",
        title=f"Operator gate `{step_id}` took two question rounds",
        body=f"Trigger: {questions.trigger}. {questions.reason}",
    )


def _refuse_missing_emits(
    label: str,
    emits: tuple[str, ...] | list[str],
    supplied: Mapping[str, str],
    recorded: Mapping[str, str] | None,
) -> None:
    """Refuse `done` for a unit that names none of an artifact it declares
    (gh#587). `_parse_emitted` checks every name GIVEN is declared; this is the
    converse — every declared artifact is given now or already on the record.
    Before it, `brainstorm` reached `done` with `emitted: None` and the run went
    on to review a spec the cursor could not locate."""
    missing = [
        n for n in emitted_artifacts(emits) if n not in supplied and n not in (recorded or {})
    ]
    if not missing:
        return
    flags = " ".join(f"--emitted {n}=<…>" for n in missing)
    err_console.print(
        f"{label}: done without the artifact(s) it declares: {', '.join(missing)}. "
        f"Name them — `{flags}`, or `emitted:` in the record — and resolve again; "
        "nothing applied.",
        style="red",
        markup=False,
        soft_wrap=True,
    )
    raise typer.Exit(2)


def _parse_emitted(pairs: list[str], repo_root: Path, step: Step | None = None) -> dict[str, str]:
    """`--emitted name=path` pairs, validated and made repo-relative.

    **The normalization is the point** (review r5-b2). `emitted.plan` is the
    key `archive.find_run_for_plan` and `run.adopt.adoptable_plans` match a
    run to its plan by, and both compare against a repo-relative posix path.
    A stored ABSOLUTE path matches neither — verified live: it made `fr run
    adopt` create a SECOND run for a plan that already had one, and would
    have left the first behind at `fr archive`. Both are silent no-ops, which
    spec §4.B calls out as worse than failing. And an absolute path is what
    an agent following SKILL.md's `--emitted plan=<path>` produces routinely.

    Only `REPO_TRACKED_ARTIFACTS` (`spec`, `plan`) are path-normalised: `pr`
    is a URL, `report` and `journal:*` have no repo path, and rewriting those
    would be nonsense.

    Five further rules, each closing a way to record a wrong thing quietly
    (review r5-e2):

    1. **Split on the FIRST `=` only.** A path may contain `=`; splitting on
       the last, or on all, silently truncates it.
    2. **Neither half may be empty.** `plan=` records the repo root as the
       plan; `=x` records an artifact with no name.
    3. **The name must be one the step declares it `emits`.** An artifact the
       manifest never mentions is a shape/agent mismatch — the agent emitted
       something the workflow does not know about, or misspelled the name it
       does — and storing it means the run carries a key nothing will ever
       read. The refusal names the step's declared emits.
    4. **No duplicate names in one call.** `--emitted plan=a --emitted plan=b`
       silently kept `b`.
    5. **A repo-tracked artifact must EXIST.** An agent reporting a spec that
       is not on disk is precisely the silent-wrong-state case the run cursor
       exists to prevent.
    """
    result: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")  # partition splits on the FIRST `=`
        if not sep:
            raise RunStateError(f"--emitted must be 'name=path', got {pair!r}")
        name = name.strip()
        if not name:
            raise RunStateError(f"--emitted has an empty artifact name: {pair!r}")
        if not value.strip():
            raise RunStateError(f"--emitted {name}= has an empty value")
        if name in result:
            raise RunStateError(
                f"--emitted {name}= given twice ({result[name]!r} then {value!r}) — "
                "one artifact, one value"
            )
        if step is not None and name not in step.emits:
            emits = ", ".join(sorted(step.emits)) or "(nothing)"
            raise RunStateError(
                f"step {step.id!r} does not emit {name!r}; it declares: {emits}. "
                "Either the workflow shape is missing an `emits:` entry or the "
                "artifact name is misspelled."
            )
        result[name] = _repo_relative_artifact(name, value.strip(), repo_root)
    return result


def _repo_relative_artifact(name: str, value: str, repo_root: Path) -> str:
    if name not in REPO_TRACKED_ARTIFACTS:
        return value
    raw = Path(value)
    target = raw if raw.is_absolute() else repo_root / raw
    # `resolve()` on BOTH sides (review r5-e2): an fr worktree lives under
    # `~/.cache`, which on macOS is reached through `/private/var/...` — so a
    # resolved artifact path and an unresolved repo root have no common
    # prefix and `relative_to` raises on a file that is plainly inside.
    resolved_root = repo_root.resolve()
    try:
        rel = target.resolve().relative_to(resolved_root)
    except ValueError as e:
        raise RunStateError(
            f"--emitted {name}={value!r} is outside the repo ({resolved_root}) — "
            "a run records repo-relative artifact paths"
        ) from e
    if not (resolved_root / rel).exists():
        raise RunStateError(
            f"--emitted {name}={value!r} does not exist ({resolved_root / rel}). "
            "A run records artifacts that were actually written; recording one "
            "that is not there is the silent-wrong-state this cursor exists to "
            "prevent."
        )
    return rel.as_posix()


# ------------------------------------------------------------------ evidence
#
# Spec 2026-09-20-unit-record-unification §4.E. The line this draws is §3's:
# an obligation's SATISFACTION is control, its CONTENT is journal. The cursor
# records THAT the review happened and WHERE the evidence is — a journal entry
# id — exactly as `emitted` records that a spec exists and where, without
# containing the spec. It never copies a finding.


# The obligations fr can check, and the subset it checks BY ITSELF. A derived
# obligation is never offered on the command line: one satisfied by passing a
# flag is satisfied by anyone who can type the flag, and `findings` exists
# precisely because "the review's findings were dealt with" was prose until
# something other than the agent's word could witness it.
PHASE_EXECUTOR_AGENT = "super-fr:fr-phase-executor"
_VERIFIABLE_EVIDENCE = (
    "review",
    "reviewer",
    "findings",
    "tests",
    "proportionality",
    "visual",
    "single-phase",
    "walk",
)
# `proportionality` (2026-09-24 spec §C) is `deliver`'s derived witness: fr runs
# `fr plan proportionality` itself and stores `<merge-base>:<sha256>`.
_DERIVED_EVIDENCE = DERIVED_EVIDENCE
# `single-phase` (2026-09-29-fr-goal-light-path §A, R2) is the light shape's
# `plan` witness: the emitted plan has exactly one phase that is not `[manual]`.
# `visual` (2026-09-28-ui-visual-evidence §C) is derived from the step record's
# `visual:` section and the witness transcript; the rules live in `fr.run.visual`.
# Evidence ABOUT A REVIEWED JOURNAL — a phase of the plan journal, or the spec
# journal (2026-09-24 spec §E) — verified against an `_EvidenceTarget`. A flat
# `step/<id>` unit with no target (`_evidence_target`) refuses them rather than
# recording them unchecked. `tests` is not one: it is delivery's evidence, on
# the flat `deliver` unit (debug journal C5).
_PHASE_EVIDENCE = frozenset({"review", "reviewer", "findings"})
# OFFERED evidence (2026-09-29-fr-goal-light-path §D, R6): a name a unit of a
# `for_each: phase` group member may carry WITHOUT its step declaring it, and
# that is never counted missing there. `tests` is the phase holder's own suite
# log, which `deliver` may later reuse (`tests: reuse`) while the code tree it
# covered is unchanged. Where a step DECLARES it (`deliver`) it stays mandatory
# exactly as before; the shipped manifests do not change.
_OFFERED_EVIDENCE = frozenset({"tests", "walk"})
# `walk` (2026-10-06-verification-strategies §C, R11) is `deliver`'s witness of
# the pre-merge strategy: a log `fr verification walk` wrote, on HEAD's code
# tree. It is owed only when the run's spec gives the run or a row an
# agent-driven pre-merge strategy (`fr.verification.walk.walk_owed`); when it is
# not, omitting it or saying `walk=none` is accepted.
_DERIVED_FROM = {
    "findings": "from the reviewed journal: every finding filed against the phase "
    "(plan journal) or the spec (spec journal) must be fixed, refuted, deferred or "
    "out of scope",
    "proportionality": "by running `fr plan proportionality` on the run's plan and "
    "hashing the report at its merge-base",
    "visual": "from the step record's `visual:` section — every owed row's screenshots "
    "cover its named states and interactions, and the witness transcript shows each "
    "one opened since the unit opened",
    "single-phase": "from the plan this step emits: exactly one phase that is not `[manual]`",
}


@dataclass(frozen=True)
class _EvidenceTarget:
    """The journal a review unit's evidence is verified against.

    `review-phase` reviews a PHASE of the plan journal (`scope="plan"`,
    `phase=N`); `spec-review` reviews the run's spec, in its spec journal
    (`scope="spec"`, no phase). One value, passed through every rule, so the
    two review steps cannot drift into two spellings of "reviewed".
    """

    scope: Literal["plan", "spec"]
    phase: int | None

    @property
    def subject(self) -> str:
        return f"phase {self.phase}" if self.phase is not None else "the spec"


def _evidence_target(step: Step, phase: int | None) -> _EvidenceTarget | None:
    """Which journal `step`'s review evidence names — or `None` when fr can
    locate none. A phase unit reviews its phase; a flat step reviews the spec
    journal only when the manifest says it writes it (`emits: [journal:spec]`,
    which is what `spec-review` is). Anything else has nothing to check an id
    against, and fr says so rather than guess."""
    if phase is not None:
        return _EvidenceTarget("plan", phase)
    if "journal:spec" in step.emits:
        return _EvidenceTarget("spec", None)
    return None


def _evidence_hint(name: str, target: _EvidenceTarget | None) -> str:
    if name == "walk":
        return (
            "<path-to-walk-log>, the log `fr verification walk --run <run> --model <m>` "
            "wrote on this code tree"
        )
    if name == "tests":
        return (
            "<path-to-log>, naming the output file of the full suite you ran "
            "yourself, in this session, during this unit"
        )
    assert target is not None  # phase-scoped evidence without a target is refused first
    if name == "review":
        when = "" if target.phase is not None else ", created after this step opened"
        return (
            f"<journal-entry-id>, naming the `kind=review` {target.scope}-journal entry "
            f"recorded for {target.subject}{when}"
        )
    not_impl = f", not {target.subject}'s implementer" if target.phase is not None else ""
    return (
        f"<agent-id>, naming the dispatched reviewer subagent (a separate context{not_impl}) "
        "by the id its dispatch returned"
    )


def _parse_evidence(pairs: list[str], step: Step, *, phase_unit: bool = False) -> dict[str, str]:
    """`--evidence name=journal-entry-id` pairs, validated against `step`.

    Same five-rule shape as `_parse_emitted` and for the same reasons — split
    on the FIRST `=`, neither half empty, no duplicate name, and the name must
    be one the STEP declares. That last rule is what stops evidence becoming
    decoration: a name the shape never asked for is verified against nothing,
    so recording it would put an unverified id on the cursor under a heading
    that reads as proof.

    `phase_unit` (the unit is a `for_each: phase` group member) admits an
    `_OFFERED_EVIDENCE` name the step does not declare — still verified, by
    `_verified_evidence`, before anything reaches the cursor.
    """
    result: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep:
            raise RunStateError(f"--evidence must be 'name=journal-entry-id', got {pair!r}")
        name = name.strip()
        if not name:
            raise RunStateError(f"--evidence has an empty obligation name: {pair!r}")
        if not value.strip():
            raise RunStateError(f"--evidence {name}= has an empty value")
        if name in result:
            raise RunStateError(
                f"--evidence {name}= given twice ({result[name]!r} then {value.strip()!r}) — "
                "one obligation, one entry"
            )
        if phase_unit and name in _OFFERED_EVIDENCE and name not in step.evidence:
            result[name] = value.strip()
            continue
        if not step.evidence:
            raise RunStateError(
                f"step {step.id!r} declares no evidence, so --evidence {name}= "
                "would record an id nothing verified"
            )
        if name not in step.evidence:
            declared = ", ".join(sorted(step.evidence))
            raise RunStateError(
                f"step {step.id!r} does not require {name!r} evidence; it declares: {declared}"
            )
        if name in _DERIVED_EVIDENCE:
            raise RunStateError(
                f"--evidence {name}= is not yours to pass — fr derives {name!r} itself "
                f"when the unit resolves `done` ({_DERIVED_FROM[name]}), and records "
                "what it saw"
            )
        result[name] = value.strip()
    return result


def _plan_journal_entries(repo_root: Path, state: RunState) -> tuple[str, list[JournalEntry]]:
    """`(slug, entries)` of this run's PLAN journal. Raises `RunStateError`
    when the run has not recorded a plan yet, which is fail-closed: a gate that
    cannot read its source does not know whether it passed."""
    plan_rel = _emitted_plan(state)
    if plan_rel is None:
        raise RunStateError(
            "cannot verify evidence — no plan recorded yet (resolve the step "
            "that emits `plan` first)"
        )
    return _journal_entries(repo_root, "plan", Path(plan_rel).name, "--phase <n> ")


def _review_journal_entries(
    repo_root: Path, state: RunState, target: _EvidenceTarget
) -> tuple[str, list[JournalEntry]]:
    """`(slug, entries)` of the journal `target` names — the plan journal, or
    the spec journal of the spec this run emitted. Fail-closed like the plan
    one: no spec recorded is a refusal, not an empty journal."""
    if target.scope == "plan":
        return _plan_journal_entries(repo_root, state)
    from fr.requirements import run_spec

    spec_rel = run_spec(state)
    if spec_rel is None:
        raise RunStateError(
            "cannot verify evidence — no spec recorded yet (resolve the step "
            "that emits `spec` first)"
        )
    return _journal_entries(repo_root, "spec", spec_journal_slug(Path(spec_rel).stem), "")


def _journal_entries(
    repo_root: Path, scope: Literal["plan", "spec"], slug: str, phase_flag: str
) -> tuple[str, list[JournalEntry]]:
    path = resolve_journal_read_path(repo_root, scope, slug)
    if not path.exists():
        raise RunStateError(
            f"cannot verify evidence — the {scope} journal {path} does not exist. "
            f"Record the review first: fr journal add --scope {scope} --slug {slug} "
            f"--kind review {phase_flag}..."
        )
    try:
        return slug, parse_journal(path.read_text())
    except (JournalParseError, OSError) as e:
        raise RunStateError(
            f"cannot verify evidence — {scope} journal {path} is unreadable: {e}"
        ) from e


def _verified_evidence(
    repo_root: Path,
    state: RunState,
    step: Step,
    *,
    key: str,
    phase: int | None,
    offered: dict[str, str],
    state_value: str,
    emitted: Mapping[str, str] | None = None,
    visual: tuple[VisualEvidence, ...] | None = None,
    holder: str | None = None,
) -> dict[str, str]:
    """The evidence `key` may be resolved with — or `typer.Exit(2)`.

    `visual` is the step record's `visual:` section — `None` on the flag form,
    which can carry none — and `holder` the unit's claimed holder (this
    resolve's `agent`, else the last attempt's); both feed the derived `visual`
    witness (2026-09-28-ui-visual-evidence §C).

    `emitted` is THIS resolve's emitted map: on the resolve of the step that
    emits the plan it is the only place that plan is named (the cursor holds
    none yet), and the `single-phase` witness reads it.

    Three rules, in this order:

    1. `--state failed` requires nothing. A failed review unit met no
       obligation, so demanding proof of one would make a failure
       unreportable — the run would wedge on exactly the outcome the cursor
       most needs to record.
    2. Every obligation the step declares must be offered, or the resolve is
       REFUSED naming the flag. This is gh#430 closed: `review-phase` leaves
       no artifact of its own, so a skipped review used to resolve identically
       to one that did the work. Now it cannot reach `done` at all.
    3. Each offered id is verified against the unit's `_EvidenceTarget`. A
       phase unit uses gh#517's OWN rule (`fr.journal.model.reviews_phase`) —
       a `kind=review` plan-journal entry carrying `phase=N` for THIS unit's
       phase. `spec-review` (2026-09-24 spec §E) uses the spec journal: a
       `kind=review` entry created after the step opened. Without that, any
       id at all satisfies the gate and "skipped" and "passed clean" are the
       same state again with extra steps.

    Fail-closed on a flat `step/<id>` with no target — one that reviews no
    journal fr can locate: review evidence is evidence about a reviewed
    journal, and fr will say it cannot verify rather than store an id nothing
    checked.
    """
    if not step.evidence and not offered:
        # `_parse_evidence` already refused an offered name the step does not
        # declare — bar `_OFFERED_EVIDENCE` on a phase unit — so this is the
        # ordinary, unchanged path every pre-existing shape takes.
        return {}
    if state_value != "done" and not offered:
        return {}
    # Refuse an obligation fr cannot check BEFORE demanding it. A shape that
    # asks for something unverifiable is a shape bug, and "you did not pass
    # --evidence sniff=" would send the operator looking for an entry id that
    # could never have satisfied it.
    unverifiable = sorted(name for name in step.evidence if name not in _VERIFIABLE_EVIDENCE)
    if unverifiable:
        known = " and ".join(f"`{name}`" for name in _VERIFIABLE_EVIDENCE)
        err_console.print(
            f"[red]{key}: cannot verify {unverifiable[0]!r} evidence — {known} are the "
            "obligations fr knows how to verify[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    target = _evidence_target(step, phase)
    phase_scoped = [n for n in step.evidence if n in _PHASE_EVIDENCE]
    if target is None and phase_scoped:
        err_console.print(
            f"[red]{key}: cannot verify `{phase_scoped[0]}` evidence for a unit that names "
            "no phase — a review is evidence about a phase, and fr will not record an "
            "id it checked nothing against[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    # The owed predicate runs BEFORE rule 2: `walk` is the one obligation a run
    # may omit, because it is owed only when the spec asks for a pre-merge walk
    # (§C) — which is how an in-flight run, or one with no `## Verification`,
    # delivers unchanged.
    walk_owed = None
    if "walk" in offered or (state_value == "done" and "walk" in step.evidence):
        walk_owed = _walk_obligation(key, repo_root, state)
    missing = (
        [
            n
            for n in step.evidence
            if n not in offered
            and n not in _DERIVED_EVIDENCE
            and not (n == "walk" and walk_owed is not None and not walk_owed.owed)
        ]
        if state_value == "done"
        else []
    )
    if missing:
        owed = ", ".join(missing)
        err_console.print(
            f"[red]{key}: refused — step {step.id!r} cannot be done without evidence "
            f"({owed}).[/red]",
            soft_wrap=True,
        )
        for name in missing:
            err_console.print(
                f"  pass --evidence {name}={_evidence_hint(name, target)}",
                markup=False,
                soft_wrap=True,
            )
        err_console.print(
            "  Work that left no evidence is work that did not happen "
            "(spec §4.E) — `--state failed` needs no evidence.",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    # Offered evidence is verified whatever the state. `failed` REQUIRES none,
    # which is not the same as "anything goes": a failed review that did
    # produce a journal entry may still name it, and an id nothing checked
    # must never reach the cursor under either state.
    verified = dict(offered)
    attempt = units.last_attempt(state, key)
    opened = attempt.dispatched if attempt is not None else None
    # A flat review unit with no attempt (an adopted cursor) is dated by its
    # step's own `at` — for the review entry AND the reviewer's dispatch, one
    # window for both (review p4-f1: a None window let any reviewer id pass).
    flat_record = state.steps.get(step.id) if target is not None and target.phase is None else None
    since = opened or (flat_record.at if flat_record is not None else None)
    # `reviewer=historical` (spec 2026-10-05-run-upgrade-midflight §D, R7): a
    # phase reviewed before this cursor existed. It skips ONLY the two checks
    # that read this cursor's dispatches (`_verify_reviewer`, the reviewer
    # return) and is held to the bound instead; the review-entry and findings
    # checks below run unchanged. Every other reviewer value keeps every check.
    historical = offered.get("reviewer") == HISTORICAL_REVIEWER
    if historical:
        assert target is not None  # phase-scoped, refused above otherwise
        _refuse_unboundable_historical(key, target, offered)
    if "reviewer" in offered and not historical:
        assert target is not None  # phase-scoped, refused above otherwise
        _verify_reviewer(
            key,
            offered["reviewer"],
            state,
            target=target,
            opened=since,
            expected_agent=step.agent if target.phase is None else None,
        )
    if "tests" in offered and phase is not None:
        verified["tests"] = _verify_phase_tests_log(
            key,
            offered["tests"],
            repo_root,
            opened=opened,
            holder=holder or (attempt.agent if attempt is not None else None),
            record_tree=state_value == "done",
        )
    elif "tests" in offered and offered["tests"] == TESTS_REUSE:
        verified["tests"] = _reuse_tests_witness(key, repo_root, state)
    elif "tests" in offered:
        verified["tests"] = _verify_tests_log(key, offered["tests"], repo_root, opened=opened)
    if "walk" in offered:
        assert walk_owed is not None
        verified["walk"] = _verify_walk(
            key, offered["walk"], repo_root, state, walk_owed, opened=opened
        )
    # Every DERIVED witness is evaluated, and every refusal printed, before the
    # resolve is refused (gh#768): one environmental blocker (no fetchable
    # remote) used to exit first and hide each witness declared after it.
    refused: list[str] = []

    def derive(name: str, witness: Callable[[], str]) -> None:
        try:
            verified[name] = witness()
        except typer.Exit:
            refused.append(name)

    if state_value == "done" and "proportionality" in step.evidence:
        derive("proportionality", lambda: _proportionality_witness(key, repo_root, state))
    if state_value == "done" and "single-phase" in step.evidence:
        derive(
            "single-phase",
            lambda: _single_phase_witness(key, repo_root, state, emitted or {}),
        )
    derives = state_value == "done" and "findings" in step.evidence
    review_journal: tuple[str, list[JournalEntry]] | None = None
    if "review" in offered or derives:
        assert target is not None  # `review`/`findings` are phase-scoped, refused above otherwise
        try:
            review_journal = _review_journal_entries(repo_root, state, target)
        except RunStateError as e:
            err_console.print(f"[red]{key}: {escape(str(e))}[/red]", soft_wrap=True)
            raise typer.Exit(2) from e
    if "review" in offered:
        assert review_journal is not None and target is not None
        slug, entries = review_journal
        _verify_review_entry(
            key, offered["review"], slug=slug, entries=entries, target=target, since=since
        )
        if historical:
            _verify_historical_bound(
                key, repo_root, state, target=target, entry_id=offered["review"], entries=entries
            )
    if state_value == "done" and "visual" in step.evidence:
        derive(
            "visual",
            lambda: _visual_witness(
                key,
                repo_root,
                state,
                step,
                phase=phase,
                entries=visual,
                holder=holder or (attempt.agent if attempt is not None else None),
                reviewer=offered.get("reviewer"),
                since=since or (state.steps[step.id].at if step.id in state.steps else None),
                dispatched_as=attempt.agent_type if attempt is not None else None,
            ),
        )
    if derives:
        assert review_journal is not None and target is not None
        slug, entries = review_journal
        findings_target = target
        # A historical review has no dispatch in this cursor, so no return to read.
        returned_phase = target.phase if "reviewer" in step.evidence and not historical else None

        def findings_witness() -> str:
            if returned_phase is not None:
                # R7: only a step that names a dispatched reviewer has a return
                # that could owe a review-findings block.
                _check_returned_findings(
                    key, entries, returned_phase, since, offered.get("reviewer")
                )
            return _closed_findings_witness(key, slug, entries, findings_target)

        derive("findings", findings_witness)
    if len(refused) > 1:
        err_console.print(
            f"{key}: refused — {len(refused)} derived witnesses failed: {', '.join(refused)}",
            markup=False,
            soft_wrap=True,
        )
    if refused:
        raise typer.Exit(2)
    return verified


def _refuse_unboundable_historical(
    key: str, target: _EvidenceTarget, offered: Mapping[str, str]
) -> None:
    """`reviewer=historical` where no bound can apply — or return. A flat unit
    (spec-review) is refused: its review must postdate the step, and adoption
    never leaves it open. A phase unit must name the `review` entry the bound
    is checked against."""
    if target.phase is None:
        err_console.print(
            f"[red]{key}: refused — reviewer={HISTORICAL_REVIEWER} is accepted only on a "
            "phase review unit; a spec review must be done by a reviewer dispatched after "
            "the step opened.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if "review" not in offered:
        err_console.print(
            f"[red]{key}: refused — reviewer={HISTORICAL_REVIEWER} needs --evidence "
            "review=<entry-id>, the journal review it stands on.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)


def _verify_historical_bound(
    key: str,
    repo_root: Path,
    state: RunState,
    *,
    target: _EvidenceTarget,
    entry_id: str,
    entries: list[JournalEntry],
) -> None:
    """The review entry `entry_id` meets spec §D's bound for `target`'s phase
    — or exit 2 naming the clause it fails."""
    from fr.run.historical import historical_review_refusal
    from fr.run.visual import VisualRefusedError, owed_for_unit

    assert target.phase is not None
    entry = next(e for e in entries if e.id == entry_id)  # `_verify_review_entry` found it
    try:
        owed = owed_for_unit(
            repo_root, plan_rel=_emitted_plan(state), phase=target.phase, spec_rel=None
        )
    except VisualRefusedError as e:
        _derived_refusal(key, e.lines)
    attempt = units.last_attempt(state, key)
    refusal = historical_review_refusal(
        state,
        target.phase,
        entry,
        owes_visual=bool(owed),
        review_key=key,
        review_dispatched=attempt.dispatched if attempt is not None else None,
    )
    if refusal is not None:
        err_console.print(
            f"[red]{key}: refused — reviewer={HISTORICAL_REVIEWER}: {escape(refusal)}.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)


def _visual_witness(
    key: str,
    repo_root: Path,
    state: RunState,
    step: Step,
    *,
    phase: int | None,
    entries: tuple[VisualEvidence, ...] | None,
    holder: str | None,
    reviewer: str | None,
    since: str | None,
    dispatched_as: str | None = None,
) -> str:
    """The derived `visual` witness — or exit 2. A thin call into
    `fr.run.visual`, which owns every rule and every refusal's wording."""
    from fr.record.model import records_dir
    from fr.requirements import run_spec
    from fr.run.visual import VisualRefusedError, derive_visual, owed_for_unit, role_for

    try:
        owed = owed_for_unit(
            repo_root, plan_rel=_emitted_plan(state), phase=phase, spec_rel=run_spec(state)
        )
        derived = derive_visual(
            owed,
            entries,
            role=role_for(step.evidence, phase),
            since=since,
            holder=holder,
            reviewer=reviewer,
            repo_root=repo_root,
            records_dir=records_dir(repo_root, state.run),
            env=os.environ,
            dispatched_as=dispatched_as,
            claim_hint=(
                f"fr run claim {state.run} --step {step.id}"
                + (f" --item phase/{phase}" if phase is not None else "")
                + " --agent <id>"
            ),
        )
    except VisualRefusedError as e:
        _derived_refusal(key, e.lines)
    if derived.unobserved:
        _note_unobserved("visual")
        err_console.print(
            f"[yellow]{key}: could not verify that the screenshots were opened — "
            f"{derived.why}; recorded as checked on disk, unverified "
            "(evidence: unobserved=visual).[/yellow]",
            soft_wrap=True,
        )
    return derived.witness


def _single_phase_witness(
    key: str, repo_root: Path, state: RunState, emitted: Mapping[str, str]
) -> str:
    """`phase <n>` — the light shape's one agentic phase — or exit 2.

    2026-09-29-fr-goal-light-path §A (R2): a structural rule checked when the
    plan is authored, not a hope that it stays small. `[manual]` phases are
    allowed (they are not work a subagent runs); anything but exactly one
    agentic phase is refused, naming the phases and the two ways forward.
    Fail-closed on a plan fr cannot read.
    """
    plan_rel = emitted.get("plan") or _emitted_plan(state)
    if plan_rel is None:
        err_console.print(
            f"[red]{key}: cannot derive single-phase evidence — no plan recorded "
            "(pass --emitted plan=<plan-dir>)[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    try:
        tags = plan_phase_tags(repo_root, plan_rel)
    except AdoptError as e:
        err_console.print(
            f"[red]{key}: cannot derive single-phase evidence — {escape(str(e))}[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2) from e
    agentic = sorted(n for n, tag in tags.items() if tag != "manual")
    if len(agentic) != 1:
        ids = ", ".join(str(n) for n in agentic) or "none"
        err_console.print(
            f"{key}: single-phase: the light shape takes one agentic phase; this plan "
            f"has {len(agentic)} ({ids}). Merge them, or start a new run on fr-goal.",
            markup=False,
            soft_wrap=True,
        )
        raise typer.Exit(2)
    return f"phase {agentic[0]}"


def _proportionality_witness(key: str, repo_root: Path, state: RunState) -> str:
    """`<merge-base-sha>:<sha256-of-report>` for this run's plan — or exit 2.

    The report itself never blocks (spec §C, report first); what fails closed
    is only the witness. A report with no merge-base is the single line naming
    `--base`, and hashing it would record "proportionality checked" over a
    diff nobody computed, so the resolve is refused with that line instead.
    """
    import hashlib

    from fr.parser import PlanSchemaError, parse
    from fr.proportionality import run_report

    plan_rel = _emitted_plan(state)
    if plan_rel is None:
        err_console.print(
            f"[red]{key}: cannot derive proportionality evidence — no plan recorded "
            "yet (resolve the step that emits `plan` first)[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    try:
        plan = parse(repo_root / plan_rel)
    except PlanSchemaError as e:
        err_console.print(
            f"[red]{key}: cannot derive proportionality evidence — plan {plan_rel} "
            f"does not parse: {escape(str(e))}[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2) from e
    base, label = _proportionality_base(repo_root)
    if base is None:
        err_console.print(
            f"{key}: cannot derive proportionality evidence — no base: {label}. Fetch the "
            "remote so its default branch resolves, or create the local default branch.",
            markup=False,
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if label is not None:
        err_console.print(
            f"{key}: proportionality: no remote default branch; using base {label}",
            markup=False,
            soft_wrap=True,
        )
    report = run_report(repo_root, plan, base)
    if report.merge_base is None:
        err_console.print(
            f"{key}: cannot derive proportionality evidence — {report.text.strip()}",
            markup=False,
            soft_wrap=True,
        )
        raise typer.Exit(2)
    return f"{report.merge_base}:{hashlib.sha256(report.text.encode()).hexdigest()}"


def _proportionality_base(repo_root: Path) -> tuple[str | None, str | None]:
    """The base `deliver`'s proportionality witness diffs against (gh#768).

    `fr run resolve` takes no `--base`, so a repo whose remote default branch
    does not resolve could never resolve `deliver`. In order: the remote
    default branch (`(ref, None)` — the ordinary case, nothing printed); the
    commit `fr isolation up` cut this branch from; the local default branch.
    `(ref, label)` names a fallback; `(None, why)` means none is left.
    """
    from fr.git import GitRefusal, GitUnavailableError, git_answer, remote_default_ref
    from fr.isolation.types import load_state

    try:
        found = remote_default_ref(repo_root)
        if found is not None and not isinstance(found, GitRefusal):
            return found, None
        head = git_answer(repo_root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        try:
            recorded = load_state(repo_root, head)
        except (OSError, ValueError):
            recorded = None
        if recorded is not None and recorded.base_sha:
            ok = git_answer(repo_root, "cat-file", "-e", f"{recorded.base_sha}^{{commit}}")
            if ok.returncode == 0:
                return recorded.base_sha, f"{recorded.base_sha[:12]} (isolation start commit)"
        for name in ("main", "master"):
            if name == head:
                continue
            ok = git_answer(repo_root, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}")
            if ok.returncode == 0:
                return name, f"{name} (local default branch)"
    except GitUnavailableError as e:
        return None, f"git could not answer ({e}); retry"
    return None, (
        "no remote default branch, no isolation start commit, and no local default branch"
    )


def _derived_refusal(key: str, lines: list[str]) -> NoReturn:
    """A derived witness's refusal: its first line after the unit key, the
    rest indented beneath it."""
    err_console.print(f"{key}: {lines[0]}", markup=False, soft_wrap=True)
    for line in lines[1:]:
        err_console.print(f"  {line}", markup=False, soft_wrap=True)
    raise typer.Exit(2)


def _verify_reviewer(
    key: str,
    agent_id: str,
    state: RunState,
    *,
    target: _EvidenceTarget,
    opened: str | None,
    expected_agent: str | None = None,
) -> None:
    """`agent_id` is a SEPARATE context that reviewed this phase — or exit 2.

    2026-09-21 debug journal C6 (operator decision: separate-context review).
    The `review=<entry-id>` gate proved an entry EXISTS; on the #497 run the
    orchestrator typed that entry itself, reviewing nothing — #430 one layer
    down. So a review also names the subagent that did it, and fr checks two
    things: it is not the agent that IMPLEMENTED this phase (a context marking
    its own work), and — where the transcript is readable — this session really
    dispatched it after the review unit opened. Unobservable: warned, recorded
    as claimed, never silently.

    A spec review (`target.phase is None`, 2026-09-24 spec §E) has no
    implementer to exclude — the spec's author is the orchestrator, which has
    no agent id and so can never pass the dispatch check. Dispatches are read
    through `fr.run.observed` — Claude Code's transcript, OpenCode's child
    sessions (once the super-fr plugin exports the run session); on Hermes, or
    wherever the session cannot be read, the id is recorded as claimed.
    When the step names its reviewer (`expected_agent`, spec-review's
    `super-fr:fr-spec-reviewer`), an observed dispatch of any OTHER agent type
    is refused (review p4-f2) — every spelling `agent_name` folds matches.
    """
    from fr.run.observed import ChildDispatch, observed_session
    from fr.run.telemetry import parse_timestamp

    phase = target.phase
    # The review unit's own holders are reviewers by construction: a reviewer
    # that claims the unit it reviews is not an implementer, and counting it
    # here would refuse the very reviewer the step dispatched.
    implementers = (
        {
            a.agent
            for record in state.steps.values()
            for unit_key in (record.units or {})
            if unit_key.startswith(f"phase/{phase}/") and unit_key != key
            for a in units.attempts(record, unit_key)
            if a.agent_type is not None and a.agent is not None
        }
        if phase is not None
        else set()
    )
    if agent_id in implementers:
        err_console.print(
            f"[red]{key}: --evidence reviewer={agent_id} is the agent that IMPLEMENTED phase "
            f"{phase} — a review must come from a separate context, not the one whose work "
            "it judges. Dispatch a reviewer subagent and name its id.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    # Through the session protocol (spec 2026-10-02-opencode-observe-2 §A):
    # the dispatch named by the id, among those since the review opened.
    start = parse_timestamp(opened)
    view = observed_session(os.environ) if start is not None else None
    dispatched = view.dispatches(start) if view is not None and start is not None else None
    observed: ChildDispatch | Literal[False] | None = (
        None
        if dispatched is None
        else next((d for d in dispatched if d.agent_id == agent_id), False)
    )
    if observed and _same_agent(observed.agent_type, PHASE_EXECUTOR_AGENT):
        # Review r1-11: a phase executor is an IMPLEMENTER by construction —
        # any phase's — so it is never the separate context a review needs.
        err_console.print(
            f"[red]{key}: --evidence reviewer={agent_id} is a {PHASE_EXECUTOR_AGENT} "
            "dispatch — an implementer, not a reviewer. Dispatch a reviewer subagent.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if (
        observed
        and expected_agent is not None
        and not _same_agent(observed.agent_type, expected_agent)
    ):
        err_console.print(
            f"[red]{key}: --evidence reviewer={agent_id} is a {observed.agent_type!r} "
            f"dispatch — this step's reviewer is {expected_agent}. Dispatch that agent "
            "and name its id.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if observed is False:
        err_console.print(
            f"[red]{key}: --evidence reviewer={agent_id} names no subagent this session "
            f"dispatched since the review opened at {opened}. The review must be done by "
            "a dispatched reviewer (a separate context), and named by the id its dispatch "
            "returned.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if observed is None:
        _note_unobserved("reviewer")
        err_console.print(
            f"[yellow]{key}: could not verify reviewer {agent_id!r} — "
            f"{_why_unobservable('subagent dispatches')}; recorded as claimed, unverified "
            "(evidence: unobserved=reviewer).[/yellow]",
            soft_wrap=True,
        )


def _same_agent(observed: str | None, expected: str) -> bool:
    """`observed` is `expected`, in any spelling `fr.run.observed.agent_name`
    folds: plugin-qualified or bare (`super-fr:fr-spec-reviewer` /
    `fr-spec-reviewer`), and OpenCode's tiered name (`fr-spec-reviewer-hard`)."""
    from fr.run.observed import agent_name

    if observed is None:
        return False
    return agent_name(observed) == agent_name(expected)


def _check_returned_findings(
    key: str,
    entries: list[JournalEntry],
    phase: int,
    since: str | None,
    reviewer: str | None,
) -> None:
    """Every finding a phase reviewer RETURNED is a plan-journal finding
    against `phase` with the reviewer's own scope tag — or exit 2 (spec
    2026-10-02-opencode-observe-2 §E, R7).

    A child dispatched since the review opened is a reviewer of this unit when
    it is the one the record names (`reviewer`), or when its return carries a
    ```review-findings fence; each owes a well-formed block (`none` when it
    raised nothing). Any other child — a helper dispatched while receiving the
    review — owes nothing. The journal may hold MORE findings than the blocks
    (the orchestrator's own), never fewer. Where fr cannot read the session, or
    the named reviewer's return, the check is noted `unobserved=reviewer-return`
    and warned, never silently skipped."""
    from fr.run.observed import observed_session
    from fr.run.review_return import ReviewFindingsBlockError, parse_review_findings
    from fr.run.telemetry import parse_timestamp

    start = parse_timestamp(since) if since is not None else None
    view = observed_session(os.environ) if start is not None else None
    dispatched = view.dispatches(start) if view is not None and start is not None else None
    if dispatched is None:
        _return_unobserved(key, "the phase reviewers", _why_unobservable("subagent returns"))
        return
    problems: list[str] = []
    returned: dict[str, tuple[str, str]] = {}  # id -> (scope, reviewer)
    for d in dispatched:
        named = reviewer is not None and d.agent_id == reviewer
        if d.returned is None:
            if named:
                _return_unobserved(key, f"reviewer {d.agent_id}", "its return is not readable yet")
            continue
        try:
            rows = parse_review_findings(d.returned)
        except ReviewFindingsBlockError as e:
            problems.append(f"{d.agent_id}: {e}")
            continue
        if rows is None:
            if named:
                problems.append(
                    f"reviewer {d.agent_id} returned no review-findings block — its return "
                    "must end with one (`none` when it raised nothing)"
                )
            continue
        for fid, scope, _summary in rows:
            if fid in returned:
                problems.append(
                    f"{fid} is returned by both {returned[fid][1]} and {d.agent_id} — "
                    "give each reviewer its own letter (p<N>a-r<k>, p<N>b-r<k>)"
                )
                continue
            returned[fid] = (scope, d.agent_id)
    # Phase N OR LATER (review p2-r3): the manifest files a finding that
    # belongs to a later phase against THAT phase, where it gates that review.
    journaled = {
        e.id: e
        for e in entries
        if e.kind == "finding" and e.resolves is None and e.phase is not None and e.phase >= phase
    }
    missing = [fid for fid in returned if fid not in journaled]
    if missing:
        problems.append(
            f"returned finding(s) not in the plan journal against phase {phase} or later: "
            + ", ".join(f"{fid} (reviewer {returned[fid][1]})" for fid in missing)
            + " — journal each under its id with the reviewer's tag "
            "(`fr journal add --kind finding --id <id> --review-scope in|out ...`)"
        )
    for fid, (scope, by) in returned.items():
        entry = journaled.get(fid)
        if entry is not None and entry.review_scope != scope:
            problems.append(
                f"{fid} is journaled with review_scope {entry.review_scope} but {by} "
                f"tagged it {scope} — keep the reviewer's tag; reclassify by resolving it "
                "out-of-scope"
            )
    if problems:
        _return_refusal(
            key,
            problems,
            "Journal every returned finding under its id with the reviewer's tag, or "
            "re-dispatch a reviewer whose return is malformed; never edit a return.",
        )


def _return_unobserved(key: str, who: str, why: str) -> None:
    """A reviewer-return check skipped: warned and noted, never silent (§E)."""
    _note_unobserved("reviewer-return")
    err_console.print(
        f"[yellow]{key}: could not read what {who} returned — {why}; the record is "
        "taken as claimed (evidence: unobserved=reviewer-return).[/yellow]",
        soft_wrap=True,
    )


def _return_refusal(key: str, problems: list[str], remedy: str) -> NoReturn:
    """THE refusal of the reviewer-return check (spec
    2026-10-02-opencode-observe-2 §E): the unit (its step and phase), every
    problem — each naming its reviewer and ids — on its own line, then what to
    do; exit 2."""
    _derived_refusal(
        key,
        [
            "refused — the review record does not match what the phase reviewers returned:",
            *(f"- {p}" for p in problems),
            remedy,
        ],
    )


def _wrote_before(
    log: Path, opened: str | None, modified: _dt.datetime, slack: _dt.timedelta
) -> bool:
    """Did a command of the orchestrator's that wrote `log` start BEFORE the unit
    opened, end after it, and write the bytes on disk? Only chooses the
    refusal's wording (gh#765)."""
    from fr.run.telemetry import orchestrator_wrote_since, parse_timestamp

    opened_at = parse_timestamp(opened)
    earlier = orchestrator_wrote_since(os.environ, log, "1970-01-01T00:00:00+00:00")
    return opened_at is not None and any(
        e >= opened_at and s - slack <= modified <= e + slack for s, e in earlier or ()
    )


def _walk_obligation(key: str, repo_root: Path, state: RunState) -> WalkOwed:
    """What walk `deliver` owes for this run (§C), or exit 2.

    Fail-closed: a section, matrix or strategy fr cannot read means fr cannot
    tell whether a walk is owed, and a gate that cannot decide does not pass.
    R10: an owed row that names no scenario is refused BY ID, before anything is
    asked of the log.
    """
    from fr.acceptance.model import AcceptanceError
    from fr.requirements import load_spec_matrix
    from fr.verification.model import StrategyError
    from fr.verification.rows import run_verification
    from fr.verification.spec_section import SectionError
    from fr.verification.walk import WalkOwed, walk_owed

    try:
        spec_rel, verification = run_verification(repo_root, state)
        if spec_rel is None:
            return WalkOwed()
        matrix, spec_ref = load_spec_matrix(repo_root, spec_rel)
        owed = walk_owed(matrix, spec_ref, verification, repo_root)
    except (AcceptanceError, SectionError, StrategyError, OSError) as e:
        err_console.print(
            f"[red]{key}: cannot tell whether a pre-merge walk is owed — {escape(str(e))}[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2) from e
    unscripted = [r.id for r in owed.rows if not r.scenario]
    if unscripted:
        err_console.print(
            f"[red]{key}: refused — row {unscripted[0]!r} has an agent-driven pre-merge "
            "strategy and names no `scenario` (set it with `fr acceptance set-status "
            "--scenario`).[/red]",
            soft_wrap=True,
        )
        for other in unscripted[1:]:
            err_console.print(f"  also unscripted: {other}", markup=False)
        raise typer.Exit(2)
    return owed


def _verify_walk(
    key: str, value: str, repo_root: Path, state: RunState, owed: WalkOwed, *, opened: str | None
) -> str:
    """`value` is `none` (accepted only when no walk is owed) or a log
    `fr verification walk` wrote on HEAD's code tree, every step passing and
    every owed row covered — or exit 2 naming the cause. Returns the witness,
    `<log>@<sha256[:12]>`.

    Attributed as `tests=` is (review p3-r1): the header is the log's own
    claim, so it must also sit in this run's walk dir and — where the
    transcript is readable — have been written inside the run window of a
    command of YOURS that ran `fr verification walk --run <run>` since this
    unit opened. Unobservable: recorded `unobserved=walk`, never silent.
    """
    from fr.run.code_tree import code_tree, dirty_code_paths
    from fr.verification.walk import WalkError, check_walk_log, parse_walk_log, walk_log_dir

    if value == "none":
        if owed.owed:
            wanted = [r.id for r in owed.rows] or [owed.run_strategy or "?"]
            err_console.print(
                f"[red]{key}: --evidence walk=none — a pre-merge walk is owed "
                f"({', '.join(wanted)}); run `fr verification walk` and name its log.[/red]",
                soft_wrap=True,
            )
            raise typer.Exit(2)
        return "none"
    path = (Path(value).expanduser() if Path(value).is_absolute() else repo_root / value).resolve()
    directory = walk_log_dir(state.run)
    if not path.is_relative_to(directory.resolve()):
        err_console.print(
            f"[red]{key}: --evidence walk={value} is not in {directory} — name the log "
            f"`fr verification walk --run {state.run}` wrote.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    try:
        data = path.read_bytes()
        log = parse_walk_log(data.decode())
        problems = check_walk_log(log, owed, code_tree(repo_root), run=state.run)
        dirty = dirty_code_paths(repo_root)
        modified = _dt.datetime.fromtimestamp(path.stat().st_mtime, tz=_dt.UTC)
    except (OSError, UnicodeDecodeError, WalkError, GitUnavailableError) as e:
        err_console.print(
            f"[red]{key}: --evidence walk={value}: {escape(str(e))}[/red]", soft_wrap=True
        )
        raise typer.Exit(2) from e
    if dirty:
        problems.append(f"uncommitted code since the walk ({dirty[0]}...)")
    problems += _walk_provenance(key, state.run, modified, opened=opened)
    if problems:
        err_console.print(f"[red]{key}: --evidence walk={value} is refused:[/red]", soft_wrap=True)
        for problem in problems:
            err_console.print(f"  - {problem}", markup=False, soft_wrap=True)
        raise typer.Exit(2)
    return _log_witness(path, data, repo_root)


def _walk_provenance(
    key: str, run: str, modified: _dt.datetime, *, opened: str | None
) -> list[str]:
    """Why a walk log modified at `modified` is not one a command of yours
    wrote during this unit (empty when it is). Unobservable: `unobserved=walk`,
    warned — and a log older than the unit is still refused."""
    from fr.run.observed import walks_run
    from fr.run.telemetry import orchestrator_ran_since, parse_timestamp

    windows = (
        orchestrator_ran_since(os.environ, lambda command: walks_run(command, run), opened)
        if opened
        else None
    )
    # One second of slack either side, as `tests=` (review r1-1).
    slack = _dt.timedelta(seconds=1)
    if windows is not None:
        if any(s - slack <= modified <= e + slack for s, e in windows):
            return []
        why = (
            "no command of yours ran it"
            if not windows
            else "its bytes were not written by the command of yours that ran it"
        )
        return [
            f"{why} — `fr verification walk --run {run}` must run in this session since "
            f"this unit opened at {opened}, and write the log you name"
        ]
    opened_at = parse_timestamp(opened)
    if opened_at is not None and modified < opened_at - slack:
        return [f"the log predates this unit (opened {opened}) — walk again"]
    _note_unobserved("walk")
    err_console.print(
        f"[yellow]{key}: could not verify who ran the walk — "
        f"{_why_unobservable('commands')}; recorded unverified "
        "(evidence: unobserved=walk).[/yellow]",
        soft_wrap=True,
    )
    return []


def _verify_tests_log(key: str, log: str, repo_root: Path, *, opened: str | None) -> str:
    """`log` is a suite the ORCHESTRATOR ran during this unit — or exit 2.
    Returns the recorded witness, `<path>@<sha256[:12]>`.

    2026-09-21 debug journal C5: `deliver` resolved `done` 28 seconds after it
    opened with nothing but a PR url, and the PR said "verified locally" on the
    executor's word. Now the unit names the log of a suite run during delivery:
    it must exist and be non-empty, and — where the transcript is readable — a
    main-thread `Bash` call naming it must have run to completion since the unit
    opened. Unobservable: the file must at least be newer than the unit, and it
    says it could not verify who ran it.
    """
    from fr.run.telemetry import orchestrator_wrote_since, parse_timestamp

    path, data = _read_suite_log(key, log, repo_root)
    modified = _dt.datetime.fromtimestamp(path.stat().st_mtime, tz=_dt.UTC)
    windows = orchestrator_wrote_since(os.environ, path, opened) if opened else None
    # One second of slack either side: the cursor stamps at second precision,
    # and a filesystem's mtime may round (review r1-1).
    slack = _dt.timedelta(seconds=1)
    if windows is not None and not any(s - slack <= modified <= e + slack for s, e in windows):
        if not windows and _wrote_before(path, opened, modified, slack):
            # gh#765: the suite shared one call with the `fr run advance` that
            # opened this unit, so that call predates it. Still refused — the
            # suite must run during delivery — but "nobody wrote it" misled.
            err_console.print(
                f"[red]{key}: --evidence tests={log}: the command of yours that wrote it "
                f"was issued before this unit opened at {opened} (in the same call as "
                "the `fr run advance` that opened it?). Run the suite again as its own "
                "command, now that the unit is open, and name that log.[/red]",
                soft_wrap=True,
            )
            raise typer.Exit(2)
        why = (
            "no command of YOURS wrote it (a `>`, `>>` or `tee` naming it)"
            if not windows
            else "its bytes were not written by the command of yours that names it"
        )
        err_console.print(
            f"[red]{key}: --evidence tests={log}: {why} since this unit opened at "
            f"{opened}. A subagent's report is not verification — run the suite in this "
            "session, writing its output to the log you name. A backgrounded suite "
            "counts once its task-notification reports it completed (Claude Code), or "
            "once a later command of yours prints the log's exit=0 line (OpenCode's "
            "detached form, gh#719).[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if windows is None:
        opened_at = parse_timestamp(opened)
        if opened_at is not None and modified < opened_at:
            err_console.print(
                f"[red]{key}: --evidence tests={log} predates this unit (opened {opened}) — "
                "it is not a run of the code being delivered.[/red]",
                soft_wrap=True,
            )
            raise typer.Exit(2)
        _note_unobserved("tests")
        err_console.print(
            f"[yellow]{key}: could not verify who ran {log} — {_why_tests_unobservable()}; "
            "recorded as a fresh log, unverified (evidence: unobserved=tests).[/yellow]",
            soft_wrap=True,
        )
    return _log_witness(path, data, repo_root)


def _read_suite_log(key: str, log: str, repo_root: Path) -> tuple[Path, bytes]:
    """`(resolved path, bytes)` of a named suite log — or exit 2 when it sits
    in a run's records dir or is missing or empty. The checks every `tests=`
    log meets, whoever wrote it (`deliver`'s and a phase unit's alike)."""
    from fr.record.model import RECORDS_SUFFIX

    path = (Path(log) if Path(log).is_absolute() else repo_root / log).resolve()
    try:
        rel_parts = path.relative_to(repo_root.resolve()).parts
    except ValueError:
        rel_parts = ()
    if rel_parts[:3] == ("docs", "superpowers", "runs") and (
        len(rel_parts) > 4 and rel_parts[3].endswith(RECORDS_SUFFIX)
    ):
        # gh#638: `<run>.records/` holds step records and fr's pr-body render,
        # and fr empties it; a log written there got committed and reached
        # `main` with nothing to remove it.
        err_console.print(
            f"[red]{key}: --evidence tests={log} is inside a run's records dir, which "
            "holds step records only and is emptied by fr. Write the suite log outside "
            "the repo (e.g. $TMPDIR/full-suite.log) and name that path.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    try:
        data = path.read_bytes()
    except OSError:
        data = b""
    if not data:
        err_console.print(
            f"[red]{key}: --evidence tests={log} is missing or empty — run the full suite "
            "yourself, write its output to a file, and name that file.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    return path, data


def _log_witness(path: Path, data: bytes, repo_root: Path) -> str:
    """`<shown>@<sha256[:12]>`. Review r1-8: the witness lands in a git-tracked
    cursor, so it names the log repo-relative, or by basename when it lives
    outside the repo — never an absolute path carrying someone's home
    directory."""
    import hashlib

    try:
        shown = str(path.relative_to(repo_root.resolve()))
    except ValueError:
        shown = path.name
    return f"{shown}@{hashlib.sha256(data).hexdigest()[:12]}"


def _phase_log_windows(
    path: Path, opened: str | None, holder: str | None
) -> list[tuple[_dt.datetime, _dt.datetime]] | str | Literal[False] | None:
    """The run windows of the holder's commands that wrote `path` — read
    through `fr.run.observed` from the holder's own session: the claimed
    agent's child (a Claude Code subagent transcript, an OpenCode child
    session), or the run session itself when the unit ran inline (no holder).

    `False` when this session dispatched no agent `holder` (a bogus or foreign
    id: refused, never unobserved); a `str` reason when nothing can be read —
    including Hermes, which has no session reader (spec
    2026-09-29-fr-goal-light-path §D, §E; 2026-10-02-opencode-observe-2 §A)."""
    from fr.run.observed import observed_session
    from fr.run.telemetry import parse_timestamp

    try:
        harness = detect_harness(os.environ)
    except HarnessError:
        harness = None
    if harness == "hermes":
        return f"fr has no child-session reader for {harness}, so a phase log is not witnessed"
    view = observed_session(os.environ)
    start = parse_timestamp(opened)
    if view is None or start is None:
        return _why_unobservable("commands") if view is None else "the unit has no opening stamp"
    found = view.child(holder) if holder is not None else view
    if found is None:
        return f"the session {view.session} could not be read"
    if found is False:
        return False
    windows = found.wrote_windows(path, start)
    if windows is None:
        return f"the holder's session {found.session} could not be read"
    return windows


TESTS_REUSE = "reuse"
"""`deliver`'s `tests: reuse` — the most recent phase suite log stands in for a
fresh run while the code tree it covered is unchanged (spec
2026-09-29-fr-goal-light-path §D, R6)."""
_TREE_SEP = ";tree="
REUSED_PREFIX = "reused:"


def _latest_tests_witness(state: RunState) -> tuple[str, str] | None:
    """`(unit key, witness)` of the most recently resolved `done` unit whose
    `tests` evidence carries a code tree (a phase unit's,
    `_verify_phase_tests_log`), or `None`. "Most recently" is the unit's last
    attempt's `returned`; a unit with none sorts first, and a tie goes to the
    later unit in cursor order."""
    best: tuple[str, int, str, str] | None = None
    seq = 0
    for record in state.steps.values():
        for key, unit in (record.units or {}).items():
            seq += 1
            witness = (unit.evidence or {}).get("tests", "")
            if _TREE_SEP not in witness or witness.startswith(REUSED_PREFIX):
                continue
            # Review r2-3: only a unit that is `done` NOW vouches for its tree
            # — a failed one, or one re-dispatched since, does not.
            if (unit.state or record.state) != "done":
                continue
            returned = unit.attempts[-1].returned if unit.attempts else None
            candidate = (returned or "", seq, key, witness)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    return (best[2], best[3]) if best is not None else None


def _reuse_tests_witness(key: str, repo_root: Path, state: RunState) -> str:
    """`reused:<unit>:<witness>` when HEAD's code tree equals the tree of the
    most recently resolved unit carrying a suite log and no code path is
    uncommitted — or exit 2 with the fresh-run instruction."""
    from fr.run.code_tree import code_paths_since_tree, code_tree, dirty_code_paths
    from fr.run.telemetry import UNOBSERVED

    latest = _latest_tests_witness(state)
    if latest is None:
        err_console.print(
            f"[red]{key}: tests: reuse — no phase unit recorded a suite log "
            "(`evidence: {tests: <log>}` on an implement-phase or review-phase record); "
            "run the full suite yourself into a log and name it.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    unit, witness = latest
    recorded = witness.rpartition(_TREE_SEP)[2]
    own_log = _own_log_path(repo_root, witness.rpartition(_TREE_SEP)[0])
    try:
        dirty = [p for p in dirty_code_paths(repo_root) if p != own_log]
        same = code_tree(repo_root) == recorded and not dirty
        changed = None if same else code_paths_since_tree(repo_root, recorded)
        if changed is not None:
            changed = [p for p in changed if p != own_log]
    except GitUnavailableError as e:
        err_console.print(
            f"[red]{key}: tests: reuse — cannot compute the code tree: {escape(str(e))}[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2) from e
    if not same:
        if changed:
            n = len(changed)
            what = f"{n} path{'' if n == 1 else 's'}, e.g. {changed[0]}"
        else:
            what = "its commit is not in HEAD's recent history"
        err_console.print(
            f"[red]{key}: tests: reuse — the code tree changed since {unit} ({what}); "
            "run the full suite yourself into a log and name it.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if "tests" in _unit_evidence(state, unit).get(UNOBSERVED, "").split(","):
        # Review r2-4: a reuse is no better verified than the log it reuses.
        _note_unobserved("tests")
        err_console.print(
            f"[yellow]{key}: {unit}'s suite log was recorded unverified "
            "(evidence: unobserved=tests), so this reuse is unverified too.[/yellow]",
            soft_wrap=True,
        )
    return f"{REUSED_PREFIX}{unit}:{witness}"


def _unit_evidence(state: RunState, key: str) -> dict[str, str]:
    """`key`'s evidence, from whichever step holds that unit (`{}` if none)."""
    for record in state.steps.values():
        unit = (record.units or {}).get(key)
        if unit is not None:
            return dict(unit.evidence or {})
    return {}


def _own_log_path(repo_root: Path, log_witness: str) -> str | None:
    """The repo-relative path of the log `log_witness` (`<shown>@<sha[:12]>`)
    names, when that file is in the worktree with exactly those bytes — so an
    untracked suite log does not read as uncommitted code (review r2-5). A
    same-named file with other bytes is not the log, and stays dirty."""
    import hashlib

    shown, _, digest = log_witness.rpartition("@")
    if not shown or not digest:
        return None
    path = repo_root / shown
    try:
        data = path.read_bytes() if path.is_file() else None
    except OSError:
        return None
    if data is None or hashlib.sha256(data).hexdigest()[:12] != digest:
        return None
    return Path(shown).as_posix()


def _verify_phase_tests_log(
    key: str,
    log: str,
    repo_root: Path,
    *,
    opened: str | None,
    holder: str | None,
    record_tree: bool = True,
) -> str:
    """A phase unit's own suite log (spec 2026-09-29-fr-goal-light-path §D,
    R6) — or exit 2. Returns `<shown>@<sha256[:12]>;tree=<code-tree>`.

    1. **Writer** — `_verify_tests_log`'s rules, read from the HOLDER's
       transcript (`_phase_log_windows`); unreadable records `unobserved=tests`.
    2. **Freshness** — the log is no older than any tracked code path, any
       directory holding one, or the directory a code path was deleted or
       renamed out of since the merge-base (`fr.run.code_tree.newest_code_mtime`).
    3. **Witness** — the code tree of HEAD. Computed here, before the record's
       own commit, and equal to the tree after it: that commit writes only fr's
       artifact trees, which the code tree excludes by definition. HEAD's tree
       is what the suite ran only when nothing is uncommitted, so a dirty code
       path (the log itself aside) is refused (review r2-1).

    `record_tree=False` (a resolve that is not `done`, review r2-3) checks the
    writer only and returns `<shown>@<sha256[:12]>` — a failed phase vouches
    for no tree, so there is no tree to record and nothing to keep fresh.
    """
    from fr.run.code_tree import (
        code_tree,
        default_merge_base,
        dirty_code_paths,
        newest_code_mtime,
    )
    from fr.run.telemetry import parse_timestamp

    path, data = _read_suite_log(key, log, repo_root)
    modified = _dt.datetime.fromtimestamp(path.stat().st_mtime, tz=_dt.UTC)
    windows = _phase_log_windows(path, opened, holder)
    if windows is False:
        err_console.print(
            f"[red]{key}: --evidence tests={log}: this session dispatched no agent "
            f"{holder!r}, so the unit's holder cannot be the one who ran the suite. "
            "Name the agent id the executor's dispatch returned.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    slack = _dt.timedelta(seconds=1)
    if isinstance(windows, list):
        if not any(s - slack <= modified <= e + slack for s, e in windows):
            why = (
                "no command of the unit's holder wrote it (a `>`, `>>` or `tee` naming it)"
                if not windows
                else "its bytes were not written by the holder's command that names it"
            )
            err_console.print(
                f"[red]{key}: --evidence tests={log}: {why} since this unit opened at "
                f"{opened}. Name the log the phase's own full-suite run wrote, or leave "
                "`tests` out of the record.[/red]",
                soft_wrap=True,
            )
            raise typer.Exit(2)
    else:
        opened_at = parse_timestamp(opened)
        if opened_at is not None and modified < opened_at:
            err_console.print(
                f"[red]{key}: --evidence tests={log} predates this unit (opened {opened}) — "
                "it is not a run of this phase's code.[/red]",
                soft_wrap=True,
            )
            raise typer.Exit(2)
        _note_unobserved("tests")
        err_console.print(
            f"[yellow]{key}: could not verify who ran {log} — {windows}; recorded "
            "unverified (evidence: unobserved=tests).[/yellow]",
            soft_wrap=True,
        )
    if not record_tree:
        return _log_witness(path, data, repo_root)
    try:
        own = _own_log_path(repo_root, _log_witness(path, data, repo_root))
        dirty = [p for p in dirty_code_paths(repo_root) if p != own]
        newest = newest_code_mtime(repo_root, default_merge_base(repo_root), ignore=[path])
        tree = code_tree(repo_root)
    except GitUnavailableError as e:
        err_console.print(
            f"[red]{key}: --evidence tests={log}: cannot compute the code tree it "
            f"covers — {escape(str(e))}[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2) from e
    if dirty:
        n = len(dirty)
        err_console.print(
            f"[red]{key}: --evidence tests={log}: {n} code path{'' if n == 1 else 's'} "
            f"uncommitted (e.g. {dirty[0]}) — the witness is HEAD's tree, which is not "
            "what the suite ran. Commit your code before recording the suite log, then "
            "run the full suite again and name the new log.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if newest is not None and newest[0] > path.stat().st_mtime:
        err_console.print(
            f"[red]{key}: --evidence tests={log} is stale — {newest[1]} changed after "
            "the log was written, so the suite did not run the code being recorded. "
            "Run the full suite again and name the new log.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    return f"{_log_witness(path, data, repo_root)}{_TREE_SEP}{tree}"


def _verify_review_entry(
    key: str,
    entry_id: str,
    *,
    slug: str,
    entries: list[JournalEntry],
    target: _EvidenceTarget,
    since: str | None,
) -> None:
    """`entry_id` is a `kind=review` entry for `target` — or `typer.Exit(2)`.

    A phase: the entry carries `phase=N` (`reviews_phase`, the one rule). The
    spec: the entry was created at or after the step opened (`since`) — a
    review recorded before spec-review began is not a review OF it.
    """
    from fr.run.telemetry import parse_timestamp

    scope = target.scope
    found = next((e for e in entries if e.id == entry_id), None)
    phase_flag = f"--phase {target.phase} " if target.phase is not None else ""
    if found is None:
        err_console.print(
            f"[red]{key}: --evidence review={entry_id} names no entry in the {scope} "
            f"journal for {slug}[/red]",
            soft_wrap=True,
        )
        err_console.print(
            f"  fr journal add --scope {scope} --slug {slug} --kind review {phase_flag}"
            f'--title "{target.subject} review" '
            "--body \"<findings raised, by id; or 'no findings'>\"",
            markup=False,
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if target.phase is not None:
        if not reviews_phase(found, target.phase):
            err_console.print(
                f"[red]{key}: --evidence review={entry_id} is a {found.kind!r} entry"
                + (f" for phase {found.phase}" if found.phase is not None else " with no phase")
                + f" — evidence must be a `kind=review` entry carrying `phase={target.phase}`, "
                "the same rule `fr journal check --require-reviews` applies[/red]",
                soft_wrap=True,
            )
            raise typer.Exit(2)
        return
    if found.kind != "review":
        err_console.print(
            f"[red]{key}: --evidence review={entry_id} is a {found.kind!r} entry — evidence "
            "must be a `kind=review` spec-journal entry[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    created = parse_timestamp(journal_stamp_as_utc(found.created))
    opened = parse_timestamp(since) if since else None
    if created is None or opened is None or created < opened.replace(microsecond=0):
        err_console.print(
            f"[red]{key}: --evidence review={entry_id} was created {found.created}, "
            f"before this step opened at {since} — a review recorded before spec-review "
            "began is not a review of it. Record the reviewer's findings, then a new "
            "`kind=review` entry.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)


def _target_finding_states(entries: list[JournalEntry], target: _EvidenceTarget) -> dict[str, str]:
    """Every finding filed against `target` -> its effective state. A phase:
    `phase_finding_states`. The spec: every finding in its journal (a spec
    journal has no phases), through the SAME fold `fr journal check` reads."""
    if target.phase is not None:
        return dict(phase_finding_states(entries, target.phase))
    states = effective_finding_states(entries)
    return {
        e.id: states[e.id]
        for e in entries
        if e.kind == "finding" and e.resolves is None and e.id in states
    }


def _closed_findings_witness(
    key: str, slug: str, entries: list[JournalEntry], target: _EvidenceTarget
) -> str:
    """The `findings` evidence for `target` — or `typer.Exit(2)` while any
    finding filed against it is still open.

    This is `superpowers:receiving-code-review`'s OUTCOME, which is the only
    part of "was the review received properly" fr can observe: every finding
    the review raised ends `fixed` or `refuted`, never dropped. It is the check
    `journal-check` already made once, before `deliver` — moved to the moment a
    finding is cheapest to act on, while the phase that caused it is still the
    one in hand.

    The value is the WITNESS, not a token: the ids fr saw closed, in the order
    they were raised, or `none`. A finding that genuinely belongs to a later
    phase is filed against THAT phase, and gates that phase's review instead.
    """
    subject, scope = target.subject, target.scope
    states = _target_finding_states(entries, target)
    still_open = [fid for fid, st in states.items() if st == "open"]
    # The operator guard `fr journal check` applies (spec 2026-09-24 §A), read
    # from the same fold: an out-of-scope finding fixed without the operator.
    unauthorized = [fid for fid in unauthorized_fixes(entries) if fid in states]
    if unauthorized:
        err_console.print(
            f"[red]{key}: refused — {len(unauthorized)} unauthorized fix(es) against "
            f"{subject}: {', '.join(unauthorized)} — moved from out-of-scope to fixed without "
            "`answered_by=operator`. Ask the operator, then:[/red]",
            soft_wrap=True,
        )
        for fid in unauthorized:
            err_console.print(
                f"  fr journal resolve --scope {scope} --slug {slug} --id {fid} --state fixed "
                '--answered-by operator --note "<what the operator decided>"',
                markup=False,
                soft_wrap=True,
            )
        raise typer.Exit(2)
    if not still_open:
        return findings_witness(states)
    err_console.print(
        f"[red]{key}: refused — {len(still_open)} finding(s) filed against {subject} "
        f"are still open: {', '.join(still_open)}.[/red]",
        soft_wrap=True,
    )
    err_console.print(
        "  A review is received, not just requested "
        "(`superpowers:receiving-code-review`): verify each finding, then fix it with "
        "a test or refute it with reasoning — never drop it. Close each one:",
        soft_wrap=True,
    )
    for fid in still_open:
        err_console.print(
            f"  fr journal resolve --scope {scope} --slug {slug} --id {fid} --state fixed "
            '--note "<what changed, and the test that pins it>"',
            markup=False,
            soft_wrap=True,
        )
    later = (
        f" One that belongs to a later phase is filed against that phase, not {subject}."
        if target.phase is not None
        else ""
    )
    err_console.print(
        "  (or `--state refuted` with the reasoning, when the finding is wrong; "
        "`--state out-of-scope` when this change did not cause it)."
        f"{later} `--state failed` needs no evidence.",
        soft_wrap=True,
    )
    raise typer.Exit(2)


def _evidence_owed(manifest: WorkflowManifest) -> dict[str, tuple[Step, ...]]:
    """`{top-level step id: (every step under it that declares evidence,)}`.

    A group's members are the realistic case (`implement`'s `review-phase`);
    a flat step declaring evidence is included so a report can never go quiet
    about a shape that asks for something it never got.
    """
    owed: dict[str, tuple[Step, ...]] = {}
    for step in manifest.steps:
        candidates = step.steps or (step,)
        declaring = tuple(s for s in candidates if s.evidence)
        if declaring:
            owed[step.id] = declaring
    return owed


def _unevidenced_units(repo_root: Path, state: RunState) -> dict[tuple[str, str], tuple[str, ...]]:
    """`{(step id, unit key): obligations it lacks}` for every unit that is
    `done` under a step which declares evidence it does not carry — spec
    §4.E's visible debt. Per OBLIGATION, because a shape can grow one: a unit
    resolved with `review=` before `findings` existed owes `findings` and
    nothing else, and saying "unevidenced" of it would be as wrong as silence.

    **Never a failure, and never an exit code.** These are reviews resolved
    before the gate existed; the migration cannot invent evidence for them and
    does not try. An obligation cannot be enforced backwards in time — doing
    so would fail every in-flight run on the day the plugin updates.

    Fail-SOFT on a manifest it cannot resolve (drifted, renamed, deleted):
    this is a report line, and a report that turns `fr run check` into an
    error is a worse outcome than a report that is silent. The exit code of
    every caller is unchanged either way.
    """
    try:
        # Schema-checked only: a step-list drift does not make "which units owe
        # evidence" unanswerable, and the caller (`status`/`check`) warns about
        # the drift itself (spec 2026-10-05-run-upgrade-midflight §B).
        manifest = _resolve_manifest_checked_schema(repo_root, state)
    except (RunStateError, WorkflowError, AdoptError, OSError):
        return {}
    out: dict[tuple[str, str], tuple[str, ...]] = {}
    for step_id, declaring in _evidence_owed(manifest).items():
        record = state.steps.get(step_id)
        if record is None:
            continue
        for member in declaring:
            suffix = f"step/{member.id}" if member.id == step_id else f"/{member.id}"
            for key in units.unit_keys(record):
                matches = key == suffix if member.id == step_id else key.endswith(suffix)
                unit_state = record.state if member.id == step_id else units.unit_state(record, key)
                if not matches or unit_state != "done":
                    continue
                held = units.evidence_of(record, key)
                if held.get("reviewer") == HISTORICAL_REVIEWER:
                    # R9: reviewed before this cursor existed — reported as
                    # such by the caller, never as debt.
                    continue
                lacking = tuple(name for name in member.evidence if name not in held)
                if lacking:
                    out[(step_id, key)] = lacking
    return out


def _debt_phrase(record: StepRecord, key: str, lacking: tuple[str, ...]) -> str:
    """How one unit's evidence debt reads — ONE spelling for `status` and
    `check`. A unit with no evidence at all keeps the sentence it always had."""
    if not units.evidence_of(record, key):
        return "unevidenced (predates the evidence gate)"
    return f"unevidenced: {', '.join(lacking)} (predates that obligation)"


def _template_context(state: RunState) -> dict[str, str]:
    ctx = {"run.id": state.run, "run.branch": state.branch}
    for record in state.steps.values():
        if record.emitted:
            for name, value in record.emitted.items():
                ctx[f"artifacts.{name}"] = value
    return ctx


def _render_template(text: str, context: Mapping[str, str], *, quote: bool) -> str:
    """Substitute `{{ ... }}` from `context`.

    `quote=True` shell-quotes every substituted value and is mandatory for
    anything handed to a shell (review fix r2-f3). The manifest itself is
    operator-authored, but `{{ artifacts.* }}` values are not: they arrive via
    `fr run resolve --emitted name=path`, i.e. from whatever a dispatched
    agent reports. The shipped `plan-review` step is `fr plan self-review
    {{ artifacts.plan }}`, so an emitted path containing `;` or backticks was
    a command-injection seam straight through `shell=True`. Quoting at the
    substitution boundary keeps the manifest's own shell syntax (pipes,
    redirects, `&&`) working while making an interpolated value inert data.
    """

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in context:
            raise RunStateError(f"unresolved template variable: {{{{ {key} }}}}")
        value = context[key]
        return shlex.quote(value) if quote else value

    return _TEMPLATE_RE.sub(repl, text)


def _build_brief(step: Step, state: RunState) -> dict[str, Any]:
    """The dispatch brief for a `kind: agent` step — everything the harness
    needs to actually run it, and nothing fr itself executes.

    Phase 11 wires `fr-goal` onto `fr run`; it must produce/consume this
    same shape, so its keys are deliberately exhaustive of `Step`'s
    agent-relevant fields rather than a subset convenient for today's tests
    — pinned by deriving the expected key set from `Step.model_fields` in
    `test_run_cli.py`, so a future `Step` field cannot be silently omitted.

    Exhaustive means every `Step` field except two: `id` (emitted as `step`)
    and `run` (the one cli-only field — `advance` executes it; it is never
    dispatched). `kind` is carried even though a brief is only ever printed
    for an `agent` step, so the brief stays self-describing and the
    exclusion list stays at exactly the two fields that have a reason.
    `for_each` and `gate` were missing until review fix r2-f4, which made
    the brief unable to express `implement`'s whole purpose (one executor
    per phase) or the fact that a step is gated at all. `steps` carries the
    member ids of a grouped `for_each` (empty for a flat step) so the
    harness can see the per-phase loop without re-reading the manifest.
    """
    return {
        "run": state.run,
        "workflow": state.workflow,
        "step": step.id,
        "kind": step.kind,
        "skill": _brief_skill(step),
        "agent": step.agent,
        "needs": list(step.needs),
        "emits": list(step.emits),
        "gate": step.gate,
        "tier": step.tier,
        "evidence": _caller_evidence(step),
        "for_each": step.for_each,
        "steps": [m.model_dump(exclude_none=True) for m in step.steps],
        # spec 2026-09-25 §5.C.3: the pre-filled step record — for a flat
        # step; a fan-out group's record is per member, in the member brief.
        "record": None if step.steps else _record_brief(state, step),
        "unbound_tiers": _unbound_tiers(resolve_repo_root()),
    }


def _unbound_tiers(repo_root: Path) -> list[str] | None:
    """The phase tiers with no model bound for the harness `advance` runs
    under, in `PHASE_TIERS` order — `None` when no harness is detected (or
    `FR_HARNESS` is invalid, which the gate path reports itself): an empty
    list would read as "every tier is bound". A malformed models.yaml raises,
    as it already did from `_orchestrator_model_notice` at the top of every
    `advance` — a broken config is reported, never read as "unbound".

    gh#538: fr-goal's model-per-tier question was gated on a `fr models
    resolve` the orchestrator had to REMEMBER to run, and on a real OpenCode
    run with nothing bound it never ran it. fr answers it in one lookup, so the
    brief states it and the question is triggered by data, not recall."""
    try:
        harness = detect_harness(os.environ)
    except HarnessError:
        return None
    if harness is None:
        return None
    return [t for t in PHASE_TIERS if _resolved_model(repo_root, harness, t) is None]


def _caller_evidence(step: Step) -> list[str]:
    """The evidence a brief lists: what the caller passes. A derived name is
    refused from the caller ("not yours to pass"), so listing it sent agents
    straight into that refusal (gh#653)."""
    return [n for n in step.evidence if n not in DERIVED_EVIDENCE]


def _record_brief(
    state: RunState, step: Step, group: Step | None = None, item: str | None = None
) -> dict[str, Any] | None:
    """The brief's `record` key — never the reason a brief fails to print."""
    from fr.record.template import record_brief

    try:
        return record_brief(resolve_repo_root(), state, step, group, item).as_dict()
    except Exception:  # noqa: BLE001 — a brief without a template still dispatches
        return None


def _brief_skill(step: Step) -> str | list[str] | None:
    """`skill` as the brief carries it: exactly what the manifest wrote. One
    skill is a string — byte-identical to every brief before the list form —
    and several are a JSON list in the manifest's order, which IS the order to
    load them in."""
    return step.skill if step.skill is None or isinstance(step.skill, str) else list(step.skill)


def _effective_tier(step: Step, group: Step | None = None) -> str | None:
    """The tier a unit actually dispatches under: its own `tier:` when set,
    else its group's — `None` when neither has one. `_build_member_brief`
    and `_open_dispatch`'s `_advance_group` call site both read this ONE
    helper (P2.T1.S3) rather than each re-deriving the fallback, which is
    how the two came to duplicate it in the first place. `group=None` for a
    flat step, which has none to fall back to."""
    if step.tier is not None:
        return step.tier
    return group.tier if group is not None else None


PHASE_TIER_SENTINEL = "from_phase"
"""`Step.tier`'s one non-tier value — the shipped `fr-goal` shape's marker for
"this unit's tier is whatever the plan's phase header says".

`Step.tier` is a free `str`, not `PhaseHeader.tier`'s closed
mechanical/standard/hard Literal, precisely so a shape can say this. The
*brief* passes the sentinel through verbatim, because there it is an
instruction to the harness: look the phase up. A dispatch RECORD cannot do
that — it stores what was actually sent — so `_advance_group` resolves it
first (finding f4). Handing the sentinel straight to `fr models resolve` can
only ever miss, which is how every real fr-goal dispatch came to record
`model: null`."""


def _dispatch_tier(repo_root: Path, state: RunState, tier: str | None, phase_n: int) -> str | None:
    """`tier` with `PHASE_TIER_SENTINEL` replaced by phase `phase_n`'s own
    tier — what a dispatch RECORD needs, as opposed to what the brief says.

    An unresolvable sentinel becomes `None`, which `_resolved_model` then
    records as an absent model: the spec §4.A rule that nothing is ever
    guessed applies to the sentinel exactly as it does to an unbound tier.

    Resolution itself is `_phase_tier`'s, gh#506's function for the same
    job — that PR landed the sentinel fix for the dispatch BRIEF while this
    one landed it for the dispatch RECORD, and one reader of the plan's
    phase header is enough for both."""
    if tier != PHASE_TIER_SENTINEL:
        return tier
    return _phase_tier(repo_root, state, phase_n)


def _resolved_model(repo_root: Path, harness: str | None, tier: str | None) -> str | None:
    """The model bound to `tier` for `harness`, via `fr.models.resolve` —
    repo config overriding user config, the same rule `fr models resolve`
    itself uses. `None` when there is no tier, no harness, or no binding for
    the pair: an unresolved tier leaves `model` absent rather than guessed
    (spec §4.A / P2.T1.S2).

    `harness` is PASSED IN rather than detected here (finding f8). A tier
    resolves to a model only *for a harness*, so the two belong to the same
    record — detecting it privately meant `_open_dispatch` could store a
    model without naming the harness that chose it, which an orchestrator-run
    step (never claimed) would never get filled in afterwards.

    `PHASE_TIER_SENTINEL` is refused here as well as resolved upstream in
    `_dispatch_tier`. Callers with no phase in hand — a flat `kind: agent`
    step — have nothing to resolve it against, and without this guard a
    models.yaml that happened to carry a `from_phase:` key would bind it,
    turning a sentinel into a model name by coincidence."""
    if tier is None or tier == PHASE_TIER_SENTINEL or harness is None:
        return None
    from fr.models import REPO_MODELS_REL, default_models_path, load_models
    from fr.models import resolve as resolve_model

    repo_cfg = load_models(repo_root / REPO_MODELS_REL)
    user_cfg = load_models(default_models_path())
    return resolve_model(harness, tier, repo_cfg=repo_cfg, user_cfg=user_cfg)


ORCHESTRATOR_ROLE = "orchestrator"
"""The models.yaml key binding the ORCHESTRATOR's model, beside the phase tiers
(`claude-code: {orchestrator: claude-opus-5, standard: …}`). A role, not a
tier: nothing dispatches to it, so it is only ever compared, never resolved
into a dispatch (2026-09-21 debug journal C3)."""


def _orchestrator_model_notice(repo_root: Path) -> str | None:
    """A loud line when the orchestrator runs on a model other than the one
    bound to `orchestrator` for this harness — else `None`.

    Record + warn, NEVER block (operator decision, debug journal C3): the
    session model is the operator's `/model` choice and outranks the binding.
    Silent with no binding (no contract was asked for) and silent when the
    running model cannot be observed — an unobservable model is not a mismatch,
    and saying so on every harness without a transcript reader would be noise.
    """
    from fr.run.telemetry import orchestrator_model

    try:
        harness = detect_harness(os.environ)
    except HarnessError:
        # A bad FR_HARNESS is `advance`'s gate path's error to raise (exit 2,
        # naming the variable); a notice must never pre-empt it.
        return None
    bound = _resolved_model(repo_root, harness, ORCHESTRATOR_ROLE)
    if bound is None:
        return None
    running = orchestrator_model(os.environ)
    if running is None or running == bound:
        return None
    return (
        f"warning: this run's orchestrator is running on {running}, but models.yaml "
        f"binds the {harness} orchestrator to {bound}. Every non-dispatched step "
        f"(brainstorm, reviews, deliver) runs on the orchestrator's model. Switch "
        f"with `/model` if that was not intended; fr records the model it observes."
    )


def _open_dispatch(
    state: RunState,
    step_id: str,
    key: str,
    *,
    agent_type: str | None,
    tier: str | None,
    repo_root: Path,
    at: str | None = None,
) -> RunState:
    """Append a new attempt opening `key`'s hold under `step_id`.

    `at` is the attempt's `dispatched`, taken by the grouped caller BEFORE
    the brief is built. Absent, it is stamped here — right for the flat
    `kind: agent` branch, which saves before it prints the brief.

    Spec §4.B.1: called exactly when `advance` moves a unit to `running` —
    from BOTH `_advance_group`'s write-claim and the flat `kind: agent`
    branch, and only on the actual transition (both call sites already guard
    on that). Never called from `_gate_pending`: a gated step is marked
    `blocked`, not `running`, so nothing was dispatched and there is nothing
    to hold.
    """
    from fr.run.telemetry import SESSION_ID_ENVS, orchestrator_model, run_session

    record = state.steps[step_id]
    # Detected ONCE and both recorded and used (finding f8): the harness is
    # what turns a tier into a model, so a record that carries the model
    # without naming it is not self-describing — and an orchestrator-run
    # step, which nothing ever claims, would never have it filled in later.
    harness = detect_harness(os.environ)
    new_record = units.with_attempt_appended(
        record,
        key,
        UnitAttempt(
            dispatched=at or _now(),
            agent_type=agent_type,
            harness=harness,
            # A tier is resolved only for work fr DISPATCHED to a tier. A tier
            # binding answers "which model does a dispatched agent of this tier
            # get"; an attempt with no `agent_type` is the orchestrator running
            # the unit in its own session. Such a member still inherits its
            # group's tier, so resolving it here wrote a model for work that
            # tier never touched — seven false `claude-opus-5` reviews in this
            # repo's own archive. That lesson stands. What changed (2026-09-21
            # debug journal C3) is that the orchestrator's model is no longer
            # invisible: its own transcript names it, so fr records what it
            # OBSERVES there — never a resolution — and `None` when it cannot.
            model=(
                _resolved_model(repo_root, harness, tier)
                if agent_type is not None
                else orchestrator_model(os.environ)
            ),
            # Derived from fr's OWN environment, exactly like `harness` — the
            # agent never reports it (§4.D.1). It is what lets a later session
            # read the RIGHT transcript directory, and what stops a window
            # from being borrowed across sessions. `None` for a harness with
            # no session concept, which reads as "not observable from here"
            # and never as zero. No hostname beside it: a missing session
            # directory already says "elsewhere".
            #
            # `current_session` reads only the key the detected harness OWNS
            # (gh#537): an OpenCode started from a Claude Code shell inherits
            # Claude Code's key, which names a session that never held this
            # unit; OpenCode's own arrives through the super-fr plugin's
            # `shell.env` export (spec 2026-10-02-opencode-observe-2 §B).
            # `run_session` walks a child's id up to the run's. An UNDETECTED
            # harness owns no key (review p1-r1): there `current_session`
            # falls back to Claude Code's, which in gh#537's mixed shell is
            # the inherited, stale one — record nothing, as main did.
            session=(run_session(os.environ) if harness in SESSION_ID_ENVS else None),
        ),
    )
    return _with_step(state, step_id, new_record)


def _dispatch_needs_open(record: StepRecord, key: str) -> bool:
    """Should `advance` append a fresh `Attempt` for `key`?

    True when nothing has been recorded for it yet, or its last attempt is
    CLOSED (`returned` is not `None`) — an abandoned (`fr run claim
    --abandoned`) or failed-and-retried unit is not currently held, so
    re-dispatching it opens a NEW hold rather than silently leaving the old,
    closed one as the only record. False while the last attempt is still
    OPEN — the unit is currently HELD, which `advance` refuses to dispatch
    over (`_hold_on`, spec §4.C / gh-499) unless `--redispatch` says so.

    This is the ONE notion of "is the last record open?" in the module:
    `_held_record` is its read half, and `advance`'s refusal (`_hold_on`),
    `--redispatch`'s abandon and `resolve`'s close all go through the pair
    rather than each re-deriving it.
    """
    return _held_record(record, key) is None


def _held_record(record: StepRecord, key: str) -> UnitAttempt | None:
    """`key`'s OPEN attempt, or `None` when the unit is free.

    The read half of `_dispatch_needs_open` — same predicate, but handing
    back the holder so a caller can name it. Delegates to
    `fr.run.units.open_attempt`, which is where "open = the last attempt,
    unreturned" is decided; this module keeps the name because every comment
    and refusal in it is written in terms of the pair."""
    return units.open_attempt(record, key)


def _close_dispatch(record: StepRecord, key: str, outcome: DispatchOutcome) -> StepRecord:
    """Close `key`'s open dispatch: `returned` = now, `outcome` = `outcome`.

    `Attempt` enforces that the two are one fact, so they are written
    in one `model_copy` and never separately. Callers must have established
    that the unit IS held (`_held_record` / `_open_dispatch_record`); this
    helper does not re-derive it, so there is still exactly one place that
    decides what "open" means."""
    return units.with_last_attempt_replaced(
        record,
        key,
        units.attempts(record, key)[-1].model_copy(update={"returned": _now(), "outcome": outcome}),
    )


def _claimed_identity(
    open_record: UnitAttempt,
    key: str,
    *,
    agent: str,
    harness: str | None,
    model: str | None,
) -> UnitAttempt:
    """`open_record` carrying the orchestrator's reported identity, or refuse.

    Shared by `fr run claim` (the eager report) and `fr run resolve`'s late
    fallback (decision d2), so a *second* agent id can never be attached to a
    dispatch by taking the other route. Re-reporting the SAME id is
    idempotent and may refresh `harness`/`model`; a DIFFERENT one is refused
    naming both, because two ids on one hold is the two-writers hazard this
    whole feature exists to make visible."""
    if open_record.agent is not None and open_record.agent != agent:
        err_console.print(
            f"[red]{key}: already claimed by {open_record.agent!r} — refusing to "
            f"attribute it to {agent!r} as well. The worktree has exactly one "
            "writer; close the first claim (`fr run resolve ... --state "
            "done|failed`, or `fr run claim ... --abandoned`) before naming a "
            "second.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    return open_record.model_copy(
        update={
            "agent": agent,
            "harness": harness if harness is not None else open_record.harness,
            "model": model if model is not None else open_record.model,
        }
    )


def _close_on_resolve(
    state: RunState,
    owner_id: str,
    key: str,
    outcome: DispatchOutcome,
    *,
    agent: str | None,
    harness: str | None,
    model: str | None,
) -> RunState:
    """`resolve`'s half of the dispatch pair: close `key`'s open record with
    `outcome`, optionally attaching a late identity first (spec §4.C).

    **Silent when there is nothing open** — and that is the requirement, not
    a shortcut. A run `fr run adopt`ed from a plan on disk has no dispatch
    history at all, and a `gate: operator` step is marked `blocked` without
    ever being dispatched; neither may start failing to resolve because this
    feature landed. Nothing is invented for them either: an absent record
    stays absent rather than being back-filled with a dispatch fr never made.

    A record that is already CLOSED (`claim --abandoned`) is likewise left
    exactly as it is — `abandoned` is what happened to that attempt, and
    overwriting it with this resolve's outcome would erase the one fact the
    operator recorded by hand.
    """
    record = state.steps[owner_id]
    open_record = _held_record(record, key)
    if open_record is None:
        return state
    if agent is not None:
        open_record = _claimed_identity(open_record, key, agent=agent, harness=harness, model=model)
    elif harness is not None or model is not None:
        open_record = open_record.model_copy(
            update={
                "harness": harness if harness is not None else open_record.harness,
                "model": model if model is not None else open_record.model,
            }
        )
    open_record = _observed_model(open_record, key)
    record = units.with_last_attempt_replaced(record, key, open_record)
    return _with_step(state, owner_id, _close_dispatch(record, key, outcome))


def _observed_model(attempt: UnitAttempt, key: str) -> UnitAttempt:
    """`attempt` carrying the model its subagent's transcript says RAN (gh#637).

    `advance` wrote the tier binding for a dispatched attempt — what SHOULD
    run. Resolve is the first point that knows the agent id, so the transcript
    can now say what DID: a dispatch sent without a model argument runs on
    the orchestrator's model, and the binding then named a model that never
    ran (run 2026-09-26-fix-624: haiku/sonnet recorded, opus throughout).
    Observed beats bound and beats reported, as `orchestrator_model` already
    does for the orchestrator's own units; a difference is said aloud, never
    blocked. Unobservable leaves the attempt as it was — an absence is not
    a mismatch."""
    from fr.run.telemetry import subagent_model

    if attempt.agent is None or attempt.agent_type is None:
        return attempt
    observed = subagent_model(os.environ, attempt.session, attempt.agent)
    if observed is None or observed == attempt.model:
        return attempt
    if attempt.model is not None and _model_family(observed) != _model_family(attempt.model):
        err_console.print(
            f"[yellow]{key}: agent {attempt.agent} ran on {observed}, but the cursor "
            f"recorded {attempt.model}. fr records what ran. If the tier's binding was "
            "meant, pass that model in the dispatch.[/yellow]",
            soft_wrap=True,
        )
    return attempt.model_copy(update={"model": observed})


_MODEL_DATE = re.compile(r"-\d{8}$")


def _model_family(model: str) -> str:
    """`model` without a context-window suffix or a trailing snapshot date, so
    a binding's `claude-haiku-4-5` and a transcript's
    `claude-haiku-4-5-20251001` compare equal: the dispatch honoured the
    binding, and a warning would be noise (review of gh#637)."""
    from fr.usage.readers.claude_code import normalize_model

    return _MODEL_DATE.sub("", normalize_model(model))


def _build_member_brief(
    member: Step,
    group: Step,
    item: str,
    state: RunState,
    resolved_tier: str | None,
    harness: str | None = None,
) -> dict[str, Any]:
    """The dispatch brief for one `(phase, member)` unit of a grouped step.

    Same keys as the step brief (so a harness parses one shape) plus `group`
    (the fan-out step's id), `item` (the `phase/<n>` unit) and
    `resolved_tier`. `tier` and `for_each` fall back to the group's when the
    member leaves them unset — the common case, where the group declares the
    dispatch policy once.

    `resolved_tier` is member-only (D5): `tier` keeps the manifest's literal
    meaning — for the shipped `fr-goal` shape, the sentinel `"from_phase"` —
    so `resolved_tier` carries what that sentinel actually resolves to for
    THIS item: the tier declared on the named phase's header, or `None` when
    the phase declares none (the dispatch-time observable form of phase 2's
    untiered-plan warning). It has no analogue on the group/flat brief
    (`_build_brief`, left untouched): a group spans every phase, so there is
    no single tier to resolve there, and a confidently-wrong value would be
    worse than an absent one.

    `long_commands` (gh#582) is the long-command rule for `harness`, the
    one `fr.harness.long_commands` resolves. It rides every member brief
    because the executor reads its task prompt when it acts, and the same
    rule in its agent file alone did not stop OpenCode killing a full suite
    at 120 s. fr-goal §5 relays it verbatim.
    """
    return {
        "run": state.run,
        "workflow": state.workflow,
        "step": member.id,
        "group": group.id,
        "long_commands": long_command_rule(harness),
        "item": item,
        "kind": member.kind,
        "skill": _brief_skill(member),
        "agent": member.agent,
        "needs": list(member.needs),
        "emits": list(member.emits),
        "gate": member.gate,
        "tier": _effective_tier(member, group),
        # The member's OWN, never the group's: an obligation is a property of
        # the step that carries it, and inheriting it would make every member
        # of the loop owe the review member's evidence.
        "evidence": _caller_evidence(member),
        "resolved_tier": resolved_tier,
        "for_each": group.for_each,
        "steps": [],
        "record": _record_brief(state, member, group, item),
        **_review_findings_brief(member, item),
    }


def _review_findings_brief(member: Step, item: str) -> dict[str, str]:
    """`review_findings` for a phase review unit whose reviewer's return fr
    checks at resolve (spec 2026-10-02-opencode-observe-2 §E, R7) — every
    `review-phase` of the shipped shapes — else nothing. fr-goal §6 puts its
    text into the reviewer's prompt verbatim."""
    from fr.run.review_return import review_findings_rule

    if not {"findings", "reviewer"} <= set(member.evidence):
        return {}
    phase = _item_phase(item)
    return {} if phase is None else {"review_findings": review_findings_rule(phase)}


def _resolve_hint(run_id: str, member_id: str, item: str | None, state: str = "done") -> str:
    """The exact `fr run resolve` command that records one grouped unit's
    outcome — the two-flag form `--step <member> --item <head>` that
    `_split_member_id` teaches when someone reaches for the composite.

    One builder because two surfaces print it for the same act: `advance`
    pre-empts the #501 error beside every dispatch brief, and (Phase 2) the
    ALREADY RUNNING refusal names the command that clears it. Spelled
    separately they would drift, and an operator who was shown two different
    commands for one outcome has no way to tell which is current.

    **`--state` is a CONCRETE value, never the alternation `done|failed`**
    (review `r1-f1`). This string is printed under "resolve with:" and is
    meant to be pasted. In every POSIX shell `|` is a pipe, so pasting
    `--state done|failed` RUNS the resolve with `--state done` and then fails
    with `command not found: failed` — exit 127 over a run whose state has
    already changed. A line that reports failure while having done the thing
    is the precise defect class this whole PR exists to remove, and the
    existing operator-gate hint (`--state done`) already set the precedent.
    A caller that needs to mention the other outcome says so in prose beside
    the command, outside the pasteable span.

    `item` is None for a TOP-LEVEL step, which has no `--item` to address —
    the flag is simply omitted. One builder rather than two spellings for the
    same act: the ALREADY RUNNING refusal (§3.A) prints this for both shapes,
    and a second inline `f"fr run resolve ..."` is exactly how the two would
    drift apart.
    """
    scope = f" --item {item}" if item is not None else ""
    return f"fr run resolve {run_id} --step {member_id}{scope} --state {state}"


def _dispatched_from_another_session(attempt: UnitAttempt | None) -> bool:
    """Was `attempt` opened by a session that is NOT this one? (spec §4.D.1)

    A PROOF, never a default. An attempt with no recorded `session` — every
    one written before the field existed, and every harness with no session
    concept — is not claimed to be elsewhere, because not knowing where it
    came from is not the same as knowing it came from somewhere else.
    """
    from fr.run.telemetry import dispatched_from_this_session

    if attempt is None or attempt.session is None:
        return False
    return not dispatched_from_this_session(os.environ, attempt.session)


def _already_running_refusal(
    step_id: str,
    subject: str,
    at: str | None,
    run_id: str,
    member_id: str,
    item: str | None,
    held: UnitAttempt | None = None,
) -> str:
    """The #499 refusal, in one renderer for both call sites (spec §3.A).

    `advance_cmd`'s top-level `agent` branch and `_advance_group`'s grouped
    member differ only in whether the outstanding unit has an `--item`, so
    they differ only in this function's last argument. Spelled separately,
    the operator would eventually be shown two different texts for one
    situation and have no way to tell which was current.

    Both ways forward are named because both are legitimate: waiting is
    almost always right, and `--redispatch` is the deliberate escape for a
    genuinely lost agent. Neither pasteable command carries a shell
    metacharacter (review `r1-f1`) — the `--state failed` alternative is
    prose OUTSIDE the command, not an alternation inside it.
    """
    # A top-level step IS its own outstanding unit, so naming it twice
    # ("plan: plan is ALREADY RUNNING") reads as a bug in the message. The
    # group prefix exists to say WHICH group the unit belongs to; when there
    # is no group there is nothing to prefix.
    named = subject if subject == step_id else f"{step_id}: {subject}"
    # HELD names the agent; RUNNING only names the clock. gh#503 and gh#519
    # each built this refusal, one from the dispatch record and one from the
    # `items` map, and the record is strictly the better witness: it knows WHO
    # is holding the unit, not merely that something is. It is still optional,
    # because a cursor adopted from disk, or written before the record existed,
    # has no holder to name — and "ALREADY RUNNING (dispatched <ts>)" is the
    # honest sentence in that case rather than a fabricated identity.
    if held is not None:
        who = _dispatch_holder_label(held)
        suffix = _dispatch_descriptor_suffix(held, with_agent_type=True)
        head = f"[red]{named} is ALREADY HELD by {who}{suffix} "
        head += f"(dispatched {held.dispatched}) — not yet returned.[/red]\n"
    else:
        head = f"[red]{named} is ALREADY RUNNING (dispatched {at}).[/red]\n"
    # §4.D.1: every other refusal fr prints means "someone is working". This
    # one may mean "that agent died with its host" — the cursor travelled with
    # the branch and nothing else did — and without saying so the operator
    # waits forever on a holder nothing here can observe. The escape is named
    # below already; this only says why to reach for it.
    if _dispatched_from_another_session(held):
        head += (
            "  Dispatched from ANOTHER session: this one cannot see whether that agent is "
            "alive, and its cost is not observable from here. If it died with its host "
            "(a run picked up on another machine), close it with the `lost agent` line "
            "below.\n"
        )
    return (
        head
        + "  Waiting on that agent — do NOT dispatch again.\n"
        + f"  resolve it:      {_resolve_hint(run_id, member_id, item)}"
        "   (or --state failed)\n"
        f"  lost agent:      fr run claim {run_id} --step {member_id}"
        + (f" --item {item}" if item else "")
        + " --abandoned\n"
        + f"  re-brief anyway: fr run advance {run_id} --redispatch"
    )


def _nothing_running_refusal(subject: str, detail: str, run_id: str) -> str:
    """`--redispatch` with nothing outstanding (spec §3.A).

    It exits 2 rather than quietly degrading into an ordinary `advance`: the
    operator reaching for the flag believes an agent is running, and if none
    is, the mental model is wrong and saying so is the whole point of §3.A.
    `fr-goal`'s loop never passes the flag, so this strictness costs the
    normal path nothing.

    Two call sites, one renderer, for the same reason as
    `_already_running_refusal`: `advance_cmd` catches the step that is not
    running at all (including every `cli` step, which fr executes inline and
    so is never `running`), `_advance_group` catches the group that is
    running with every unit already resolved. `detail` is the only part that
    differs.
    """
    return (
        f"[red]{subject}: --redispatch, but nothing is running{detail}.[/red]\n"
        "  --redispatch re-briefs a unit already dispatched; it never starts one.\n"
        f"  advance normally: fr run advance {run_id}"
    )


def _manual_placement_errors(repo_root: Path, state: RunState) -> tuple[str | None, list[str]]:
    """`(plan_rel, messages)` — every way this run's plan mis-places a manual
    phase (spec §3.D.2). Empty when the plan is fine, missing or unparseable.

    The VERDICT half of `_manual_placement_preflight`, split out so the idle
    reading (`fr run check --idle`, spec 2026-09-20-unit-record-unification
    §4.G) can ask "would `advance` refuse this group?" without a second
    definition of the rule — and without printing or exiting.

    It calls `fr.plan_ops._manual_placement_issues` — the authoring gate
    ITSELF, not a re-implementation of it — so the two points share one
    definition of "trailing" (`_trailing_manual_block`), one definition of
    "outstanding", and one message. Spelled twice they would drift, and an
    operator shown two different texts for one situation has no way to tell
    which is current.
    """
    from fr.parser import PlanSchemaError, parse
    from fr.plan_ops import _manual_placement_issues

    plan_rel = _emitted_plan(state)
    if plan_rel is None:  # pragma: no cover — `_group_phases` refused first
        return None, []
    try:
        plan = parse(repo_root / plan_rel)
    except PlanSchemaError:  # pragma: no cover — `_group_phases` refused first
        return plan_rel, []
    return plan_rel, [i.message for i in _manual_placement_issues(plan) if i.severity == "error"]


def _manual_placement_preflight(repo_root: Path, state: RunState, step_id: str) -> None:
    """Refuse a whole group whose plan mis-places a manual phase (spec §3.D.2).

    The rule is one invariant — *no manual phase may be outstanding when an
    agentic phase after it runs* — and `fr plan self-review` is its primary
    gate, running as fr-goal's `plan-review` `kind: cli` step, where a `cli`
    step's exit code is its verdict. This is the second enforcement point,
    for the paths that never pass through the first: a run reached by
    `fr run adopt`, or driven by a repo-authored shape with no plan-review
    step, arrives at the fan-out with the plan unchecked.

    Silent when the plan is missing or unparseable: `_group_phases` has
    already refused the advance for both, naming the cause, and a second
    refusal here would only mask its message.
    """
    plan_rel, messages = _manual_placement_errors(repo_root, state)
    if not messages:
        return
    detail = "\n".join(f"  {message}" for message in messages)
    err_console.print(
        f"[red]{step_id}: this plan mis-places a manual phase — refusing to "
        f"dispatch ANY of it.[/red]\n{detail}\n"
        f"  re-check it with: fr plan self-review {plan_rel}",
        # soft_wrap: the last line is a command meant to be pasted, and rich
        # folds at width 80 whenever stderr is not a tty (`p1-f1`, `r1-f2`).
        soft_wrap=True,
    )
    raise typer.Exit(2)


def _print_member_dispatch(
    step: Step,
    member: Step,
    item: str,
    state: RunState,
    resolved_tier: str | None,
) -> None:
    """The three stdout lines a dispatched grouped unit produces, in the one
    order that is safe to print them.

    Extracted (P5.T2.S3) because the order is an INVARIANT with two separate
    reasons behind it, and it had accumulated twelve lines of comment at the
    tail of an already-long `_advance_group` — which is where a future editor
    appending "just one more line" would never think to look:

    1. **The JSON brief is last.** `run_cmd` treats it as the line a naive
       `tail -1` parses off stdout (spec §3.B), so the resolve hint goes
       BEFORE it, never after — the same ordering constraint the
       gate-degradation notice in `advance_cmd` carries its own comment for.
       Nothing printed before it may contain a `{`, or the tests' tolerant
       `output[output.index("{"):]` lifts the wrong span (`p1-d1`).
    2. **Every line is `soft_wrap=True`.** rich picks width 80 whenever stdout
       is not a tty — exactly when a harness is piping it — and folding the
       brief hands `tail -1` a fragment (`p1-f1`); folding the hint makes a
       pasteable command unpasteable (`r1-f2`).

    Taking `member` rather than its id keeps the dispatch key spelled once:
    `item/member.id` is the `items`-map key, the display id and the hint's
    two flags, and `_resolve_hint` takes (member, item) while
    `_split_member_id` returns (item, member) — opposite orders that are
    easy to splat into each other by accident.
    """
    _note_subject(step=member.id, item=item, outcome="running")
    _commit_run_writes_now()
    console.print(f"{step.id}: dispatch brief ({item}/{member.id})", soft_wrap=True)
    console.print(
        f"  resolve with: {_resolve_hint(state.run, member.id, item)}   (or --state failed)",
        soft_wrap=True,
    )
    console.print(
        json.dumps(
            _build_member_brief(
                member,
                step,
                item,
                state,
                resolved_tier,
                harness=detect_harness(os.environ),
            ),
            sort_keys=True,
        ),
        soft_wrap=True,
    )


AdvanceStop = Literal["brief", "gate", "cli-done", "cli-failed", "refused", "complete"]
"""Why one `_advance_once` stopped. Only `cli-done` lets `_advance_chain` go on."""


def _advance_group(
    repo_root: Path,
    state: RunState,
    manifest: WorkflowManifest,
    step: Step,
    record: StepRecord,
    *,
    redispatch: bool = False,
) -> AdvanceStop:
    """Dispatch the next pending `(phase, member)` unit of a grouped step.

    The cursor stays on the group while any unit is outstanding; `resolve`
    records each unit, and the group completes (cursor advances) only when
    every expected `phase/<n>/<member>` key is done. A group with nothing
    pending but no `done` record (every unit resolved before this build
    learned members) completes here rather than dispatching thin air.
    """
    try:
        agentic, manual = _group_phases(repo_root, state)
    except (RunStateError, AdoptError) as e:
        err_console.print(f"[red]{step.id}: {escape(str(e))}[/red]", soft_wrap=True)
        raise typer.Exit(2) from e
    expected = _expected_group_items(step, agentic)
    # #496 (spec §3.D.3): the manual markers are merged in HERE, above the
    # running-check, because `items` is what every branch below reads and
    # every save below writes — the completion path included. They are never
    # in `expected`, so they cannot be dispatched, resolved or counted.
    items = {**units.unit_states(record), **_manual_items(manual)}
    # #499 (spec §3.A): the pending-picker below is `!= "done"`, which cannot
    # tell `running` from `pending` — so a second `advance` re-emitted a
    # byte-identical brief for a unit already dispatched. A `running` key is
    # the refusal's subject, and it wins over any later pending one: the
    # group is serial by construction (`_resolve_member` refuses a second
    # writer), so an outstanding unit is the only thing this step is doing.
    #
    # LIFECYCLE, not refusal: `running` answers "which unit is outstanding",
    # which is what `--redispatch` re-briefs and what its nothing-is-running
    # refusal is about. Whether an outstanding unit may be briefed AGAIN is a
    # different question with one answer, `_hold_on` (decision u1) — an
    # `--abandoned` unit is still `running` here and is not held.
    running = next((key for key in expected if items.get(key) == "running"), None)
    hold = _hold_on(record, running, running=True) if running is not None else None
    if running is not None and hold is not None and not redispatch:
        # `_split_member_id` returns (item, member); `_resolve_hint` takes
        # (member, item). Same two strings, opposite order — do not splat one
        # into the other (phase 1, `p1-d1`).
        item, _, member_id = running.rpartition("/")
        err_console.print(
            _already_running_refusal(
                step.id,
                running,
                record.at,
                state.run,
                member_id,
                item,
                hold.holder,
            ),
            # soft_wrap: the refusal's middle line is a command meant to be
            # pasted, and rich folds at width 80 whenever stderr is not a tty
            # — exactly when a harness captures it (`p1-f1`, `r1-f2`).
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if redispatch and running is None:
        err_console.print(
            _nothing_running_refusal(
                step.id, " — every unit of this group is already resolved", state.run
            ),
            soft_wrap=True,
        )
        raise typer.Exit(2)
    # `--redispatch` re-briefs the OUTSTANDING unit and nothing else: never a
    # different unit, never a reset to `pending`. Guarded above, so `running`
    # is not None on that branch.
    pending = (
        running if redispatch else next((key for key in expected if items.get(key) != "done"), None)
    )
    if pending is None:
        # `_complete_step` copies the PRIOR record's items, so the manual
        # markers have to be on the record before it runs or a group that
        # completes here would lose them.
        if items != units.unit_states(record):
            state = _with_step(state, step.id, units.with_unit_states(record, items))
        _save_run_state(repo_root, _complete_step(state, manifest, step.id, "done"))
        console.print(_group_done_line(step.id, expected, manual), soft_wrap=True)
        # The group completed inline with nothing dispatched — the cursor moved
        # exactly as a passed cli step moves it, so `_advance_chain` goes on.
        return "cli-done"
    # Spec §3.D.2 point 2: the preflight, ONCE, before the first unit of this
    # group is dispatched — `pending` is known and nothing has been saved yet.
    # Defence in depth behind `fr plan self-review`, not a substitute for it:
    # a plan reached via `fr run adopt`, or run under a repo-authored shape,
    # can arrive here without the authoring gate ever having run.
    if record.state != "running":
        _manual_placement_preflight(repo_root, state, step.id)
    item, _, member_id = pending.rpartition("/")
    member = next(m for m in step.steps if m.id == member_id)
    phase_n = int(item.rsplit("/", 1)[-1])
    dispatched_at = _now()
    # The write-claim: this unit is now outstanding. A resolve for any OTHER
    # unit while it is running is a second writer — refused in `_resolve_member`.
    # Unconditional (not setdefault): a retried failed unit is running again,
    # not still failed.
    items[pending] = "running"
    # `dispatch` reopens independently of `items`/`state`: an `--abandoned`
    # unit leaves BOTH unchanged (still "running") so its hold looks
    # unchanged to this comparison, yet its last dispatch record is CLOSED —
    # exactly the case a fresh hold must open a new record for
    # (`_dispatch_needs_open`).
    held = _held_record(record, pending)
    if held is not None:
        record = _close_dispatch(record, pending, "abandoned")
        state = _with_step(state, step.id, record)
    needs_dispatch = _dispatch_needs_open(record, pending)
    # `or redispatch`: on a re-dispatch neither the state nor the item map
    # moves, so without it the record would keep the ORIGINAL dispatch time
    # and the next ALREADY RUNNING refusal would name the wrong moment.
    if redispatch or record.state != "running" or units.unit_states(record) != items:
        record = units.with_unit_states(
            record.model_copy(update={"state": "running", "at": _now()}), items
        )
        state = _with_step(state, step.id, record)
    if needs_dispatch:
        state = _open_dispatch(
            state,
            step.id,
            pending,
            agent_type=member.agent,
            tier=_dispatch_tier(repo_root, state, _effective_tier(member, step), phase_n),
            repo_root=repo_root,
            at=dispatched_at,
        )
    _save_run_state(repo_root, state)
    resolved_tier = _phase_tier(repo_root, state, phase_n)
    _print_member_dispatch(step, member, item, state, resolved_tier)
    return "brief"


def _existing_run_for_workflow(repo_root: Path, workflow: str, branch: str) -> str | None:
    """The id of a run on `branch` already driving `workflow`, if any.

    Compares `state.branch` rather than trusting the workspace to stand in for
    it. The previous version scanned every run file in the workspace on the
    reasoning that "`fr run start` writes the run inside the isolation worktree
    for `--branch`, so every run file here belongs to that branch by
    construction" — true of runs CREATED here, false of runs INHERITED here. A
    workspace is a fresh checkout of `origin/main`, so it carries every cursor
    ever merged and not yet archived, and one merged `fr-goal` cursor therefore
    refused every subsequent `fr-goal` run in the repo: the shape worked exactly
    once between archives. The refusal even named the new branch as the one that
    "already has a run".

    Found by Test Plan item 1 of the 2026-09-18 harness-parity work, running
    `/fr-goal` on OpenCode against a clean branch — post-merge testing catching
    what CI structurally could not, since every unit fixture creates its runs in
    the workspace and so satisfies the false assumption by construction.
    """
    runs_dir = repo_root / RUNS_REL
    if not runs_dir.is_dir():
        return None
    for candidate in sorted(runs_dir.glob("*.yaml")):
        try:
            state = parse_run_state(candidate.read_text())
        except (RunStateError, OSError):
            continue  # a broken run file is a different problem
        if state.workflow.split("@", 1)[0] == workflow and state.branch == branch:
            return state.run
    return None


def _bind_session(workspace: Path, branch: str, session: str | None, harness: str) -> None:
    """Attach `session` to the run's workspace — traceability only (#500, spec §3.C.1).

    `fr run start` enters isolation itself, so before this every fr-goal
    workspace reported `sessions=none` while sibling workspaces entered via
    `fr isolation up` carried a uuid: the bind hook's verb regex is
    start-anchored on `fr isolation (up|exec|down)`, which `fr run start`
    could not match.

    NON-FATAL by design. Bindings are traceability, not enforcement — the
    `fr-isolation-required` edit gate reads the `.fr-isolation` marker and
    never a binding — so a bind that fails must never cost the operator a
    started run. It warns on stderr, naming the branch, and returns.

    `sessions.attach` resolves its state through `_git_common_dir`, so this
    works whether the run was born in the base clone's workspace or inside
    the linked worktree.
    """
    if not session:
        return
    try:
        _sessions.attach(workspace, branch, session, harness=harness)
    except IsolationError as e:
        # soft_wrap: an operator-facing line rich would otherwise fold at 80
        # columns whenever stderr is not a tty — i.e. exactly when a harness
        # captures it (journal p1-f1, r1-f2).
        err_console.print(
            f"[yellow]warning: could not bind session {session!r} to branch "
            f"{branch!r}: {escape(str(e))}[/yellow]",
            soft_wrap=True,
        )
        err_console.print(
            f"  the run is started; bind it later with: fr isolation attach "
            f"--session {session} --branch {branch} --harness {harness}",
            soft_wrap=True,
        )


@run_app.command("start")
@_commits_run_writes("start")
def start_cmd(
    workflow: str = typer.Argument(..., help="Workflow shape name (resolved repo > shipped)."),
    branch: str = typer.Option(..., "--branch", help="Branch this run operates on."),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Override the derived run id (default: date + sanitized branch)."
    ),
    session: str | None = typer.Option(
        None, "--session", help="Bind this agent session to the run's workspace (#500)."
    ),
    harness: str = typer.Option(
        "unknown", "--harness", help="claude | hermes | opencode | unknown (with --session)."
    ),
    driver: str | None = typer.Option(
        None,
        "--driver",
        help="`standalone` when standalone fr-brainstorming starts the run: its operator "
        "gate is not held to fr-goal's two-round cap (gh#761). Omit under /fr-goal.",
    ),
) -> None:
    """Start a run: resolve the shape, ensure isolation, write run state in it.

    Isolation is a PRECONDITION, not the run's first step (spec §4.B, review
    fix r2-f5): the run file is written inside the workspace for `--branch`,
    because that is where every later step runs and the only place the file
    is on the feature branch. See `fr.run.workspace`.

    The shape is resolved BEFORE isolation is ensured, so a typo'd shape name
    fails without provisioning a worktree or starting a container.
    """
    if driver not in (None, "standalone"):
        err_console.print(
            f"[red]--driver {driver!r}: the only driver is `standalone` (omit it when "
            "/fr-goal drives the run)[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    repo_root = resolve_repo_root()
    try:
        manifest = resolve_workflow(workflow, repo_root)
    except WorkflowError as e:
        err_console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(2) from e
    if not manifest.steps:
        err_console.print(f"[red]workflow {workflow!r} has no steps[/red]")
        raise typer.Exit(2)
    # Validate the RESOLVED manifest before provisioning anything (review
    # r5-b6). `fr workflow check` was opt-in, so a repo-authored shape with a
    # dangling `needs`, a cycle, or a `kind: cli` step carrying no `run:`
    # started a run — and a `cli` step with no command exits 0, i.e. a green
    # step that did nothing. Cheap, and it runs before isolation is ensured,
    # so a bad shape costs no worktree and no container.
    shape_errors = check_workflow(manifest, repo_root)
    if shape_errors:
        err_console.print(f"[red]workflow {workflow!r} is not valid:[/red]")
        for err in shape_errors:
            err_console.print(f"  {err}", soft_wrap=True)
        raise typer.Exit(2)

    try:
        workspace = ensure_run_workspace(repo_root, branch)
    except RunWorkspaceError as e:
        # soft_wrap=True, like every other operator-facing refusal in this
        # module (p1-f1, r1-f2). This message embeds the repository path, so
        # rich's fold lands at a different word on every host — on a machine
        # with long temp paths it broke `is not a linked git worktree` across a
        # newline mid-phrase. A refusal an operator cannot read, or grep for,
        # is a bug wherever it appears.
        err_console.print(f"[red]{escape(str(e))}[/red]", soft_wrap=True)
        raise typer.Exit(2) from e

    if workspace.resolve() != repo_root.resolve():
        # RE-RESOLVE inside the workspace (review r5-e3). The first resolution
        # is a cheap name check, done before anything is provisioned so a typo
        # costs no worktree; but `advance` runs in the WORKSPACE, and a repo
        # override lives at `docs/superpowers/workflows/<name>.yaml` — which is
        # a different file in the base clone and in the worktree. Starting
        # against one and advancing against the other is the "manifest changed
        # under the run" case, arranged by fr itself.
        try:
            manifest = resolve_workflow(workflow, workspace)
        except WorkflowError as e:
            err_console.print(f"[red]{escape(str(e))}[/red]")
            raise typer.Exit(2) from e
        shape_errors = check_workflow(manifest, workspace)
        if shape_errors:
            err_console.print(f"[red]workflow {workflow!r} is not valid in {workspace}:[/red]")
            for err in shape_errors:
                err_console.print(f"  {err}", soft_wrap=True)
            raise typer.Exit(2)

    try:
        # `--run-id` is operator input and becomes a path segment
        # (`runs/<id>.yaml`) plus a §4.D item-id segment. Unvalidated,
        # `--run-id ../../../escaped` exited 0 and wrote outside `runs/`
        # (review r5-b1). `derive_run_id` already flattens `/`, so this only
        # ever fires on an explicit override.
        rid = validate_run_id(run_id) if run_id else derive_run_id(branch)
    except RunStateError as e:
        err_console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(2) from e
    path = run_path(workspace, rid)
    # The case check runs FIRST so its (more informative) message wins on both
    # kinds of filesystem: on macOS/APFS `path.exists()` is already true for a
    # case-variant, and "run 'Run-1' already exists" would leave the operator
    # hunting for a file that is spelled differently.
    collision = existing_run_id_colliding_with(workspace, rid)
    if collision is not None:
        # macOS/APFS and Windows are case-insensitive, so `Run-1` and `run-1`
        # are ONE file there and two on Linux (review r5-e1). Refusing makes
        # the behaviour identical everywhere, and matches the intuition that
        # two ids differing only by case are one id with a typo.
        err_console.print(
            f"[red]run {collision!r} already exists and differs from {rid!r} only by "
            "case; on a case-insensitive filesystem these are the same file[/red]"
        )
        raise typer.Exit(2)
    if path.exists():
        err_console.print(f"[red]run {rid!r} already exists at {path}[/red]")
        # After `up` restored a torn-down run (#575 §3.D.4) this is the usual
        # way here: the run is back, and it is resumed, not restarted.
        err_console.print(
            f"  inspect it:  fr run status {rid}\n  resume it:   fr run advance {rid}",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    existing = _existing_run_for_workflow(workspace, manifest.workflow, branch)
    if existing is not None:
        # A second `start` on the same branch and shape is nearly always a
        # mistake — a re-run after a wedge, or a forgotten in-flight run
        # (review r5-e5). Both have better answers than a duplicate cursor.
        err_console.print(
            f"[red]branch {branch!r} already has a {manifest.workflow!r} run: {existing}[/red]"
        )
        err_console.print(
            f"  inspect it:  fr run status {existing}\n"
            f"  resume it:   fr run advance {existing}\n"
            "  or start a differently-named shape, or delete that run file.",
            soft_wrap=True,
        )
        raise typer.Exit(2)

    steps = {
        s.id: StepRecord(state="pending", members=[m.id for m in s.steps] or None)
        for s in manifest.steps
    }
    state = RunState(
        schema_version=current_run_schema_version(),
        run=rid,
        workflow=f"{manifest.workflow}@{manifest.schema_version}",
        branch=branch,
        started=_now(),
        cursor=manifest.steps[0].id,
        steps=steps,
        driver="standalone" if driver == "standalone" else None,
    )
    _save_run_state(workspace, state)
    console.print(f"started run {rid} ({state.workflow}) — cursor: {state.cursor}")
    # soft_wrap: rich would fold a long worktree path across lines and break
    # the operator's copy-paste (same reason `commands/common.py` uses a plain
    # echo for its `fr migrate dirs` hint).
    console.print(
        f"workspace: {workspace} — run every later `fr run` command from there",
        soft_wrap=True,
    )
    # AFTER `save_run_state` (spec §3.C.1): a bind failure must not be able to
    # leave a bound workspace with no run in it. The reverse order would make
    # the failure look like "the session is here" while the cursor the session
    # was bound for does not exist.
    _bind_session(workspace, branch, *_sessions.ambient_binding(session, harness, os.environ))
    notice = _orchestrator_model_notice(workspace)
    if notice is not None:
        err_console.print(f"[yellow]{notice}[/yellow]", soft_wrap=True)


@run_app.command("reshape")
@_commits_run_writes("reshape")
def reshape_cmd(
    run_id: str = typer.Argument(..., help="Run id."),
    yes: bool = typer.Option(
        False, "--yes", help="Write the reshaped cursor (default: preview the diff only)."
    ),
) -> None:
    """Move a drifted cursor onto the shape's current step list.

    A run records its step list at `fr run start`; when the shape later gains or
    loses a step every mutating command refuses it. Reshape inserts an added
    step `pending` (only AFTER the cursor), drops a removed one that recorded
    nothing, and refuses — exit 2, nothing written — when the rewrite would lose
    something the run recorded (spec 2026-10-05-run-upgrade-midflight §A).
    Dry-run by default; `--yes` writes one `chore(fr):` commit.
    """
    repo_root = resolve_repo_root()
    state = _load_or_exit(repo_root, run_id)
    try:
        # Not `_resolve_manifest_checked_schema`: its refusal says "start a new
        # run", and rule 1 of `reshape` names the way on (`adopt --supersede`).
        manifest = resolve_workflow(state.workflow.partition("@")[0], repo_root)
        new = reshape(state, manifest)
    except (RunStateError, WorkflowError, ReshapeError) as e:
        err_console.print(f"[red]{escape(str(e))}[/red]", soft_wrap=True)
        raise typer.Exit(2) from e
    added, removed = diff_ids(state.steps, new.steps)
    members_changed = [
        sid for sid in new.steps if sid in state.steps and new.steps[sid] != state.steps[sid]
    ]
    if new == state:
        console.print(f"{state.run}: nothing to reshape")
        return
    parts = []
    if added:
        parts.append(f"added: {', '.join(added)}")
    if removed:
        parts.append(f"removed: {', '.join(removed)}")
    if members_changed:
        parts.append(f"members rewritten: {', '.join(members_changed)}")
    console.print(f"{state.run}: {'; '.join(parts)}", soft_wrap=True)
    if not yes:
        console.print("(preview — re-run with --yes to write)")
        return
    _save_run_state(repo_root, new)
    console.print(f"{state.run}: reshaped")


def _print_supersede_preview(state: RunState, effects: Superseded, notes: list[str]) -> None:
    console.print(
        f"supersede: {effects.old} -> {state.run} (cursor: {state.cursor})", soft_wrap=True
    )
    for step, key, agent, session in effects.holds:
        who = ", ".join(
            part
            for part in (f"agent {agent}" if agent else "", f"session {session}" if session else "")
            if part
        )
        console.print(
            f"  closes a hold on {step} {key} ({who or 'holder unrecorded'}) "
            "as abandoned — that work is cut off",
            soft_wrap=True,
        )
    if not effects.holds:
        console.print("  no unit is held; nothing is cut off")
    for note in notes:
        console.print(f"  {note}", soft_wrap=True)
    console.print("(preview — re-run with --yes to write)")


def _note_supersede_writes(repo_root: Path, effects: Superseded) -> None:
    """Name the removed and moved files for the closing commit. A removed path
    git never tracked is left out: `git add` of a missing, untracked path fails
    and would refuse the whole commit."""
    writes = _RUN_WRITES.get()
    if writes is None:
        return
    writes.supersedes = effects.old
    for path in (*effects.removed, *effects.written):
        if path.exists() or _is_tracked(repo_root, path):
            writes.note(repo_root, path)


def _is_tracked(repo_root: Path, path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
        return git_answer(repo_root, "ls-files", "--error-unmatch", "--", rel).returncode == 0
    except (ValueError, GitUnavailableError):
        return False


@run_app.command("adopt")
@_commits_run_writes("adopt")
def adopt_cmd(
    target: Path = typer.Argument(
        ..., help="Plan folder to adopt (or the spec, when no plan exists yet)."
    ),
    branch: str | None = typer.Option(
        None, "--branch", help="Branch this run operates on (default: the checked-out one)."
    ),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Override the derived run id (default: date + sanitized branch)."
    ),
    workflow: str | None = typer.Option(
        None, "--workflow", help="Shape to adopt against (default: fr-goal)."
    ),
    pr: str | None = typer.Option(
        None, "--pr", help="URL of the PR delivering this work, if one is already open."
    ),
    supersede: bool = typer.Option(
        False,
        "--supersede",
        help=(
            "Replace the plan's existing run with a freshly adopted one, carrying its gate "
            "answers, units and evidence forward (preview unless --yes)."
        ),
    ),
    yes: bool = typer.Option(
        False, "--yes", help="With --supersede over an existing run: write it (default: preview)."
    ),
) -> None:
    """Give in-flight work a run cursor, inferred from artifacts that exist.

    The other half of the 2026-08-30 artifact-migration framework (§3.E): the
    installed fr changes under work already under way, and `fr run start` would
    put the cursor at step one with the spec and plan already written. Adoption
    reads what is on disk instead — spec only, plan with no phase complete, some
    phases complete, all complete, a PR already open — and lands the cursor on
    the step that state implies, recording the emitted spec and plan so
    archival keys on them afterwards.

    Explicit by design. `fr migrate artifacts` *reports* which plans could be
    adopted, and adopts only with `--adopt`; nothing creates a run as a side
    effect of an unrelated command.

    Over a plan that already has a run it refuses, naming `fr run reshape` and
    `--supersede`. `--supersede` replaces that run (spec
    2026-10-05-run-upgrade-midflight §C): the old cursor's gate answers, emitted
    artifacts, units, attempts and evidence are carried into the fresh one, any
    open attempt closed `abandoned`, its usage file moved to the new id. Dry-run
    by default; `--yes` writes one commit.
    """
    repo_root = resolve_repo_root()
    notes: list[str] = []
    effects = Superseded(old="")
    try:
        state = adopt_run(
            repo_root,
            target,
            branch=branch,
            run_id=run_id,
            workflow=workflow,
            pr_url=pr,
            notes=notes,
            supersede=supersede,
            dry_run=not yes,
            superseded=effects,
        )
    except AdoptError as e:
        err_console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(2) from e
    if effects.old and not effects.written_new:
        _print_supersede_preview(state, effects, notes)
        return
    _note_record_write(repo_root, run_path(repo_root, state.run), state)
    if effects.old:
        _note_supersede_writes(repo_root, effects)

    console.print(f"adopted run {state.run} ({state.workflow}) \u2014 cursor: {state.cursor}")
    done = [sid for sid, rec in state.steps.items() if rec.state == "done"]
    if done:
        console.print(f"  already done: {', '.join(done)}")
    items = _fan_out_items(state)
    # #496: a `tag: manual` phase is not outstanding work, it is work this run
    # will never dispatch — counting it in the denominator says "one phase
    # left to do" about a phase nothing will ever do. Named on its own line
    # instead of hidden, for the same reason the cursor records it at all.
    manual = sorted(k for k, v in items.items() if v == MANUAL_ITEM)
    dispatched = {k: v for k, v in items.items() if v != MANUAL_ITEM}
    if dispatched:
        complete = [k for k, v in dispatched.items() if v == "done"]
        # Grouped fan-out keys (`phase/<n>/<member>`) count member outcomes,
        # not phases — label them honestly so "3/3" never reads as reviewed.
        unit = "phase members" if any(k.count("/") >= 2 for k in dispatched) else "phases"
        console.print(f"  {len(complete)}/{len(dispatched)} {unit} complete")
    if manual:
        console.print(f"  never dispatched (`tag: manual`): {', '.join(manual)}", soft_wrap=True)
    for note in notes:
        console.print(f"  {note}", soft_wrap=True)
    console.print(f"  advance it with: fr run advance {state.run}", soft_wrap=True)


def _fan_out_items(state: RunState) -> dict[str, str]:
    """The per-phase items of the step that fans out — NOT of the cursor.

    `build_run_state` attaches `items` to the `for_each: phase` step
    (`implement` in the shipped fr-goal shape), and adoption deliberately moves
    the cursor PAST it when every phase is done. Reading the cursor's record
    therefore made "N/M phases complete" vanish for `review` and `deliver` —
    the two cases where the answer is most worth printing. At most one step
    fans out, so scanning for the record that carries items needs no knowledge
    of the workflow's step names.
    """
    return units.fan_out_states(state)


def _missing_run_exit(repo_root: Path, run_id: str, path: Path) -> NoReturn:
    """Exit 2 with an HONEST run-not-found (#575, spec §3.D.5): the run may be
    in another live workspace, or preserved by a teardown, or never existed —
    `preserve.explain_missing` says which. Imported lazily, here at the CLI
    layer, so `fr/run/model.py`'s `load_run_state` stays import-free."""
    from fr.isolation.preserve import explain_missing

    err_console.print(f"[red]{explain_missing(repo_root, run_id, path)}[/red]", soft_wrap=True)
    raise typer.Exit(2)


def _load_or_exit(repo_root: Path, run_id: str) -> RunState:
    """Load a run, or exit 2 naming the FILE (review r5-e3) — or, when there is
    no file, explaining where the run went (`_missing_run_exit`).

    Every load site in this module goes through here (the three that also
    resolve a manifest call it inside their own `try`; `typer.Exit` passes
    through their `except`).

    Every `fr run` subcommand needs this and each did it slightly differently.
    A missing or unparseable run file is an ordinary operator situation — a
    typo'd id, a half-written file, a bad merge — and must never be a
    traceback; `RunStateError` already carries the path.
    """
    path = run_path(repo_root, run_id)
    if not path.exists():  # a present-but-unreadable file keeps its own error (p5-f9)
        _missing_run_exit(repo_root, run_id, path)
    try:
        state = load_run_state(repo_root, run_id)
    except RunStateError as e:
        err_console.print(f"[red]{escape(str(e))}[/red]", soft_wrap=True)
        raise typer.Exit(2) from e
    except OSError as e:  # pragma: no cover — unreadable file
        err_console.print(
            f"[red]cannot read {run_path(repo_root, run_id)}: {escape(str(e))}[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2) from e
    _note_loaded(state)
    return state


def _dispatch_holder_label(attempt: UnitAttempt) -> str:
    """Who to name for `attempt` — the priority spec §4.B.1/§4.C both rely on.

    `agent_type is None` means an orchestrator-run `kind: agent` step (the
    manifest's own `agent: null`): that is not a missing value, it is the
    orchestrator doing the work itself, and it never reports an `agent` id
    for itself. Only once a unit IS dispatched to an actual agent type does
    an absent `agent` read as `an unclaimed agent` — the same distinction
    the gh-499 refusal (`_already_running_refusal`) draws, by calling this.
    """
    if attempt.agent_type is None:
        return "the orchestrator"
    if attempt.agent is not None:
        return f"agent {attempt.agent}"
    return "an unclaimed agent"


def _dispatch_descriptor_suffix(attempt: UnitAttempt, *, with_agent_type: bool = False) -> str:
    """` (harness, model)` — and, for the gh-499 refusal, the agent TYPE first.

    `fr run status` prints one line per attempt and already says which unit it
    is under, so the type would be noise there. The refusal is read by someone
    deciding whether to wait, and "what kind of agent has this" is one of the
    four facts that decision needs (who, what kind, which harness, since when).
    """
    agent_type = attempt.agent_type if with_agent_type else None
    descriptors = [d for d in (agent_type, attempt.harness, attempt.model) if d]
    return f" ({', '.join(descriptors)})" if descriptors else ""


def _render_dispatch_attempt(attempt: UnitAttempt) -> str:
    """One `Attempt` as a line of `fr run status`/`fr run check`
    prose — spec §4.C's illustration, cases (a)-(d) of P5.T1.S1."""
    if attempt.synthesized:
        # NOT "held by the orchestrator": this attempt has no `agent_type`
        # because fr never recorded one, and no `returned` for the same reason.
        return (
            f"dispatched {attempt.dispatched} — holder not recorded (predates the dispatch record)"
        )
    who = _dispatch_holder_label(attempt)
    suffix = _dispatch_descriptor_suffix(attempt)
    if attempt.returned is None:
        if attempt.agent_type is None:
            return f"held by the orchestrator{suffix} since {attempt.dispatched}"
        return f"HELD BY {who}{suffix} since {attempt.dispatched}"
    return f"{who}{suffix} {attempt.dispatched} -> {attempt.returned} {attempt.outcome}"


def _render_unit_dispatch(record: StepRecord, key: str, *, indent: str, console: Console) -> None:
    """Every attempt recorded for `key`, oldest first (case (e)) — each one
    followed by its own cost."""
    for attempt in units.attempts(record, key):
        console.print(f"{indent}{_render_dispatch_attempt(attempt)}", soft_wrap=True)


def _render_unit_evidence(
    record: StepRecord,
    step_id: str,
    key: str,
    unevidenced: Mapping[tuple[str, str], tuple[str, ...]],
    *,
    indent: str,
) -> None:
    """A unit's evidence, or the fact that it owes some (§4.E).

    `evidence: review=<id>` for what was verified, and a debt line for what the
    step declares and the unit lacks — both, when a unit was resolved before
    its step grew an obligation. A unit under a step that declares no evidence
    prints neither, so `fr run status` is byte-identical for every shape that
    never opted in.
    """
    evidence = units.evidence_of(record, key)
    if evidence:
        shown = " ".join(f"{name}={eid}" for name, eid in sorted(evidence.items()))
        console.print(f"{indent}evidence: {shown}", soft_wrap=True)
    if evidence.get("reviewer") == HISTORICAL_REVIEWER:
        console.print(f"{indent}{historical_sentence(evidence.get('review', '?'))}", soft_wrap=True)
    lacking = unevidenced.get((step_id, key))
    if lacking:
        console.print(f"{indent}{_debt_phrase(record, key, lacking)}", soft_wrap=True)


def _render_step_and_items(
    state: RunState,
    console: Console,
    unevidenced: Mapping[tuple[str, str], tuple[str, ...]] | None = None,
) -> None:
    """The step/items renderer — unchanged in shape from before this phase
    when a run carries no dispatch data (case (f)): the dispatch lines are
    additive, never a replacement for the existing `items` line."""
    owed = unevidenced or {}
    for step_id, record in state.steps.items():
        console.print(f"  {step_id}: {record.state}")
        # Two passes, in this order, because a unit WITH a state renders as
        # `key: <state>` and one without renders as a bare `key:` — a flat
        # `kind: agent` step's `step/<id>` unit carries no state at all
        # (§4.B), and interleaving the two by key would reorder the block.
        for key in units.unit_keys(record):
            if units.unit_state(record, key) is not None:
                console.print(f"    {key}: {units.unit_state(record, key)}")
                _render_unit_evidence(record, step_id, key, owed, indent="      ")
                _render_unit_dispatch(record, key, indent="      ", console=console)
        for key in units.unit_keys(record):
            if units.unit_state(record, key) is None:
                console.print(f"    {key}:")
                _render_unit_evidence(record, step_id, key, owed, indent="      ")
                _render_unit_dispatch(record, key, indent="      ", console=console)


def _render_cursor(state: RunState, console: Console) -> None:
    """The run's own four facts — where it is, and what it is driving."""
    console.print(f"run: {state.run}")
    console.print(f"workflow: {state.workflow}")
    console.print(f"branch: {state.branch}")
    console.print(f"cursor: {state.cursor}")


@run_app.command("status")
def status_cmd(run_id: str = typer.Argument(..., help="Run id.")) -> None:
    """Print the cursor, every step's state, who is holding each dispatched
    unit, since when, and whether it has returned (spec §4.C).

    Two sections: `_render_cursor` and `_render_step_and_items` (which
    delegates one attempt's holder line to `_render_dispatch_attempt`). What
    a run COST is `fr run cost`'s, read from the usage file — the cost column
    went with run 7 (spec 2026-09-25-lean-cost-aware-process §5.B.4).
    """
    repo_root = resolve_repo_root()
    state = _load_or_exit(repo_root, run_id)
    try:
        _resolve_manifest_for_read(repo_root, state)
    except (RunStateError, WorkflowError) as e:
        # status is how an operator finds out a cursor is unusable — it reports
        # the problem and still prints what it can read.
        err_console.print(f"[yellow]warning: {escape(str(e))}[/yellow]", soft_wrap=True)

    _render_cursor(state, console)
    _render_step_and_items(state, console, _unevidenced_units(repo_root, state))


@run_app.command("cost")
def cost_cmd(
    run_id: str = typer.Argument(..., help="Run id."),
    recompute: bool = typer.Option(
        False,
        "--recompute",
        help="Re-derive the figures from THIS host's transcripts instead of the "
        "run's usage file (nothing is written).",
    ),
) -> None:
    """Print what a run cost, per step and per model, from its usage file
    (`docs/superpowers/usage/<run>.yaml`, then `implemented/usage/`) — spec
    `2026-09-25-lean-cost-aware-process-design.md` §5.B.4.

    Read-only. Works on any checkout that has the file, including one that
    never ran the run. A figure nobody could observe prints as `—`, never `0`.
    """
    from rich.table import Table

    from fr.run.cost import effective_entries, load_run_usage, recompute_entries, summarize
    from fr.usage.file import UsageFileError

    repo_root = resolve_repo_root()
    order: list[str] = []
    note = ""
    if recompute:
        state = _load_or_exit(repo_root, run_id)
        entries = recompute_entries(repo_root, state, os.environ)
        order = list(state.steps)
        note = "recomputed from this host's transcripts (not written)"
    else:
        try:
            usage = load_run_usage(repo_root, run_id)
        except (OSError, UsageFileError) as e:
            err_console.print(
                f"[red]fr run cost: the usage file of {run_id} is unreadable: "
                f"{escape(str(e))}[/red]"
            )
            raise typer.Exit(2) from e
        if usage is None:
            err_console.print(
                f"[red]fr run cost: no usage recorded for {run_id!r} — nothing has been "
                f"captured yet. `fr run cost {run_id} --recompute` re-derives it from this "
                "host's transcripts.[/red]",
                soft_wrap=True,
            )
            raise typer.Exit(2)
        entries, replayed, ignored = effective_entries(usage)
        try:
            order = list(load_run_state(repo_root, run_id).steps)
        except RunStateError:
            order = []
        captures = ", ".join(f"{'+'.join(c.at)}@{c.host}" for c in usage.captures) or "none"
        note = f"captures: {captures}"
        if replayed:
            note += " — only figures migrated from the run 6 cursor (no dollars)"
        if ignored:
            note += f"; {ignored} migrated entries ignored (a live capture covers them)"
    summary = summarize(entries, order)

    def usd(value: float | None) -> str:
        return "—" if value is None else f"${value:,.2f}"

    def n(value: int | None) -> str:
        return "—" if value is None else f"{value:,}"

    steps = Table(title=f"Cost — {run_id}")
    steps.add_column("step", overflow="fold", min_width=12)
    steps.add_column("turns", justify="right")
    steps.add_column("cost", justify="right")
    for row in summary.steps:
        steps.add_row(row.step, n(row.turns), usd(row.usd))
    steps.add_section()
    steps.add_row("total", "", usd(summary.total))
    console.print(steps)
    models = Table(title="By model")
    models.add_column("model", overflow="fold", min_width=12)
    for column in ("input", "cache write", "cache read", "output", "cost", "source"):
        models.add_column(column, justify="right", overflow="fold")
    for m in summary.models:
        models.add_row(
            m.model,
            n(m.input),
            n(m.cache_write),
            n(m.cache_read),
            n(m.output),
            usd(m.usd),
            "/".join(m.sources),
        )
    console.print(models)
    console.print(
        f"sessions: {summary.read} read, {summary.unavailable} unavailable; {note}",
        soft_wrap=True,
    )
    # Each unavailable session's reason, so `--recompute` reads exactly as the
    # committed file does (`unavailable: no session found`, spec
    # 2026-10-02-opencode-observe-2 §C).
    for entry in entries:
        if entry.unavailable is not None:
            who = f"{entry.session}: " if entry.session else ""
            console.print(f"  {who}unavailable: {entry.unavailable}", soft_wrap=True, markup=False)


def _observed_holder(state: RunState, key: str) -> str | None:
    """The child session that holds `key`, observed — or `None` (spec
    2026-10-02-opencode-observe-2 §D, R5).

    Only for an OPEN attempt dispatched to an agent type with nobody claiming
    it: when the session protocol shows exactly ONE child of that agent type
    (compared through `agent_name`) dispatched since the attempt opened, that
    child is the holder. Zero or several, or a session fr cannot read, leave
    the unit unclaimed — the existing "unclaimed" handling stands."""
    from fr.run.observed import agent_name, observed_session
    from fr.run.telemetry import parse_timestamp

    attempt = units.last_attempt(state, key)
    if (
        attempt is None
        or attempt.returned is not None
        or attempt.synthesized
        or attempt.agent is not None
        or attempt.agent_type is None
    ):
        return None
    start = parse_timestamp(attempt.dispatched)
    view = observed_session(os.environ) if start is not None else None
    dispatched = view.dispatches(start) if view is not None and start is not None else None
    if not dispatched:
        return None
    wanted = agent_name(attempt.agent_type)
    matching = [
        d.agent_id
        for d in dispatched
        if d.agent_type is not None and agent_name(d.agent_type) == wanted
    ]
    if len(matching) != 1:
        return None
    err_console.print(
        f"{key}: holder {matching[0]} observed — the one {attempt.agent_type} "
        "dispatch since the unit opened; recorded as its claim.",
        soft_wrap=True,
        markup=False,
    )
    return matching[0]


@run_app.command("advance")
@_commits_run_writes("advance")
def advance_cmd(
    run_id: str = typer.Argument(..., help="Run id."),
    redispatch: bool = typer.Option(
        False,
        "--redispatch",
        help="Re-brief the unit that is already held: close its open dispatch "
        "`abandoned` and append a fresh one (gh-499). The deliberate escape for "
        "a genuinely lost agent — the old holder stays in the unit's list, which "
        "is the forensic trail. Refuses when nothing is outstanding.",
    ),
) -> None:
    """Advance the cursor by one step.

    `kind: cli` executes directly (exit code + stdout captured; cursor
    moves only on success). `kind: agent` is NEVER executed — it emits a
    dispatch brief and marks itself `running`. A `gate: operator` step whose
    gate is unanswered marks `blocked` and executes nothing; an `agent` step
    still prints its brief there, since the gate stops the run, not the
    harness's view of what the step is. `fr run resolve` answers the gate.

    A unit somebody is ALREADY HOLDING is refused — exit 2, and no brief of
    any kind (gh-499, where an identical second brief read as an instruction
    to dispatch a second `fr-phase-executor` into the one worktree the first
    was already writing). `--redispatch` is the deliberate escape.
    An `agent` step already `running` is REFUSED (#499, spec §3.A) rather
    than re-briefed: fr-goal dispatches phase executors into one shared
    isolation worktree, so a second brief means two writers in one tree.
    `--redispatch` is the deliberate escape, and refuses in turn when
    nothing is outstanding.

    Consecutive `kind: cli` steps run in this ONE invocation (spec
    2026-09-29-fr-goal-light-path §B, R5): the advance repeats while the
    previous step was a cli step that passed, and ends on the first brief,
    gate, failure, refusal or the end of the run — one commit per step, as a
    single advance has always made.
    """
    repo_root = resolve_repo_root()
    stop = _advance_chain(repo_root, run_id, redispatch=redispatch)
    if stop == "cli-failed":
        raise typer.Exit(1)
    if stop == "refused":
        raise typer.Exit(2)


def _advance_chain(repo_root: Path, run_id: str, *, redispatch: bool) -> AdvanceStop:
    """Advance until something other than a passed cli step happens (R5).

    Each step is committed on its own, under its own subject, exactly as one
    `fr run advance` per step used to commit it: every iteration runs inside
    a fresh `_RunWrites` and commits it on every exit path. The chain is
    capped by the manifest's step count, so a manifest can never spin.
    """
    # Every advance, not once at start: `/model` can move mid-run, and the
    # moment a turn is spent on the wrong model is the moment to hear it (C3).
    # Once per chain — the chain is one call, so one notice.
    notice = _orchestrator_model_notice(repo_root)
    if notice is not None:
        err_console.print(f"[yellow]{notice}[/yellow]", soft_wrap=True)
    try:
        state = load_run_state(repo_root, run_id)
        bound = len(_resolve_manifest_for_state(repo_root, state).steps) + 1
    except Exception:  # noqa: BLE001 — `_advance_once` reports it, in its own words
        bound = 1
    stop: AdvanceStop = "cli-done"
    for _ in range(bound):
        writes = _RunWrites(verb="advance")
        token = _RUN_WRITES.set(writes)
        try:
            stop = _advance_once(repo_root, run_id, redispatch=redispatch)
        finally:
            _RUN_WRITES.reset(token)
            writes.commit()
        # `--redispatch` names the unit held NOW, never one a later step briefs.
        redispatch = False
        if stop != "cli-done":
            break
    return stop


def _advance_once(repo_root: Path, run_id: str, *, redispatch: bool) -> AdvanceStop:
    """One `advance` step — its prints unchanged; its exits become a stop."""
    try:
        return _advance_step(repo_root, run_id, redispatch=redispatch)
    except typer.Exit:
        # A failed cli step RETURNS `cli-failed`; every exit, whatever its code,
        # is a refusal that wrote nothing it had not already said (review r1-1).
        return "refused"


def _advance_step(repo_root: Path, run_id: str, *, redispatch: bool) -> AdvanceStop:
    try:
        state = _load_or_exit(repo_root, run_id)
        manifest = _resolve_manifest_for_state(repo_root, state)
        step = _step_by_id(manifest, state.cursor)
    except (RunStateError, WorkflowError, AdoptError) as e:
        err_console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(2) from e

    record = state.steps.get(state.cursor)
    if record is None:
        # Every other lookup in this module is guarded; this one was not, so a
        # manifest that gained a step after `fr run start` tracebacked instead
        # of reporting something an operator could act on (review fix r2-f7).
        err_console.print(
            f"[red]run {state.run!r} has no record for its cursor step "
            f"{state.cursor!r} — workflow {state.workflow!r} changed after "
            "`fr run start`; start a new run[/red]"
        )
        raise typer.Exit(2)

    if redispatch and record.state != "running":
        # Placed before every other branch, including the gate: a `blocked`,
        # `pending`, `done` or `failed` step has no outstanding dispatch, and
        # a `cli` step is never `running` at all — fr executes it inline — so
        # this is also what keeps the flag from becoming a second way to run
        # a command. Reported rather than silently downgraded (spec §3.A).
        # LIFECYCLE, not the held-question: "was anything ever dispatched
        # here" is a fact about the step's state. Whether a dispatched unit
        # may be briefed again is `_hold_on`'s, below.
        err_console.print(
            _nothing_running_refusal(state.cursor, f" (the step is {record.state})", state.run),
            soft_wrap=True,
        )
        raise typer.Exit(2)

    if record.state == "done" and _next_step_id(manifest, state.cursor) is None:
        # The run is finished: the cursor sits on the LAST step and that step
        # is done. Without this, one more `advance` flipped the last step from
        # `done` back to `running` (verified live, review r5-b3) — and for a
        # `cli` last step it would have RE-EXECUTED the command, after
        # `fr run check` had already exited 0. Nothing is written here; a
        # finished run is read-only until something else moves it.
        console.print(f"run {state.run} complete — cursor {state.cursor!r} is done")
        # spec §3.D.2: the same `fr pickup --run` handoff `resolve` prints
        # when `deliver` lands `done` — repeated here because a run can be
        # rediscovered by `advance` long after that one printing scrolled
        # out of the delivering session's transcript. Nothing is pending this
        # call (nothing was written above), so `_commit_run_writes_now()` is a
        # no-op — called anyway (p4-r1) so `committed` reflects a real outcome
        # rather than assuming one.
        outcome = _commit_run_writes_now()
        for line in _closeout_handoff_lines(
            repo_root,
            state.run,
            committed=outcome is None or outcome.committed or outcome.unchanged,
        ):
            console.print(line, soft_wrap=True)
        return "complete"

    if _gate_pending(step, record):
        if record.state != "blocked":
            new_record = record.model_copy(update={"state": "blocked", "at": _now()})
            _save_run_state(repo_root, _with_step(state, state.cursor, new_record))
        # soft_wrap on both: the gate line ends in a command the operator
        # copy-pastes, and the brief is JSON a harness parses off stdout —
        # rich's default folding would break a long token mid-string and
        # produce invalid JSON.
        try:
            notice = _gate_degradation_notice()
        except HarnessError as e:
            err_console.print(f"[red]{escape(str(e))}[/red]", soft_wrap=True)
            raise typer.Exit(2) from e
        # R10: where fr cannot observe who answers, the resolve must carry the
        # claim — so the command the agent copies carries it too.
        claim = "" if notice is None else " --answered-by <operator|agent>"
        console.print(
            f"{step.id}: blocked on operator gate — answer it, then "
            f"`fr run resolve {state.run} --step {step.id} --state done{claim}`",
            soft_wrap=True,
        )
        # spec §3.D.1: printed BEFORE the agent brief (below), not after — the
        # brief is a single JSON line a harness parses off stdout, and this
        # notice must not become the last line a naive `tail -1` reads.
        if notice is not None:
            console.print(notice, soft_wrap=True)
        # A gate stops the RUN, not the harness's view of the step: an `agent`
        # step still prints its brief here, because the skill/agent named in it
        # is how the operator's question gets asked in the first place. Nothing
        # is executed either way — a `cli` step's side effect is exactly what
        # the gate is guarding.
        _commit_run_writes_now()
        if step.kind == "agent":
            console.print(json.dumps(_build_brief(step, state), sort_keys=True), soft_wrap=True)
        return "gate"

    if step.kind == "agent":
        if step.steps:
            return _advance_group(repo_root, state, manifest, step, record, redispatch=redispatch)
        # #499 (spec §3.A): the same rule as `_advance_group`'s, at the other
        # call site. This sits AFTER the `_gate_pending` block on purpose — a
        # gated step is `blocked`, never `running`, and its brief is how the
        # operator's question gets asked, so the two must not interact.
        key = _unit_key(repo_root, state, step, None, None)
        # The same ONE question as the grouped call site (`_hold_on`, decision
        # u1). `state == "running"` is passed in as a fact about the unit, not
        # tested here: after `claim --abandoned` the step is still `running`
        # and must be briefed again.
        hold = _hold_on(record, key, running=record.state == "running")
        if hold is not None and not redispatch:
            err_console.print(
                # subject == step_id and member_id == step_id: a top-level
                # step is its own unit, and `item=None` drops `--item` from
                # the resolve hint. Same renderer as the grouped call site.
                _already_running_refusal(
                    step.id, step.id, record.at, state.run, step.id, None, hold.holder
                ),
                soft_wrap=True,
            )
            raise typer.Exit(2)
        brief = _build_brief(step, state)
        held = _held_record(record, key)
        if held is not None:
            record = _close_dispatch(record, key, "abandoned")
            state = _with_step(state, state.cursor, record)
        needs_dispatch = _dispatch_needs_open(record, key)
        if redispatch or record.state != "running" or needs_dispatch:
            if redispatch or record.state != "running":
                record = record.model_copy(update={"state": "running", "at": _now()})
                state = _with_step(state, state.cursor, record)
            if needs_dispatch:
                state = _open_dispatch(
                    state,
                    state.cursor,
                    key,
                    agent_type=step.agent,
                    tier=step.tier,
                    repo_root=repo_root,
                )
            _save_run_state(repo_root, state)
        _commit_run_writes_now()
        console.print(f"{step.id}: dispatch brief")
        console.print(json.dumps(brief, sort_keys=True), soft_wrap=True)
        return "brief"

    # kind == "cli"
    context = _template_context(state)
    try:
        command = _render_template(step.run or "", context, quote=True)
    except RunStateError as e:
        err_console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(2) from e

    if not command.strip():
        # `subprocess.run("", shell=True)` exits 0, so an omitted `run:` used
        # to report a green step that did nothing (review fix r2-f2).
        # `check_workflow` rejects the authored form; this catches the
        # hand-built manifest and the template that renders to nothing.
        err_console.print(
            f"[red]{step.id}: kind: cli with no `run:` command — a cli step's "
            "exit code is its verdict, so there is nothing to be the verdict[/red]"
        )
        raise typer.Exit(2)

    proc = subprocess.run(  # noqa: S602 — manifest is operator-authored; values are shlex-quoted
        command, shell=True, cwd=repo_root, capture_output=True, text=True
    )
    if proc.returncode == 0:
        new_state = _complete_step(
            state, manifest, state.cursor, "done", exit_code=0, stdout=proc.stdout
        )
        _save_run_state(repo_root, new_state)
        console.print(f"{step.id}: done (exit 0)")
        return "cli-done"
    else:
        new_state = _complete_step(
            state, manifest, state.cursor, "failed", exit_code=proc.returncode, stdout=proc.stdout
        )
        _save_run_state(repo_root, new_state)
        err_console.print(f"{step.id}: failed (exit {proc.returncode})")
        # A return value, not `typer.Exit(1)`: only this branch knows a step
        # ran and failed, so only it may say so (review r1-1). Every
        # `typer.Exit` raised under `_advance_step` is a refusal.
        return "cli-failed"


def _resolve_member(
    repo_root: Path,
    state: RunState,
    manifest: WorkflowManifest,
    *,
    member: Step,
    group: Step,
    item: str | None,
    state_value: Literal["done", "failed"],
    emitted_map: dict[str, str],
    evidence_map: dict[str, str],
    agent: str | None = None,
    harness: str | None = None,
    model: str | None = None,
    visual: tuple[VisualEvidence, ...] | None = None,
) -> None:
    """Record one `(phase, member)` outcome on its group's item map.

    The group completes — via the same `_complete_step` cursor asymmetry as
    every other step — only when every expected `phase/<n>/<member>` key is
    done; a `failed` unit fails the group at once and holds the cursor, same
    as a failed step. Whole-group completion (`resolve --step <group>`) stays
    available for harnesses that do not address members.
    """
    grec = state.steps.get(group.id)
    if grec is None:  # pragma: no cover — drift guarantees top-level records
        err_console.print(f"[red]{group.id}: no step record in run {state.run!r}[/red]")
        raise typer.Exit(2)
    if grec.state == "done":
        err_console.print(
            f"[red]{group.id}: already done — re-resolving it does nothing. "
            "Pass --emitted to amend the artifacts it recorded.[/red]"
        )
        raise typer.Exit(2)
    if grec.state not in ("running", "blocked"):
        err_console.print(
            f"[red]{group.id}: not running (state={grec.state!r}) — advance "
            "the group first, then resolve its members[/red]"
        )
        raise typer.Exit(2)
    key = _unit_key(repo_root, state, member, group, item)
    # `_unit_key` already validated `key` against the expected set; recomputed
    # here (cheap, and already proven readable) only to know when EVERY
    # expected key is done, which is a different question than "is this ONE
    # key valid".
    try:
        agentic, manual = _group_phases(repo_root, state)
    except (RunStateError, AdoptError) as e:
        err_console.print(f"[red]{group.id}: {escape(str(e))}[/red]", soft_wrap=True)
        raise typer.Exit(2) from e
    expected = _expected_group_items(group, agentic)
    # The manual markers are `_advance_group`'s to write (a group can only be
    # resolved after it was advanced, so they are already here); merged again
    # only so a cursor written before #496 acquires them on its next resolve
    # rather than completing with the omission unrecorded.
    items = {**units.unit_states(grec), **_manual_items(manual)}
    if items.get(key) == "done" and state_value == "done":
        err_console.print(f"[red]{key}: already recorded done[/red]")
        raise typer.Exit(2)
    # One writer at a time: any OTHER outstanding unit means a second writer
    # is active (a finished executor still writing, or the orchestrator
    # alongside it) — resolve the running unit first instead of interleaving.
    # LIFECYCLE, not the held-question (`_hold_on`): this guards `resolve`
    # against a second WRITER, and an `--abandoned` unit still counts — it is
    # unresolved work that must be re-briefed or resolved before another
    # unit's outcome is recorded over it.
    running = sorted(k for k, v in items.items() if v == "running" and k != key)
    if running:
        err_console.print(
            f"[red]{key}: refused — {running[0]} is still running. The worktree "
            "has exactly one writer; resolve the running unit first.[/red]"
        )
        raise typer.Exit(2)
    # The unit must have been BRIEFED — checked AFTER the one-writer refusal
    # above, so "run `fr run advance`" is only ever said when advance would
    # actually brief it rather than refuse a held unit. The flat path has always refused a step
    # that is not running ("advance first"); this path checked the group and
    # the other units and never the unit itself, so a never-advanced unit went
    # absent -> done with no attempt: no holder, no cost, and — for a review —
    # evidence attached to work nothing records anyone being asked to do.
    # `_close_on_resolve` is silent when nothing is open ON PURPOSE (adopted
    # cursors), so nothing downstream would ever notice; the check belongs
    # here, before the write. A unit that is `running` with no record still
    # resolves — a cursor migrated from before dispatch records existed carries
    # those; `adopt` itself never writes `running`, only `done` and `pending`.
    if items.get(key) in (None, "pending"):
        err_console.print(
            f"[red]{key}: refused — this unit was never briefed, so there is no dispatch "
            f"to close and nothing to record an outcome for. `fr run advance "
            f"{state.run}` briefs the next unit in order — which may be an earlier "
            f"one than this — and prints its brief; resolve what it briefs.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    # R5 (spec 2026-10-02-opencode-observe-2 §D): the holder is filled FIRST,
    # before any evidence is derived — the visual witness refuses an unclaimed
    # unit — and written through the claim path `_close_on_resolve` takes.
    agent = agent if agent is not None else _observed_holder(state, key)
    # The evidence gate runs BEFORE any write (§4.E). A refusal must leave
    # the unit exactly as it found it — a half-resolved review is a worse
    # state than an unresolved one, and is indistinguishable from the skipped
    # review this gate exists to make impossible.
    if state_value == "done":
        _refuse_missing_emits(key, member.emits or group.emits, emitted_map, grec.emitted)
    if state_value == "done" and "plan:ticks" in (member.emits or group.emits):
        _refactor_gate(repo_root, state, key, _item_phase(item) if item is not None else None)
    verified = _verified_evidence(
        repo_root,
        state,
        member,
        key=key,
        phase=_item_phase(item) if item is not None else None,
        offered=evidence_map,
        state_value=state_value,
        emitted=emitted_map,
        visual=visual,
        holder=agent,
    )
    verified = {**verified, **_take_unobserved()}
    items[key] = state_value
    merged_emitted = {**(grec.emitted or {}), **emitted_map}
    base_record = grec.model_copy(update={"emitted": merged_emitted or None})
    if "tests" not in verified:
        # Review r2-3: evidence merges across attempts, so a retry resolved
        # without a suite log would otherwise inherit the last attempt's.
        base_record = units.without_tests_evidence(base_record, key)
    updated = _with_step(state, group.id, units.with_unit_states(base_record, items))
    if verified:
        updated = _with_step(
            updated, group.id, units.with_evidence(updated.steps[group.id], key, verified)
        )
    # The dispatch closes BEFORE `_complete_step` runs, so the closed record
    # is what that rebuild carries forward — and before the `failed` branch
    # too, because a failed unit's holder returned just as surely as a done
    # one's did.
    updated = _close_on_resolve(
        updated, group.id, key, state_value, agent=agent, harness=harness, model=model
    )
    if state_value == "failed":
        _save_run_state(repo_root, _complete_step(updated, manifest, group.id, "failed"))
        console.print(f"{member.id} {item}: failed")
        return
    if all(items.get(k) == "done" for k in expected):
        _save_run_state(
            repo_root, _complete_step(updated, manifest, group.id, "done", emitted=merged_emitted)
        )
        console.print(_group_done_line(group.id, expected, manual), soft_wrap=True)
        return
    _save_run_state(repo_root, updated)
    console.print(f"{member.id} {item}: done")


@run_app.command("resolve")
@_commits_run_writes("resolve", lambda kw: kw.get("state_value"), after=_capture_on_new_host)
def resolve_cmd(
    run_id: str = typer.Argument(..., help="Run id."),
    step_id: str = typer.Option(..., "--step", help="Step id to resolve (must be `running`)."),
    state_value: str | None = typer.Option(
        None, "--state", help="done | failed (required unless --record)."
    ),
    emitted: list[str] = typer.Option(
        [], "--emitted", help="'name=path' artifact this step emitted (repeatable)."
    ),
    evidence: list[str] = typer.Option(
        [],
        "--evidence",
        help="'name=journal-entry-id' proof of an obligation the step declares "
        "(repeatable). `review=<id>` is verified against the plan journal: it "
        "must be a `kind=review` entry carrying this unit's `phase=N`.",
    ),
    item: str | None = typer.Option(
        None,
        "--item",
        help="Phase item (phase/<n>) this outcome is for — required when --step "
        "names a member of a grouped `for_each` step.",
    ),
    no_questions: bool = typer.Option(
        False,
        "--no-questions",
        help="Clear an operator gate WITHOUT having asked the operator — the "
        "explicit, recorded bypass. Requires --reason. On Claude Code a gate "
        "cleared with no answered question in the transcript is otherwise refused.",
    ),
    reason: str | None = typer.Option(
        None,
        "--reason",
        help="Why no operator decision was needed (with --no-questions); written "
        "to the spec journal this resolve emits.",
    ),
    question_rounds: int | None = typer.Option(
        None,
        "--question-rounds",
        help="1 | 2 — how many operator question rounds cleared this gate (default 1). "
        "Verified against the session transcript on Claude Code; 2 needs "
        "--round-two-trigger and --round-two-reason.",
    ),
    round_two_trigger: str | None = typer.Option(
        None,
        "--round-two-trigger",
        help="design-risk | operator-request — why a second round was asked "
        "(with --question-rounds 2). A design-risk round 1 must announce `a 2nd round may follow`.",
    ),
    round_two_reason: str | None = typer.Option(
        None,
        "--round-two-reason",
        help="What round 1 opened that round 2 settled (with --question-rounds 2); "
        "written to the spec journal.",
    ),
    answered_by: str | None = typer.Option(
        None,
        "--answered-by",
        help="operator | agent — who answered this step's operator gate. "
        "Required when the gate's answer cannot be observed (there is no "
        "default); an observed gate derives it. Recorded only when a gate "
        "is cleared, and reported by `fr run check` and in the PR body.",
    ),
    agent: str | None = typer.Option(
        None,
        "--agent",
        help="The harness-reported agent/task id that held this unit — the "
        "LATE fallback for an orchestrator that never called `fr run claim`. "
        "Applied only to an unclaimed record; one that disagrees with an "
        "existing claim is refused, naming both.",
    ),
    harness: str | None = typer.Option(
        None, "--harness", help="One of fr.harness's HARNESSES, alongside --agent."
    ),
    model: str | None = typer.Option(
        None, "--model", help="The model actually dispatched, alongside --agent."
    ),
    record_file: Path | None = typer.Option(
        None,
        "--record",
        help="The step's record (docs/superpowers/runs/<run>.records/<step>[__<item>].yaml): "
        "its outcome, ticks, journal entries, resolutions, acceptance rows and evidence, "
        "applied in one commit (spec 2026-09-25 §5.C.2). Replaces --state/--evidence/--emitted.",
    ),
    no_advance: bool = typer.Option(
        False,
        "--no-advance",
        help="With --record: apply the record and stop. By default an `outcome: done` "
        "record goes on to advance the run — running any following `kind: cli` steps "
        "and printing the next dispatch brief — in this same call.",
    ),
) -> None:
    """Record the outcome of an `agent` step, or answer a step's operator gate.

    The harness calls this when a dispatched agent returns. `advance`
    deliberately never executes an `agent` step, so this is the only way its
    cursor can move past `running`; `done` advances the cursor, `failed`
    leaves it put (same asymmetry `advance` already has for `cli` steps —
    see `_complete_step`).

    It is also the CLOSING half of the dispatch pair `advance` opened: the
    unit's open `Attempt` gets `returned` = now and `outcome` =
    `--state`, which is what stops `advance` refusing the unit as held.
    `--agent/--harness/--model` attach a late identity to a record nobody
    claimed — the fallback for an orchestrator that never called
    `fr run claim`, refused if it disagrees with an existing claim.

    It also clears an operator gate (review fix r2-f1), which is what makes
    a `gate: operator` step something other than a permanent dead end — the
    shipped `fr-goal` `brainstorm` step is `kind: agent` + `gate: operator`,
    so before this the shipped shape wedged on its first step. A **blocked**
    step resolves like this:

    - `kind: agent` — exactly like a `running` one: `done`/`failed`, cursor
      asymmetry unchanged. The gate WAS the agent's question; answering it
      and reporting the outcome are the same act.
    - `kind: cli` — `done` clears the gate and returns the step to `pending`
      so the next `advance` executes it and its exit code is still the
      verdict; `failed` records a declined gate. The flag form executes
      nothing, ever.

    `--record` also ADVANCES (spec 2026-09-29-fr-goal-light-path §B, R4): once
    an `outcome: done` record is applied and committed, the run advances in
    the same call exactly as `fr run advance` would — any following `kind:
    cli` steps run, and the next brief prints. `--no-advance` stops after the
    apply. A `failed` or `blocked` record never advances: its step keeps the
    cursor, and advancing would re-brief the work that just failed.
    """
    if record_file is not None:
        # p3-r4: every flag the record carries is refused beside it, never
        # silently dropped — a flag that is ignored reads as one honoured.
        given = [
            flag
            for flag, value in (
                ("--state", state_value),
                ("--emitted", emitted),
                ("--evidence", evidence),
                ("--no-questions", no_questions),
                ("--reason", reason),
                ("--question-rounds", question_rounds),
                ("--round-two-trigger", round_two_trigger),
                ("--round-two-reason", round_two_reason),
                ("--answered-by", answered_by),
                ("--agent", agent),
                ("--harness", harness),
                ("--model", model),
            )
            if value not in (None, False, [])
        ]
        if given:
            err_console.print(
                f"[red]--record carries the outcome, evidence and emitted artifacts — "
                f"do not pass {'/'.join(given)} with it (record fields: `outcome`, "
                "`emitted`, `evidence` — answered_by/agent/harness/model go in `evidence` — "
                "and `no_questions` + `reason`, or `questions`)[/red]",
                soft_wrap=True,
            )
            raise typer.Exit(2)
        _resolve_with_record(run_id, step_id, item, record_file, advance=not no_advance)
        return
    if no_advance:
        err_console.print(
            "[red]--no-advance goes with --record — the flag form never advances[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if state_value is None:
        err_console.print("[red]--state done|failed is required (or pass --record <file>)[/red]")
        raise typer.Exit(2)
    questions = _questions_from_flags(question_rounds, round_two_trigger, round_two_reason)
    _resolve_body(
        run_id=run_id,
        step_id=step_id,
        state_value=state_value,
        emitted=emitted,
        evidence=evidence,
        item=item,
        no_questions=no_questions,
        reason=reason,
        questions=questions,
        answered_by=_answered_by_or_exit(answered_by),
        agent=agent,
        harness=harness,
        model=model,
    )


def _questions_from_flags(
    rounds: int | None, trigger: str | None, reason: str | None
) -> QuestionRounds | None:
    """The flag form of a record's `questions:` section — the SAME model, so
    both paths hand `_gate_provenance` one value (spec 2026-09-26 §3.B)."""
    from pydantic import ValidationError

    from fr.record.model import QuestionRounds

    if rounds is None:
        if trigger is not None or reason is not None:
            err_console.print(
                "--round-two-trigger/--round-two-reason describe a second round: pass "
                "them with --question-rounds 2",
                style="red",
                markup=False,
                soft_wrap=True,
            )
            raise typer.Exit(2)
        return None
    try:
        return QuestionRounds.model_validate(
            {"rounds": rounds, "trigger": trigger, "reason": reason}
        )
    except ValidationError as e:
        detail = "; ".join(str(err["msg"]) for err in e.errors())
        err_console.print(
            f"--question-rounds {rounds}: {detail}", style="red", markup=False, soft_wrap=True
        )
        raise typer.Exit(2) from e


def _deliver_pr_gate(repo_root: Path, state: RunState, pr: str | None) -> None:
    """Render the PR body fr owns, then refuse `deliver` until the LIVE PR
    carries every required section (spec 2026-09-25 §5.C.4). The render is
    the one file a refusal leaves behind: it is what the agent opens the PR
    with. On success the render is removed — it goes with the delivered step.
    """
    from fr.artifacts.atomic import write_text_atomic
    from fr.hostclient import FORGE_ERRORS, client_for, pr_command
    from fr.record.model import records_dir
    from fr.record.pr_body import (
        PR_BODY_NAME,
        REQUIRED_SECTIONS,
        missing_sections,
        render_pr_body,
        shared_closing_keywords,
    )

    body_path = records_dir(repo_root, state.run) / PR_BODY_NAME
    body_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(body_path, render_pr_body(repo_root, state))
    rel = body_path.relative_to(repo_root).as_posix()
    ref = pr or state.branch
    # Through the forge adapter, never `fr.gh`: on GitLab/Gitea `gh` cannot
    # read the PR, and a gate that cannot read it never passes (gh#742).
    try:
        live = client_for(repo_root).pr_body(ref, cwd=repo_root)
    except FORGE_ERRORS as e:
        create = pr_command(repo_root, "create", body=rel)
        err_console.print(
            f"refused: cannot read the PR {ref!r} ({e}). fr rendered its body to {rel}: open "
            f"the PR with `{create}`, record its url (`emitted: "
            "{pr: <url>}` in the record, or `--emitted pr=<url>`), and resolve again",
            markup=False,
            soft_wrap=True,
        )
        raise typer.Exit(2) from e
    required = (
        (*REQUIRED_SECTIONS, HISTORICAL_HEADING) if historical_reviews(state) else REQUIRED_SECTIONS
    )
    missing = missing_sections(live, required=required)
    # Review p2-r1: the heading alone is not the control — the operator's ok
    # is given against the LIST, so every historical review must be named.
    live_lines = {line.strip() for line in live.splitlines()}
    missing += [line for line in historical_review_lines(state) if line not in live_lines]
    if missing:
        edit = pr_command(repo_root, "edit", ref=ref, body=rel)
        err_console.print(
            f"refused: the PR body lacks required section(s): {', '.join(missing)}. Update "
            f"it from fr's render — `{edit}` — and resolve again",
            markup=False,
            soft_wrap=True,
        )
        raise typer.Exit(2)
    # gh#821: one keyword closes one reference, so `Closes #a and #b` would
    # leave #b open after its fix merges. Checked on the body already read.
    shared = shared_closing_keywords(live)
    if shared:
        fixes = "\n".join(
            f"  {bad!r} — write instead:\n" + "\n".join(f"    {f}" for f in fixed)
            for bad, fixed in shared
        )
        err_console.print(
            "refused: the PR body shares one closing keyword across several issues, "
            "and only the first would close on merge. Give each reference its own "
            "keyword, one per line (move a non-closing mention to a line with no "
            f"keyword), then resolve again:\n{fixes}",
            markup=False,
            soft_wrap=True,
        )
        raise typer.Exit(2)
    _refuse_premature_closes(repo_root, state, live)
    from fr.record.apply import _is_tracked

    tracked = _is_tracked(repo_root, body_path)
    _remember(body_path)
    body_path.unlink()
    if tracked:
        _note_record_write(repo_root, body_path)


def _refuse_premature_closes(repo_root: Path, state: RunState, live: str) -> None:
    """R15: a live PR body that closes, fixes or resolves an issue a post-merge,
    not-walk-verified row cites would close it on merge, before the promise it
    carries has been verified. Printed with the `Refs <ref>` that mentions it
    without closing; exit 2. A repo whose matrix cites no issue is never asked
    (the reference's repo identity needs a remote or matrix keys)."""
    from fr.acceptance.check import resolve_identity
    from fr.acceptance.model import AcceptanceError, load_matrix
    from fr.commands.acceptance_cmd import MATRIX_REL
    from fr.record.pr_body import holds_open_for_run, premature_closes
    from fr.requirements import load_spec_matrix, run_spec

    path = repo_root / MATRIX_REL
    if not path.is_file():
        return
    try:
        matrix = load_matrix(path)
        if not any(row.issues for row in matrix.rows):
            return
        identity = resolve_identity(matrix, repo_root)
        spec_rel = run_spec(state)
        spec_ref = load_spec_matrix(repo_root, spec_rel)[1] if spec_rel is not None else None
    except AcceptanceError as e:
        err_console.print(
            f"[red]refused: cannot check the PR body's closing keywords against the "
            f"acceptance matrix — {escape(str(e))}[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2) from e
    found = premature_closes(
        live, matrix, identity, holds_open_for_run(repo_root, state, matrix, spec_ref)
    )
    if not found:
        return
    lines = "\n".join(
        f"  {p.line!r} closes {p.ref}, which row {', '.join(p.rows)} still holds open "
        f"(post-merge, not yet walk-verified) — write instead: {p.fix}"
        for p in found
    )
    err_console.print(
        "refused: the PR body closes an issue whose promise is not verified until after "
        "merge. Mention it without closing (`Refs <ref>`); the close command is printed "
        f"when the walk is recorded (`fr acceptance set-status --walk`):\n{lines}",
        markup=False,
        soft_wrap=True,
    )
    raise typer.Exit(2)


def _answered_by_or_exit(value: str | None) -> AnsweredBy | None:
    """Narrow an `answered_by` string where it ENTERS fr — the flag, or a
    record's evidence key — to the closed set (spec §F). Refused rather than
    coerced: a typo recorded as a third provenance would be read by nobody and
    would quietly weaken the one claim this field exists to make."""
    if value is None:
        return None
    if value == "operator":
        return "operator"
    if value == "agent":
        return "agent"
    err_console.print(f"[red]--answered-by must be 'operator' or 'agent', got {value!r}[/red]")
    raise typer.Exit(2)


def _resolve_body(
    *,
    run_id: str,
    step_id: str,
    state_value: str,
    emitted: list[str],
    evidence: list[str],
    item: str | None,
    no_questions: bool = False,
    reason: str | None = None,
    questions: QuestionRounds | None = None,
    answered_by: AnsweredBy | None = None,
    agent: str | None = None,
    harness: str | None = None,
    model: str | None = None,
    visual: tuple[VisualEvidence, ...] | None = None,
    shape: str | None = None,
) -> None:
    """`fr run resolve`'s body, callable in process — the flag form and the
    step-record engine (`fr.record.apply`) both run exactly this.

    `shape` is a record's `shape:` (2026-09-29-fr-goal-light-path §A): on a
    `done` resolve of the run's first step it rebinds the run onto that
    shape (`_rebind_shape`), riding this resolve's one commit."""
    if state_value not in ("done", "failed"):
        err_console.print(f"[red]--state must be 'done' or 'failed', got {state_value!r}[/red]")
        raise typer.Exit(2)
    if harness is not None and harness not in HARNESSES:
        err_console.print(f"[red]--harness must be one of {list(HARNESSES)}, got {harness!r}[/red]")
        raise typer.Exit(2)

    repo_root = resolve_repo_root()
    _UNOBSERVED.set(None)
    _GATE_DECISIONS.set(None)
    try:
        state = _load_or_exit(repo_root, run_id)
        manifest = _resolve_manifest_for_state(repo_root, state)
        step, parent = _find_step(manifest, step_id)
        # A member validates against its own declared emits, falling back to
        # the group's; a top-level step always validates against its own —
        # even when it declares none, so `--emitted` on a non-emitting step
        # stays refused (rule 3) rather than silently recorded.
        emits_owner = step if parent is None or step.emits else parent
        emitted_map = _parse_emitted(emitted, repo_root, emits_owner)
        # Against the STEP itself, never a parent: evidence is an obligation of
        # the step that carries it (the `review-phase` member), and falling
        # back to the group the way `emits` does would let a member satisfy an
        # obligation it never declared.
        evidence_map = _parse_evidence(
            evidence, step, phase_unit=parent is not None and parent.for_each == "phase"
        )
        rebind = (
            _rebind_shape(state, manifest, step_id, shape, repo_root) if shape is not None else None
        )
    except (RunStateError, WorkflowError, AdoptError) as e:
        # soft_wrap (review `r1-f2`): `_find_step`'s composite-id message ends
        # in a flag pair the operator copy-pastes, and rich folds at width 80
        # whenever stderr is not a tty — i.e. exactly when a harness captures
        # it. Same reason every other hint in this module carries it.
        err_console.print(f"[red]{escape(str(e))}[/red]", soft_wrap=True)
        raise typer.Exit(2) from e

    if parent is not None and (no_questions or reason is not None or questions is not None):
        # A grouped member never carries an operator gate, and `_resolve_member`
        # has no gate path: before this, the gate flags were dropped silently
        # here (review r1-7's refusal only covered top-level steps).
        _refuse_gate_flags(step_id)
    if parent is not None:
        _resolve_member(
            repo_root,
            state,
            manifest,
            member=step,
            group=parent,
            item=item,
            state_value=state_value,  # type: ignore[arg-type]  # validated below
            emitted_map=emitted_map,
            evidence_map=evidence_map,
            agent=agent,
            harness=harness,
            model=model,
            visual=visual,
        )
        return
    if item is not None:
        if step.steps:
            members = ", ".join(m.id for m in step.steps)
            err_console.print(
                f"[red]{step_id}: a group outcome must address a member step "
                f"({members}) — pass --step <member> --item phase/<n>[/red]"
            )
        else:
            err_console.print(
                f"[red]{step_id}: --item is only for members of a grouped "
                "`for_each` step — {step_id!r} has no members[/red]"
            )
        raise typer.Exit(2)

    record = state.steps.get(step_id)
    if record is None:
        err_console.print(
            f"[red]{step_id}: no step record in run {run_id!r} — workflow "
            f"{state.workflow!r} changed after `fr run start`[/red]"
        )
        raise typer.Exit(2)

    cursor_record = state.steps.get(state.cursor)
    finished = (
        cursor_record is not None
        and cursor_record.state == "done"
        and _next_step_id(manifest, state.cursor) is None
    )
    if finished and not emitted_map:
        # Symmetric with `advance` (review r5-b3/e3): a finished run is
        # read-only. Amending `emitted` is still allowed — that is a
        # correction to the record, not a resumption of the run.
        err_console.print(
            f"[red]run {run_id!r} is complete (cursor {state.cursor!r} is done). "
            "Pass --emitted to amend what a step recorded; nothing else moves.[/red]"
        )
        raise typer.Exit(2)

    # Decided ONCE, before either branch writes a byte: a refused gate leaves
    # the cursor exactly as it was (debug journal C1).
    if no_questions and questions is not None:
        err_console.print(
            f"[red]{step_id}: --no-questions and a question-rounds declaration contradict "
            "each other — a gate cleared without asking took no rounds.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    gate_flags = no_questions or reason is not None or questions is not None
    if gate_flags and not _clears_gate(step, record, state_value):
        # Review r1-7: silently ignored flags read as honoured ones.
        _refuse_gate_flags(step_id)
    gate_by: AnsweredBy | None = (
        _gate_provenance(
            repo_root,
            step_id,
            record,
            claimed=answered_by,
            no_questions=no_questions,
            reason=reason,
            questions=questions,
            emitted=emitted_map,
            state=state,
        )
        if _clears_gate(step, record, state_value)
        else None
    )

    if step.kind == "cli":
        # A `cli` step is fr's to execute, so `resolve` may never declare one
        # done — that would let an operator report success for a command that
        # never ran. The ONE thing it can do is answer that step's operator
        # gate (review fix r2-f1), which is a decision, not an execution.
        if record.state != "blocked":
            err_console.print(
                f"[red]{step_id}: kind {step.kind!r} — resolved by `fr run advance`, "
                "not `fr run resolve` (resolve records an `agent` step's outcome, "
                "or clears a blocked step's operator gate)[/red]"
            )
            raise typer.Exit(2)
        if state_value == "done":
            unobserved = _take_unobserved()
            if unobserved:
                # gh#632: the note `_gate_provenance` just made reaches the
                # cursor on this branch too — on the step's flat unit, which
                # `_complete_step` carries through the `advance` that runs it.
                record = units.with_evidence(
                    record, _unit_key(repo_root, state, step, None, None), unobserved
                )
            new_record = record.model_copy(
                update={
                    "state": "pending",
                    "gate": "cleared",
                    # `_clears_gate`, not the inline `blocked and done` this
                    # branch already established (review r4-m1). The two are
                    # equivalent today — the only writer of `blocked` is
                    # `_gate_pending`, which requires `gate == "operator"` —
                    # but the helper exists so the condition lives in one
                    # place, and a future second writer of `blocked` would
                    # have made these diverge silently.
                    "answered_by": gate_by,
                    "at": _now(),
                    "emitted": dict(emitted_map) if emitted_map else record.emitted,
                }
            )
            _flush_gate_decisions(repo_root)
            _save_run_state(repo_root, _with_step(state, step_id, new_record))
            console.print(
                f"{step_id}: operator gate cleared — `fr run advance {run_id}` now executes it",
                soft_wrap=True,
            )
            return
        # `failed` = the operator declined the gate. Same cursor asymmetry as
        # every other failure: recorded, and the run does not move past it.
        _save_run_state(repo_root, _complete_step(state, manifest, step_id, "failed"))
        console.print(f"{step_id}: failed (operator gate declined)")
        return

    if record.state == "done" and state_value == "done":
        # AMEND, not a re-resolve (review r5-b6). A wrong `emitted` on a step
        # already `done` was unamendable: `resolve` refused ("not running or
        # blocked") and nothing else writes the field, so a run whose
        # `emitted.plan` pointed at the wrong path stayed that way — and that
        # is the key `fr archive` and `fr run adopt` match on. The cursor is
        # deliberately NOT moved: `_complete_step` only moves it when the
        # step IS the cursor, and re-running that for a step already done
        # would advance the run a second time.
        if not emitted_map:
            err_console.print(
                f"[red]{step_id}: already done — re-resolving it does nothing. "
                "Pass --emitted to amend the artifacts it recorded.[/red]"
            )
            raise typer.Exit(2)
        merged = {**(record.emitted or {}), **emitted_map}
        _save_run_state(
            repo_root, _with_step(state, step_id, record.model_copy(update={"emitted": merged}))
        )
        console.print(f"{step_id}: amended emitted artifacts (still done; cursor unchanged)")
        return

    if record.state not in ("running", "blocked"):
        err_console.print(
            f"[red]{step_id}: not running or blocked (state={record.state!r}) — "
            "only a dispatched or gated step can be resolved[/red]"
        )
        raise typer.Exit(2)

    flat_key = _unit_key(repo_root, state, step, None, None)
    # R5: the observed holder, before any evidence is derived.
    agent = agent if agent is not None else _observed_holder(state, flat_key)
    # A flat `step/<id>` unit names no phase, so `review` evidence cannot be
    # verified for it and `_verified_evidence` refuses rather than records.
    verified = _verified_evidence(
        repo_root,
        state,
        step,
        key=flat_key,
        phase=None,
        offered=evidence_map,
        state_value=state_value,
        emitted=emitted_map,
        visual=visual,
        holder=agent,  # the filled holder reaches the visual witness (review p2-r2)
    )
    verified = {**verified, **_take_unobserved()}
    if verified:
        # Reached by `deliver`'s `tests` evidence (debug journal C5) — the first
        # obligation a flat unit can carry, since `review` needs a phase.
        state = _with_step(
            state, step_id, units.with_evidence(state.steps[step_id], flat_key, verified)
        )
    # The flat unit's dispatch closes here, keyed through the SAME `_unit_key`
    # `advance` opened it with and `claim` annotates it by — a `step/<id>` key
    # computed a second time by hand is the drift phase 3 removed.
    state = _close_on_resolve(
        state,
        step_id,
        flat_key,
        state_value,  # type: ignore[arg-type]  # validated above
        agent=agent,
        harness=harness,
        model=model,
    )
    if "pr" in step.emits and state_value == "done":
        # p3-r2: the live-PR section check is `deliver`'s own gate, so the flag
        # form and a record reach the same one — before the cursor moves.
        pr = emitted_map.get("pr") or (record.emitted or {}).get("pr")
        _deliver_pr_gate(repo_root, state, pr)
    if state_value == "done":
        # gh#587: after `deliver`'s PR gate, which renders the body a first
        # `pr`-less resolve exists to fetch, and before the gate's queued
        # journal decision is written — the last refusal before any write.
        _refuse_missing_emits(step_id, step.emits, emitted_map, record.emitted)
    if rebind is not None and state_value == "done":
        state, manifest = _rebound(state, rebind, step_id), rebind
        console.print(f"{step_id}: run rebound onto {state.workflow}", soft_wrap=True)
    new_state = _complete_step(
        state,
        manifest,
        step_id,
        state_value,  # type: ignore[arg-type]  # validated above
        emitted=emitted_map,
        # A gated `agent` step is the shape of the measured failure (spec §1):
        # it goes straight from `blocked` to `done` here and never acquires
        # `gate: cleared`, so provenance is the only trace that its gate was
        # cleared at all.
        answered_by=gate_by,
    )
    _flush_gate_decisions(repo_root)
    _save_run_state(repo_root, new_state)
    console.print(f"{step_id}: {state_value}")
    if step_id == "deliver" and state_value == "done":
        # spec 2026-09-25 §5.B.3: the usage capture rides this commit
        _capture_usage(repo_root, new_state, "deliver")
        # p3-m4: commit BEFORE reading HEAD's sha for the "push it" line below
        # — the decorator's own commit runs in `finally`, after this function
        # returns, so a sha read any earlier would not exist yet. `.commit()`
        # is idempotent once called (it empties the pending paths), so the
        # decorator's later call is a no-op — never a second stderr line.
        # p4-r1: `outcome` is THIS commit's real result — a refusal (default
        # branch, stuck lock, detached HEAD, …) must not be followed by a
        # "push it" line that assumes the commit landed.
        outcome = _commit_run_writes_now()
        for line in _closeout_handoff_lines(
            repo_root, run_id, committed=outcome is None or outcome.committed or outcome.unchanged
        ):
            console.print(line, soft_wrap=True)


# --- step records (spec 2026-09-25-lean-cost-aware-process §5.C.2) ----------


@dataclass(frozen=True)
class InProcessResolve:
    """What `resolve_in_process` hands the step-record engine back."""

    committed: bool
    next_step: str | None
    notices: tuple[str, ...]


def _next_unit(
    repo_root: Path, run_id: str, step_id: str, item: str | None, done: bool
) -> str | None:
    """The unit the next `fr run advance` briefs, as `step [item]` — for the
    step-record line. `None` when the run is complete."""
    here = f"{step_id} {item}" if item else step_id
    if not done:
        return f"{here} (retry)"
    try:
        state = load_run_state(repo_root, run_id)
        manifest = _resolve_manifest_for_state(repo_root, state)
        _step, parent = _find_step(manifest, step_id)
    except (RunStateError, WorkflowError, AdoptError):
        return None
    if parent is not None:
        grec = state.steps.get(parent.id)
        if grec is not None and grec.state != "done":
            try:
                agentic, _manual = _group_phases(repo_root, state)
            except (RunStateError, AdoptError):
                return parent.id
            items = units.unit_states(grec)
            for key in _expected_group_items(parent, agentic):
                if items.get(key) != "done":
                    unit, _, member = key.rpartition("/")
                    return f"{member} {unit}"
            return parent.id
    cursor = state.steps.get(state.cursor)
    if (
        cursor is not None
        and cursor.state == "done"
        and _next_step_id(manifest, state.cursor) is None
    ):
        return None
    return state.cursor


def resolve_in_process(
    repo_root: Path,
    run_id: str,
    *,
    step_id: str,
    item: str | None,
    state_value: str,
    evidence: dict[str, str],
    emitted: dict[str, str],
    also_commit: list[Path],
    no_questions: bool = False,
    reason: str | None = None,
    questions: QuestionRounds | None = None,
    guard: ResolveGuard | None = None,
    visual: tuple[VisualEvidence, ...] = (),
    shape: str | None = None,
) -> InProcessResolve:
    """`fr run resolve` for the step-record engine: the SAME body the flags run
    (every gate included), with the engine's written paths noted into the same
    commit, and the body's own stdout held back — the engine prints one line.

    Four non-evidence keys a record's evidence may carry are the flags of the
    same names: `answered_by` (who answered the step's operator gate) and
    `agent`/`harness`/`model` (the late identity of the unit's holder).
    """
    import contextlib
    import io
    import sys

    offered = dict(evidence)
    answered_by = offered.pop("answered_by", None)
    agent = offered.pop("agent", None)
    harness = offered.pop("harness", None)
    model = offered.pop("model", None)
    writes = _RunWrites(
        verb="resolve", step=step_id, item=item, outcome=state_value, guard=guard, quiet=True
    )
    for path in also_commit:
        writes.note(repo_root, path)
    token = _RUN_WRITES.set(writes)
    held = io.StringIO()
    try:
        with contextlib.redirect_stdout(held):
            _resolve_body(
                run_id=run_id,
                step_id=step_id,
                state_value=state_value,
                emitted=[f"{k}={v}" for k, v in emitted.items()],
                evidence=[f"{k}={v}" for k, v in offered.items()],
                item=item,
                no_questions=no_questions,
                reason=reason,
                questions=questions,
                answered_by=_answered_by_or_exit(answered_by),
                agent=agent,
                harness=harness,
                model=model,
                visual=visual,
                shape=shape,
            )
            _capture_on_new_host(writes, {"step_id": step_id})
        writes.commit()
    except BaseException:
        writes.paths = {}  # a refusal commits nothing; the engine restores the bytes
        sys.stderr.write(held.getvalue())
        raise
    finally:
        _RUN_WRITES.reset(token)
    outcome = writes.last_outcome
    # The body's first line restates what the engine's line says; anything
    # after it (a group-done line, deliver's closeout handoff) is kept.
    notices = tuple(line for line in held.getvalue().splitlines()[1:] if line.strip())
    return InProcessResolve(
        committed=outcome is not None and (outcome.committed or outcome.unchanged),
        next_step=_next_unit(repo_root, run_id, step_id, item, state_value == "done"),
        notices=notices,
    )


def _resolve_with_record(
    run_id: str, step_id: str, item: str | None, record_file: Path, *, advance: bool = True
) -> None:
    """`fr run resolve --record`: parse, fill run/step/item, apply — one line —
    then, for an `outcome: done` record, advance the run (R4) unless `advance`
    is false."""
    from fr.record.apply import RecordRefusedError, apply_record
    from fr.record.model import RecordError, load_record, records_dir

    repo_root = resolve_repo_root()
    # p3-r9: a record is resolved against the repo root (never the cwd) and
    # must live in this run's records dir — the engine deletes and commits
    # it, which must never reach an arbitrary file.
    path = record_file if record_file.is_absolute() else repo_root / record_file
    home = records_dir(repo_root, run_id)
    if not path.resolve().is_relative_to(home.resolve()):
        err_console.print(
            f"refused: {record_file} is not in this run's records dir "
            f"({home.relative_to(repo_root).as_posix()}/) — nothing applied",
            markup=False,
            soft_wrap=True,
        )
        raise typer.Exit(2)
    try:
        record = load_record(path)
    except RecordError as e:
        err_console.print(f"[red]{e}[/red] Nothing applied.", soft_wrap=True, markup=False)
        raise typer.Exit(2) from e
    for name, flag, value in (("step", "--step", step_id), ("item", "--item", item)):
        mine = getattr(record, name)
        if value is not None and mine is not None and mine != value:
            err_console.print(
                f"record names {name} {mine!r} but {flag} is {value!r} — nothing applied",
                markup=False,
            )
            raise typer.Exit(2)
    record = record.model_copy(
        update={"run": record.run or run_id, "step": step_id, "item": record.item or item}
    )
    try:
        outcome = apply_record(repo_root, run_id, record, record_file=path)
    except RecordRefusedError as e:
        err_console.print(f"refused: {e} — nothing applied", markup=False, soft_wrap=True)
        raise typer.Exit(2) from e
    for notice in outcome.notices:
        err_console.print(notice, markup=False, soft_wrap=True)
    typer.echo(outcome.line)
    # deliver's closeout handoff is NOT printed here: the body prints it into
    # the held stdout, and `resolve_in_process` replays it among the notices
    # above — printing it again duplicated it on a real terminal.
    if advance and record.outcome == "done":
        _advance_after_record(repo_root, run_id)


def _advance_after_record(repo_root: Path, run_id: str) -> None:
    """The advance half of a one-call resolve (spec 2026-09-29 §B, R4).

    Runs only after the record's commit landed, so a failure here must say the
    record is applied — nobody should re-apply it. A record that finished the
    run (its last step, `deliver` on fr-goal) has nothing to advance: the
    resolve already printed the closeout, and an advance would repeat it."""
    try:
        state = load_run_state(repo_root, run_id)
        manifest = _resolve_manifest_for_state(repo_root, state)
    except Exception:  # noqa: BLE001 — `_advance_chain` reports it, in its own words
        pass
    else:
        record = state.steps.get(state.cursor)
        if record is not None and record.state == "done":
            if _next_step_id(manifest, state.cursor) is None:
                return
    stop = _advance_chain(repo_root, run_id, redispatch=False)
    if stop == "cli-failed":
        state = load_run_state(repo_root, run_id)
        failed = state.steps.get(state.cursor)
        code = failed.exit if failed is not None else None
        err_console.print(
            f"record applied; {state.cursor} failed (exit {code})", markup=False, soft_wrap=True
        )
        raise typer.Exit(1)
    if stop == "refused":
        err_console.print(
            "record applied; the advance after it was refused (above) — "
            f"fix that, then `fr run advance {run_id}`",
            markup=False,
            soft_wrap=True,
        )
        raise typer.Exit(2)


def _refactor_gate(repo_root: Path, state: RunState, key: str, phase_n: int | None) -> None:
    """The refactor-or-justify gate, moved here from `fr plan self-review`
    (spec 2026-09-25 §5.C.2.2): resolving a `plan:ticks` unit `done` needs,
    for every multi-step task of its phase with no refactor step, a reason —
    a record's `refactor:` entry (journalled as `no-refactor-because`) or,
    for a run started before records existed, that journal entry itself."""
    from fr.parser import PlanSchemaError, parse
    from fr.record.gates import refactor_gaps

    plan_rel = _emitted_plan(state)
    if plan_rel is None or phase_n is None:
        return
    try:
        plan = parse(repo_root / plan_rel)
    except PlanSchemaError:
        return  # `_group_phases` already refused an unreadable plan
    gaps = refactor_gaps(plan, phase_n)
    if not gaps:
        return
    err_console.print(
        f"[red]{key}: refused — task(s) {', '.join(gaps)} have no refactor step and no "
        "refactor reason.[/red]",
        soft_wrap=True,
    )
    err_console.print(
        f"  add `refactor: {{{gaps[0]}: <why there was nothing to clean>}}` to the step "
        "record (or journal a `no-refactor-because` discovery naming the task)",
        markup=False,
        soft_wrap=True,
    )
    raise typer.Exit(2)


def _open_dispatch_record(record: StepRecord, key: str) -> UnitAttempt:
    """The OPEN (`returned is None`) `Attempt` for `key`, or refuse.

    `fr run claim` annotates a dispatch `fr run advance` already made; it
    never invents one (spec §4.C) — a unit with no attempts at all, or whose
    last attempt is already closed, has nothing open to annotate."""
    open_record = _held_record(record, key)
    if open_record is None:
        err_console.print(
            f"[red]{key}: no open dispatch — nothing to claim. `fr run claim` "
            "annotates a dispatch `fr run advance` already made; it does not "
            "invent one. Advance the run first.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    return open_record


def _claim_abandon(repo_root: Path, state: RunState, owner_id: str, key: str) -> None:
    """Close `key`'s open dispatch as `abandoned`, WITHOUT resolving the step
    it belongs to (spec §4.C, §1.C).

    The step's `items`/`state` are left exactly as they are — still
    `running` — so the next `fr run advance` sees the unit as still pending
    and briefs it again, appending a fresh `Attempt` alongside this
    now-closed one (`_dispatch_needs_open`). This is the sanctioned recovery
    for an executor that is never coming back: nothing can retire it from the
    orchestrator side, so freeing the tree has to be a named operator act.

    It also MEASURES the attempt it closes (§4.D). An agent that produced
    nothing still burned tokens, and that is the spend most worth seeing —
    before this, abandoning a unit discarded its cost entirely, and the next
    `advance`'s estimate overwrote the only trace it had.
    """
    record = state.steps[owner_id]
    _open_dispatch_record(record, key)  # refuses when there is nothing to abandon
    new_record = _close_dispatch(record, key, "abandoned")
    _save_run_state(repo_root, _with_step(state, owner_id, new_record))
    console.print(
        f"{key}: dispatch abandoned — `fr run advance` will brief it again", soft_wrap=True
    )


def _claim_identity(
    repo_root: Path,
    state: RunState,
    owner_id: str,
    key: str,
    *,
    agent: str,
    harness: str | None,
    model: str | None,
    agent_type: str | None = None,
) -> None:
    """Fill `key`'s open dispatch record with the orchestrator's reported
    `agent`/`harness`/`model` (spec §3, §4.C).

    Idempotent for the SAME `agent` id (re-claiming just refreshes
    `harness`/`model` when given again); refuses a DIFFERENT one while the
    first is still open, naming both — the two-writers hazard this whole
    feature exists to make visible.

    `agent_type` is the agent that actually RAN (gh#537): on OpenCode the tier
    rides in the agent's name (`fr-phase-executor-<tier>`), so the manifest id
    `advance` recorded never says which tier did the work. It replaces the
    recorded one only when it is that agent or one of its tier variants
    (`_ran_as`); anything else is a different agent, and is refused.
    """
    record = state.steps[owner_id]
    open_record = _open_dispatch_record(record, key)
    if agent_type is not None and not _ran_as(open_record.agent_type, agent_type):
        err_console.print(
            f"[red]{key}: was dispatched to {open_record.agent_type or 'the orchestrator'}, "
            f"not {agent_type!r} — --agent-type names the agent that ran this unit, which "
            "is the dispatched agent or one of its -<tier> variants.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    claimed = _claimed_identity(open_record, key, agent=agent, harness=harness, model=model)
    if agent_type is not None:
        claimed = claimed.model_copy(update={"agent_type": agent_type})
    new_record = units.with_last_attempt_replaced(record, key, claimed)
    _save_run_state(repo_root, _with_step(state, owner_id, new_record))
    console.print(f"{key}: claimed by {agent}", soft_wrap=True)


def _ran_as(dispatched: str | None, ran: str) -> bool:
    """Is `ran` the agent `dispatched` names — in its plugin-qualified or bare
    spelling, or as one of its `-<tier>` variants (`fr.types.PHASE_TIERS`, the
    names `scripts/sync-opencode.py` generates)? Work the orchestrator runs
    itself (`dispatched is None`) ran as no agent."""
    if dispatched is None:
        return False
    bare = dispatched.split(":", 1)[-1]
    return ran in (dispatched, bare) or ran in {f"{bare}-{tier}" for tier in PHASE_TIERS}


def _claim_open_unit(
    repo_root: Path,
    run_id: str | None,
    *,
    agent: str,
    agent_type: str,
    harness: str | None,
    model: str | None,
) -> None:
    """`fr run claim --open-unit` (gh#530): claim THE open unit dispatched to
    `agent_type` that nobody else holds, without naming it.

    The caller is the child session itself (fr-opencode-plugin, on its first
    tool call): it knows its own id and the agent it runs as, never a step or
    item. Phase executors run serially in one workspace, so at most one unit
    fits; zero or several is refused naming what was found, because a claim
    that guessed would name the wrong holder — the defect gh#537 is. Work
    with no `agent_type` is the orchestrator's own and is never a candidate.
    """
    runs = (
        [_load_or_exit(repo_root, run_id)]
        if run_id is not None
        else _runs_on_this_branch(repo_root)
    )
    fits = [
        (state, owner_id, key)
        for state in runs
        for owner_id, key, attempt in _liveness.open_attempts(state)
        if attempt.agent in (None, agent) and _ran_as(attempt.agent_type, agent_type)
    ]
    if len(fits) != 1:
        found = ", ".join(f"{state.run}:{key}" for state, _, key in fits)
        err_console.print(
            f"[red]--open-unit: {'no open' if not fits else 'more than one open'} unit "
            f"dispatched to {agent_type!r} that {agent} could hold"
            + (f" ({found})" if fits else "")
            + " — name it with --step/--item.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    state, owner_id, key = fits[0]
    writes = _RUN_WRITES.get()
    if writes is not None:
        writes.step = owner_id
    _claim_identity(
        repo_root,
        state,
        owner_id,
        key,
        agent=agent,
        harness=harness,
        model=model,
        agent_type=agent_type,
    )


@run_app.command("claim")
@_commits_run_writes("claim", lambda kw: "abandoned" if kw.get("abandoned") else "claimed")
def claim_cmd(
    run_id: str | None = typer.Argument(
        None, help="Run id. Optional with --open-unit: the runs of the checked-out branch."
    ),
    step_id: str | None = typer.Option(
        None, "--step", help="Step id (or member id) to claim. Required without --open-unit."
    ),
    item: str | None = typer.Option(
        None,
        "--item",
        help="Phase item (phase/<n>) this claim is for — required when --step "
        "names a member of a grouped `for_each` step.",
    ),
    agent: str | None = typer.Option(
        None, "--agent", help="The harness-reported agent/task id claiming this dispatch."
    ),
    harness: str | None = typer.Option(
        None,
        "--harness",
        help="One of fr.harness's HARNESSES; defaults to "
        "fr.harness.detect.detect_harness(), recording nothing when it cannot tell.",
    ),
    model: str | None = typer.Option(
        None, "--model", help="The model actually dispatched, if known."
    ),
    abandoned: bool = typer.Option(
        False,
        "--abandoned",
        help="Close this dispatch as abandoned WITHOUT resolving its step — the "
        "sanctioned recovery when an executor is never coming back (spec §1.C), since "
        "nothing can retire it from the orchestrator side; the step stays `running` so "
        "the next `fr run advance` briefs the unit again.",
    ),
    agent_type: str | None = typer.Option(
        None,
        "--agent-type",
        help="The agent that actually ran the unit — the dispatched agent or one of its "
        "-<tier> variants (on OpenCode the tier rides in the agent's name). Recorded in "
        "place of the manifest's agent id.",
    ),
    open_unit: bool = typer.Option(
        False,
        "--open-unit",
        help="Claim THE open, unclaimed unit dispatched to --agent-type, without naming "
        "it — for a child session that knows its own id and agent but not its step "
        "(gh#530). Refuses when zero or several units fit.",
    ),
) -> None:
    """Put the orchestrator's reported identity onto the dispatch `fr run
    advance` already opened for a unit (spec §3, §4.C) — the `agent`/
    `harness` half of `Attempt` that only the orchestrator can report,
    fr itself can only derive `agent_type`/`model` and time its own act.

    Requires an OPEN dispatch record for the unit: a claim annotates a
    dispatch `fr run advance` made, it does not invent one. Re-claiming the
    SAME agent id is idempotent; a DIFFERENT one while the first is open is
    refused, naming both — the two-writers hazard this whole feature exists
    to make visible. `--abandoned` closes the record instead, for a dispatch
    that is never returning; see its own help text.
    """
    if abandoned and agent is not None:
        err_console.print(
            "[red]--abandoned closes a dispatch; it does not also claim one — "
            "pass --agent or --abandoned, not both[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if not abandoned and agent is None:
        err_console.print(
            "[red]--agent is required (or pass --abandoned to close without one)[/red]"
        )
        raise typer.Exit(2)
    if harness is not None and harness not in HARNESSES:
        err_console.print(f"[red]--harness must be one of {list(HARNESSES)}, got {harness!r}[/red]")
        raise typer.Exit(2)
    if open_unit and (step_id is not None or item is not None or abandoned):
        err_console.print(
            "[red]--open-unit finds the unit itself — it does not combine with "
            "--step, --item or --abandoned[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if open_unit and agent_type is None:
        err_console.print(
            "[red]--open-unit needs --agent-type: the agent a unit was dispatched to is "
            "what ties it to the child claiming it[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if not open_unit and (run_id is None or step_id is None):
        err_console.print("[red]fr run claim needs a run id and --step (or --open-unit)[/red]")
        raise typer.Exit(2)

    repo_root = resolve_repo_root()
    resolved_harness = harness
    if resolved_harness is None and not abandoned:
        try:
            resolved_harness = detect_harness(os.environ)
        except HarnessError as e:
            err_console.print(f"[red]{escape(str(e))}[/red]", soft_wrap=True)
            raise typer.Exit(2) from e
    if open_unit:
        assert agent is not None and agent_type is not None  # guarded above
        _claim_open_unit(
            repo_root,
            run_id,
            agent=agent,
            agent_type=agent_type,
            harness=resolved_harness,
            model=model,
        )
        return
    assert run_id is not None and step_id is not None  # guarded above
    try:
        state = _load_or_exit(repo_root, run_id)
        manifest = _resolve_manifest_for_state(repo_root, state)
        step, parent = _find_step(manifest, step_id)
        key = _unit_key(repo_root, state, step, parent, item)
    except (RunStateError, WorkflowError, AdoptError) as e:
        err_console.print(f"[red]{escape(str(e))}[/red]")
        raise typer.Exit(2) from e

    owner_id = parent.id if parent is not None else step.id
    if abandoned:
        _claim_abandon(repo_root, state, owner_id, key)
        return

    assert agent is not None  # guarded above: not abandoned => agent is required
    _claim_identity(
        repo_root,
        state,
        owner_id,
        key,
        agent=agent,
        harness=resolved_harness,
        model=model,
        agent_type=agent_type,
    )


def _open_dispatches(state: RunState) -> list[tuple[str, str, UnitAttempt]]:
    """Every currently-open `(step_id, key, attempt)` in `state` — see
    `fr.run.liveness.open_attempts`, where it moved so the idle reading and
    this report walk the same list."""
    return _liveness.open_attempts(state)


IDLE_EXIT_CODE = 3
"""`fr run check --idle` on an idle run. `check` used 0/1/2 before it; 3 is the
one code both harness adapters act on, and they act on nothing else."""


_IDLE_REPORT_ORDER: tuple[str, ...] = (
    "idle",
    "held",
    "gate",
    "manual",
    "failed",
    "not-advanceable",
    "finished",
)


def _plan_refusals(
    repo_root: Path, state: RunState, manifest: WorkflowManifest
) -> list[_liveness.Refusal]:
    """The reasons `advance` would refuse that only the plan ON DISK shows —
    the I/O half `fr.run.liveness.is_idle` (pure) is handed.

    Both are `_advance_group`'s own refusals, asked through its own functions:
    `_group_phases` (no plan recorded, or an unreadable one) and the
    manual-placement preflight, which `advance` runs exactly while the group
    has not started (`record.state != "running"`) — so this does too.
    """
    step = next((s for s in manifest.steps if s.id == state.cursor), None)
    record = state.steps.get(state.cursor)
    if step is None or record is None or step.kind != "agent" or not step.steps:
        return []
    try:
        _group_phases(repo_root, state)
    except (RunStateError, AdoptError) as e:
        return [_liveness.Refusal("not-advanceable", f"{step.id}: {e}")]
    if record.state == "running":
        return []
    _, messages = _manual_placement_errors(repo_root, state)
    return [_liveness.Refusal("manual", message) for message in messages]


def _idle_reading(repo_root: Path, state: RunState) -> _liveness.Idle:
    """`is_idle` for one run, with everything `advance` would refuse over
    folded in as *not idle* — an unresolvable or drifted manifest included.
    Never raises for a state `advance` would merely refuse."""
    try:
        manifest = _resolve_manifest_for_state(repo_root, state)
    except (RunStateError, WorkflowError, AdoptError) as e:
        return _liveness.Idle(False, "not-advanceable", str(e))
    return _liveness.is_idle(state, manifest, refusals=_plan_refusals(repo_root, state, manifest))


def _runs_on_this_branch(repo_root: Path) -> list[RunState]:
    """Every readable run whose `branch` is the one checked out here.

    `state.branch`, never "every file in the runs dir": a workspace is a
    checkout of `main` and carries every cursor merged and not yet archived
    (`_existing_run_for_workflow` learned this the hard way), and somebody
    else's advanceable cursor is nobody's stall. An unreadable file is
    skipped — it is a different problem, and `fr validate artifacts` reports
    it; here it must not become a reason to act, or to fail.
    """
    from fr.run.adopt import current_branch

    branch = current_branch(repo_root)
    runs_dir = repo_root / RUNS_REL
    if branch is None or not runs_dir.is_dir():
        return []
    found: list[RunState] = []
    for candidate in sorted(runs_dir.glob("*.yaml")):
        try:
            state = parse_run_state(candidate.read_text())
        except (RunStateError, OSError):
            continue
        if state.branch == branch:
            found.append(state)
    return found


def _stalled_payload(stalled: list[_liveness.StalledAttempt]) -> list[dict[str, Any]]:
    return [
        {
            "step": s.step,
            "unit": s.unit,
            "dispatched": s.attempt.dispatched,
            "age_minutes": s.age_minutes,
        }
        for s in stalled
    ]


def _stalled_line(s: _liveness.StalledAttempt) -> str:
    return (
        f"{s.step}: {s.unit} has been held for {_liveness.render_age(s.age_minutes)} "
        f"(dispatched {s.attempt.dispatched}) — reported, never failed: fr cannot "
        "tell a long phase from a dead agent"
    )


def _check_idle(repo_root: Path, run_id: str | None, stalled_after: int, fmt: str) -> None:
    """`fr run check --idle` — exit 3 exactly on an idle run (spec §4.G)."""
    if run_id is not None:
        candidates = [_load_or_exit(repo_root, run_id)]
    else:
        candidates = _runs_on_this_branch(repo_root)
    readings = [(state, _idle_reading(repo_root, state)) for state in candidates]
    idle = [(state, reading) for state, reading in readings if reading.idle]

    if not readings or len(idle) > 1:
        # No run at all is the sixth legitimate stop. MORE than one idle run on
        # a branch is a state fr-goal never produces (a stranded cursor is not
        # advanceable), so fr does not guess which one the session meant:
        # ambiguity is silence.
        reason = "ambiguous" if idle else "no-run"
        runs = [state.run for state, _ in idle]
        if fmt == "json":
            typer.echo(json.dumps({"idle": False, "reason": reason, "runs": runs}))
        elif idle:
            console.print(
                f"not idle (ambiguous) — {len(runs)} idle runs on this branch "
                f"({', '.join(runs)}); name one: fr run check <run> --idle",
                soft_wrap=True,
                markup=False,
            )
        else:
            console.print("not idle (no-run) — no run on this branch", markup=False)
        return

    # With nothing idle, REPORT the run most worth reading about: a branch can
    # carry a delivered run, a stranded one and the live one at once (this
    # feature's own branch did), and the held run is the one a human means.
    # Which is reported never changes the exit code — none of these is idle.
    state, reading = (
        idle[0]
        if idle
        else min(readings, key=lambda pair: _IDLE_REPORT_ORDER.index(pair[1].reason))
    )
    now = _dt.datetime.now(_dt.UTC)
    stalled = _liveness.stalled_attempts(state, now=now, after_minutes=stalled_after)
    next_command = f"fr run advance {state.run}" if reading.idle else None
    if fmt == "json":
        typer.echo(
            json.dumps(
                {
                    "idle": reading.idle,
                    "reason": reading.reason,
                    "detail": reading.detail,
                    "run": state.run,
                    "cursor": state.cursor,
                    "position": _liveness.position(state),
                    "next_command": next_command,
                    "stalled": _stalled_payload(stalled),
                }
            )
        )
    else:
        verdict = "idle" if reading.idle else f"not idle ({reading.reason})"
        console.print(f"{state.run}: {verdict} — {reading.detail}", soft_wrap=True, markup=False)
        for s in stalled:
            console.print(_stalled_line(s), soft_wrap=True, markup=False)
        if next_command is not None:
            console.print(f"  next: {next_command}", soft_wrap=True, markup=False)
    if reading.idle:
        raise typer.Exit(IDLE_EXIT_CODE)


@run_app.command("check")
def check_cmd(
    run_id: str | None = typer.Argument(
        None, help="Run id. Optional with --idle: the runs of the checked-out branch."
    ),
    idle: bool = typer.Option(
        False,
        "--idle",
        help="Liveness instead of freshness: exit 3, naming the next command, "
        "exactly when the run is advanceable and nobody is working on it. Exit 0 "
        "in every legitimate stop — a pending operator gate, an outstanding "
        "manual phase, a HELD unit, a failed step, a finished run, no run.",
    ),
    stalled_after: int = typer.Option(
        _liveness.DEFAULT_STALLED_AFTER_MINUTES,
        "--stalled-after",
        min=0,
        help="Report an open attempt older than this many minutes, with its age. "
        "Never a failure and never an exit code: fr cannot tell a long phase "
        "from a dead agent.",
    ),
    fmt: str = typer.Option("text", "--format", help="text | json (json: with --idle only)."),
) -> None:
    """Freshness gate: non-zero when the cursor sits on a failed step.

    It also REPORTS every operator gate the agent cleared itself (spec
    §3.D.3), every currently open dispatch, how many of those are unclaimed
    (spec §4.C), and any held past `--stalled-after` — none of it changes the
    exit code. The exit code stays exactly what it was: `check` is a narrow
    freshness gate, and making an open or unclaimed dispatch non-zero would
    turn every ordinary in-flight run red, which is the same hard-refusal
    shape the operator already rejected for an agent-cleared gate. The
    enforcement is that the same list rides the delivered PR body, where a
    human reads it.

    `--idle` asks the OTHER question (gh#518, spec
    2026-09-20-unit-record-unification §4.G) and owns exit code 3. It is what
    the Claude Code `Stop` hook and the OpenCode `session.idle` handler run;
    the answer is `fr.run.liveness.is_idle`'s and nobody else's.
    """
    if fmt not in ("text", "json"):
        err_console.print(f"[red]--format must be text or json, not {fmt!r}[/red]")
        raise typer.Exit(2)
    repo_root = resolve_repo_root()
    if idle:
        _check_idle(repo_root, run_id, stalled_after, fmt)
        return
    if fmt == "json":
        err_console.print("[red]--format json is only available with --idle[/red]")
        raise typer.Exit(2)
    if run_id is None:
        err_console.print(
            "[red]fr run check needs a run id (only --idle can find the run "
            "of the checked-out branch itself)[/red]"
        )
        raise typer.Exit(2)
    state = _load_or_exit(repo_root, run_id)
    try:
        _resolve_manifest_for_read(repo_root, state)  # warns once on a drifted cursor
    except (RunStateError, WorkflowError):
        pass  # check's verdict never depended on the manifest resolving

    record = state.steps.get(state.cursor)
    step_state = record.state if record is not None else "unknown"
    console.print(f"{state.run}: cursor={state.cursor} ({step_state})")
    for gate in cleared_gates(state):
        # An observed operator answer is the gate working — nothing to report.
        # An agent clearance, or an operator answer fr only has the caller's
        # word for (R11, p3-r2), is reported in the sentence `gates` prints.
        if gate.by_agent:
            line = _agent_clearance(gate.unobserved)
        elif gate.unobserved:
            line = _operator_answer(unobserved=True)
        else:
            continue
        # soft_wrap: this line is read for the step id it names, and rich
        # would fold a long id across a line break at a narrow width.
        console.print(f"{gate.step}: operator gate {line}", soft_wrap=True)
    open_dispatches = _open_dispatches(state)
    for step_id, key, held in open_dispatches:
        console.print(
            f"{step_id}: {key} is open — {_render_dispatch_attempt(held)}",
            soft_wrap=True,
        )
    unclaimed = [
        held for _, _, held in open_dispatches if held.agent_type is not None and held.agent is None
    ]
    if unclaimed:
        console.print(
            f"{len(unclaimed)} unclaimed dispatch(es) — visible debt, not a failure",
            soft_wrap=True,
        )
    # Stalled (§4.G): gh#503's 11.5-hour executor, visible from fr instead of
    # from the harness's private files. A report and nothing more.
    for stalled in _liveness.stalled_attempts(
        state, now=_dt.datetime.now(_dt.UTC), after_minutes=stalled_after
    ):
        console.print(_stalled_line(stalled), soft_wrap=True, markup=False)
    # Reviews resolved before the evidence gate existed (§4.E). Reported, never
    # failed, and deliberately NOT part of the exit code below: an obligation
    # cannot be enforced backwards in time, and doing so here would turn every
    # in-flight run red on the day the plugin updates.
    for (step_id, key), lacking in _unevidenced_units(repo_root, state).items():
        console.print(
            f"{step_id}: {key} is done, {_debt_phrase(state.steps[step_id], key, lacking)}",
            soft_wrap=True,
        )
    # R9: a review made before this cursor existed — reported, never debt.
    for step_id, key, entry in historical_reviews(state):
        console.print(f"{step_id}: {key} {historical_sentence(entry)}", soft_wrap=True)
    if record is not None and record.state == "failed":
        err_console.print(f"[red]{state.cursor}: failed[/red]")
        raise typer.Exit(1)


def _agent_clearance(unobserved: bool) -> str:
    """One sentence for an `agent` clearance, shared by `check` and `gates`
    (R11): an observed one says no operator answered; an unobserved one says
    only that the agent claimed it and fr could not read the truth."""
    if unobserved:
        return "cleared by the agent, as claimed — unobserved: fr could not read who answered"
    return "cleared by the agent (answered_by: agent) — no operator answered it"


def _operator_answer(unobserved: bool) -> str:
    """One sentence for an `operator` answer, shared by `check` and `gates`
    (R11, p3-r2): an unobserved one is the caller's claim, and says so."""
    return "answered by the operator" + (", as claimed — unobserved" if unobserved else "")


@run_app.command("gates")
def gates_cmd(run_id: str = typer.Argument(..., help="Run id.")) -> None:
    """Every `gate: operator` step this run's manifest declares, and who
    cleared it — the source `fr-goal`'s `deliver` step reads for the PR
    body's "Operator gates" section (spec §3.D.3, review r4-i2).

    NEVER prints nothing: a workflow with no operator gates says so
    explicitly, and a step whose cursor predates `answered_by` (this
    feature's own OpenCode run, or any `fr run adopt` cursor) says THAT
    explicitly too — both `cleared_gates()`-only readings would have
    rendered blank here, which on a delivered PR reads as "the feature
    never ran".
    """
    repo_root = resolve_repo_root()
    try:
        state = _load_or_exit(repo_root, run_id)
        manifest = _resolve_manifest_for_read(repo_root, state)
    except (RunStateError, WorkflowError, AdoptError) as e:
        err_console.print(f"[red]{escape(str(e))}[/red]", soft_wrap=True)
        raise typer.Exit(2) from e

    statuses = gates(state, manifest)
    if not statuses:
        console.print(f"{state.run}: no `gate: operator` steps recorded as cleared")
        return
    for status in statuses:
        if status.outcome == "recorded" and status.answered_by == "agent":
            # The same sentence `fr run check` prints (review r5-m3). This is
            # the surface that rides the delivered PR body, so the case a human
            # most needs to notice must not be the tersest line on the page —
            # "cleared by agent" alone reads as bookkeeping, not as a warning.
            console.print(
                f"{status.step}: operator gate {_agent_clearance(status.unobserved)}",
                soft_wrap=True,
            )
        elif status.outcome == "recorded":
            console.print(
                f"{status.step}: operator gate {_operator_answer(status.unobserved)}",
                soft_wrap=True,
            )
        else:
            console.print(
                f"{status.step}: cleared, but provenance not recorded "
                "(this cursor predates `answered_by`)",
                soft_wrap=True,
            )
