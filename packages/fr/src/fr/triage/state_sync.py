"""Move a scope's durable triage state between its state directory and a repo
(spec 2026-10-05-triage-pages-goal, R12, §H).

The durable state is what an agent or the engine authored and cannot recollect:
the three YAML files, each page's manifest directory (manifest and fragment files),
the stored snapshots and the authored fragment sources. Facts files and the rendered
pages are rebuilt from the forge and never travel, in either direction.

Copies keep the source's mtime (`shutil.copy2`) and never delete a destination file.
Import skips a state file that is newer than the repo copy unless forced, so a
judgement edited since the last export is never silently overwritten.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

DURABLE_FILES = ("judgements.yaml", "origins.yaml", "subsystems.yaml")
DURABLE_DIRS = ("board", "origins", "architecture", "history", "snapshots", "authored-src")
_SKIPPED_PARTS = frozenset({"__pycache__"})


@dataclass(frozen=True)
class SyncReport:
    """The repo-relative paths copied, and those left alone (import only)."""

    copied: tuple[str, ...]
    skipped: tuple[str, ...]


def durable_paths(root: Path) -> Iterator[str]:
    """Every durable file under *root*, as a POSIX path relative to it, in order."""
    for name in DURABLE_FILES:
        if (root / name).is_file():
            yield name
    for name in DURABLE_DIRS:
        base = root / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            rel = path.relative_to(root)
            if path.is_file() and not _SKIPPED_PARTS.intersection(rel.parts):
                yield rel.as_posix()


def _sync(src: Path, dest: Path, *, keep_newer: bool) -> SyncReport:
    copied: list[str] = []
    skipped: list[str] = []
    for rel in durable_paths(src):
        source, target = src / rel, dest / rel
        if keep_newer and target.is_file() and target.stat().st_mtime > source.stat().st_mtime:
            skipped.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(rel)
    return SyncReport(copied=tuple(copied), skipped=tuple(skipped))


def export_state(state_dir: Path, dest_root: Path) -> SyncReport:
    """Copy *state_dir*'s durable state into *dest_root* (the repo-side
    `<dir>/<scope>/`), overwriting what is there."""
    return _sync(state_dir, dest_root, keep_newer=False)


def import_state(src_root: Path, state_dir: Path, *, force: bool) -> SyncReport:
    """Copy *src_root*'s durable state (the repo-side `<dir>/<scope>/`) into
    *state_dir*; a state file newer than its copy is skipped unless *force*."""
    return _sync(src_root, state_dir, keep_newer=not force)
