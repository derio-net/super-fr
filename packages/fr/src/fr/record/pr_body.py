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
import re
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
    "shared_closing_keywords",
]

PR_BODY_NAME = "pr-body.md"

REQUIRED_SECTIONS = (
    "## Findings",
    "## Out-of-scope findings",
    "## Post-merge verification owed",
    "## Proportionality",
    "## Cost",
)
"""The headings a delivered PR's body must carry, in order. `Post-merge
verification owed` (spec 2026-09-28 §F) lists the acceptance rows only a live
run after merge can move."""

_CLOSED_OUT = frozenset({"out-of-scope", "deferred"})


def missing_sections(body: str, required: Sequence[str] = REQUIRED_SECTIONS) -> list[str]:
    """The `required` headings `body` does not carry (a heading is a line).
    `deliver` adds `## Historical reviews` to the static set when the run has
    any (spec 2026-10-05-run-upgrade-midflight §D, R9)."""
    lines = {line.strip() for line in body.splitlines()}
    return [h for h in required if h not in lines]


# GitHub's closing keywords. Each closes the ONE reference directly after it.
_KEYWORD = re.compile(r"\b(close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b", re.IGNORECASE)
_KEYWORD_BEFORE = re.compile(rf"{_KEYWORD.pattern}\s*:?\s*$", re.IGNORECASE)
_ISSUE_REF = re.compile(r"https?://\S+?/issues/\d+\b|(?<![\w/])(?:[\w.-]+/[\w.-]+)?#\d+\b")
_CODE_SPAN = re.compile(r"(`+).+?\1")
_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]*)[^)]*\)")
# A fence may sit inside a blockquote or a list item (CommonMark).
_FENCE = re.compile(r"^\s*(?:>\s*)*(?:(?:[-*+]|\d+[.)])\s+)?(`{3,}|~{3,})(.*)$")
_RENDER_MARKER = "<!-- rendered by fr for run "


def _one_ref_per_link(match: re.Match[str]) -> str:
    text, url = match.group(1), match.group(2)
    return text if _ISSUE_REF.search(text) else url


def shared_closing_keywords(body: str) -> list[tuple[str, list[str]]]:
    """Every line of `body` that shares one closing keyword across several
    issue references (gh#821), with the lines that would close each of them.

    `Closes #a and #b` closes only `#a` on GitHub, so the rule is strict: on a
    line carrying a closing keyword, every reference needs its own keyword
    directly before it. Code (fenced or inline) is skipped, as GitHub skips it,
    and so is fr's own render below its marker: a finding line carries a
    free-text title, a state word (`fixed`) and `→ #N`, none of which closes.
    """
    out: list[tuple[str, list[str]]] = []
    fence: str | None = None  # the open fence's run, e.g. "````"
    for raw in body.split(_RENDER_MARKER, 1)[0].splitlines():
        m = _FENCE.match(raw)
        if fence is None and m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            fence = m.group(1)
            continue
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                if not m.group(2).strip():
                    fence = None
            continue
        line = _LINK.sub(_one_ref_per_link, _CODE_SPAN.sub("", raw)).replace("*", "")
        keywords = list(_KEYWORD.finditer(line))
        refs = list(_ISSUE_REF.finditer(line))
        if not keywords or not refs:
            continue
        starts = [0, *(r.end() for r in refs[:-1])]
        if all(_KEYWORD_BEFORE.search(line[s : r.start()]) for s, r in zip(starts, refs)):
            continue
        fixed = []
        for r in refs:
            before = [k for k in keywords if k.end() <= r.start()]
            fixed.append(f"{(before[-1] if before else keywords[0]).group(1)} {r.group(0)}")
        out.append((raw.strip(), fixed))
    return out


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


def _post_merge_owed(repo_root: Path, state: RunState) -> str:
    """Every `verify: post-merge` row citing the run's spec (§F), or `None.`."""
    from fr.acceptance.model import AcceptanceError
    from fr.commands.acceptance_cmd import MATRIX_REL
    from fr.requirements import load_spec_matrix, rows_citing, run_spec

    spec_rel = run_spec(state)
    if spec_rel is None or not (repo_root / MATRIX_REL).is_file():
        return "None."
    try:
        matrix, spec_ref = load_spec_matrix(repo_root, spec_rel)
    except AcceptanceError as e:
        return f"Not available: {e}"
    lines = [
        f"- `{r.id}` — {r.acceptance}"
        for r in rows_citing(matrix, spec_ref)
        if r.verify == "post-merge"
    ]
    return "\n".join(lines) if lines else "None."


def _tests(state: RunState) -> str | None:
    """`deliver`'s suite evidence, or `None` when it carries none yet (spec
    2026-09-29-fr-goal-light-path §D: the PR body renders a reused unit and its
    witness). Not a required section — a body rendered before the evidence
    exists simply has no line to show."""
    record = state.steps.get("deliver")
    unit = (record.units or {}).get("step/deliver") if record is not None else None
    witness = (unit.evidence or {}).get("tests") if unit is not None else None
    if not witness:
        return None
    assert unit is not None
    # Review r2-4: a log nobody could tie to a command says so, reused or not.
    unverified = "tests" in (unit.evidence or {}).get("unobserved", "").split(",")
    caveat = (
        " (unverified: fr could not tie the log to the command that wrote it)" if unverified else ""
    )
    if witness.startswith("reused:"):
        source, _, rest = witness.removeprefix("reused:").partition(":")
        log, _, tree = rest.partition(";tree=")
        return (
            f"Full suite reused from `{source}` — `{log}`, on code tree `{tree[:12]}`, "
            f"unchanged at delivery{caveat}."
        )
    return f"Full suite run at delivery — `{witness}`{caveat}."


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
    from fr.run.cost import effective_entries, load_run_usage, summarize
    from fr.usage.capture import live_usage

    try:
        usage = load_run_usage(repo_root, state.run)
    except Exception:  # noqa: BLE001 — a bad usage file does not stop a delivery
        usage = None
    # gh#680: `deliver` renders this before its own capture, so the file holds
    # only what the last capture on this host saw — fold a live reading over it.
    entries, _replayed, _ignored = effective_entries(
        live_usage(repo_root, state, "deliver", os.environ, usage, ambient=True)
    )
    summary = summarize(entries, list(state.steps))
    note = ""
    if summary.total is None and any(r.turns for r in summary.steps):
        note = (
            "\n\n_Dollars are `—`: no cost recorded yet. A harness may write a "
            "session's cost only when the session ends (Claude Code does). "
            f"`fr run cost {state.run}` reads it afterwards._"
        )

    def usd(value: float | None) -> str:
        return "—" if value is None else f"${value:,.2f}"

    def n(value: int | None) -> str:
        return "—" if value is None else f"{value:,}"

    rows = ["| step | turns | cost |", "|---|---:|---:|"]
    rows += [f"| {r.step} | {n(r.turns)} | {usd(r.usd)} |" for r in summary.steps]
    rows.append(f"| **total** | | {usd(summary.total)} |")
    sessions = f"\n\nSessions: {summary.read} read, {summary.unavailable} unavailable."
    return "\n".join(rows) + sessions + note


def _historical(state: RunState) -> str | None:
    """Every phase reviewed before this cursor existed, by name (R9) — the
    operator's review ok is given against this list, the human control the
    historical bound's trust model rests on. `None` when there is none."""
    from fr.run.historical import historical_reviews

    def phase_of(key: str) -> int:
        part = key.split("/")[1] if key.startswith("phase/") else ""
        return int(part) if part.isdigit() else 0

    found = sorted(historical_reviews(state), key=lambda h: (phase_of(h[1]), h[1]))
    if not found:
        return None
    return "\n".join(
        f"- phase {phase_of(key)} — journal {entry} (reviewed before this run's cursor "
        "existed; reviewer not observed)"
        for _, key, entry in found
    )


def render_pr_body(repo_root: Path, state: RunState) -> str:
    """The PR body fr owns: every `REQUIRED_SECTIONS` heading, in order, plus
    `## Historical reviews` when the run has any. The agent may add a summary
    above it; it may not drop a section."""
    inside, outside = _findings(repo_root, state)
    parts = [
        f"{_RENDER_MARKER}{state.run}; edit above this line only -->",
        "## Findings",
        "\n".join(inside) if inside else "None.",
        "## Out-of-scope findings",
        render_out_of_scope(outside),
    ]
    historical = _historical(state)
    if historical is not None:
        from fr.run.historical import HISTORICAL_HEADING

        parts += [HISTORICAL_HEADING, historical]
    parts += [
        "## Post-merge verification owed",
        _post_merge_owed(repo_root, state),
    ]
    tests = _tests(state)
    if tests is not None:
        parts += ["## Tests", tests]
    parts += [
        "## Proportionality",
        _proportionality(repo_root, state),
        "## Cost",
        _cost(repo_root, state),
    ]
    return "\n\n".join(parts) + "\n"
