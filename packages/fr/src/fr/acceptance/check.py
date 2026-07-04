"""The acceptance gate: ref resolution, staleness guard, exit contract.

Exit contract (spec §4): any `failing` row → 2; resolution / staleness /
schema errors → 1; `skipped` / `not-implemented` rows → 0 with
`::warning::`-formatted annotation lines.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from fr.acceptance.model import (
    AcceptanceError,
    Matrix,
    Row,
    archive_twin,
    split_ref,
)

SPEC_DIRS = ("docs/superpowers/specs", "docs/superpowers/implemented/specs")
TEST_PLAN_MARKER = "## Test Plan"

_REMOTE_RE = re.compile(r"github\.com[:/]([^/]+)/([^/\s]+?)(?:\.git)?/?$")


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
        "cannot resolve repo identity: set top-level `org:` and `repo:` keys "
        "in matrix.yaml (fr acceptance init writes them) or add a github origin remote"
    )


def open_rows(matrix: Matrix) -> list[Row]:
    """The nag set: `skipped` / `not-implemented` rows in matrix (= age) order."""
    return [r for r in matrix.rows if r.status in ("skipped", "not-implemented")]


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


def _resolve_ref(row_id: str, ref: str, base: Path, result: CheckResult) -> None:
    _, path, _ = split_ref(ref)  # fragment stripped for existence (trap 3)
    if (base / path).exists():
        return
    twin = archive_twin(path)
    if twin and (base / twin).exists():
        result.warnings.append(
            f"row {row_id}: {ref} moved to {twin} (spec archived) — links "
            f"auto-resolve; update the matrix ref when convenient"
        )
        return
    result.errors.append(f"row {row_id}: ref does not resolve: {ref}")


def _workflow_coverage_warnings(matrix: Matrix, root: Path, own: str) -> list[str]:
    """Trap 7, code-enforced: every own-repo path the matrix references must
    fall inside the workflow's PR-time path filters, or a rename merges clean
    and the break surfaces only at the weekly cron."""
    import fnmatch

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
    uncovered: list[str] = []
    for r in matrix.rows:
        for ref in r.refs():
            try:
                repo, path, _ = split_ref(ref)
            except AcceptanceError:
                continue
            if repo != own:
                continue  # sister-repo refs are honestly out of PR-time reach
            if not any(fnmatch.fnmatch(path, g) for g in globs):
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

    for r in matrix.rows:
        for ref in r.refs():
            try:
                repo, _, _ = split_ref(ref)
            except AcceptanceError as e:
                result.errors.append(str(e))
                continue
            if repo == own:
                base: Path | None = root
            else:
                base = _sibling_base(root, sibling_root, repo)
            if base is None:
                missing_repos.add(repo)
                continue
            _resolve_ref(r.id, ref, base, result)
    for repo in sorted(missing_repos):
        result.warnings.append(f"repo {repo} not checked out locally — its refs were not verified")

    # Staleness guard: every own-repo spec with a Test Plan must be cited by
    # >=1 row origin. A citation survives `fr archive` (twin-aware, trap 1).
    referenced: set[str] = set()
    for r in matrix.rows:
        for ref in r.origin:
            try:
                repo, path, _ = split_ref(ref)
            except AcceptanceError:
                continue  # already reported above
            if repo != own:
                continue
            referenced.add(path)
            twin = archive_twin(path)
            if twin:
                referenced.add(twin)
    for spec_dir in SPEC_DIRS:
        for spec in sorted((root / spec_dir).glob("*.md")):
            if TEST_PLAN_MARKER not in spec.read_text():
                continue
            rel = str(spec.relative_to(root))
            if rel not in referenced:
                result.errors.append(
                    f"staleness: {rel} has a Test Plan but no matrix row cites it "
                    f"(add rows or fold it into an existing origin)"
                )

    result.warnings.extend(_workflow_coverage_warnings(matrix, root, own))

    result.failing_ids = [r.id for r in matrix.rows if r.status == "failing"]
    result.warning_rows = open_rows(matrix)
    result.summary = (
        f"acceptance matrix check: {len(matrix.rows)} rows OK "
        f"({dict(Counter(r.status for r in matrix.rows))})"
    )
    return result
