"""One reader per harness, each normalizing a session into a `UsageRecord`.

A reader is a `read(source, session=None) -> UsageRecord` that NEVER raises:
every I/O or parse failure becomes `UsageRecord.unavailable`. `source` is the
harness's own store — a Claude Code main transcript (the session id is its
file name), or an OpenCode / Hermes SQLite database plus a session id.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, runtime_checkable

from fr.usage.model import UsageRecord
from fr.usage.readers import claude_code, hermes, opencode


@runtime_checkable
class UsageReader(Protocol):
    def read(self, source: Path, session: str | None = None) -> UsageRecord: ...


class _ModuleReader:
    def __init__(self, module: object) -> None:
        self._read = getattr(module, "read")

    def read(self, source: Path, session: str | None = None) -> UsageRecord:
        return self._read(source, session)  # type: ignore[no-any-return]


READERS: Mapping[str, UsageReader] = {
    claude_code.HARNESS: _ModuleReader(claude_code),
    opencode.HARNESS: _ModuleReader(opencode),
    hermes.HARNESS: _ModuleReader(hermes),
}
"""Harness key -> reader. An unlisted harness has no reader — never a fallback."""
