"""`fr usage compare` — two sets of runs, side by side (spec
`2026-10-06-cost-evidence-design.md` §F, R10).

A pure engine over loaded inputs: `load_run_inputs` reads a run's usage file
(live, then archived), its cursor (live, then archived — read RAW and
tolerantly, because archived cursors are never migrated and runs before
2026-09-20 are v1-v4), its plan's journal; `run_row`/`set_summary` are pure.

A run missing an input keeps a row with `None` in that column (rendered `—`)
and is still counted. A figure nobody observed is never a zero.

Phases are counted from the cursor's `phase/<n>/...` keys under any step's
`units` (v5+) or `items` (v1-v4). Findings per phase are journal `finding`
entries grouped by their `phase`; a re-opened finding is one a later
resolution record moved from a non-open effective state back to `open`.
"""

from __future__ import annotations

import datetime as _dt
import re
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from fr.journal.model import (
    JournalEntry,
    _record_state,
    parse_journal,
    resolve_journal_read_path,
)
from fr.run.cost import effective_entries, load_run_usage, plus_figure, summarize
from fr.run.model import archived_run_path, run_path
from fr.usage.file import Figure, UsageFile, UsageFileError
from fr.usage.split import MAIN, SUBAGENT

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2})?)?$")
_PHASE_KEY = re.compile(r"^phase/(\d+)/")
_RUN_DIRS = (Path("docs/superpowers/runs"), Path("docs/superpowers/implemented/runs"))


@dataclass(frozen=True)
class RunInputs:
    run: str
    started: str | None
    cursor: dict[str, Any] | None
    usage: UsageFile | None
    journal: list[JournalEntry] | None
    """`None` when the run has no plan or its plan has no journal."""


@dataclass(frozen=True)
class RunRow:
    run: str
    phases: int | None
    turns: int | None
    main: Figure | None
    subagent: Figure | None
    usd: float | None
    priced: bool
    findings: int | None
    findings_per_phase: float | None
    reopened: int | None


@dataclass(frozen=True)
class SetSummary:
    """Medians over the runs that HAVE each figure; `n` counts every run."""

    n: int
    priced: int
    phases: float | None
    turns: float | None
    main_cache_read: float | None
    main_output: float | None
    subagent_cache_read: float | None
    subagent_output: float | None
    usd: float | None
    findings_per_phase: float | None
    reopened: float | None


def _read_cursor(repo: Path, run: str) -> dict[str, Any] | None:
    for path in (run_path(repo, run), archived_run_path(repo, run)):
        if path.is_file():
            data = yaml.safe_load(path.read_text())
            if isinstance(data, dict):
                return data
    return None


def _plan_slug(cursor: Mapping[str, Any]) -> str | None:
    steps = cursor.get("steps")
    plan = steps.get("plan") if isinstance(steps, Mapping) else None
    emitted = plan.get("emitted") if isinstance(plan, Mapping) else None
    path = emitted.get("plan") if isinstance(emitted, Mapping) else None
    return Path(str(path)).name if path else None


def _read_journal(repo: Path, slug: str) -> list[JournalEntry] | None:
    path = resolve_journal_read_path(repo, "plan", slug)
    return parse_journal(path.read_text()) if path.is_file() else None


def load_run_inputs(repo: Path, run: str) -> RunInputs:
    cursor = _read_cursor(repo, run)
    try:
        usage = load_run_usage(repo, run)
    except UsageFileError:
        usage = None
    slug = _plan_slug(cursor) if cursor else None
    started = cursor.get("started") if cursor else None
    return RunInputs(
        run=run,
        started=str(started) if started else None,
        cursor=cursor,
        usage=usage,
        journal=_read_journal(repo, slug) if slug else None,
    )


def _all_runs(repo: Path) -> dict[str, str | None]:
    """Every run with a cursor, live or archived -> its `started` stamp."""
    found: dict[str, str | None] = {}
    for rel in _RUN_DIRS:
        for path in sorted((repo / rel).glob("*.yaml")):
            if path.stem in found:
                continue
            data = yaml.safe_load(path.read_text())
            started = data.get("started") if isinstance(data, dict) else None
            found[path.stem] = str(started) if started else None
    return found


def _instant(text: str) -> _dt.datetime | None:
    try:
        at = _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=_dt.UTC)


def select_runs(repo: Path, selector: str, *, before: bool) -> list[str]:
    """An ISO date or timestamp (a bare date is midnight UTC) selects runs
    started before it (`before=True`) or at or after it; a run id selects that
    one run. Sorted by run id."""
    runs = _all_runs(repo)
    cut = _instant(selector) if _DATE.match(selector) else None
    if cut is not None:
        picked = []
        for run, started in runs.items():
            at = _instant(started) if started else None
            if at is not None and (at < cut if before else at >= cut):
                picked.append(run)
        return sorted(picked)
    if selector in runs:
        return [selector]
    raise ValueError(f"no run {selector!r} (a run id, or an ISO date YYYY-MM-DD)")


def _phases(cursor: Mapping[str, Any]) -> int:
    found: set[str] = set()
    steps = cursor.get("steps")
    for record in steps.values() if isinstance(steps, Mapping) else ():
        if not isinstance(record, Mapping):
            continue
        for key in ("units", "items"):
            keyed = record.get(key)
            for unit in keyed if isinstance(keyed, Mapping) else ():
                match = _PHASE_KEY.match(str(unit))
                if match:
                    found.add(match.group(1))
    return len(found)


def _journal_counts(entries: Iterable[JournalEntry]) -> tuple[int, int]:
    """`(findings filed, findings re-opened)`. A resolution record that says
    `open` for a finding whose effective state was not open is a re-open."""
    filed = 0
    reopened: set[str] = set()
    states: dict[str, str] = {}
    for e in entries:
        if e.resolves is None:
            if e.kind == "finding" and e.state is not None:
                filed += 1
                states[e.id] = e.state
            continue
        new = _record_state(e)
        if new is None:
            continue
        if new == "open" and states.get(e.resolves, "open") != "open":
            reopened.add(e.resolves)
        states[e.resolves] = new
    return filed, len(reopened)


def run_row(inputs: RunInputs) -> RunRow:
    phases = _phases(inputs.cursor) if inputs.cursor is not None else None
    turns: int | None = None
    main: Figure | None = None
    sub: Figure | None = None
    usd: float | None = None
    priced = False
    if inputs.usage is not None:
        entries, _replayed, _ignored = effective_entries(inputs.usage)
        for entry in entries:
            if entry.unavailable is not None:
                continue
            for figure in entry.steps.values():
                if figure.turns is not None:
                    turns = (turns or 0) + figure.turns
            for figure in entry.steps_by_role.get(MAIN, {}).values():
                main = plus_figure(main, figure)
            for figure in entry.steps_by_role.get(SUBAGENT, {}).values():
                sub = plus_figure(sub, figure)
        usd = summarize(entries).total
        priced = usd is not None
    findings = reopened = None
    per_phase: float | None = None
    if inputs.journal is not None:
        findings, reopened = _journal_counts(inputs.journal)
        per_phase = findings / phases if phases else None
    return RunRow(
        run=inputs.run,
        phases=phases,
        turns=turns,
        main=main,
        subagent=sub,
        usd=usd,
        priced=priced,
        findings=findings,
        findings_per_phase=per_phase,
        reopened=reopened,
    )


def _median(values: Iterable[float | int | None]) -> float | None:
    have = [v for v in values if v is not None]
    return float(statistics.median(have)) if have else None


def set_summary(rows: list[RunRow]) -> SetSummary:
    return SetSummary(
        n=len(rows),
        priced=sum(r.priced for r in rows),
        phases=_median(r.phases for r in rows),
        turns=_median(r.turns for r in rows),
        main_cache_read=_median(r.main.cache_read if r.main else None for r in rows),
        main_output=_median(r.main.output if r.main else None for r in rows),
        subagent_cache_read=_median(r.subagent.cache_read if r.subagent else None for r in rows),
        subagent_output=_median(r.subagent.output if r.subagent else None for r in rows),
        usd=_median(r.usd for r in rows),
        findings_per_phase=_median(r.findings_per_phase for r in rows),
        reopened=_median(r.reopened for r in rows),
    )


DASH = "—"


def _num(value: float | int | None) -> str:
    if value is None:
        return DASH
    if isinstance(value, float) and value != int(value):
        return f"{value:.2f}"
    return f"{int(value):,}"


def _tok(value: float | int | None) -> str:
    if value is None:
        return DASH
    n = int(value)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.0f}k"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def _usd(value: float | None) -> str:
    return DASH if value is None else f"${value:,.2f}"


def _grid(headers: list[str], rows: list[list[str]]) -> str:
    widths = [
        max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)
    ]

    def line(cells: list[str]) -> str:
        return "  ".join(
            c.ljust(w) if i == 0 else c.rjust(w) for i, (c, w) in enumerate(zip(cells, widths))
        )

    return "\n".join([line(headers), line(["-" * w for w in widths]), *(line(r) for r in rows)])


_RUN_HEADERS = [
    "run",
    "phases",
    "turns",
    "main cr/out",
    "subagent cr/out",
    "cost",
    "priced",
    "findings/phase",
    "re-opened",
]


def _run_cells(row: RunRow) -> list[str]:
    def pair(f: Figure | None) -> str:
        return DASH if f is None else f"{_tok(f.cache_read)} / {_tok(f.output)}"

    return [
        row.run,
        _num(row.phases),
        _num(row.turns),
        pair(row.main),
        pair(row.subagent),
        _usd(row.usd),
        "yes" if row.priced else "no",
        _num(row.findings_per_phase),
        _num(row.reopened),
    ]


def _summary_cells(label: str, s: SetSummary) -> list[str]:
    return [
        f"{label} median (n={s.n})",
        _num(s.phases),
        _num(s.turns),
        f"{_tok(s.main_cache_read)} / {_tok(s.main_output)}",
        f"{_tok(s.subagent_cache_read)} / {_tok(s.subagent_output)}",
        _usd(s.usd),
        f"{s.priced}/{s.n}",
        _num(s.findings_per_phase),
        _num(s.reopened),
    ]


def render_compare(before: list[RunRow], after: list[RunRow]) -> str:
    """Two tables: every run of both sets, then the per-set medians."""
    runs = [_run_cells(r) for r in before] + [_run_cells(r) for r in after]
    tagged = [[f"[before] {c[0]}", *c[1:]] for c in runs[: len(before)]] + [
        [f"[after] {c[0]}", *c[1:]] for c in runs[len(before) :]
    ]
    summaries = [
        _summary_cells("before", set_summary(before)),
        _summary_cells("after", set_summary(after)),
    ]
    return (
        "Per run\n"
        + _grid(_RUN_HEADERS, tagged)
        + "\n\nPer set\n"
        + _grid(_RUN_HEADERS, summaries)
        + "\n"
    )
