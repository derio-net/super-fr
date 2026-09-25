"""Where a session's transcript lives on THIS host, and which sessions a run names.

Shared by `fr usage` (`fr.commands.usage_cmd`) and capture (`fr.usage.capture`),
so "find a session" is one rule, not two.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

from fr.run.telemetry import OpenCodeReader, claude_code_session
from fr.usage.model import UsageRecord, unavailable
from fr.usage.readers import READERS

HERMES_DB_ENV = "FR_HERMES_DB"
HERMES_DB = Path(".hermes") / "state.db"


def source_of(harness: str, session: str, env: Mapping[str, str]) -> Path | None:
    if harness == "claude-code":
        return claude_code_session(env, session)
    if harness == "opencode":
        return OpenCodeReader().database(env)
    override = env.get(HERMES_DB_ENV)
    return Path(override) if override else Path.home() / HERMES_DB


def read_session(harness: str, session: str, env: Mapping[str, str]) -> UsageRecord:
    """The live record for one session — `unavailable` when it cannot be found,
    or when fr has no reader for its harness (never read as another harness)."""
    if harness not in READERS:
        return unavailable(session, harness, "no reader for this harness")
    source = source_of(harness, session, env)
    if source is None:
        return unavailable(session, harness, "no transcript found for this session on this host")
    return READERS[harness].read(source, session)


def sessions_of(node: object) -> Iterator[tuple[str, str]]:
    """Every `(harness, session)` a cursor records, wherever an attempt sits.

    Only an attempt that names NO harness is read as Claude Code (the cursors
    that predate the field); a harness fr has no reader for stays itself, and
    `read_session` reports it unavailable rather than relabelling it."""
    if isinstance(node, Mapping):
        session = node.get("session")
        if isinstance(session, str) and session:
            harness = node.get("harness")
            yield ("claude-code" if harness is None else str(harness), session)
        for value in node.values():
            yield from sessions_of(value)
    elif isinstance(node, list | tuple):
        for value in node:
            yield from sessions_of(value)


__all__ = ["HERMES_DB", "HERMES_DB_ENV", "read_session", "sessions_of", "source_of"]
