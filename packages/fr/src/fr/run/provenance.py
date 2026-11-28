"""Reading gate provenance off a run cursor — spec §3.D.3, widened in Phase 5
(review r4-i2) to also read the WORKFLOW MANIFEST.

Two surfaces report the same thing: `fr run check` (informational, exit code
unchanged) and, from phase 5, fr-goal's `deliver` step (`fr run gates`), which
puts the list in the PR body under an "Operator gates" heading. They must not
be able to disagree about what counts as agent-cleared, so neither of them
reads `StepRecord.answered_by` itself — both call in here.

**What counts as a cleared gate is `answered_by`, not `gate`.** The two
branches of `fr run resolve` record differently: clearing a `cli` step's gate
writes `gate: cleared` and returns the step to `pending`, while a gated
`agent` step goes straight to `done` through `fr.run.steps.complete_step`, which writes no
`gate` at all. `answered_by` is written on *both* paths and on no other, so it
is the one field that means "a gate was cleared here" whatever kind of step it
was — and the gated agent step is precisely the shape of the measured failure
(spec §1), so a reader keyed on `gate` would have missed it.

**Why `gates()` reads the manifest too (r4-i2).** `cleared_gates`/
`agent_cleared_gates` read `RunState` alone, so they cannot tell "this run has
no gates" apart from "this run HAS a gate whose provenance predates
`answered_by`" — both read as empty. Verified live on this very feature's own
run cursor: `brainstorm` IS `gate: operator` in the shipped manifest and WAS
cleared by the operator, before the field existed, and `cleared_gates()`
returns `()` regardless. Only the manifest knows a gate was DECLARED at all,
so `gates()` takes it as a second argument and can render "provenance not
recorded" instead of nothing — nothing, on a PR body, reads as "the feature
never ran", this repo's signature failure mode. The same gap applies to a run
built by `fr run adopt`: it marks prior steps `done` with no `gate` and no
`answered_by` either, for the same underlying reason (the field did not exist
when the work happened) — `gates()` reports that run the same "unrecorded"
way, not as "no gates fired".

**Deriving a gate's provenance (spec 2026-11-27-run-verdict R8).** The other half of the
module is how a resolve OBSERVES who answered a gate: `gate_degradation_notice`,
`derive_gate_answer`, `gate_provenance` and the queue of spec-journal decisions it makes
(`GATE_DECISIONS`, flushed once the resolve's last refusal has passed). Refusals raise
`RunRefusal` and warnings go through the caller's `warn`; a gate that cannot observe notes
itself in `fr.run.unobserved`. No `typer`, no console.
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NoReturn

from fr.harness import HARNESSES, load_matrix
from fr.harness.detect import detect_harness
from fr.journal.model import (
    JournalEntry,
    JournalParseError,
    journal_now,
    parse_journal,
    spec_journal_slug,
)
from fr.run.model import AnsweredBy, RunState, StepRecord
from fr.run.unobserved import note_unobserved, why_unobservable
from fr.run.verdict import RunRefusal, Say, Warn
from fr.run.writes import note_record_write, remember
from fr.workflow.artifacts import emitted_artifacts
from fr.workflow.model import Step, WorkflowManifest

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from fr.record.model import QuestionRounds
    from fr.run.telemetry import Round


@dataclass(frozen=True)
class ClearedGate:
    """One gate this run records as cleared, and who cleared it.

    `at` is the record's LAST WRITE, not the moment the gate was answered
    (review r4-m2). On the `cli` path the gate is cleared, the step returns to
    `pending`, and the next `advance` executes it — `fr.run.steps.complete_step` then
    overwrites `at`, so what survives is the execution time. Render it as "last
    write to this record" or not at all; do not present it as when a human
    answered, which is a claim this field cannot support."""

    step: str
    answered_by: AnsweredBy
    at: str | None = None
    unobserved: bool = False
    """The step's evidence says fr could not read who answered (`unobserved`
    names `operator-gate`): `answered_by` is a claim, not an observation."""

    @property
    def by_agent(self) -> bool:
        return self.answered_by == "agent"


def gate_unobserved(record: StepRecord) -> bool:
    """Did the resolve that cleared this step's gate note `operator-gate` as
    unobserved? Read off the step's units' evidence (R11)."""
    for unit in (record.units or {}).values():
        found = (unit.evidence or {}).get("unobserved", "")
        if "operator-gate" in found.split(","):
            return True
    return False


def cleared_gates(state: RunState) -> tuple[ClearedGate, ...]:
    """Every gate `state` records as cleared, in step order.

    Step order, not resolution order: `RunState.steps` is built from the
    manifest, so this reads down the run the way the operator reads it.
    """
    return tuple(
        ClearedGate(
            step=step_id,
            answered_by=record.answered_by,
            at=record.at,
            unobserved=gate_unobserved(record),
        )
        for step_id, record in state.steps.items()
        if record.answered_by is not None
    )


def agent_cleared_gates(state: RunState) -> tuple[ClearedGate, ...]:
    """The gates no operator answered — what both surfaces actually report."""
    return tuple(gate for gate in cleared_gates(state) if gate.by_agent)


GateOutcome = Literal["recorded", "unrecorded"]
"""What `gates()` knows about one manifest-declared `gate: operator` step
that this cursor shows as cleared. A step the cursor has not reached yet
(no record, or a record still `pending`/`blocked`) is left OUT of the
result entirely — `gates()` reports what happened, not what has not."""


@dataclass(frozen=True)
class GateStatus:
    """One `gate: operator` step the MANIFEST declares, and what this
    cursor's record shows about it being cleared.

    `recorded` means `answered_by` is set — the same fact `ClearedGate`
    carries. `unrecorded` means the record shows the gate WAS cleared (`cli`
    path: `gate == "cleared"`; `agent` path: `state == "done"`, since that
    branch never writes `gate` at all) but `answered_by` is `None` — a
    cursor written before the field existed, or an `fr run adopt` cursor
    that marked the step `done` with no gate history to read. Distinct from
    a step this run has not reached, which never appears here at all."""

    step: str
    outcome: GateOutcome
    answered_by: AnsweredBy | None = None
    at: str | None = None
    unobserved: bool = False


def _gated_steps(steps: tuple[Step, ...]) -> tuple[Step, ...]:
    """The TOP-LEVEL steps declaring `gate: operator`.

    Deliberately not flattened into `for_each` members, and the docstring that
    claimed otherwise was wrong (review r5-i2). A member step never has a
    `StepRecord`: both builders key `RunState.steps` on top-level ids only
    (`run_cmd.py`'s `{s.id: StepRecord(...) for s in manifest.steps}` and the
    identical comprehension in `adopt.py`), and member progress lives in the
    group's own UNITS (`fr.run.units`) under `phase/<n>/<member>`. So a walk
    that descended
    into members could only ever look up records that do not exist — and the
    test covering it passed solely because it hand-built a member-keyed state no
    fr code path writes. A green test over an impossible state is worse than no
    test.

    Member gates are also unenforced upstream: `_advance_group` never consults
    `member.gate`, so nothing blocks on one either. Modelling them means giving
    members records and teaching `_advance_group` to honour the gate — a real
    change, not a walk. Until then this says what is true."""
    return tuple(step for step in steps if step.gate == "operator")


def gates(state: RunState, manifest: WorkflowManifest) -> tuple[GateStatus, ...]:
    """Every `gate: operator` step `manifest` declares that this cursor shows
    as cleared, in manifest step order — recorded or not (r4-i2).

    Reading the manifest is what lets this tell "no gate exists here" apart
    from "a gate existed and was cleared before `answered_by` existed": a
    step `RunState` alone cannot distinguish (`cleared_gates` above cannot
    either, for exactly that reason)."""
    statuses: list[GateStatus] = []
    for step in _gated_steps(manifest.steps):
        record = state.steps.get(step.id)
        if record is None:
            continue
        if record.answered_by is not None:
            statuses.append(
                GateStatus(
                    step=step.id,
                    outcome="recorded",
                    answered_by=record.answered_by,
                    at=record.at,
                    unobserved=gate_unobserved(record),
                )
            )
            continue
        cleared = record.gate == "cleared" or record.state == "done"
        if cleared:
            statuses.append(GateStatus(step=step.id, outcome="unrecorded", at=record.at))
    return tuple(statuses)


# --- the operator gate's provenance (moved from run_cmd by spec 2026-11-27-run-verdict R8) ---


def gate_degradation_notice() -> str | None:
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


def refuse_gate_flags(step_id: str) -> NoReturn:
    """Gate flags on a resolve that clears no gate — refused, because silently
    ignored flags read as honoured ones (review r1-7)."""
    raise RunRefusal(
        (
            Say(
                f"[red]{step_id}: --no-questions/--reason and question rounds only apply to a "
                "resolve that clears an operator gate, and this one clears none.[/red]",
                soft_wrap=True,
            ),
        )
    )


def clears_gate(step: Step, record: StepRecord, outcome: str) -> bool:
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


# gh#690: a gate DECIDES in `gate_provenance` but its spec-journal decision
# is only QUEUED there, and written by `flush_gate_decisions` immediately
# before the resolve saves the cursor — after every refusal point. Written at
# decision time, a later refusal left the entry behind, and the command's
# closing commit (which keeps every noted write, on every exit path) recorded a
# decision the cursor never did.

GATE_DECISIONS: ContextVar[list[tuple[Path, str, JournalEntry]] | None] = ContextVar(
    "fr_gate_decisions", default=None
)


def queue_gate_decision(
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
        raise RunRefusal(
            (
                Say(
                    f"journal entry `{entry_id}` in {shown} already records a different body "
                    f"({existing.body.strip()!r}) than this resolve would write "
                    f"({body.strip()!r}). "
                    "Resolve again with what that entry says, or correct the entry first if it is "
                    "the one that is wrong — nothing applied.",
                    markup=False,
                    soft_wrap=True,
                    style="red",
                ),
            )
        )
    queued = GATE_DECISIONS.get()
    if queued is None:
        queued = []
        GATE_DECISIONS.set(queued)
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


def flush_gate_decisions(repo_root: Path) -> None:
    """Write every queued gate decision — called by each `resolve` branch
    immediately before it saves the cursor, so nothing after it can refuse."""
    from fr.journal.model import append_journal_entry

    queued = GATE_DECISIONS.get() or []
    GATE_DECISIONS.set(None)
    for target, slug, entry in queued:
        remember(target)
        append_journal_entry(target, slug, entry)
        note_record_write(repo_root, target)


def observed_gate_rounds(record: StepRecord) -> list[Round] | None:
    """The answered question rounds since this gate blocked (`record.at`), or
    `None` where fr cannot read them — THE observation `gate_provenance` and
    `derive_gate_answer` share, so the two cannot disagree."""
    from fr.run.telemetry import answered_rounds_since

    return answered_rounds_since(os.environ, record.at) if record.at else None


@dataclass(frozen=True)
class GateAnswer:
    """Who answered an operator gate, as `gate_provenance` derives it (spec
    2026-10-14 R12): `who` is `operator`, `agent` or `None` (a gate it refuses);
    `observed` says the transcript was read; `rounds` are the answered rounds."""

    who: str | None
    observed: bool
    rounds: tuple[Round, ...] = ()


def derive_gate_answer(
    record: StepRecord, *, no_questions: bool, claimed: str | None
) -> GateAnswer:
    """The answer `gate_provenance` records, without its refusals or writes:
    `--no-questions` → agent; answered rounds observed → operator; observed and
    none → `None` (the gate refuses); not observable → the claim, unverified."""
    if no_questions:
        return GateAnswer("agent", observed=False)
    rounds = observed_gate_rounds(record)
    if rounds is None:
        return GateAnswer(claimed if claimed in ("operator", "agent") else None, observed=False)
    return GateAnswer("operator" if rounds else None, observed=True, rounds=tuple(rounds))


def gate_provenance(
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
    warn: Warn,
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
    if no_questions and not (reason and reason.strip()):
        raise RunRefusal(
            (
                Say(
                    f'[red]{step_id}: --no-questions needs --reason "…" — clearing an operator '
                    "gate without asking is allowed, but only on the record.[/red]",
                    soft_wrap=True,
                ),
            )
        )
    # Review r1-5: "on the record" means a journal the PR body reads — the spec
    # this resolve emits, else one an earlier step already emitted. With
    # neither there is nowhere durable for the reason, so the bypass is refused
    # rather than printed to a stderr nobody keeps.
    spec_for_reason = emitted.get("spec") or next(
        (r.emitted["spec"] for r in state.steps.values() if r.emitted and "spec" in r.emitted),
        None,
    )
    if no_questions and not (spec_for_reason and spec_for_reason.endswith(".md")):
        raise RunRefusal(
            (
                Say(
                    f"[red]{step_id}: --no-questions has nowhere to record its reason — this "
                    "resolve emits no spec and the run has none yet. Pass the spec with "
                    "`--emitted spec=<path>`, or ask the operator.[/red]",
                    soft_wrap=True,
                ),
            )
        )
    round_two = questions is not None and questions.rounds == 2
    if round_two and not (spec_for_reason and spec_for_reason.endswith(".md")):
        raise RunRefusal(
            (
                Say(
                    f"[red]{step_id}: a second question round has nowhere to record its reason — "
                    "this resolve emits no spec and the run has none yet. Pass the spec with "
                    "`--emitted spec=<path>` (or `emitted: {spec: <path>}` in the record).[/red]",
                    soft_wrap=True,
                ),
            )
        )
    rounds = observed_gate_rounds(record)
    observed = None if rounds is None else bool(rounds)
    if observed is True and not no_questions:
        assert rounds is not None
        # gh#761: standalone fr-brainstorming asks one question per turn, so
        # every question is a round to the transcript; the cap is fr-goal's.
        refusal = (
            None if state.driver == "standalone" else question_rounds_refusal(rounds, questions)
        )
        if refusal is not None:
            raise RunRefusal(
                (Say(f"{step_id}: {refusal}", markup=False, soft_wrap=True, style="red"),)
            )
        record_round_two(repo_root, step_id, questions, spec_for_reason)
        return "operator"
    if observed is False and not no_questions:
        raise RunRefusal(
            (
                Say(
                    f"[red]{step_id}: no answered question in this session's transcript since "
                    f"the gate blocked at {record.at}. Put the questions to the operator with "
                    "your harness's question tool (AskUserQuestion on Claude Code) and resolve "
                    "again once they answer — or clear it without asking, on the record: "
                    f'`--no-questions --reason "<why no operator decision was needed>"`.[/red]',
                    soft_wrap=True,
                ),
            )
        )
    if no_questions:
        assert spec_for_reason is not None  # refused above otherwise
        queue_gate_decision(
            repo_root,
            spec_for_reason,
            f"gate-no-questions-{step_id}",
            title=f"Operator gate `{step_id}` cleared without asking",
            body=reason or "",
        )
        warn(
            Say(
                f"[yellow]{step_id}: operator gate cleared WITHOUT asking (answered_by: "
                f"agent). Reason: {reason}[/yellow]",
                soft_wrap=True,
            )
        )
        return "agent"
    if claimed is None:
        # R10 (spec 2026-10-02 §F): there is no default. An unobserved gate with
        # no claim is a question fr cannot answer for the caller, so it asks.
        raise RunRefusal(
            (
                Say(
                    f"[red]{step_id}: could not verify who answered this gate "
                    f"({why_unobservable('questions')}) — pass `answered_by: operator` "
                    "(the operator answered) or `answered_by: agent` (cleared without asking): "
                    "`--answered-by operator|agent` on the flag form, "
                    "`evidence: {answered_by: …}` in a record.[/red]",
                    soft_wrap=True,
                ),
            )
        )
    # Wherever the gate cannot observe — no harness, an unreadable Claude Code
    # transcript, OpenCode without a session id (OPENCODE_SESSION_ID),
    # or with an unreadable store, or Hermes, which has no question reader —
    # it says so on the record (§5.B.7, p2-r28); `advance` already printed the
    # degradation notice there, which is no reason to be quiet now.
    note_unobserved("operator-gate")
    record_round_two(repo_root, step_id, questions, spec_for_reason)
    # p2-r2: only `rounds: 2` writes anything (`record_round_two`); `rounds: 1`
    # is the default and is merely accepted.
    if questions is None:
        declared = ""
    elif questions.rounds == 2:
        declared = " The declared `questions: {rounds: 2}` is recorded as claimed too."
    else:
        declared = (
            f" The declared `questions: {{rounds: {questions.rounds}}}` is accepted, unverified."
        )
    warn(
        Say(
            f"[yellow]{step_id}: could not verify this gate — {why_unobservable('questions')}, "
            f"so `answered_by: {claimed}` is recorded as claimed, unverified "
            f"(evidence: unobserved=operator-gate).{declared}[/yellow]",
            soft_wrap=True,
        )
    )
    return claimed


def record_round_two(
    repo_root: Path, step_id: str, questions: QuestionRounds | None, spec: str | None
) -> None:
    """A cleared gate that took two question rounds says so on the spec journal
    (spec 2026-09-26 §3.C) — where the PR body reads it. `rounds: 1` is the
    default and writes nothing."""
    if questions is None or questions.rounds != 2:
        return
    assert spec is not None  # refused before observation otherwise
    queue_gate_decision(
        repo_root,
        spec,
        f"gate-question-rounds-{step_id}",
        title=f"Operator gate `{step_id}` took two question rounds",
        body=f"Trigger: {questions.trigger}. {questions.reason}",
    )


def refuse_missing_emits(
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
    raise RunRefusal(
        (
            Say(
                f"{label}: done without the artifact(s) it declares: {', '.join(missing)}. "
                f"Name them — `{flags}`, or `emitted:` in the record — and resolve again; "
                "nothing applied.",
                markup=False,
                soft_wrap=True,
                style="red",
            ),
        )
    )
