"""Where a test writes repo configuration: the `.fr/` home S1 gave it (spec
2026-11-19-event-driven-a-la-carte R9), never the old paths a 9.2 fr refuses (spec
2026-11-28-s1-followups R2, R10)."""

from __future__ import annotations

from pathlib import Path


def fr_file(root: Path, name: str) -> Path:
    """`<root>/.fr/<name>`, its parent created."""
    path = Path(root) / ".fr" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def profiles_file(root: Path) -> Path:
    """`<root>/.fr/profiles.yaml`, its parent created."""
    return fr_file(root, "profiles.yaml")
