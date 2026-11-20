"""`drive.log`: what a looping driver and its supervisor print, kept (spec
2026-11-19-batch-train-truth R22-R23).

One host-local file in the scope's state directory, never on the state ref and never read to
decide anything: it is for the operator (`fr triage drive log`, the board's Activity panel).
Each line is `<ISO UTC> <kind> <line>`; a write that would pass the size limit first moves the
file to `drive.log.1`, replacing the previous one, so two files at most remain.
"""

from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

LOG_FILE = "drive.log"
LOCK_FILE = "drive.log.lock"
KINDS = ("pass", "action", "transient", "refusal", "restart", "stop")
LIMIT_BYTES = 5 * 1024 * 1024
FOLLOW_POLL_S = 1.0


class DriveLog:
    """The activity log of the scope whose state directory is *state_dir*."""

    def __init__(self, state_dir: Path, *, limit: int = LIMIT_BYTES) -> None:
        self.path = state_dir / LOG_FILE
        self.previous = state_dir / f"{LOG_FILE}.1"
        self.lock = state_dir / LOCK_FILE
        self.limit = limit

    @contextmanager
    def _locked(self, *, shared: bool = False) -> Iterator[None]:
        """`flock` on a sidecar file: the size check, the rotation and the write of one
        appender are one step across processes, and a reader never sees a half-rotation."""
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        with self.lock.open("ab") as handle:
            fcntl.flock(handle, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def append(self, kind: str, line: str, now: datetime) -> None:
        """Add one entry, rotating first when it would pass the limit. Opened, written and
        closed per line, so a crash loses no earlier line. A multi-line *line* is one entry.
        The size is read again under the lock, so two processes never rotate twice."""
        stamp = now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        text = f"{stamp} {kind} {' '.join(line.split())}\n"
        data = text.encode("utf-8")
        with self._locked():
            try:
                size = self.path.stat().st_size
            except FileNotFoundError:
                size = 0
            if size and size + len(data) > self.limit:
                os.replace(self.path, self.previous)
            with self.path.open("ab") as handle:
                handle.write(data)

    @staticmethod
    def _lines(path: Path) -> list[str]:
        try:
            return path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

    def tail(self, n: int = 50) -> list[str]:
        """The newest *n* lines, oldest first, across the rotation boundary."""
        if n <= 0:
            return []
        with self._locked(shared=True):
            lines = self._lines(self.previous) + self._lines(self.path)
        return lines[-n:]

    def follow(
        self,
        *,
        tail: int | None = None,
        sleep: Callable[[float], None] = time.sleep,
        poll: float = FOLLOW_POLL_S,
    ) -> Iterator[str]:
        """Lines appended from now on, polling every *poll* seconds; with *tail*, the newest
        that many first, from the SAME read that fixes where following starts, so no line
        falls between the two. A rotation (the path now names another file, or a smaller
        one) is followed: the old file's tail is drained, then the new one is read from its
        start. Only whole lines are yielded. Never ends by itself."""
        handle: BinaryIO | None = None
        inode = 0
        pending = b""  # the bytes after the last newline read: a line still being written
        first = True  # the first open starts at the end; any later one (a rotation) at 0
        try:
            if tail is not None:
                with self._locked(shared=True):
                    earlier = self._lines(self.previous)
                    try:
                        handle = self.path.open("rb")
                    except FileNotFoundError:
                        handle = None
                    if handle is not None:
                        inode = os.fstat(handle.fileno()).st_ino
                        lines, pending = self._split(handle.read(), b"")
                    else:
                        lines = []
                first = False
                if tail > 0:
                    yield from (earlier + lines)[-tail:]
            while True:
                try:
                    st: os.stat_result | None = self.path.stat()
                except FileNotFoundError:
                    st = None
                if handle is not None and (
                    st is None or st.st_ino != inode or st.st_size < handle.tell()
                ):
                    lines, pending = self._split(handle.read(), pending)
                    yield from lines
                    if pending:
                        yield pending.decode("utf-8", errors="replace")
                        pending = b""
                    handle.close()
                    handle = None
                if handle is None and st is not None:
                    handle = self.path.open("rb")
                    inode = os.fstat(handle.fileno()).st_ino
                    if first:
                        handle.seek(0, os.SEEK_END)
                    first = False
                if handle is None:
                    first = False  # no file yet: whatever appears is new
                else:
                    lines, pending = self._split(handle.read(), pending)
                    yield from lines
                sleep(poll)
        finally:
            if handle is not None:
                handle.close()

    @staticmethod
    def _split(chunk: bytes, pending: bytes) -> tuple[list[str], bytes]:
        """The whole lines of *pending* + *chunk*, and the unfinished rest."""
        data = pending + chunk
        *whole, rest = data.split(b"\n")
        return [raw.decode("utf-8", errors="replace") for raw in whole], rest
