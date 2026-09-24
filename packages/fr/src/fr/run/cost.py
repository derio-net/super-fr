"""What a run cost, step by step — the rows behind `fr run cost` (spec
`2026-09-24-fr-goal-scope-proportion-cost-design.md` §D, gh#593's table).

Pure functions over a `RunState`: no I/O, no rendering, so the numbers are
testable without a terminal and the command stays a thin printer.

Two sources, never mixed:

- **the main session** — `StepRecord.main_session`, one row per top-level
  step. Absent is `None` in every cell, printed as `—`: a step nobody could
  measure is not a step that cost nothing (gh#514).
- **subagents** — every attempt's `measured`, summed on one line. Read per
  ATTEMPT, never per unit (`tests/unit/test_tripwire_per_unit_cost_reads.py`),
  so a redispatched unit's abandoned attempt still counts.

**Possibly over-counted.** Until the per-message dedupe
(`fr.run.telemetry._distinct_messages`) a subagent measurement summed every
transcript RECORD, and Claude Code writes one record per content block, each
repeating the whole message's usage. Recorded values are history and are not
rewritten, so this module flags them instead. The dedupe shipped in the same
release as main-session measurement, so the run's own cursor dates it: a
measured attempt that returned before the run's FIRST main-session
measurement was taken by an older fr. The rule is conservative — a run whose
main session could not be measured at all flags every measurement — because
"possibly" is the honest word for a figure fr cannot vouch for.
"""

from __future__ import annotations

from dataclasses import dataclass

from fr.run.model import MeasuredTokens, RunState
from fr.run.telemetry import parse_timestamp

__all__ = ["CostRow", "SubagentTotal", "cost_rows", "possibly_over_counted", "subagent_total"]


@dataclass(frozen=True)
class CostRow:
    """One top-level step's main-session figures; every field `None` when the
    step carries no `main_session`."""

    step: str
    turns: int | None = None
    sessions: int | None = None
    input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_per_turn: int | None = None
    """Cache-read tokens per turn — gh#593's measure of how much context each
    turn re-reads. `None` with no turns, rather than a division by zero."""
    cost_usd: float | None = None


@dataclass(frozen=True)
class SubagentTotal:
    """Every attempt's `measured`, summed. `tokens` is `None` when no attempt
    was measured — "not observable", not zero."""

    measured: int
    attempts: int
    tokens: MeasuredTokens | None


def cost_rows(state: RunState) -> list[CostRow]:
    """One row per top-level step, in the cursor's own step order."""
    rows: list[CostRow] = []
    for step_id, record in state.steps.items():
        usage = record.main_session
        if usage is None:
            rows.append(CostRow(step=step_id))
            continue
        rows.append(
            CostRow(
                step=step_id,
                turns=usage.turns,
                sessions=usage.sessions,
                input_tokens=usage.input_tokens,
                cache_creation_input_tokens=usage.cache_creation_input_tokens,
                cache_read_input_tokens=usage.cache_read_input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_per_turn=(
                    usage.cache_read_input_tokens // usage.turns if usage.turns else None
                ),
                cost_usd=usage.cost_usd,
            )
        )
    return rows


def subagent_total(state: RunState) -> SubagentTotal:
    """The sum of every attempt's `measured`, and how many of how many."""
    attempts = [
        attempt
        for record in state.steps.values()
        for unit in (record.units or {}).values()
        for attempt in unit.attempts
    ]
    measured = [a.measured for a in attempts if a.measured is not None]
    tokens = (
        MeasuredTokens(
            input_tokens=sum(m.input_tokens for m in measured),
            cache_creation_input_tokens=sum(m.cache_creation_input_tokens for m in measured),
            cache_read_input_tokens=sum(m.cache_read_input_tokens for m in measured),
            output_tokens=sum(m.output_tokens for m in measured),
        )
        if measured
        else None
    )
    return SubagentTotal(measured=len(measured), attempts=len(attempts), tokens=tokens)


def possibly_over_counted(state: RunState) -> list[str]:
    """Unit keys, sorted, holding a measured attempt that returned before the
    run's first main-session measurement (module docstring)."""
    stamps = [
        parse_timestamp(record.at)
        for record in state.steps.values()
        if record.main_session is not None
    ]
    known = [s for s in stamps if s is not None]
    since = min(known) if known else None
    flagged: set[str] = set()
    for record in state.steps.values():
        for key, unit in (record.units or {}).items():
            for attempt in unit.attempts:
                if attempt.measured is None:
                    continue
                returned = parse_timestamp(attempt.returned)
                if since is None or returned is None or returned < since:
                    flagged.add(key)
    return sorted(flagged)
