"""The acceptance gate: ref resolution, staleness guard, exit contract.

Exit contract (spec §4): any `failing` row → 2; resolution / staleness /
schema errors → 1; acceptance debt rows (`DEBT_STATUSES`) → 0 with
`::warning::`-formatted annotation lines.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from fr.acceptance.anchors import collected_node_at, is_python, line_of, node_line
from fr.acceptance.model import (
    AcceptanceError,
    Matrix,
    Row,
    archive_twin,
    same_repo,
    split_ref,
)
from fr.artifacts.paths import KIND_DIRS

SPEC_DIRS = (KIND_DIRS["spec"], KIND_DIRS["spec-archived"])
LIVE_SPEC_DIR = SPEC_DIRS[0]


def spec_test_plan(root: Path, spec: Path) -> tuple[bool, str | None]:
    """`(has a Test Plan, problem)` for the staleness guard (super-fr#1315).

    A live spec whose heading is a near-miss of `## Test Plan` is a problem (the
    line and the fix), and counts as having one. An archived spec is frozen and
    never judged: only its exact heading counts, a near-miss there is ignored."""
    from fr.settings import disabled
    from fr.spec import find_test_plan_heading, near_miss_message

    if disabled(root, "test_plan"):
        return False, None  # R7: no row is required to cite a Test Plan

    heading = find_test_plan_heading(spec.read_text())
    if heading is None:
        return False, None
    if heading.exact:
        return True, None
    rel = spec.relative_to(root).as_posix()
    if not rel.startswith(LIVE_SPEC_DIR + "/"):
        return False, None
    return True, near_miss_message(heading, rel)


# Generalized beyond the original github.com-only pattern (multi-backend
# design, docs/superpowers/specs/
# 2026-07-09-multi-backend-git-host-adapters-design.md §10) — without
# this, `fr acceptance init` hard-fails on a fresh GitLab/Gitea repo
# before it could even write the matrix that would make org/repo
# explicit going forward. Captures the trailing `owner/repo` from ANY
# host's remote URL (https or ssh), matching only the last two path
# segments — a deeply-nested GitLab subgroup (group/subgroup/proj) loses
# the outer group here, a known, narrow limitation of this two-field
# org/repo model (not introduced by this generalization; the same
# two-segment assumption existed for github.com before).
_REMOTE_RE = re.compile(r"[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")


def resolve_identity(matrix: Matrix, root: Path) -> tuple[str, str]:
    """(org, repo) — explicit matrix keys win; else parse the origin remote.

    `init` writes the keys explicitly so CI never depends on remote parsing;
    the fallback keeps hand-rolled matrices working in any GitHub checkout.
    """
    if matrix.org and matrix.repo:
        return matrix.org, matrix.repo
    out = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    m = _REMOTE_RE.search(out.stdout.strip()) if out.returncode == 0 else None
    if m:
        return matrix.org or m.group(1), matrix.repo or m.group(2)
    raise AcceptanceError(
        "cannot resolve repo identity: write a fragment under docs/acceptance/features/ "
        "(each carries `repo: <org>/<repo>`; `fr acceptance add --repo` writes the first) "
        "or add a github origin remote"
    )


_ORIGIN_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _age_key(row: Row) -> str:
    """The earliest date an origin names (`YYYY-MM-DD` in a spec path); "" when none.

    File position stopped meaning age once `add` began inserting by capability
    (spec 2026-09-26-version-bump-churn §3.H, review rp4-f2), so age comes from the
    origin. A row with no dated origin sorts FIRST: a nag surfaces debt of unknown
    age rather than burying it behind debt it can date.
    """
    dates = [m.group(0) for o in row.origin for m in _ORIGIN_DATE.finditer(o)]
    return min(dates, default="")


def open_rows(
    matrix: Matrix, contested: frozenset[str] = frozenset(), retired: Sequence[Row] = ()
) -> list[Row]:
    """The nag set: the debt rows (`is_debt`: a `DEBT_STATUSES` status, or one of
    the fold's *contested* rows), oldest origin first. A *retired* row a merged
    amendment still names is contested too (plan journal `fold-merged-stale-targets`),
    and debt like any other: it is listed although it left the matrix.

    The sort is stable, so rows of the same age keep their matrix order.
    """
    from fr.acceptance.model import is_debt

    opens = [r for r in matrix.rows if is_debt(r.status, contested=r.id in contested)]
    opens += [r for r in retired if r.id in contested]
    return sorted(opens, key=_age_key)


@dataclass
class CheckResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    warning_rows: list[Row] = field(default_factory=list)
    failing_ids: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def exit_code(self) -> int:
        if self.failing_ids:
            return 2
        if self.errors:
            return 1
        return 0


def _sibling_base(root: Path, sibling_root: str, repo: str) -> Path | None:
    """Trap 4: a plain directory at the sibling path (e.g. a worktree cache
    parent) is NOT a checkout — require `.git` to exist. The own repo is
    exempt: its root came from resolve_repo_root and is authoritative."""
    base = (root / sibling_root).resolve() / repo
    return base if (base / ".git").exists() else None


def archived_counterpart(path: str) -> str | None:
    """Where `fr archive` moves `path`, or None (review p2-r5).

    Refs are not retargeted at archive time any more (spec 2026-11-04 R18), so a
    path ref into `docs/superpowers/{specs,journals,plans}/` is resolved at READ
    time against its archived twin. The mapping is the archive's own, not
    restated: `archive_twin` for specs and journals (derived from
    `fr.journal.model`), and the plan roots `fr archive` moves between
    (`fr.archive.PLANS_REL` → `fr.closeout.IMPLEMENTED_PLANS_REL`)."""
    twin = archive_twin(path)
    if twin is not None:
        return twin
    from fr.archive import PLANS_REL
    from fr.closeout import IMPLEMENTED_PLANS_REL

    live, done = f"{PLANS_REL.as_posix()}/", f"{IMPLEMENTED_PLANS_REL.as_posix()}/"
    if path.startswith(live):
        return done + path[len(live) :]
    if path.startswith(done):
        return live + path[len(done) :]
    return None


def _resolve_ref(row_id: str, ref: str, base: Path, result: CheckResult) -> None:
    _, path, frag = split_ref(ref)  # fragment stripped for existence (trap 3)
    if (base / path).exists():
        if frag and is_python(path):
            _check_python_anchor(row_id, ref, base / path, result)
        return
    twin = archived_counterpart(path)
    if twin and (base / twin).exists():
        result.warnings.append(
            f"row {row_id}: {ref} names an archived path, resolved at {twin} — "
            "refs are read through the archive, so nothing needs to change"
        )
        return
    result.errors.append(f"row {row_id}: ref does not resolve: {ref}")


def _check_python_anchor(row_id: str, ref: str, file: Path, result: CheckResult) -> None:
    """gh#531: a `.py` fragment is a test's name, and it must still name one.

    A line anchor is reported with the name the line sits in today, so the fix
    is a copy-paste (or `fr migrate artifacts --yes`, whose matrix repair makes
    exactly that rewrite).
    """
    repo, path, frag = split_ref(ref)
    try:
        source = file.read_text()
    except (OSError, UnicodeDecodeError) as e:
        result.errors.append(f"row {row_id}: cannot read {ref} to resolve its anchor: {e}")
        return
    line = line_of(frag)
    if line is not None:
        name = collected_node_at(source, line)
        fix = (
            f"use {repo}:{path}#{name}"
            if name
            else f"line {line} sits in no test today; anchor on a test name or drop the anchor"
        )
        result.errors.append(f"row {row_id}: line anchor into Python rots silently: {ref} — {fix}")
        return
    if node_line(source, frag) is None:
        result.errors.append(
            f"row {row_id}: anchor {ref} names no def or class in {path} (renamed or deleted test?)"
        )


def _actions_glob_match(pattern: str, path: str) -> bool:
    """GitHub Actions path-filter semantics: `**` spans `/`; `*` and `?` do
    NOT (fnmatch's `*` spans, which would report "covered" for paths Actions
    never triggers on — the false negative trap 7 exists to prevent)."""
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1
    return re.fullmatch("".join(parts), path) is not None


def _workflow_coverage_warnings(matrix: Matrix, root: Path, own: str) -> list[str]:
    """Trap 7, code-enforced: every own-repo path the matrix references must
    fall inside the workflow's PR-time path filters, or a rename merges clean
    and the break surfaces only at the weekly cron."""
    import yaml

    wf_path = root / ".github" / "workflows" / "acceptance-report.yml"
    if not wf_path.exists():
        return []
    try:
        doc = yaml.safe_load(wf_path.read_text()) or {}
    except yaml.YAMLError:
        return [f"{wf_path.name}: unparseable YAML — path-filter coverage not verified"]
    # YAML 1.1 parses the `on:` key as boolean True.
    triggers = doc.get("on", doc.get(True)) or {}
    pr = triggers.get("pull_request") or {}
    globs = pr.get("paths") or []
    if not globs:
        return []
    from fr.acceptance.logical import as_path_ref

    uncovered: list[str] = []
    for r in matrix.rows:
        for ref in r.refs():
            try:
                repo, path, _ = split_ref(as_path_ref(ref, root, own))
            except AcceptanceError:
                continue
            if not same_repo(repo, own):
                continue  # sister-repo refs are honestly out of PR-time reach
            if not any(_actions_glob_match(g, path) for g in globs):
                uncovered.append(path)
    return [
        f"{p} is matrix-referenced but outside {wf_path.name}'s pull_request "
        f"path filters — a rename would only surface at the weekly cron"
        for p in sorted(set(uncovered))
    ]


def check(matrix: Matrix, root: Path, sibling_root: str = "..") -> CheckResult:
    result = CheckResult()
    own = resolve_identity(matrix, root)[1]
    missing_repos: set[str] = set()
    case_only: set[str] = set()

    from fr.acceptance.logical import candidates, is_logical, parse_logical, resolution_problem

    for r in matrix.rows:
        for ref in r.refs():
            if is_logical(ref):
                # R18: `spec:<slug>` / `plan:<slug>` name this repo's artifacts.
                problem = resolution_problem(ref, root)
                if problem is not None:
                    result.errors.append(f"row {r.id}: ref does not resolve: {problem}")
                continue
            try:
                repo, _, _ = split_ref(ref)
            except AcceptanceError as e:
                result.errors.append(str(e))
                continue
            if same_repo(repo, own):
                if repo != own:
                    case_only.add(repo)
                base: Path | None = root
            else:
                base = _sibling_base(root, sibling_root, repo)
            if base is None:
                missing_repos.add(repo)
                continue
            _resolve_ref(r.id, ref, base, result)
    for repo in sorted(missing_repos):
        result.warnings.append(f"repo {repo} not checked out locally — its refs were not verified")
    # gh#1237: tolerated, never silent — a case-only spelling used to make every
    # own-repo ref a sibling, surfacing only as report drift and skipped refs.
    for repo in sorted(case_only):
        result.warnings.append(
            f"ref prefix {repo}: differs from the matrix's repo: {own} only by case — "
            f"read as the own repo; rewrite it as {own}:"
        )

    # Staleness guard: every own-repo spec with a Test Plan must be cited by
    # >=1 row origin. A citation survives `fr archive` (twin-aware, trap 1).
    referenced: set[str] = set()
    for r in matrix.rows:
        for ref in r.origin:
            if is_logical(ref):
                try:
                    referenced.update(candidates(parse_logical(ref)))
                except AcceptanceError:
                    pass  # already reported above
                continue
            try:
                repo, path, _ = split_ref(ref)
            except AcceptanceError:
                continue  # already reported above
            if not same_repo(repo, own):
                continue
            referenced.add(path)
            twin = archive_twin(path)
            if twin:
                referenced.add(twin)
    from fr.settings import disabled

    # R6: under `acceptance: off` there is no matrix to cite a Test Plan from.
    rows_off = disabled(root, "acceptance")
    for spec_dir in SPEC_DIRS:
        for spec in sorted((root / spec_dir).glob("*.md")):
            has_plan, problem = spec_test_plan(root, spec)
            if problem:
                result.errors.append(f"test-plan heading: {problem}")
            if not has_plan or rows_off:
                continue
            rel = str(spec.relative_to(root))
            if rel not in referenced:
                result.errors.append(
                    f"staleness: {rel} has a Test Plan but no matrix row cites it "
                    f"(add rows or fold it into an existing origin)"
                )

    result.warnings.extend(_workflow_coverage_warnings(matrix, root, own))

    # Reports are derived from the fold, never committed (spec 2026-11-04 R20): a
    # tracked one is a second copy that drifts, so it is refused, naming the file.
    from fr.acceptance.report import tracked_report_paths

    for rel in tracked_report_paths(root):
        result.errors.append(
            f"reports are derived; remove {rel} (`git rm {rel}`) — "
            "render one locally with `fr acceptance report`"
        )

    from fr.acceptance.model import walked_error

    result.errors.extend(why for row in matrix.rows if (why := walked_error(row)) is not None)
    result.failing_ids = [r.id for r in matrix.rows if r.status == "failing"]
    result.warning_rows = open_rows(matrix)
    result.summary = (
        f"acceptance matrix check: {len(matrix.rows)} rows OK "
        f"({dict(Counter(r.status for r in matrix.rows))})"
    )
    return result
