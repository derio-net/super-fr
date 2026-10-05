"""The drive lock's file and liveness rule, as pure path + pid logic (wave-driver R6).

`fr triage batch drive` takes `<state dir>/drive.lock` (see `triage_batch_cmd.drive_lock`);
`fr triage board --watch` only needs to know whether a live driver holds it, and must not
import the command module that owns the lock (the import between the two stays one-way).
Both share this reading, so "alive" means the same thing to each.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DRIVE_LOCK = "drive.lock"


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


def live_driver(target: Path) -> int | None:
    """The pid of the live driver holding `<target>/drive.lock`, else None (no lock,
    a lock not yet whole, or one whose pid is gone)."""
    held = lock_text(target / DRIVE_LOCK)
    pid = lock_pid(held) if held is not None else None
    return pid if pid is not None and pid_alive(pid) else None
