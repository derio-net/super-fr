"""One harness-neutral view of a harness session — what every transcript gate
reads (spec 2026-09-29-opencode-observe §A, R4).

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
    @property
    def harness(self) -> str:
        """The `detect_harness` key of the backend."""
        ...

    @property
    def session(self) -> str:
        """The session id this view reads."""
        ...

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


def _iso(stamp: _dt.datetime) -> str:
    return stamp.isoformat()


@dataclass(frozen=True)
class ClaudeCodeSession:
    """One Claude Code transcript file: the orchestrator's own
    `<session>.jsonl` (`main_thread`, its sidechain records skipped), or one
    subagent's `agent-<id>.jsonl` (sidechain throughout, read whole). Every
    method delegates to the reader `fr.run.telemetry` always had."""

    transcript: Path
    session: str
    main_thread: bool = True
    harness: str = "claude-code"

    def answered_rounds(self, since: _dt.datetime) -> list[Round] | None:
        from fr.run.telemetry import answered_rounds_in

        return answered_rounds_in(self.transcript, since)

    def dispatches(self, since: _dt.datetime) -> list[ChildDispatch] | None:
        from fr.run.telemetry import _read_records, attribute_dispatches, dispatch_results

        records = _read_records(self.transcript)
        if records is None:
            return None
        results = dispatch_results(records)
        return [
            ChildDispatch(
                agent_id=d.agent_id,
                agent_type=d.agent_type,
                started=d.started,
                returned=results.get(d.tool_use_id),
            )
            for d in attribute_dispatches(self.transcript)
            if d.started is not None and d.started >= since
        ]

    def child(self, agent_id: str) -> ClaudeCodeSession | Literal[False] | None:
        from fr.run.telemetry import witness_transcript

        found = witness_transcript(self.transcript, agent_id)
        if not isinstance(found, Path):
            return found
        return ClaudeCodeSession(found, agent_id, main_thread=False)

    def first_read(
        self, path: Path, since: _dt.datetime, *, not_before: _dt.datetime | None = None
    ) -> _dt.datetime | Literal[False] | None:
        from fr.run.telemetry import read_file_since

        return read_file_since(
            self.transcript,
            path,
            _iso(since),
            not_before=not_before,
            main_thread=self.main_thread,
        )

    def first_shell_executing(
        self, script: Path, since: _dt.datetime
    ) -> _dt.datetime | Literal[False] | None:
        from fr.run.telemetry import shell_named_since

        return shell_named_since(self.transcript, script, _iso(since), main_thread=self.main_thread)

    def wrote_windows(
        self, log: Path, since: _dt.datetime
    ) -> list[tuple[_dt.datetime, _dt.datetime]] | None:
        from fr.run.telemetry import orchestrator_wrote_in

        return orchestrator_wrote_in(self.transcript, log, since)


@dataclass
class OpenCodeSession:
    db: Path
    session: str
    harness: str = "opencode"


def _harness(env: Mapping[str, str]) -> str | None:
    from fr.harness.detect import detect_harness
    from fr.harness.model import HarnessError

    try:
        return detect_harness(env)
    except HarnessError:
        return None


def observed_session(env: Mapping[str, str], session: str | None = None) -> ObservedSession | None:
    """The view of `session` (default: this process's own, `current_session`)
    for the harness `env` runs under — or `None` where fr cannot observe one:
    no harness detected, a harness with no backend (Hermes), no session id, or
    (Claude Code) no transcript for it."""
    from fr.run.telemetry import (
        ClaudeCodeReader,
        OpenCodeReader,
        claude_code_session,
        current_session,
    )

    harness = _harness(env)
    sid = session or current_session(env)
    if harness is None or not sid:
        return None
    if harness == ClaudeCodeReader.harness:
        try:
            transcript = claude_code_session(env, sid)
        except OSError:
            return None
        return None if transcript is None else ClaudeCodeSession(transcript, sid)
    if harness == OpenCodeReader.harness:
        return OpenCodeSession(OpenCodeReader().database(env), sid)  # type: ignore[return-value]
    return None
