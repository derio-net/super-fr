"""The drive lock's file and liveness rule, as pure path + pid logic (wave-driver R6).

`fr triage batch drive` takes `<state dir>/drive.lock` (see `triage_batch_cmd.drive_lock`);
`fr triage board --watch` only needs to know whether a live driver holds it, and must not
import the command module that owns the lock (the import between the two stays one-way).
Both share this reading, so "alive" means the same thing to each.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

DRIVE_LOCK = "drive.lock"
LOCK_GRACE = 10.0
"""Seconds an unreadable `drive.lock` is held: long enough for a starter that
created it to have written it (review rg-7)."""


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # alive, owned by someone else
    return True


def lock_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def lock_pid(text: str) -> int | None:
    """The pid a lock names, or None when it is not (yet) a whole lock."""
    try:
        return int(json.loads(text)["pid"])
    except (ValueError, KeyError, TypeError):
        return None


def lock_holder(path: Path, text: str) -> str | None:
    """THE liveness rule: who holds the lock at *path* whose content is *text*, or None
    when it is stale. A whole lock is held while its pid lives (`pid <n>, started <t>`);
    one not yet whole is held for `LOCK_GRACE` seconds after it was written (`a driver
    starting up`). The drive and `--watch` both decide through this (review p3-r4)."""
    pid = lock_pid(text)
    if pid is None:
        try:
            age = time.time() - path.stat().st_mtime
        except FileNotFoundError:
            return None
        return "a driver starting up" if age < LOCK_GRACE else None
    if not pid_alive(pid):
        return None
    return f"pid {pid}, started {json.loads(text).get('started')}"


def live_driver(target: Path) -> str | None:
    """Who holds `<target>/drive.lock` (see `lock_holder`), else None: no lock, or a
    stale one."""
    path = target / DRIVE_LOCK
    held = lock_text(path)
    return lock_holder(path, held) if held is not None else None
