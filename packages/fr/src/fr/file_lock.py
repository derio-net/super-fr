"""Shared nonblocking OS-backed file ownership with independent exclusion verification.

Some shared filesystems acknowledge flock without excluding another process. Never
yield ownership there: this infrastructure helper probes that contract, not a forge.
"""

from __future__ import annotations

import fcntl
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class FileLockError(Exception):
    """Contention or unverifiable OS exclusion is not permission to mutate."""


@contextmanager
def exclusive_file_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise FileLockError("locked") from exc
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
                raise FileLockError("filesystem does not enforce lock")
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
