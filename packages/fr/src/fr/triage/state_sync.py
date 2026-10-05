"""Move a scope's durable triage state between its state directory and a repo
(spec 2026-10-05-triage-pages-goal, R12, §H).

The durable state is what an agent or the engine authored and cannot recollect:
the three YAML files, each page's manifest directory (manifest and fragment files),
the stored snapshots and the authored fragment sources. Facts files and the rendered
pages are rebuilt from the forge and never travel, in either direction.

Copies keep the source's mtime (`shutil.copy2`) and never delete a destination file.
A destination file byte-identical to its source is skipped as `identical`: it is
neither copied nor overwritten. Import skips a state file whose mtime is newer than
the repo copy's unless forced. That check reads file mtimes only, and git keeps none:
a fresh checkout or pull stamps every file with the time it was written, so the repo
copy looks newer than anything edited before it and an edited state file is
overwritten (p4-r5). Export before you pull, or compare first.

A symlink is never followed, in either direction and at any depth, and a destination
that is (or sits under) a symlink is never written through: export feeds a commit the
driver pushes, and import reads a cloned repo (p4-sec-symlink-follow). Both are
skipped and reported.

The repo-side root is `<base>/<rel>`, and only *rel* (the parts fr appends: the scope
name, the configured export path) is checked by `contained`: no `..`, no symlinked
component, nothing that resolves outside *base* (p4-sec-root-symlink-traversal). The
base itself is trusted as given: on macOS `/var` and `/tmp` are symlinks.
"""

from __future__ import annotations

import filecmp
import os
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from fr.triage.errors import TriageError

DURABLE_FILES = ("judgements.yaml", "origins.yaml", "subsystems.yaml")
DURABLE_DIRS = ("board", "origins", "architecture", "history", "snapshots", "authored-src")
_SKIPPED_PARTS = frozenset({"__pycache__"})
SYMLINK = "symlink, not followed"
SYMLINK_DEST = "the destination is a symlink, not written through"
NEWER = "newer in the state directory; --force overwrites it"
IDENTICAL = "identical"


class Skipped(NamedTuple):
    path: str  # POSIX, relative to the root it was read from
    reason: str


@dataclass(frozen=True)
class SyncReport:
    """The relative paths copied, and those left alone with the reason."""

    copied: tuple[str, ...]
    skipped: tuple[Skipped, ...]


def contained(base: Path, rel: str) -> Path:
    """`base / rel`, refused (`TriageError`, naming the path) when *rel* is absolute,
    has an empty, `.` or `..` part, has an existing component under *base* that is a
    symlink (the last one included), or resolves outside `base.resolve()`."""
    parts = rel.replace("\\", "/").split("/")
    if not rel or rel.startswith(("/", "\\")) or any(p in ("", ".", "..") for p in parts):
        raise TriageError(f"{rel!r} must be a plain relative path under {base}")
    path = base
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise TriageError(f"{path} is a symlink; refusing to read or write through it")
    target = base / "/".join(parts)
    root = base.resolve()
    if not target.resolve().is_relative_to(root):
        raise TriageError(f"{target} resolves outside {base}; refusing it")
    return target


def check_scope_name(name: str) -> str:
    """*name* when it is one plain path part (no separator, not `.` or `..`): the scope
    names the repo-side directory, so it must never step out of it."""
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise TriageError(f"scope name {name!r} is not a single plain path part")
    return name


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
        if target.is_file() and filecmp.cmp(source, target, shallow=False):
            skipped.append(Skipped(rel, IDENTICAL))
            continue
        if keep_newer and target.is_file() and target.stat().st_mtime > source.stat().st_mtime:
            skipped.append(Skipped(rel, NEWER))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)
        copied.append(rel)
    return SyncReport(copied=tuple(copied), skipped=tuple(skipped))


def export_state(state_dir: Path, base: Path, rel: str) -> SyncReport:
    """Copy *state_dir*'s durable state into the repo-side root `contained(base, rel)`
    (`<dir>/<scope>/`), overwriting what is there."""
    return _sync(state_dir, contained(base, rel), keep_newer=False)


def import_state(base: Path, rel: str, state_dir: Path, *, force: bool) -> SyncReport:
    """Copy the repo-side root `contained(base, rel)` into *state_dir*; a state file
    newer than its copy is skipped unless *force*."""
    return _sync(contained(base, rel), state_dir, keep_newer=not force)
