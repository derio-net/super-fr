"""The effective strategy of an acceptance row — spec 2026-10-06 §B (R7).

Every consumer asks these two functions and none compares strings itself, so
"post-merge" has one definition: whatever the resolved manifest says.
"""

from __future__ import annotations

from pathlib import Path

from fr.verification.model import RESERVED
from fr.verification.resolve import resolve_strategy
from fr.verification.spec_section import Section


def effective_strategy(
    row_verify: str | None,
    row_id: str,
    section: Section | None,
    shape_default: str | None,
) -> str | None:
    """The first of these that is set: the row's own `verify:`, the spec's
    override line for the row, the spec's `strategy:`, the shape's default.

    A run with no `## Verification` section is the world before this feature:
    only a row's own `verify:` counts, and the shape's default does NOT apply —
    that is how every row behaves today. `none` is returned as the reserved
    word, not as `None`: "no strategy applies" and "unset" differ.
    """
    if row_verify is not None:
        return row_verify
    if section is None:
        return None
    line = section.rows.get(row_id)
    if line is not None:
        return line.strategy
    if section.strategy is not None:
        return section.strategy
    return shape_default


def is_post_merge(strategy: str | None, repo_root: Path | None) -> bool:
    """Whether `strategy`'s manifest says `post-merge`.

    No strategy and `none` are neither post-merge nor pre-merge. A name that
    does not resolve raises `StrategyError` — a caller asking about a strategy
    that does not exist has a bug to hear about, not a `False` to act on.
    """
    if strategy is None or strategy == RESERVED:
        return False
    return resolve_strategy(strategy, repo_root).when == "post-merge"
