"""Walk-verification of a row, and which issues a walk frees (spec
2026-10-06-verification-strategies §E, R14/R16).

A row is walk-verified once it has a passing walk on every harness it names,
or on any one harness when it names none. A walk that makes a row
walk-verified frees each issue that row cites which no other row still holds
open — "holds open" meaning that row is post-merge and not yet walk-verified.
fr only prints the commands that close such an issue; it never closes one.
"""

from __future__ import annotations

from pathlib import Path

from fr.acceptance.model import Matrix, Row, Walk
from fr.artifacts.paths import KIND_DIRS
from fr.labels import FR_AWAITING_LIVE

__all__ = [
    "AWAITING_LIVE_LABEL",
    "close_commands",
    "holds_open",
    "issues_now_closable",
    "owed_harnesses",
    "row_walked",
    "walk_verified",
]

AWAITING_LIVE_LABEL = FR_AWAITING_LIVE.name
"""The label an issue carries while a post-merge row citing it waits for its
walk (R17)."""

_SPECS = (f"{KIND_DIRS['spec']}/", f"{KIND_DIRS['spec-archived']}/")


def walk_verified(row: Row) -> bool:
    passing = {w.harness for w in row.walks if w.outcome == "pass"}
    if row.harnesses:
        return all(h in passing for h in row.harnesses)
    return bool(passing)


def owed_harnesses(row: Row, walks: tuple[Walk, ...] | list[Walk] | None = None) -> list[str]:
    """The harnesses *row* names that no passing walk in *walks* (default: the row's own)
    covers yet, in the row's order (ops-gate-truth R9, R10)."""
    passing = {w.harness for w in (row.walks if walks is None else walks) if w.outcome == "pass"}
    return [h for h in row.harnesses if h not in passing]


def row_walked(row: Row, exclude: frozenset[Walk] | set[Walk] = frozenset()) -> bool:
    """The one rule for a walked row (spec 2026-11-27-ops-gate-truth R10): its status
    is `walked` and its latest walk (by `at`) passed. A walk in *exclude* does not
    count (R12: the DevOps stage ignores the walks the pinned PR head carries)."""
    if row.status != "walked":
        return False
    walks = [w for w in row.walks if w not in exclude]
    return bool(walks) and max(walks, key=lambda w: w.at).outcome == "pass"


def _spec_of(row: Row, repo_root: Path) -> str | None:
    """The first spec the row's `origin` names (repo-relative), or `None`; a
    logical `spec:<slug>` origin resolves in *repo_root* (spec 2026-11-04 R18)."""
    from fr.acceptance.logical import origin_spec_path

    for origin in row.origin:
        path = origin_spec_path(origin, repo_root)
        if path is not None and path.startswith(_SPECS):
            return path
    return None


def holds_open(row: Row, repo_root: Path) -> bool:
    """Whether `row` still holds its issues open: its effective strategy is
    post-merge and it is not yet walk-verified. The strategy is resolved
    against the spec its `origin` names; outside a run no shape is known, so
    the shape default does not apply. A strategy or section fr cannot read
    holds the issue open — printing a premature close is the worse error."""
    from fr.verification.model import StrategyError
    from fr.verification.rows import spec_verification
    from fr.verification.spec_section import SectionError

    if walk_verified(row):
        return False
    spec = _spec_of(row, repo_root)
    try:
        return spec_verification(repo_root, spec).is_post_merge(row)
    except StrategyError, SectionError, OSError:
        return True


def issues_now_closable(matrix: Matrix, before: Row, after: Row, repo_root: Path) -> list[str]:
    """The issues `after` cites that its new walk freed (R16): empty unless
    the walk moved the row from not walk-verified to walk-verified; then each
    cited issue no OTHER row in `matrix` still holds open."""
    if walk_verified(before) or not walk_verified(after):
        return []
    return [
        issue
        for issue in after.issues
        if not any(
            r.id != after.id and issue in r.issues and holds_open(r, repo_root) for r in matrix.rows
        )
    ]


def close_commands(root: Path, before: Row) -> list[str]:
    """The lines naming each issue the latest walk on *before*'s row freed (R16), with
    the forge's close and unlabel commands; empty when forge issues are off
    (`forge.issues: off` or `tracking: none`). Reads the effective matrix in *root*
    after the write. fr never closes the issues (ops-gate-truth R9: one printer for
    `set-status --walk` and `closeout outcome`)."""
    from fr.acceptance.fold import load_effective
    from fr.hostclient import issue_command
    from fr.settings import forge_allows

    matrix = load_effective(root)
    after = next((r for r in matrix.rows if r.id == before.id), None)
    if after is None or not after.walks:
        return []
    freed = issues_now_closable(matrix, before, after, root)
    if not freed or not forge_allows(root, "issues", lenient=True):
        return []
    w = after.walks[-1]
    comment = f"Walk-verified ({w.strategy}, {w.harness}, {w.model}): {w.evidence}"
    lines: list[str] = []
    for ref in freed:
        lines.append(f"{ref}: every row citing it is walk-verified — close it:")
        lines.append("  " + issue_command(root, "issue-close", ref=ref, comment=comment))
        lines.append(
            "  " + issue_command(root, "issue-unlabel", ref=ref, label=AWAITING_LIVE_LABEL)
        )
    return lines
