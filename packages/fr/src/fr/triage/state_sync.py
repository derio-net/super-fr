"""Move a scope's durable triage state between its state directory and a repo
(spec 2026-10-05-triage-pages-goal, R12, §H).

The durable state is what an agent or the engine authored and cannot recollect:
the three YAML files, each page's manifest directory (manifest and fragment files),
the stored snapshots and the authored fragment sources. Facts files and the rendered
pages are rebuilt from the forge and never travel, in either direction.

Copies keep the source's mode and mtime (as `shutil.copy2` did) and never delete a
destination file.
A destination file byte-identical to its source is skipped as `identical`: it is
neither copied nor overwritten. Import skips a state file whose mtime is newer than
the repo copy's unless forced. That check reads file mtimes only, and git keeps none:
a fresh checkout or pull stamps every file with the time it was written, so the repo
copy looks newer than anything edited before it and an edited state file is
overwritten (p4-r5). Export before you pull, or compare first.

A symlink is never followed, in either direction and at any depth, and a destination
that is (or sits under) a symlink is never written through: export feeds a commit the
driver pushes, and import reads a cloned repo (p4-sec-symlink-follow). Both are
skipped and reported. The copy itself opens every component with `O_NOFOLLOW` from
its parent's descriptor, so a path swapped for a symlink after those checks is
skipped the same way rather than followed (gh#1003).

The repo-side root is `<base>/<rel>`, and only *rel* (the parts fr appends: the scope
name, the configured export path) is checked by `contained`: no `..`, no symlinked
component, nothing that resolves outside *base* (p4-sec-root-symlink-traversal). The
base itself is trusted as given: on macOS `/var` and `/tmp` are symlinks.
"""

from __future__ import annotations

import errno
import filecmp
import os
import shutil
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from fr.triage.errors import TriageError

# The export set: a subset of `fr.triage.state_ref.REF_FILES` (the state ref carries more:
# merge stops, the lease, durable settings, the cloud mailbox), pinned by test_triage_state_ref.
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


def _same(a: Path, b: Path) -> bool:
    try:
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False  # unreadable: never "identical"; the copy reports the error


class _SymlinkError(Exception):
    """A path component turned out to be a symlink when it was opened."""


def _open(name: str, flags: int, *, dir_fd: int, mode: int = 0o777) -> int:
    """`os.open` of *name* under *dir_fd* with `O_NOFOLLOW`: `_SymlinkError` when the
    refusal was a symlink, the `OSError` itself otherwise."""
    try:
        return os.open(name, flags | os.O_NOFOLLOW | os.O_CLOEXEC, mode, dir_fd=dir_fd)
    except OSError as exc:
        try:
            link = stat.S_ISLNK(os.lstat(name, dir_fd=dir_fd).st_mode)
        except OSError:
            raise exc from None
        if link:
            raise _SymlinkError(name) from None
        raise


def _open_dir(root: Path, parts: tuple[str, ...], *, create: bool) -> int:
    """A descriptor for `root/<parts>`, each part opened from its parent's descriptor
    and never through a symlink; *create* makes the missing ones, *root* included.
    *root* is trusted as given, like the base `contained` leaves alone."""
    if create:
        root.mkdir(parents=True, exist_ok=True)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, dir_fd=fd)
                except FileExistsError:
                    pass
            child = _open(part, os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = child
    except BaseException:
        os.close(fd)
        raise
    return fd


def _copy(src: Path, dest: Path, rel: str) -> str | None:
    """Copy `src/rel` to `dest/rel` from descriptors, keeping the source's mode and
    times as `shutil.copy2` did; the skip reason when a component is a symlink by the
    time it is opened, None once copied. The checks before it read the tree by name,
    so a path swapped after them must still never be followed (gh#1003)."""
    *dirs, name = PurePosixPath(rel).parts
    try:
        parent = _open_dir(src, tuple(dirs), create=False)
        try:  # O_NONBLOCK: a fifo swapped in must not hang the open
            source = _open(name, os.O_RDONLY | os.O_NONBLOCK, dir_fd=parent)
        finally:
            os.close(parent)
    except _SymlinkError:
        return SYMLINK
    with os.fdopen(source, "rb") as reader:
        info = os.fstat(reader.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OSError(errno.EINVAL, "not a regular file")
        try:
            parent = _open_dir(dest, tuple(dirs), create=True)
            try:
                target = _open(
                    name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, dir_fd=parent, mode=0o600
                )
            finally:
                os.close(parent)
        except _SymlinkError:
            return SYMLINK_DEST
        with os.fdopen(target, "wb") as writer:
            shutil.copyfileobj(reader, writer)
            writer.flush()
            os.fchmod(writer.fileno(), stat.S_IMODE(info.st_mode))
            os.utime(writer.fileno(), ns=(info.st_atime_ns, info.st_mtime_ns))
    return None


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
        if target.is_file() and _same(source, target):
            skipped.append(Skipped(rel, IDENTICAL))
            continue
        if keep_newer and target.is_file() and target.stat().st_mtime > source.stat().st_mtime:
            skipped.append(Skipped(rel, NEWER))
            continue
        try:
            refused = _copy(src, dest, rel)
        except OSError as exc:  # p4-r10: a clean refusal naming the file, never a traceback
            why = exc.strerror or type(exc).__name__
            raise TriageError(f"cannot copy {rel} to {dest}: {why}") from exc
        if refused:
            skipped.append(Skipped(rel, refused))
            continue
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
