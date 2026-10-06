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

from fr.acceptance.model import AcceptanceError, Matrix, Row, split_ref

__all__ = ["AWAITING_LIVE_LABEL", "holds_open", "issues_now_closable", "walk_verified"]

AWAITING_LIVE_LABEL = "fr:awaiting-live"
"""The label an issue carries while a post-merge row citing it waits for its
walk (R17)."""

_SPECS = ("docs/superpowers/specs/", "docs/superpowers/implemented/specs/")


def walk_verified(row: Row) -> bool:
    passing = {w.harness for w in row.walks if w.outcome == "pass"}
    if row.harnesses:
        return all(h in passing for h in row.harnesses)
    return bool(passing)


def _spec_of(row: Row) -> str | None:
    """The first spec the row's `origin` names (repo-relative), or `None`."""
    for origin in row.origin:
        try:
            _, path, _ = split_ref(origin)
        except AcceptanceError:
            continue
        if path.endswith(".md") and path.startswith(_SPECS):
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
    spec = _spec_of(row)
    try:
        return spec_verification(repo_root, spec).is_post_merge(row)
    except (StrategyError, SectionError, OSError):
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
