"""Crash-safe artifact writes and the cross-process migration lock (r5-e7).

Two hazards this module closes, both of which the migration framework is
unusually exposed to because it runs **automatically, before the command the
operator typed**, over files an agent may have open:

1. **A half-written artifact.** Every stamp writer and every repair was
   `path.write_text(...)`, which truncates first and writes second. A crash, a
   full disk, or an `ENOSPC` between the two leaves a plan's `_meta.yaml`
   truncated — and a truncated `_meta.yaml` reads as version 1, so the next run
   tries to migrate it again and `fr` refuses every command until a human
   notices. `write_text_atomic` writes a sibling temp file and `os.replace`s
   it, which is atomic within a filesystem: the artifact is either wholly old
   or wholly new.

2. **Two fr processes migrating one tree.** Two agents, or an agent and the
   operator, can easily run `fr` at the same second. Both would plan the same
   work, both would apply it, and both would try to commit — the second
   producing either an empty commit or a duplicate. `migration_lock` is an
   advisory `flock` in the repo's **git common directory**, so it is shared by
   every linked worktree of one repository (they share an object store) and is
   never itself an artifact.
"""

from __future__ import annotations

import contextlib
import errno
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

__all__ = ["LockBusyError", "migration_lock", "write_text_atomic"]


class LockBusyError(Exception):
    """Another fr process holds the migration lock for this repository."""


def write_text_atomic(path: Path, text: str) -> None:
    """Replace `path`'s contents with `text`, all-or-nothing.

    The temp file is created in the SAME directory, because `os.replace` is
    only atomic within one filesystem and `/tmp` frequently is not one. The
    original's permission bits are carried over — an artifact someone has
    `chmod`ed stays as they left it.

    A failure anywhere before the `os.replace` leaves the original file byte
    identical, which is the property the whole module exists for; the temp
    file is removed on the way out either way.
    """
    path = Path(path)
    directory = path.parent
    mode: int | None = None
    with contextlib.suppress(OSError):
        mode = path.stat().st_mode & 0o7777

    fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=f".{path.name}.", suffix=".fr-tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            # `newline=""` so a CRLF artifact stays CRLF: this is a byte-level
            # replacement of a file someone else authored, not a normaliser.
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


@contextlib.contextmanager
def migration_lock(lock_file: Path | None) -> Iterator[bool]:
    """Hold the advisory migration lock, or report that someone else does.

    Yields `True` when the lock was taken and `False` when it was already
    held — the caller decides. The migration runner's caller re-checks
    `is_stale` on `False`: the other process has very likely just finished
    the same work, in which case there is nothing left to do and the command
    proceeds normally. Blocking would be wrong (the gate runs before every
    command) and so would refusing outright (the common case is a race that
    has already resolved itself).

    `lock_file=None` — no git directory to put it in — yields `True`: an
    unlocked migration is what happened before this existed, and a repo
    without git has no concurrent-commit hazard to protect against.
    """
    if lock_file is None:
        yield True
        return

    import fcntl

    try:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o644)
    except OSError:
        # A read-only or unreachable git dir must not make migration
        # impossible; it only means the race is unguarded, exactly as before.
        yield True
        return

    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            if e.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            yield False
            return
        try:
            yield True
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        with contextlib.suppress(OSError):
            os.close(fd)
