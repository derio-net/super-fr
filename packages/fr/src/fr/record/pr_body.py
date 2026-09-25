"""`deliver`'s PR body, rendered by fr (spec
`2026-09-25-lean-cost-aware-process-design.md` §5.C.4).

The orchestrator used to assemble the PR body by hand from `fr journal render`,
`fr run cost` and `fr plan proportionality` — and PR #612 shipped with no
out-of-scope section at all. So fr renders it: in-scope findings from both of
the run's journals, the out-of-scope ones (or "None."), the proportionality
report and the cost table. The agent passes the file to the PR; `resolve`
then reads the LIVE body back through `fr.gh` and refuses `deliver` while a
required section is missing.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from fr.journal.model import (
    JournalEntry,
    JournalParseError,
    effective_finding_states,
    parse_journal,
    resolve_journal_read_path,
    spec_journal_slug,
)

if TYPE_CHECKING:
    from fr.run.model import RunState

__all__ = [
    "PR_BODY_NAME",
    "REQUIRED_SECTIONS",
    "missing_sections",
    "render_out_of_scope",
    "render_pr_body",
]

PR_BODY_NAME = "pr-body.md"

REQUIRED_SECTIONS = (
    "## Findings",
    "## Out-of-scope findings",
    "## Proportionality",
    "## Cost",
)
"""The headings a delivered PR's body must carry, in order."""

_CLOSED_OUT = frozenset({"out-of-scope", "deferred"})


def missing_sections(body: str) -> list[str]:
    """The required headings `body` does not carry (a heading is a line)."""
    lines = {line.strip() for line in body.splitlines()}
    return [h for h in REQUIRED_SECTIONS if h not in lines]


def _journals(repo_root: Path, state: RunState) -> list[tuple[str, list[JournalEntry]]]:
    out: list[tuple[str, list[JournalEntry]]] = []
    emitted: dict[str, str] = {}
    for record in state.steps.values():
        emitted.update(record.emitted or {})
    wanted: list[tuple[str, str]] = []
    if "spec" in emitted:
        wanted.append(("spec", spec_journal_slug(Path(emitted["spec"]).stem)))
    if "plan" in emitted:
        wanted.append(("plan", Path(emitted["plan"]).name))
    for scope, slug in wanted:
        path = resolve_journal_read_path(repo_root, scope, slug)  # type: ignore[arg-type]
        if not path.is_file():
            continue
        try:
            out.append((scope, parse_journal(path.read_text())))
        except JournalParseError:
            continue
    return out


def _finding_line(scope: str, entry: JournalEntry, state: str, where: str | None) -> str:
    phase = f", phase {entry.phase}" if entry.phase is not None else ""
    tail = f" → {where}" if where else ""
    return f"- `{entry.id}` ({scope}{phase}) — {entry.title} — **{state}**{tail}"


def _findings(repo_root: Path, state: RunState) -> tuple[list[str], list[str]]:
    inside: list[str] = []
    outside: list[str] = []
    for scope, entries in _journals(repo_root, state):
        states = effective_finding_states(entries)
        tracked = {e.resolves: e.tracked_by for e in entries if e.resolves and e.tracked_by}
        for e in entries:
            if e.kind != "finding" or e.resolves is not None:
                continue
            verdict = states.get(e.id, e.state or "open")
            line = _finding_line(scope, e, verdict, tracked.get(e.id))
            (outside if verdict in _CLOSED_OUT else inside).append(line)
    return inside, outside


def render_out_of_scope(lines: Sequence[str]) -> str:
    return "\n".join(lines) if lines else "None."


def _proportionality(repo_root: Path, state: RunState) -> str:
    from fr.parser import PlanSchemaError, parse
    from fr.proportionality import run_report

    plan_rel = next(
        (r.emitted["plan"] for r in state.steps.values() if r.emitted and "plan" in r.emitted),
        None,
    )
    if plan_rel is None:
        return "No plan recorded for this run."
    try:
        report = run_report(repo_root, parse(repo_root / plan_rel), None)
    except (PlanSchemaError, OSError) as e:
        return f"Not available: {e}"
    return f"```text\n{report.text.rstrip()}\n```"


def _cost(repo_root: Path, state: RunState) -> str:
    from fr.run.cost import effective_entries, load_run_usage, recompute_entries, summarize

    note = ""
    try:
        usage = load_run_usage(repo_root, state.run)
    except Exception:  # noqa: BLE001 — a bad usage file does not stop a delivery
        usage = None
    if usage is not None:
        entries, _replayed, _ignored = effective_entries(usage)
    else:
        entries = recompute_entries(repo_root, state, os.environ)
        note = "\n\n_Read from this host's transcripts; the usage file is written by this resolve._"
    summary = summarize(entries, list(state.steps))

    def usd(value: float | None) -> str:
        return "—" if value is None else f"${value:,.2f}"

    def n(value: int | None) -> str:
        return "—" if value is None else f"{value:,}"

    rows = ["| step | turns | cost |", "|---|---:|---:|"]
    rows += [f"| {r.step} | {n(r.turns)} | {usd(r.usd)} |" for r in summary.steps]
    rows.append(f"| **total** | | {usd(summary.total)} |")
    sessions = f"\n\nSessions: {summary.read} read, {summary.unavailable} unavailable."
    return "\n".join(rows) + sessions + note


def render_pr_body(repo_root: Path, state: RunState) -> str:
    """The PR body fr owns: every `REQUIRED_SECTIONS` heading, in order.
    The agent may add a summary above it; it may not drop a section."""
    inside, outside = _findings(repo_root, state)
    parts = [
        f"<!-- rendered by fr for run {state.run}; edit above this line only -->",
        "## Findings",
        "\n".join(inside) if inside else "None.",
        "## Out-of-scope findings",
        render_out_of_scope(outside),
        "## Proportionality",
        _proportionality(repo_root, state),
        "## Cost",
        _cost(repo_root, state),
    ]
    return "\n\n".join(parts) + "\n"
