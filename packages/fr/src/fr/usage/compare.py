"""`fr usage compare` — two sets of runs, side by side (spec
`2026-10-06-cost-evidence-design.md` §F, R10).

A pure engine over loaded inputs: `load_run_inputs` reads a run's usage file
(live, then archived), its cursor (live, then archived — read RAW and
tolerantly, because archived cursors are never migrated and runs before
2026-09-20 are v1-v4), its plan's journal; `run_row`/`set_summary` are pure.

A run missing an input keeps a row with `None` in that column (rendered `—`)
and is still counted. A figure nobody observed is never a zero.

Phases are the plan folder's `NN.yaml` files (live, then
`implemented/plans/`); only when the plan is missing are they counted from the
cursor's `phase/<n>` keys (with or without a member segment) under any step's
`units` (v5+) or `items` (v1-v4) — a pre-v5 cursor lists only the phases fr
dispatched. Findings per phase are journal `finding` entries grouped by their
`phase`; findings with no phase are a separate column, never divided in. A
re-opened finding is one the journal fold (`fr.journal.model`) moved from a
closed state back to `open`.
"""

from __future__ import annotations

import datetime as _dt
import re
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from fr.journal.model import (
    JournalEntry,
    finding_states_and_reopens,
    parse_journal,
    resolve_journal_read_path,
)
from fr.run.cost import effective_entries, load_run_usage, plus_figure, summarize
from fr.run.model import archived_run_path, run_path
from fr.usage.file import Figure, UsageFile, UsageFileError
from fr.usage.split import MAIN, SUBAGENT

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2})?)?$")
_PHASE_KEY = re.compile(r"^phase/(\d+)(/|$)")
_PHASE_FILE = re.compile(r"^(\d+)\.yaml$")
_PLANS_REL = (Path("docs/superpowers/plans"), Path("docs/superpowers/implemented/plans"))
_RUN_DIRS = (Path("docs/superpowers/runs"), Path("docs/superpowers/implemented/runs"))


@dataclass(frozen=True)
class RunInputs:
    run: str
    started: str | None
    cursor: dict[str, Any] | None
    usage: UsageFile | None
    journal: list[JournalEntry] | None
    """`None` when the run has no plan or its plan has no journal."""
    plan_phases: int | None = None
    """The plan folder's `NN.yaml` count; `None` when the plan is missing."""


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
    """Findings filed against a phase."""
    findings_per_phase: float | None
    reopened: int | None
    unphased: int | None = None
    """Findings carrying no `phase` — never divided into the per-phase figure."""
    sessions: tuple[str, ...] = ()
    shared: int = 0
    """How many of this run's sessions another run of the same set also holds."""


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
    unphased: float | None = None
    shared_runs: int = 0
    """Runs of the set that share a session with another run of it."""


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


def _plan_phase_count(repo: Path, cursor: Mapping[str, Any]) -> int | None:
    steps = cursor.get("steps")
    plan = steps.get("plan") if isinstance(steps, Mapping) else None
    emitted = plan.get("emitted") if isinstance(plan, Mapping) else None
    rel = emitted.get("plan") if isinstance(emitted, Mapping) else None
    slug = _plan_slug(cursor)
    if not rel or not slug:
        return None
    candidates = [repo / str(rel), *(repo / base / slug for base in _PLANS_REL)]
    for folder in candidates:
        if folder.is_dir():
            return sum(1 for f in folder.iterdir() if _PHASE_FILE.match(f.name))
    return None


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
        plan_phases=_plan_phase_count(repo, cursor) if cursor else None,
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


def _journal_counts(entries: list[JournalEntry]) -> tuple[int, int, int]:
    """`(findings filed against a phase, findings with no phase, re-opened)` —
    re-opens from the journal's own fold, never a second walk."""
    originals = [e for e in entries if e.kind == "finding" and e.resolves is None]
    phased = sum(1 for e in originals if e.phase is not None)
    _states, reopened = finding_states_and_reopens(entries)
    return phased, len(originals) - phased, len(reopened)


def run_row(inputs: RunInputs) -> RunRow:
    phases = inputs.plan_phases
    if phases is None and inputs.cursor is not None:
        phases = _phases(inputs.cursor)
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
    findings = reopened = unphased = None
    sessions: list[str] = []
    if inputs.usage is not None:
        sessions = sorted(
            {
                e.session
                for e in effective_entries(inputs.usage)[0]
                if e.unavailable is None and e.session
            }
        )
    per_phase: float | None = None
    if inputs.journal is not None:
        findings, unphased, reopened = _journal_counts(inputs.journal)
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
        unphased=unphased,
        sessions=tuple(sessions),
    )


def mark_shared(rows: list[RunRow]) -> list[RunRow]:
    """Rows with `shared` set: how many of each run's sessions another run of
    the same set also holds (its cost and turns count that session in full
    under each)."""
    holders: dict[str, int] = {}
    for row in rows:
        for session in row.sessions:
            holders[session] = holders.get(session, 0) + 1
    return [replace(row, shared=sum(1 for s in row.sessions if holders[s] > 1)) for row in rows]


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
        unphased=_median(r.unphased for r in rows),
        shared_runs=sum(1 for r in rows if r.shared),
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
    "unphased",
    "re-opened",
    "shared",
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
        _num(row.unphased),
        _num(row.reopened),
        str(row.shared) if row.shared else DASH,
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
        _num(s.unphased),
        _num(s.reopened),
        f"{s.shared_runs} run(s)" if s.shared_runs else DASH,
    ]


def render_compare(before: list[RunRow], after: list[RunRow]) -> str:
    """Two tables: every run of both sets, then the per-set medians. Rows are
    expected through `mark_shared`; a footnote names each set's shared runs."""
    runs = [_run_cells(r) for r in before] + [_run_cells(r) for r in after]
    tagged = [[f"[before] {c[0]}", *c[1:]] for c in runs[: len(before)]] + [
        [f"[after] {c[0]}", *c[1:]] for c in runs[len(before) :]
    ]
    summaries = [
        _summary_cells("before", set_summary(before)),
        _summary_cells("after", set_summary(after)),
    ]
    notes = []
    for label, rows in (("before", before), ("after", after)):
        n = sum(1 for r in rows if r.shared)
        if n:
            notes.append(
                f"* {label}: {n} of {len(rows)} runs share a session with another run of the "
                "set; that session's turns and cost count in full under each."
            )
    note = ("\n" + "\n".join(notes) + "\n") if notes else ""
    return (
        "Per run\n"
        + _grid(_RUN_HEADERS, tagged)
        + "\n\nPer set\n"
        + _grid(_RUN_HEADERS, summaries)
        + "\n"
        + note
    )


@dataclass(frozen=True)
class StepStat:
    """One step's main-session figures: medians over the runs that have it."""

    runs: int
    turns: float | None
    cache_read: float | None
    output: float | None
    usd: float | None
    usd_per_turn: float | None


@dataclass(frozen=True)
class StepTable:
    steps: dict[str, StepStat]
    sources: dict[str, int]
    """How many runs each source served: `steps_by_role.main` (v2 split),
    `role: main entry` (a v1 file's main-session entry) or `none` (no usage)."""


_STEP_ORDER = (
    "brainstorm",
    "spec-review",
    "plan",
    "plan-review",
    "implement",
    "journal-check",
    "deliver",
)
SRC_SPLIT = "steps_by_role.main"
SRC_ENTRY = "role: main entry"
SRC_NONE = "none"


def _main_steps(inputs: RunInputs) -> tuple[dict[str, Figure], str]:
    """The main session's per-step figures for one run, and where they came
    from: the v2 split where the file has one, else the steps of its
    `role: main` (or unlabelled) entries."""
    if inputs.usage is None:
        return {}, SRC_NONE
    entries = [e for e in effective_entries(inputs.usage)[0] if e.unavailable is None]
    out: dict[str, Figure] = {}
    if any(e.steps_by_role.get(MAIN) for e in entries):
        for e in entries:
            for step, figure in e.steps_by_role.get(MAIN, {}).items():
                merged = plus_figure(out.get(step), figure)
                if merged is not None:
                    out[step] = merged
        return out, SRC_SPLIT
    for e in entries:
        if e.role not in (None, MAIN):
            continue
        for step, figure in e.steps.items():
            merged = plus_figure(out.get(step), figure)
            if merged is not None:
                out[step] = merged
    return out, SRC_ENTRY if out else SRC_NONE


def step_table(inputs: list[RunInputs]) -> StepTable:
    per_step: dict[str, list[Figure]] = {}
    sources = {SRC_SPLIT: 0, SRC_ENTRY: 0, SRC_NONE: 0}
    for run in inputs:
        figures, source = _main_steps(run)
        sources[source] += 1
        for step, figure in figures.items():
            per_step.setdefault(step, []).append(figure)
    ordered = [s for s in _STEP_ORDER if s in per_step] + sorted(
        s for s in per_step if s not in _STEP_ORDER
    )
    steps = {
        step: StepStat(
            runs=len(per_step[step]),
            turns=_median(f.turns for f in per_step[step]),
            cache_read=_median(f.cache_read for f in per_step[step]),
            output=_median(f.output for f in per_step[step]),
            usd=_median(f.usd for f in per_step[step]),
            usd_per_turn=_median(
                f.usd / f.turns for f in per_step[step] if f.usd is not None and f.turns
            ),
        )
        for step in ordered
    }
    return StepTable(steps=steps, sources=sources)


def render_steps(label: str, table: StepTable) -> str:
    """The main session's per-step medians for one set, naming the source."""
    rows = [
        [
            name,
            str(st.runs),
            _num(st.turns),
            _tok(st.cache_read),
            _tok(st.output),
            _usd(st.usd),
            DASH if st.usd_per_turn is None else f"${st.usd_per_turn:,.3f}",
        ]
        for name, st in table.steps.items()
    ]
    src = ", ".join(f"{k} in {v} run(s)" for k, v in table.sources.items() if v)
    head = ["step", "runs", "turns", "cache-read", "output", "cost", "$/turn"]
    return (
        f"Main-session steps ({label}): medians over the runs that have the step\n"
        f"main = {src or DASH}\n" + _grid(head, rows) + "\n"
    )
