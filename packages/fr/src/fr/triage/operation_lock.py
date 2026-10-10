"""Nonblocking OS ownership of a scope's replacement writer (scope before pane)."""

from __future__ import annotations

import fcntl
import hashlib
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fr.triage.errors import TriageError


@contextmanager
def replacement_scope_lock(target: Path) -> Iterator[None]:
    root = Path(os.environ.get("FR_TRIAGE_LOCK_DIR", Path.home() / ".cache/fr/triage-locks"))
    key = hashlib.sha256(str(target.resolve()).encode()).hexdigest()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{key}.lock"
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise TriageError("scope replacement writer is locked") from exc
        try:
            probe = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import fcntl,sys\nwith open(sys.argv[1], 'a') as f:\n"
                    " try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                    " except BlockingIOError: sys.exit(3)\n sys.exit(0)\n",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if probe.returncode != 3:
                raise TriageError(
                    "filesystem does not enforce scope lock; use reliable local FR_TRIAGE_LOCK_DIR"
                )
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
