"""What a run cost — the rows behind `fr run cost` (spec
`2026-09-25-lean-cost-aware-process-design.md` §5.B.4).

Read from the run's usage file (`docs/superpowers/usage/<run>.yaml`, then
`implemented/usage/`), never from the cursor: run 7 moved the figures out of
it. Pure functions over `SessionEntry` values; the command is a thin printer.

**Which entries count.** No totals are stored, so readers sum on read — and
must not count one session twice:

- **Live captures supersede migrated ones — per session and per step, never
  wholesale** (p2-r22). A `migrated` capture holds the figures run 6 kept in
  the cursor (per-attempt subagent tokens, per-step main-session tokens). A
  migrated entry is ignored when a live capture READ its session, or when
  every step it names has live turns or dollars; one only partly covered keeps
  its uncovered steps and drops its token figures, which span the covered
  ones and cannot be apportioned. A live capture of an unrelated session (a
  closeout) therefore drops nothing. `fr run cost` says how many it ignored.
  The file itself is never rewritten: migrated briefs stay where they are.
- **Per session, a reading beats an absence**, and among readings the later
  capture wins: a host that could not read a session does not erase the host
  that could.

A figure nobody observed stays `None` and prints `—`, never `0`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from fr.usage.file import (
    Capture,
    Figure,
    SessionEntry,
    UsageFile,
    archived_usage_path,
    load_usage,
    usage_path,
)

if TYPE_CHECKING:
    from fr.run.model import Attempt, RunState

REPLAYED = ("migrated",)
"""Capture kinds that re-state figures rather than read transcripts."""


def replayed_capture(capture: Capture) -> bool:
    """A capture that only re-states figures (every event is a replay)."""
    return all(event in REPLAYED for event in capture.at)


@dataclass(frozen=True)
class StepRow:
    step: str
    usd: float | None
    turns: int | None
    main: Figure | None = None
    """The main thread's figure for the step (`steps_by_role.main`, R8)."""
    subagent: Figure | None = None
    """Its subagents' figure (`steps_by_role.subagent`)."""


@dataclass(frozen=True)
class PhaseRow:
    """One agentic phase (spec 2026-10-06-cost-evidence §E, R8)."""

    phase: int
    tier: str | None
    bound: str | None
    ran: str | None
    """What ran — shown only for an attempt that recorded `bound`: before run
    version 9 a subagent attempt's `model` held the binding (gh#637)."""
    mismatch: bool
    executor: Figure | None = None
    reviewer: Figure | None = None
    orchestrator: Figure | None = None


@dataclass(frozen=True)
class ModelRow:
    model: str
    input: int
    cache_write: int
    cache_read: int
    output: int
    usd: float | None
    sources: tuple[str, ...]


@dataclass
class Summary:
    steps: list[StepRow] = field(default_factory=list)
    models: list[ModelRow] = field(default_factory=list)
    read: int = 0
    unavailable: int = 0

    @property
    def total(self) -> float | None:
        priced = [m.usd for m in self.models if m.usd is not None]
        return sum(priced) if priced else None


def load_run_usage(repo_root: Path, run_id: str) -> UsageFile | None:
    """The run's usage file — active first, then archived. Raises on a bad one."""
    for path in (usage_path(repo_root, run_id), archived_usage_path(repo_root, run_id)):
        found = load_usage(path)
        if found is not None:
            return found
    return None


def _covers(figure: Figure) -> bool:
    return bool(figure.turns) or bool(figure.usd)


def effective_entries(file: UsageFile) -> tuple[list[SessionEntry], bool, int]:
    """`(entries, replayed, ignored)` — each session counted once, by the rules
    above. `replayed` is True when no live capture read anything, so only
    migrated figures are shown; `ignored` counts the migrated entries a live
    reading wholly superseded."""
    best: dict[str, SessionEntry] = {}
    for capture in (c for c in file.captures if not replayed_capture(c)):
        for entry in capture.sessions:
            held = best.get(entry.session)
            if held is None or entry.unavailable is None or held.unavailable is not None:
                best[entry.session] = entry
    readings = [e for e in best.values() if e.unavailable is None]
    covered = {name for e in readings for name, f in e.steps.items() if _covers(f)}
    read_sessions = {e.session for e in readings}
    ignored = 0
    kept: list[SessionEntry] = []
    for capture in (c for c in file.captures if replayed_capture(c)):
        for entry in capture.sessions:
            if entry.unavailable is not None:
                continue
            if entry.session in read_sessions:
                ignored += 1
                continue
            steps = {n: f for n, f in entry.steps.items() if n not in covered}
            if entry.steps and not steps:
                ignored += 1
                continue
            if steps != entry.steps:
                # its tokens span a covered step and cannot be apportioned per
                # step: keep the uncovered steps, drop the models, never count twice
                entry = entry.model_copy(update={"steps": steps, "models": {}})
            kept.append(entry)
    replayed = bool(kept) and not readings
    return [*best.values(), *kept], replayed, ignored


@dataclass
class _ModelAcc:
    input: int = 0
    cache_write: int = 0
    cache_read: int = 0
    output: int = 0
    usd: float | None = None
    sources: dict[str, None] = field(default_factory=dict)


def _plus_usd(a: float | None, b: float | None) -> float | None:
    if b is None:
        return a
    return b if a is None else a + b


def _plus_turns(a: int | None, b: int | None) -> int | None:
    if b is None:
        return a
    return b if a is None else a + b


def _plus_int(a: int | None, b: int | None) -> int | None:
    return _plus_turns(a, b)


def plus_figure(a: Figure | None, b: Figure | None) -> Figure | None:
    """`a + b`, field by field; a field neither observed stays `None`."""
    if b is None:
        return a
    if a is None:
        return b
    return Figure(
        usd=_plus_usd(a.usd, b.usd),
        turns=_plus_int(a.turns, b.turns),
        input=_plus_int(a.input, b.input),
        cache_write=_plus_int(a.cache_write, b.cache_write),
        cache_read=_plus_int(a.cache_read, b.cache_read),
        output=_plus_int(a.output, b.output),
    )


def summarize(entries: Iterable[SessionEntry], step_order: Sequence[str] = ()) -> Summary:
    from fr.usage.split import MAIN, SUBAGENT

    summary = Summary()
    steps: dict[str, StepRow] = {name: StepRow(name, None, None) for name in step_order}
    models: dict[str, _ModelAcc] = {}
    for entry in entries:
        if entry.unavailable is not None:
            summary.unavailable += 1
            continue
        summary.read += 1
        for name, figure in entry.steps.items():
            row = steps.get(name, StepRow(name, None, None))
            steps[name] = replace(
                row, usd=_plus_usd(row.usd, figure.usd), turns=_plus_turns(row.turns, figure.turns)
            )
        for name, figure in entry.steps_by_role.get(MAIN, {}).items():
            row = steps.get(name, StepRow(name, None, None))
            steps[name] = replace(row, main=plus_figure(row.main, figure))
        for name, figure in entry.steps_by_role.get(SUBAGENT, {}).items():
            row = steps.get(name, StepRow(name, None, None))
            steps[name] = replace(row, subagent=plus_figure(row.subagent, figure))
        for model, m in entry.models.items():
            acc = models.setdefault(model, _ModelAcc())
            acc.input += m.input
            acc.cache_write += m.cache_write
            acc.cache_read += m.cache_read
            acc.output += m.output
            acc.usd = _plus_usd(acc.usd, m.usd)
            acc.sources[m.usd_source] = None
    summary.steps = list(steps.values())
    summary.models = [
        ModelRow(
            model=model,
            input=acc.input,
            cache_write=acc.cache_write,
            cache_read=acc.cache_read,
            output=acc.output,
            usd=acc.usd,
            sources=tuple(acc.sources),
        )
        for model, acc in models.items()
    ]
    return summary


_PHASE_UNIT = re.compile(r"^phase/(\d+)/(implement-phase|review-phase)$")


def phase_rows(state: RunState, entries: Iterable[SessionEntry]) -> list[PhaseRow]:
    """One row per agentic phase, in phase order (spec §E).

    Tier, bound and ran come from the phase's latest non-synthesized
    `implement-phase` attempt; the mismatch mark compares ran and bound by
    `fr.models.model_family`, and an unobserved `ran` is never a mismatch.
    Figures sum `units` across `entries`; the phase's orchestrator is the sum
    over its implement and review units."""
    from fr.models import model_family

    phases: set[int] = set()
    latest: dict[int, Attempt] = {}
    for record in state.steps.values():
        for key, unit in (record.units or {}).items():
            match = _PHASE_UNIT.match(key)
            if match is None:
                continue
            n = int(match.group(1))
            phases.add(n)
            if match.group(2) == "implement-phase":
                real = [a for a in unit.attempts if not a.synthesized]
                if real:
                    latest[n] = real[-1]
    figures: dict[tuple[int, str], Figure | None] = {}
    for entry in entries:
        if entry.unavailable is not None:
            continue
        for key, roles in entry.units.items():
            match = _PHASE_UNIT.match(key)
            if match is None:
                continue
            n = int(match.group(1))
            phases.add(n)
            for role in ("executor", "reviewer", "orchestrator"):
                if role in roles:
                    figures[n, role] = plus_figure(figures.get((n, role)), roles[role])
    rows: list[PhaseRow] = []
    for n in sorted(phases):
        attempt = latest.get(n)
        tier = attempt.tier if attempt is not None else None
        bound = attempt.bound if attempt is not None else None
        ran = attempt.model if attempt is not None and bound is not None else None
        rows.append(
            PhaseRow(
                phase=n,
                tier=tier,
                bound=bound,
                ran=ran,
                mismatch=(
                    ran is not None
                    and bound is not None
                    and model_family(ran) != model_family(bound)
                ),
                executor=figures.get((n, "executor")),
                reviewer=figures.get((n, "reviewer")),
                orchestrator=figures.get((n, "orchestrator")),
            )
        )
    return rows


# --- shared formatting: `fr run cost` and the PR body's `## Cost` -------------

DASH = "—"


def usd_text(value: float | None) -> str:
    return DASH if value is None else f"${value:,.2f}"


def count_text(value: int | None) -> str:
    return DASH if value is None else f"{value:,}"


def _compact(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.0f}k"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def compact_tokens(figure: Figure | None) -> str:
    """`cache-read / output`, compacted (`1.2M / 34k`); `—` when neither was
    observed."""
    if figure is None or (figure.cache_read is None and figure.output is None):
        return DASH
    read = DASH if figure.cache_read is None else _compact(figure.cache_read)
    out = DASH if figure.output is None else _compact(figure.output)
    return f"{read} / {out}"


def figure_cells(figure: Figure | None) -> tuple[str, str, str]:
    """`(turns, cache-read / output, dollars)` for one figure."""
    if figure is None:
        return DASH, DASH, DASH
    return count_text(figure.turns), compact_tokens(figure), usd_text(figure.usd)


def ran_text(row: PhaseRow) -> str:
    """The model that ran, `≠`-marked when its family differs from `bound`."""
    if row.ran is None:
        return DASH
    return f"{row.ran} ≠" if row.mismatch else row.ran


FIGURE_COLUMNS = ("turns", "cache-read / output", "cost")
STEP_ROLES = ("main", "subagent")
PHASE_ROLES = ("executor", "reviewer", "orchestrator")


def recompute_entries(
    repo_root: Path, state: RunState, env: Mapping[str, str]
) -> list[SessionEntry]:
    """Every session the run has evidence for, re-read from THIS host's
    transcripts — what a capture here would record, without writing it. Never
    the session of whoever runs it (spec 2026-10-02-opencode-observe-2 §C,
    #848); with none, the `NO_SESSION_FOUND` placeholder a capture writes."""
    from fr.usage.capture import candidates
    from fr.usage.file import NO_SESSION_FOUND, session_entry, unit_index
    from fr.usage.model import unavailable
    from fr.usage.rollup import windows_from_cursor
    from fr.usage.sources import read_session

    windows = windows_from_cursor(
        {"started": state.started, "steps": {k: {"at": v.at} for k, v in state.steps.items()}}
    )
    index = unit_index(state.model_dump(mode="json"))
    out: list[SessionEntry] = []
    for harness, session in candidates(state, env, repo_root, ambient=False):
        try:
            record = read_session(harness, session, env)
        except Exception as e:  # noqa: BLE001 — one bad reader is one unavailable session
            record = unavailable(session, harness, f"reader failed: {type(e).__name__}")
        out.append(session_entry(record, windows, index))
    if not out:
        out.append(session_entry(unavailable("", "unknown", NO_SESSION_FOUND), windows, index))
    return out


__all__ = [
    "DASH",
    "FIGURE_COLUMNS",
    "PHASE_ROLES",
    "STEP_ROLES",
    "PhaseRow",
    "compact_tokens",
    "count_text",
    "figure_cells",
    "phase_rows",
    "plus_figure",
    "ran_text",
    "usd_text",
    "ModelRow",
    "StepRow",
    "Summary",
    "effective_entries",
    "load_run_usage",
    "recompute_entries",
    "summarize",
]
