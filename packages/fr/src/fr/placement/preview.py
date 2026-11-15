"""What a read-only preview of a placement cannot see (`fr archive --dry-run`, spec
2026-11-15-owed-archive-side-effects R10, review p3-r5).

Under quiet and stealth a real run first makes the placement's checkout current — it
creates the `fr` worktree, checks the tracking repo and syncs its clone — and only then
reads it. A preview may make none of those writes, so where they would change what the
run reads, it cannot tell what the run would do, and says why instead of guessing."""

from __future__ import annotations

from pathlib import Path

from fr.artifacts import paths


def cannot_tell(root: Path) -> str | None:
    """Why a preview at the checkout *root* cannot see what a real run would read, or
    None when it can (always None under `repo`)."""
    placement = paths.outside_repo(Path(root))
    if placement == paths.STEALTH:
        from fr.placement import stealth

        return stealth.preview_problem(root)
    if placement == paths.QUIET:
        from fr.placement import quiet

        return quiet.preview_problem(root)
    return None
