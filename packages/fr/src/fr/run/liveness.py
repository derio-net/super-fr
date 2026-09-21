"""Liveness — is anybody working on this run? Spec
`2026-09-20-unit-record-unification-design.md` §4.G, the artifact half of
gh#518.

*"Keep going" was an obligation with no enforcing artifact.* A run whose cursor
was ready — `fr run advance` would have printed the next brief immediately —
looked exactly like a run still working, until a human noticed the wall clock.
This module draws that one line, twice:

- **idle** (`is_idle`) — the run is *advanceable and nobody is working on it*.
  `fr run check --idle` exits 3 on it; the Claude Code `Stop` hook
  (`fr-run-idle-guard.sh`) and the OpenCode `session.idle` handler both ask
  that command and **neither re-derives the answer**. A harness adapter holds
  no opinion about cursors: it holds a session, a working directory, and the
  position it last acted on.
- **stalled** (`stalled_attempts`) — an open attempt older than a threshold.
  REPORTED, never failed: fr cannot tell a long phase from a dead agent.

**The bias is deliberate and one-directional.** A false "idle" is not a wrong
report — it is a hook refusing to let an operator end a turn, the worst outcome
this feature can have. A false "not idle" costs one missed nudge. So every
state this module does not positively recognise as advanceable is NOT idle,
and the legitimate stops (a pending operator gate, an outstanding manual phase,
a HELD unit, a failed step, a finished run) are each named rather than falling
out of a general rule.

It also owns the three small predicates `advance` and the idle reading must
agree on — `gate_pending`, `next_step_id` and `hold_on` — moved here from
`fr.commands.run_cmd` (which re-imports them under their old private names) so
that "would `advance` refuse this?" has one definition, not a CLI's and a
guard's.

Pure: nothing here touches a disk, a clock or the environment. What only the
plan on disk can show — `advance`'s manual-placement preflight, an unreadable
plan — arrives as `refusals`, computed by the caller.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, NamedTuple

from fr.run import units
from fr.run.model import RunState, StepRecord
from fr.run.units import UnitAttempt
from fr.workflow.model import Step, WorkflowManifest

__all__ = [
    "DEFAULT_STALLED_AFTER_MINUTES",
    "Hold",
    "Idle",
    "IdleReason",
    "Refusal",
    "StalledAttempt",
    "flat_unit_key",
    "gate_pending",
    "hold_on",
    "is_idle",
    "next_step_id",
    "open_attempts",
    "position",
    "render_age",
    "stalled_attempts",
]

DEFAULT_STALLED_AFTER_MINUTES = 120
"""Two hours. A phase of the run that built this took a legitimate 58 minutes;
gh#503's dead executor sat for 690. The default has to clear the first by a wide
margin, and the operator can move it (`--stalled-after`)."""


def next_step_id(manifest: WorkflowManifest, step_id: str) -> str | None:
    ids = [s.id for s in manifest.steps]
    idx = ids.index(step_id)
    return ids[idx + 1] if idx + 1 < len(ids) else None


def gate_pending(step: Step, record: StepRecord) -> bool:
    """Is this step still waiting on its operator gate?

    A gate is answered by `fr run resolve` (which records `gate: cleared`),
    not by the step's lifecycle state — spec §4.A: "a pause. The step ends
    the turn and the run does not advance until the operator answers."
    """
    return step.gate == "operator" and record.gate != "cleared" and record.state != "done"


def flat_unit_key(step_id: str) -> str:
    """The unit key of a flat `kind: agent` step (spec §4.B) — spelled once."""
    return f"step/{step_id}"


class Hold(NamedTuple):
    """Why `advance` will not brief a unit again (`hold_on`)."""

    holder: UnitAttempt | None
    """The open record — or `None` for a unit that is `running` with no
    record at all, where there is a hold to respect but nobody to name."""


def hold_on(record: StepRecord, key: str, *, running: bool) -> Hold | None:
    """Is `key` held — must `advance` refuse to brief it again? Decision u1
    (spec 2026-09-20-unit-record-unification §4.C), and the ONLY function
    that answers it; both refusal call sites AND the idle reading ask here and
    nowhere else.

    **The dispatch record is the witness.** A unit is held iff its last record
    is open (`units.open_attempt`). `running` is deliberately NOT part of that
    answer: `fr run claim --abandoned` closes the record and leaves the unit
    `running` on purpose, so a refusal keyed on state never lifts and a lost
    executor can never be re-briefed — the defect gh#508 and gh#519 produced
    between them by each building this refusal off a different map.

    **`running` is consulted in exactly one case: there is no record at
    all.** A cursor written before the record existed (`run` 2 -> 3 -> 4 are
    stamp-only migrations) or adopted from disk has running units with no
    attempts. No witness is not the same as a witness saying "free", so there
    gh#519's state-based refusal stands, and the caller words it `ALREADY
    RUNNING (dispatched <at>)` because there is no holder to name. A unit
    with ANY record, even a closed one, never reaches this branch. (An attempt
    the 4 -> 5 migration SYNTHESIZED to carry an old cost snapshot is not a
    record in this sense — `units.dispatch_recorded` — so a migrated in-flight
    cursor is refused, and retried, exactly as it was the day before.)
    """
    held = units.open_attempt(record, key)
    if held is not None:
        return Hold(held)
    never_recorded = not units.dispatch_recorded(record, key)
    return Hold(None) if running and never_recorded else None


def open_attempts(state: RunState) -> list[tuple[str, str, UnitAttempt]]:
    """Every currently-open `(step_id, key, attempt)` in `state`, steps in
    cursor order and keys sorted within a step.

    `units.open_attempt` is the one notion of "is this unit held"; this only
    walks it. A `synthesized` attempt is never open (it skips them)."""
    found: list[tuple[str, str, UnitAttempt]] = []
    for step_id, record in state.steps.items():
        for key in units.unit_keys(record):
            held = units.open_attempt(record, key)
            if held is not None:
                found.append((step_id, key, held))
    return found


# ---------------------------------------------------------------------------
# idle
# ---------------------------------------------------------------------------

IdleReason = Literal[
    "idle",
    "gate",
    "manual",
    "held",
    "failed",
    "finished",
    "not-advanceable",
]
"""`idle` is the ONLY value that means "act". Everything else is a stop an
adapter must stay silent on; they are told apart for the human reading
`fr run check --idle`, never for the adapters."""


class Refusal(NamedTuple):
    """A reason `advance` would refuse that only the plan ON DISK can show.

    `is_idle` is pure, so the caller reads the plan and hands the verdicts in:
    `manual` for `advance`'s manual-placement preflight (a front-loaded manual
    phase the operator has not given the go for), `not-advanceable` for a plan
    that is missing or unreadable. Both mean the same thing to an adapter."""

    reason: Literal["manual", "not-advanceable"]
    detail: str


@dataclass(frozen=True)
class Idle:
    """The idle reading of one run."""

    idle: bool
    reason: IdleReason
    detail: str


def _stop(reason: IdleReason, detail: str) -> Idle:
    return Idle(False, reason, detail)


def is_idle(
    state: RunState,
    manifest: WorkflowManifest,
    *,
    refusals: Sequence[Refusal] = (),
) -> Idle:
    """Is this run *advanceable, with nobody working on it*?

    THE predicate (§4.G). `fr run check --idle` is its only caller in `fr`,
    and both harness adapters call THAT — so there is one definition of
    "idle", in one language, and a bug in it is fixed once.

    It mirrors `fr run advance` branch for branch, because "idle" is precisely
    "`advance` would do something and nobody has asked it to": wherever
    `advance` refuses or has nothing to do, this says *not idle*. The order is
    `advance`'s own, except that every HOLD is checked before the plan-level
    refusals — a held run is healthy, and should be reported as such whatever
    else is true of it.
    """
    step = next((s for s in manifest.steps if s.id == state.cursor), None)
    record = state.steps.get(state.cursor)
    if step is None or record is None:
        return _stop(
            "not-advanceable",
            f"cursor {state.cursor!r} has no step or no record under this workflow",
        )

    # 4. A failed step — or a failed unit of it. `advance` WOULD retry, which
    # is exactly why this is a named stop and not left to the rule: deciding to
    # retry a failure is a judgment, and a guard must not make it by reflex.
    failed = sorted(k for k, v in units.unit_states(record).items() if v == "failed")
    if record.state == "failed" or failed:
        subject = failed[0] if failed else state.cursor
        return _stop("failed", f"{subject} failed — a failure is a stop, never a stall")

    if record.state == "done":
        if next_step_id(manifest, state.cursor) is None:
            return _stop("finished", f"the run is complete — {state.cursor!r} is done")
        return _stop(
            "not-advanceable",
            f"{state.cursor!r} is done but the cursor never moved past it",
        )

    # 1. A pending operator gate — asked (`blocked`) or not yet (`pending`).
    if gate_pending(step, record):
        return _stop("gate", f"{state.cursor} waits on its operator gate")

    # 3. A HELD unit. On Claude Code a dispatched executor runs in the
    # background and its return arrives as a notification, so a turn that ends
    # while anything is held is CORRECT. Anywhere in the cursor, not only under
    # the cursor step: an open attempt is somebody working.
    for step_id, key, _ in open_attempts(state):
        return _stop("held", f"{step_id}: {key} is held — somebody is working")
    # ... and `hold_on`'s recordless fallback, the same question `advance`
    # asks: a `running` unit with no witness at all is refused there (ALREADY
    # RUNNING), so it is not advanceable here.
    if step.kind == "agent":
        if step.steps:
            running = sorted(k for k, v in units.unit_states(record).items() if v == "running")
        else:
            running = [flat_unit_key(step.id)] if record.state == "running" else []
        for key in running:
            if hold_on(record, key, running=True) is not None:
                return _stop("held", f"{key} is running with no dispatch record — not re-briefable")
    elif record.state != "pending":
        # A `cli` step is executed inline and is never `running`; a cleared
        # gate returns it to `pending`. Anything else is a state this module
        # does not recognise, and unrecognised is not idle.
        return _stop("not-advanceable", f"{state.cursor} is a cli step in state {record.state!r}")

    # 2. What only the plan on disk shows — handed in, never read here.
    for refusal in refusals:
        return _stop(refusal.reason, refusal.detail)

    return Idle(True, "idle", f"{state.cursor} is advanceable and nobody is working on it")


def position(state: RunState) -> str:
    """An opaque token for WHERE the run is — the loop breaker's key (§4.G).

    Both adapters act at most once per position, so it must hold still while
    nothing moves and move when anything does: the cursor, the cursor step's
    state, every unit's state under it, and how many attempts each unit has
    (a re-dispatch that was abandoned again is movement). No timestamp enters
    it — a failing `advance` that only re-stamps a record must not look like
    progress, because "advance keeps failing" is the trap this exists for.
    """
    record = state.steps.get(state.cursor)
    facts: dict[str, object] = {"run": state.run, "cursor": state.cursor}
    if record is not None:
        facts["state"] = record.state
        facts["gate"] = record.gate
        facts["units"] = {
            key: [units.unit_state(record, key), len(units.attempts(record, key))]
            for key in units.unit_keys(record)
        }
    digest = hashlib.sha256(json.dumps(facts, sort_keys=True, default=str).encode())
    return digest.hexdigest()[:16]


# ---------------------------------------------------------------------------
# stalled
# ---------------------------------------------------------------------------


class StalledAttempt(NamedTuple):
    step: str
    unit: str
    attempt: UnitAttempt
    age_minutes: int


def _parse_instant(text: str) -> _dt.datetime | None:
    try:
        parsed = _dt.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=_dt.UTC)


def stalled_attempts(
    state: RunState, *, now: _dt.datetime, after_minutes: int
) -> list[StalledAttempt]:
    """Every open attempt dispatched more than `after_minutes` ago.

    A report, and only a report. A `dispatched` fr cannot parse is skipped
    rather than raised: this rides `fr run check`, and a liveness footnote must
    never be what turns a freshness gate into an error."""
    found: list[StalledAttempt] = []
    for step_id, key, attempt in open_attempts(state):
        since = _parse_instant(attempt.dispatched)
        if since is None:
            continue
        age = int((now - since).total_seconds() // 60)
        if age > after_minutes:
            found.append(StalledAttempt(step_id, key, attempt, age))
    return found


def render_age(minutes: int) -> str:
    """`58m`, `11h30m`, `2d03h` — coarse on purpose; this is a nudge to look."""
    if minutes < 60:
        return f"{minutes}m"
    hours, mins = divmod(minutes, 60)
    if hours < 48:
        return f"{hours}h{mins:02d}m"
    days, hours = divmod(hours, 24)
    return f"{days}d{hours:02d}h"
