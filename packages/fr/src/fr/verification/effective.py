"""The effective strategy of an acceptance row — spec 2026-10-06 §B (R7).

Every consumer asks these two functions and none compares strings itself, so
"post-merge" has one definition: whatever the resolved manifest says.
"""

from __future__ import annotations

import os
from pathlib import Path

from fr.verification.model import RESERVED, StrategyError, StrategyManifest
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


def install_problem(manifest: StrategyManifest, repo_root: Path) -> str | None:
    """Why the repo cannot run the manifest's install program, or `None`.

    The ONE install rule (spec 2026-10-12 §B): no `install` is not a problem
    (nothing to install is no reason a strategy cannot be owed), and an
    `install[0]` that is a bare command or an absolute path is accepted; a
    repo-relative one must be an executable file."""
    if not manifest.install:
        return None
    program = manifest.install[0]
    if "/" not in program or program.startswith("/"):
        return None
    path = repo_root / program
    if path.is_file() and os.access(path, os.X_OK):
        return None
    return (
        f"strategy {manifest.verification!r} needs the repo's executable `{program}` "
        f"<prefix> <source> (the candidate-install contract, spec R8), and {path} "
        + ("is not executable" if path.is_file() else "does not exist")
    )


def effective_shape_default(name: str | None, repo_root: Path | None) -> str | None:
    """The shape's default strategy `name`, unless the repo cannot run it.

    A default that does not resolve is returned UNFILTERED: the gates that
    refuse an unknown strategy by name keep doing so, and no `StrategyError`
    reaches a caller that does not catch one."""
    if name is None or name == RESERVED or repo_root is None:
        return name
    try:
        manifest = resolve_strategy(name, repo_root)
    except StrategyError:
        return name
    return None if install_problem(manifest, repo_root) is not None else name
