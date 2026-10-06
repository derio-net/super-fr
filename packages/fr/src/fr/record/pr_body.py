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
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
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
    from fr.acceptance.model import Matrix, Row
    from fr.run.model import RunState
    from fr.verification.model import StrategyManifest
    from fr.verification.rows import SpecVerification

__all__ = [
    "PR_BODY_NAME",
    "REQUIRED_SECTIONS",
    "PrematureClose",
    "closing_refs",
    "holds_open_for_run",
    "missing_sections",
    "normalize_issue_ref",
    "pre_merge_owed_lines",
    "premature_closes",
    "prerelease_route",
    "referenced_refs",
    "render_out_of_scope",
    "render_pr_body",
    "shared_closing_keywords",
    "walk_command",
]

PR_BODY_NAME = "pr-body.md"

REQUIRED_SECTIONS = (
    "## Findings",
    "## Out-of-scope findings",
    "## Pre-merge verification owed",
    "## Post-merge verification owed",
    "## Proportionality",
    "## Cost",
)
"""The headings a delivered PR's body must carry, in order. `Post-merge
verification owed` (spec 2026-09-28 §F) lists the acceptance rows only a live
run after merge can move; `Pre-merge verification owed` (spec
2026-10-06-verification-strategies §D, R12) the operator-driven ones to walk
before it, each with its exact walk command."""

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
_ISSUE_REF_GITHUB = re.compile(rf"{_ISSUE_REF.pattern}|(?<![\w/-])(?i:gh)-\d+\b")
"""`_ISSUE_REF` plus GitHub's `GH-<n>` (case-insensitive): every spelling a
merge closes on, which the premature-close gate must see (review p3-r4)."""
_CODE_SPAN = re.compile(r"(`+).+?\1")
_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]*)[^)]*\)")
# A fence may sit inside a blockquote or a list item (CommonMark).
_FENCE = re.compile(r"^\s*(?:>\s*)*(?:(?:[-*+]|\d+[.)])\s+)?(`{3,}|~{3,})(.*)$")
_RENDER_MARKER = "<!-- rendered by fr for run "


def _one_ref_per_link(match: re.Match[str]) -> str:
    text, url = match.group(1), match.group(2)
    return text if _ISSUE_REF.search(text) else url


def _closing_lines(
    body: str, *, as_github: bool = False, keyword: re.Pattern[str] = _KEYWORD
) -> Iterator[tuple[str, str, list[re.Match[str]], list[re.Match[str]]]]:
    """`(raw line, cleaned line, keyword matches, reference matches)` for every line of `body`
    that carries both a closing keyword and an issue reference. Code (fenced or
    inline) is skipped, as GitHub skips it, and so is fr's own render below its
    marker: a finding line carries a free-text title, a state word (`fixed`) and
    `→ #N`, none of which closes.

    `as_github` reads the body as a merge does (review p3-r4): the WHOLE of it —
    a finding title below the marker reading `Fixes #959` closes #959 on merge
    all the same — and `GH-<n>` references too."""
    fence: str | None = None  # the open fence's run, e.g. "````"
    scanned = body if as_github else body.split(_RENDER_MARKER, 1)[0]
    pattern = _ISSUE_REF_GITHUB if as_github else _ISSUE_REF
    for raw in scanned.splitlines():
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
        keywords = list(keyword.finditer(line))
        refs = list(pattern.finditer(line))
        if keywords and refs:
            yield raw, line, keywords, refs


def closing_refs(body: str, *, as_github: bool = False) -> list[tuple[str, str, str]]:
    """`(line, keyword, ref)` for every issue reference on a closing-keyword
    line of `body` — the keyword nearest before it, as written, and the
    reference as written (`#n`, `owner/repo#n` or an issue URL). The same
    code-fence, inline-code and fr-marker skipping as `shared_closing_keywords`
    — unless `as_github`, which reads the whole body and `GH-<n>` too
    (`_closing_lines`)."""
    out: list[tuple[str, str, str]] = []
    for raw, _line, keywords, refs in _closing_lines(body, as_github=as_github):
        for r in refs:
            before = [k for k in keywords if k.end() <= r.start()]
            out.append((raw.strip(), (before[-1] if before else keywords[0]).group(1), r.group(0)))
    return out


_REFS_KEYWORD = re.compile(r"\brefs\b", re.IGNORECASE)
"""`Refs`, case-insensitive and plural only: the bare prose word "ref" is not it."""


def referenced_refs(body: str) -> list[str]:
    """Every issue reference written on a `Refs` line of `body`, as written —
    the mention that does NOT close (spec 2026-10-06-verification-strategies §D).
    Read as `closing_refs` reads by default: code (fenced or inline) is skipped,
    and so is fr's own render below its marker, so a finding title there cannot
    fake a `Refs`. Only `#n`, `owner/repo#n` and issue URLs count, not `GH-<n>`."""
    return [
        r.group(0)
        for _raw, _line, _keywords, refs in _closing_lines(
            body, as_github=False, keyword=_REFS_KEYWORD
        )
        for r in refs
    ]


def shared_closing_keywords(body: str) -> list[tuple[str, list[str]]]:
    """Every line of `body` that shares one closing keyword across several
    issue references (gh#821), with the lines that would close each of them.

    `Closes #a and #b` closes only `#a` on GitHub, so the rule is strict: on a
    line carrying a closing keyword, every reference needs its own keyword
    directly before it.
    """
    out: list[tuple[str, list[str]]] = []
    for raw, line, keywords, refs in _closing_lines(body):
        starts = [0, *(r.end() for r in refs[:-1])]
        if all(_KEYWORD_BEFORE.search(line[s : r.start()]) for s, r in zip(starts, refs)):
            continue
        fixed = []
        for r in refs:
            before = [k for k in keywords if k.end() <= r.start()]
            fixed.append(f"{(before[-1] if before else keywords[0]).group(1)} {r.group(0)}")
        out.append((raw.strip(), fixed))
    return out


_URL_REF = re.compile(r"^https?://[^/\s]+/(?P<path>.+?)(?:/-)?/issues/(?P<n>\d+)$")


def normalize_issue_ref(ref: str, identity: tuple[str, str]) -> str | None:
    """`owner/repo#n` for a reference as a PR body writes it — a bare `#n` or
    `GH-n` takes `identity` (`(org, repo)`, no forge call), an `owner/repo#n` is
    kept, and a GitHub or GitLab issue URL (`.../issues/n`, `.../-/issues/n`)
    becomes the same shape. Owner and repo are lowercased: GitHub matches them
    case-insensitively, so `Derio-Net/Super-FR#9` is `derio-net/super-fr#9`
    (review p3-r4). `None` for anything else."""
    here = f"{identity[0]}/{identity[1]}".lower()
    if ref.startswith("#"):
        return f"{here}{ref}"
    gh = re.fullmatch(r"(?i:gh)-(\d+)", ref)
    if gh:
        return f"{here}#{gh.group(1)}"
    url = _URL_REF.match(ref)
    if url:
        return f"{url.group('path').lower()}#{url.group('n')}"
    if re.fullmatch(r"[\w.-]+/[\w.-]+#\d+", ref):
        repo, _, n = ref.partition("#")
        return f"{repo.lower()}#{n}"
    return None


@dataclass(frozen=True)
class PrematureClose:
    """A closing line whose issue a not-yet-verified post-merge row still holds
    open (R15)."""

    line: str
    ref: str
    rows: tuple[str, ...]

    @property
    def fix(self) -> str:
        return f"Refs {self.ref}"


def premature_closes(
    live_body: str,
    matrix: Matrix,
    identity: tuple[str, str],
    holds_open: Callable[[Row], bool],
) -> list[PrematureClose]:
    """Each closing-keyword line of `live_body` whose issue a row of `matrix`
    cites while `holds_open(row)` — i.e. it is post-merge and not walk-verified.
    Merging such a PR would close an issue its promise has not been verified
    for; `Refs <ref>` mentions it without closing (spec §D, R15)."""
    holding: dict[str, list[str]] = {}
    for row in matrix.rows:
        for issue in row.issues:
            if holds_open(row):
                key = normalize_issue_ref(issue, identity) or issue.lower()
                holding.setdefault(key, []).append(row.id)
    out: list[PrematureClose] = []
    for line, _keyword, written in closing_refs(live_body, as_github=True):
        ref = normalize_issue_ref(written, identity)
        if ref is not None and ref in holding:
            out.append(PrematureClose(line, ref, tuple(holding[ref])))
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


def post_merge_owed_lines(
    matrix: Matrix, spec_ref: str, verification: SpecVerification
) -> list[str]:
    """One line per row citing the spec whose EFFECTIVE strategy is post-merge
    (spec 2026-10-06-verification-strategies §B), with the section's reason or
    `no reason recorded (legacy)`. A strategy that does not resolve is listed
    with the error, never silently dropped."""
    from fr.requirements import rows_citing
    from fr.verification.model import StrategyError

    lines: list[str] = []
    for r in rows_citing(matrix, spec_ref):
        try:
            owed = verification.is_post_merge(r)
        except StrategyError as e:
            lines.append(f"- `{r.id}` — {r.acceptance} — strategy does not resolve: {e}")
            continue
        if owed:
            reason = verification.reason(r) or "no reason recorded (legacy)"
            lines.append(f"- `{r.id}` — {r.acceptance} — {reason}")
    return lines


def walk_command(run: str, strategy: str, row_id: str) -> str:
    """The exact walk an operator runs for one operator-driven row (R12)."""
    return (
        f"fr verification walk --run {run} --model <model> --strategy {strategy} "
        f"--client <client-repo> --row {row_id}"
    )


def prerelease_route(manifest: StrategyManifest, branch: str, scenario: str | None) -> str:
    """What an operator runs, from the repo root, for one row on a `source:
    prerelease` strategy — which `fr verification walk` refuses (review p3-r5).
    Cut the rc (`fr verification prerelease` prints its `<source>`), then ONE
    shell line: install it into a throwaway prefix through the repo's install
    contract (`UV_TOOL_*` inside the prefix, as the walk does, so the
    operator's own `fr` is untouched) and run the scenario in the client repo
    with the prefix first on PATH. Runs as written once `<source>` and
    `<client-repo>` are filled."""
    from fr.verification.walk import render_argv

    values = {
        "prefix": "$prefix",
        "bin": "$prefix/bin",
        "source": "<source>",
        "repo": "$repo",
        "worktree": "$repo",
        "client": "<client-repo>",
        "fixture": "<client-repo>",
        "scenario": f"$repo/{scenario or '<scenario>'}",
    }

    def shell(argv: list[str]) -> str:
        return " ".join(f'"{a}"' if "$" in a else a for a in argv)

    install = shell(render_argv(manifest.install or (), values))
    run = shell(["sh", *render_argv(manifest.scenario or ("{scenario}",), values)])
    return (
        f"`fr verification prerelease --branch {branch}` prints the rc's `<source>`; then "
        f'`repo=$(pwd) prefix=$(mktemp -d) && UV_TOOL_DIR="$prefix/uv-tools" '
        f'UV_TOOL_BIN_DIR="$prefix/bin" {install} && cd <client-repo> && '
        f'PATH="$prefix/bin:$PATH" {run}`'
    )


def pre_merge_owed_lines(
    matrix: Matrix,
    spec_ref: str,
    verification: SpecVerification,
    run: str,
    branch: str = "<branch>",
) -> list[str]:
    """One line per row citing the spec whose effective strategy is
    operator-driven and pre-merge (spec §D, R12), each with its walk command —
    or, for a `source: prerelease` strategy the walk refuses, its manual route
    (`prerelease_route`); a strategy that does not resolve is listed with the
    error, never dropped."""
    from fr.requirements import rows_citing
    from fr.verification.model import StrategyError
    from fr.verification.resolve import resolve_strategy

    lines: list[str] = []
    for r in rows_citing(matrix, spec_ref):
        name = verification.strategy(r)
        if name is None or name == "none":
            continue
        try:
            manifest = resolve_strategy(name, verification.repo_root)
        except StrategyError as e:
            lines.append(f"- `{r.id}` — {r.acceptance} — strategy does not resolve: {e}")
            continue
        if manifest.when != "pre-merge" or manifest.driver != "operator":
            continue
        if manifest.source == "prerelease":
            route = prerelease_route(manifest, branch, r.scenario)
            lines.append(f"- `{r.id}` — {r.acceptance} — {route}")
        else:
            lines.append(f"- `{r.id}` — {r.acceptance} — `{walk_command(run, name, r.id)}`")
    return lines


def _pre_merge_owed(repo_root: Path, state: RunState) -> str:
    """Every operator-driven pre-merge row citing the run's spec with its walk
    command, then the Ready-checklist line the operator ticks after the walk —
    or `None.` (spec §D, R12). `deliver` does not wait for the walk."""
    from fr.acceptance.model import AcceptanceError
    from fr.commands.acceptance_cmd import MATRIX_REL
    from fr.requirements import load_spec_matrix, run_spec
    from fr.verification.rows import shape_default, spec_verification
    from fr.verification.spec_section import SectionError

    spec_rel = run_spec(state)
    if spec_rel is None or not (repo_root / MATRIX_REL).is_file():
        return "None."
    try:
        matrix, spec_ref = load_spec_matrix(repo_root, spec_rel)
        verification = spec_verification(repo_root, spec_rel, shape_default(repo_root, state))
    except (AcceptanceError, SectionError) as e:
        return f"Not available: {e}"
    lines = pre_merge_owed_lines(matrix, spec_ref, verification, state.run, state.branch)
    if not lines:
        return "None."
    lines.append(
        "- [ ] Ready: the walk above is run and recorded (`fr acceptance set-status "
        "--walk <log> --harness <h> --model <m> --strategy <s> --notes ...`)"
    )
    return "\n".join(lines)


def holds_open_for_run(
    repo_root: Path, state: RunState, matrix: Matrix, spec_ref: str | None
) -> Callable[[Row], bool]:
    """`row -> whether it still holds its issues open`: its effective strategy
    is post-merge and it is not walk-verified. A row citing the run's spec is
    judged with that spec's section and the shape's default; any other row as
    `fr.acceptance.walks.holds_open` does. A strategy fr cannot read holds the
    issue open — a premature close is the worse error."""
    from fr.acceptance.walks import holds_open, walk_verified
    from fr.requirements import rows_citing, run_spec
    from fr.verification.model import StrategyError
    from fr.verification.rows import shape_default, spec_verification
    from fr.verification.spec_section import SectionError

    spec_rel = run_spec(state)
    ours: set[str] = set()
    verification = None
    if spec_rel is not None and spec_ref is not None:
        try:
            verification = spec_verification(repo_root, spec_rel, shape_default(repo_root, state))
            ours = {r.id for r in rows_citing(matrix, spec_ref)}
        except (SectionError, OSError):
            verification = None

    def holds(row: Row) -> bool:
        if verification is None or row.id not in ours:
            return holds_open(row, repo_root)
        if walk_verified(row):
            return False
        try:
            return verification.is_post_merge(row)
        except StrategyError:
            return True

    return holds


def _post_merge_owed(repo_root: Path, state: RunState) -> str:
    """Every row citing the run's spec whose effective strategy is post-merge
    (spec 2026-09-28 §F, 2026-10-06 §B), or `None.`."""
    from fr.acceptance.model import AcceptanceError
    from fr.commands.acceptance_cmd import MATRIX_REL
    from fr.requirements import load_spec_matrix, run_spec
    from fr.verification.rows import shape_default, spec_verification
    from fr.verification.spec_section import SectionError

    spec_rel = run_spec(state)
    if spec_rel is None or not (repo_root / MATRIX_REL).is_file():
        return "None."
    try:
        matrix, spec_ref = load_spec_matrix(repo_root, spec_rel)
        verification = spec_verification(repo_root, spec_rel, shape_default(repo_root, state))
    except (AcceptanceError, SectionError) as e:
        return f"Not available: {e}"
    lines = post_merge_owed_lines(matrix, spec_ref, verification)
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
    from fr.run.historical import historical_review_lines

    lines = historical_review_lines(state)
    return "\n".join(lines) if lines else None


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
        "## Pre-merge verification owed",
        _pre_merge_owed(repo_root, state),
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
