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
    "## Built without operator confirmation",
    "## Input coverage",
    "## Post-merge verification owed",
    "## Proportionality",
    "## Cost",
)
"""The headings a delivered PR's body must carry, in order. The middle three
are spec 2026-09-28 §D (d12) and §F: what was built on the orchestrator's
reading alone, the spec review's input partition, and the acceptance rows only
a live run after merge can move."""

_CLOSED_OUT = frozenset({"out-of-scope", "deferred"})
_UNCONFIRMED = "unconfirmed"
PREDATES_LINE = "Not recorded (predates the requirements gate)."


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


def _findings(
    repo_root: Path, state: RunState
) -> tuple[list[str], list[str], list[str]]:
    """`(in scope, out of scope, unconfirmed)` — three disjoint buckets, so an
    unconfirmed spec finding renders under its own section only (§D)."""
    inside: list[str] = []
    outside: list[str] = []
    unconfirmed: list[str] = []
    for scope, entries in _journals(repo_root, state):
        states = effective_finding_states(entries)
        tracked = {e.resolves: e.tracked_by for e in entries if e.resolves and e.tracked_by}
        # The note is the body of the LAST unconfirmed resolution record: what
        # gets built, in the orchestrator's words — not the finding's own body.
        notes = {e.resolves: e.body for e in entries if e.resolves and e.unconfirmed}
        for e in entries:
            if e.kind != "finding" or e.resolves is not None:
                continue
            verdict = states.get(e.id, e.state or "open")
            if verdict == _UNCONFIRMED:
                unconfirmed.append(f"{_finding_line(scope, e, verdict, None)}: {notes.get(e.id, '')}")
                continue
            line = _finding_line(scope, e, verdict, tracked.get(e.id))
            (outside if verdict in _CLOSED_OUT else inside).append(line)
    return inside, outside, unconfirmed


def render_out_of_scope(lines: Sequence[str]) -> str:
    return "\n".join(lines) if lines else "None."


def _run_spec(state: RunState) -> str | None:
    return next(
        (r.emitted["spec"] for r in state.steps.values() if r.emitted and "spec" in r.emitted),
        None,
    )


def _input_coverage(repo_root: Path, state: RunState) -> str:
    """The spec review's `input-coverage` block inside `<details>` (it can be
    long), read from the review entry the unit that recorded `coverage` names —
    or the predates line for a run §G covers."""
    from fr.requirements import REQUIREMENTS_PREDATES, coverage_block
    from fr.run import units

    spec_rel = _run_spec(state)
    for step_id, record in state.steps.items():
        evidence = units.evidence_of(record, f"step/{step_id}")
        if "coverage" not in evidence or "review" not in evidence or spec_rel is None:
            continue
        if evidence["coverage"] == REQUIREMENTS_PREDATES:
            continue
        for scope, entries in _journals(repo_root, state):
            review = next((e for e in entries if e.id == evidence["review"]), None)
            if scope != "spec" or review is None:
                continue
            block = coverage_block(review.body)
            if block is not None:
                summary = f"{evidence['coverage']} (review `{review.id}`)"
                return f"<details>\n<summary>{summary}</summary>\n\n{block}\n</details>"
    return PREDATES_LINE


def _post_merge_owed(repo_root: Path, state: RunState) -> str:
    """Every `verify: post-merge` row citing the run's spec (§F), or `None.`."""
    from fr.acceptance.check import resolve_identity
    from fr.acceptance.model import AcceptanceError, load_matrix
    from fr.requirements import origin_fragment

    spec_rel = _run_spec(state)
    matrix_path = repo_root / "docs" / "acceptance" / "matrix.yaml"
    if spec_rel is None or not matrix_path.is_file():
        return "None."
    try:
        matrix = load_matrix(matrix_path)
        _, repo = resolve_identity(matrix, repo_root)
    except AcceptanceError as e:
        return f"Not available: {e}"
    ref = f"{repo}:{spec_rel}"
    lines = [
        f"- `{r.id}` — {r.acceptance}"
        for r in matrix.rows
        if r.verify == "post-merge"
        and any(origin_fragment(o, ref) is not None for o in r.origin)
    ]
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
    inside, outside, unconfirmed = _findings(repo_root, state)
    parts = [
        f"<!-- rendered by fr for run {state.run}; edit above this line only -->",
        "## Findings",
        "\n".join(inside) if inside else "None.",
        "## Out-of-scope findings",
        render_out_of_scope(outside),
        "## Built without operator confirmation",
        "\n".join(unconfirmed) if unconfirmed else "None.",
        "## Input coverage",
        _input_coverage(repo_root, state),
        "## Post-merge verification owed",
        _post_merge_owed(repo_root, state),
        "## Proportionality",
        _proportionality(repo_root, state),
        "## Cost",
        _cost(repo_root, state),
    ]
    return "\n\n".join(parts) + "\n"
