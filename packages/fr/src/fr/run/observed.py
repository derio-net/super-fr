"""One harness-neutral view of a harness session — what every transcript gate
reads (spec 2026-10-02-opencode-observe-2 §A, R4).

A gate asks an `ObservedSession` what happened in a session: the operator
question rounds answered, the subagents it dispatched and what each returned,
the files it read, the shells it ran, the logs it wrote. Two backends answer:
`ClaudeCodeSession` (the session's JSONL transcript, today's readers in
`fr.run.telemetry` moved behind the protocol) and `OpenCodeSession`
(`opencode.db`, read-only, scoped to one session id).

Every method keeps the three-valued contract the transcript gates were built
on: `None` = could not read, `False` / `[]` = read and found nothing.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from fr.run.telemetry import Round


@dataclass(frozen=True)
class ChildDispatch:
    """One subagent this session dispatched."""

    agent_id: str
    """Claude Code: the subagent's agentId; OpenCode: the child session id."""
    agent_type: str | None
    started: _dt.datetime | None
    returned: str | None
    """The child's final message as the dispatcher received it; `None` while it
    runs, or when it cannot be read."""


class ObservedSession(Protocol):
    harness: str
    session: str

    def answered_rounds(self, since: _dt.datetime) -> list[Round] | None: ...

    def dispatches(self, since: _dt.datetime) -> list[ChildDispatch] | None: ...

    def child(self, agent_id: str) -> ObservedSession | Literal[False] | None: ...

    def first_read(
        self, path: Path, since: _dt.datetime, *, not_before: _dt.datetime | None = None
    ) -> _dt.datetime | Literal[False] | None: ...

    def first_shell_executing(
        self, script: Path, since: _dt.datetime
    ) -> _dt.datetime | Literal[False] | None: ...

    def wrote_windows(
        self, log: Path, since: _dt.datetime
    ) -> list[tuple[_dt.datetime, _dt.datetime]] | None: ...


_TIER_SUFFIXES = ("-mechanical", "-standard", "-hard")


def agent_name(agent_type: str) -> str:
    """`agent_type` without a plugin qualifier (`super-fr:`) or an OpenCode
    tier suffix (`-mechanical`, `-standard`, `-hard`): the one spelling every
    agent-type comparison uses."""
    bare = agent_type.split(":", 1)[-1]
    for suffix in _TIER_SUFFIXES:
        if bare.endswith(suffix):
            return bare[: -len(suffix)]
    return bare


@dataclass
class OpenCodeSession:
    db: Path
    session: str
    harness: str = "opencode"


def observed_session(env: Mapping[str, str], session: str | None = None) -> ObservedSession | None:
    """The session view for the harness `env` runs under, or `None`."""
    from fr.run.telemetry import OpenCodeReader

    sid = session or env.get("FR_OPENCODE_SESSION_ID")
    if env.get("FR_HARNESS") == "opencode" and sid:
        return OpenCodeSession(OpenCodeReader().database(env), sid)  # type: ignore[return-value]
    return None
