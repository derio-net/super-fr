"""Nonblocking OS ownership of a scope's replacement writer (scope before pane)."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fr.file_lock import FileLockError, exclusive_file_lock
from fr.triage.errors import TriageError


@contextmanager
def replacement_scope_lock(target: Path) -> Iterator[None]:
    root = Path(os.environ.get("FR_TRIAGE_LOCK_DIR", Path.home() / ".cache/fr/triage-locks"))
    key = hashlib.sha256(str(target.resolve()).encode()).hexdigest()
    path = root / f"{key}.lock"
    try:
        with exclusive_file_lock(path):
            yield
    except FileLockError as exc:
        raise TriageError(
            f"scope replacement writer: {exc}; use reliable local FR_TRIAGE_LOCK_DIR"
        ) from exc
