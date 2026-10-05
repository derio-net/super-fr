"""Move a scope's durable triage state between its state directory and a repo
(spec 2026-10-05-triage-pages-goal, R12, §H).

The durable state is what an agent or the engine authored and cannot recollect:
the three YAML files, each page's manifest directory (manifest and fragment files),
the stored snapshots and the authored fragment sources. Facts files and the rendered
pages are rebuilt from the forge and never travel, in either direction.

Copies keep the source's mtime (`shutil.copy2`) and never delete a destination file.
Import skips a state file that is newer than the repo copy unless forced, so a
judgement edited since the last export is never silently overwritten.

A symlink is never followed, in either direction and at any depth, and a destination
that is (or sits under) a symlink is never written through: export feeds a commit the
driver pushes, and import reads a cloned repo (p4-sec-symlink-follow). Both are
skipped and reported.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import NamedTuple

DURABLE_FILES = ("judgements.yaml", "origins.yaml", "subsystems.yaml")
DURABLE_DIRS = ("board", "origins", "architecture", "history", "snapshots", "authored-src")
_SKIPPED_PARTS = frozenset({"__pycache__"})
SYMLINK = "symlink, not followed"
SYMLINK_DEST = "the destination is a symlink, not written through"
NEWER = "newer in the state directory; --force overwrites it"


class Skipped(NamedTuple):
    path: str  # POSIX, relative to the root it was read from
    reason: str


@dataclass(frozen=True)
class SyncReport:
    """The relative paths copied, and those left alone with the reason."""

    copied: tuple[str, ...]
    skipped: tuple[Skipped, ...]


def _walk(root: Path, rel: PurePosixPath) -> Iterator[tuple[str, bool]]:
    """(path, is_symlink) for every regular file and symlink under *root*/*rel*, never
    descending into a symlinked directory (`os.scandir` with `follow_symlinks=False`)."""
    try:
        entries = sorted(os.scandir(root / rel), key=lambda e: e.name)
    except FileNotFoundError:
        return
    for entry in entries:
        if entry.name in _SKIPPED_PARTS:
            continue
        child = rel / entry.name
        if entry.is_symlink():
            yield child.as_posix(), True
        elif entry.is_dir(follow_symlinks=False):
            yield from _walk(root, child)
        elif entry.is_file(follow_symlinks=False):
            yield child.as_posix(), False


def durable_entries(root: Path) -> Iterator[tuple[str, bool]]:
    """Every durable file or symlink under *root*: (POSIX path relative to it, whether
    it is a symlink). A symlink is reported, never followed, at any depth: a durable
    file or directory that is itself a symlink included. Anything else (a socket, a
    fifo) is not durable state and is left out."""
    for name in DURABLE_FILES:
        path = root / name
        if path.is_symlink():
            yield name, True
        elif path.is_file():
            yield name, False
    for name in DURABLE_DIRS:
        path = root / name
        if path.is_symlink():
            yield name, True
        elif path.is_dir():
            yield from _walk(root, PurePosixPath(name))


def _symlinked_dest(dest: Path, rel: str) -> bool:
    """Whether the target, or any directory between *dest* and it, is a symlink."""
    path = dest
    for part in PurePosixPath(rel).parts:
        path = path / part
        if path.is_symlink():
            return True
    return False


def _sync(src: Path, dest: Path, *, keep_newer: bool) -> SyncReport:
    copied: list[str] = []
    skipped: list[Skipped] = []
    for rel, link in durable_entries(src):
        source, target = src / rel, dest / rel
        if link:
            skipped.append(Skipped(rel, SYMLINK))
            continue
        if _symlinked_dest(dest, rel):
            skipped.append(Skipped(rel, SYMLINK_DEST))
            continue
        if keep_newer and target.is_file() and target.stat().st_mtime > source.stat().st_mtime:
            skipped.append(Skipped(rel, NEWER))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)
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
