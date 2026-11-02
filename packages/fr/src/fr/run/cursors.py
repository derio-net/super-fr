"""Every run cursor a checkout holds: the one reader `fr gate` and `fr gate backfill` share."""

from __future__ import annotations

from pathlib import Path


def all_cursors(root: Path) -> list[Path]:
    """Every run cursor this checkout holds, live then archived (archived runs count)."""
    from fr.record.model import RUNS_REL
    from fr.run.model import IMPLEMENTED_RUNS_REL

    dirs = (root / RUNS_REL, root / IMPLEMENTED_RUNS_REL)
    return [p for d in dirs if d.is_dir() for p in sorted(d.glob("*.yaml"))]
