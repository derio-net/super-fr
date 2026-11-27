"""Shared placement of a step record under a tmp root (spec 2026-11-27 R4)."""

from __future__ import annotations

from pathlib import Path


def write_record(root: Path, text: str, *, stem: str = "implement-phase__phase-1") -> Path:
    """Write *text*, byte for byte, to `<root>/docs/superpowers/runs/r1.records/<stem>.yaml`."""
    path = root / "docs" / "superpowers" / "runs" / "r1.records" / f"{stem}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path
