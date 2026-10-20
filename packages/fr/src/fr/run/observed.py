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
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from fr.run.opencode_store import (
    ACTIVE_SINCE,
    DISPATCH_TOOL,
    MESSAGES_OF,
    MESSAGES_OF_SINCE,
    QUESTION_TOOL,
    READ_TOOL,
    SESSION_CHILDREN,
    SESSION_PARENT,
    SHELL_TOOL,
    TOP_LEVEL_MESSAGES_SINCE,
    V1_ONLY_REASON,
    StoredMessage,
    ToolItem,
    dispatch_agent,
    dispatch_child,
    dispatch_parent,
    final_text,
    store_version,
    stored_message,
    tool_items,
)
from fr.run.opencode_store import query as store_query

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

    def ran_windows(
        self, matches: Callable[[str], bool], since: _dt.datetime
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
        """`returned` is the child's own `SubagentHandback` report when it
        made one (a backgrounded dispatch — the parent then holds only a
        launch ack), else the parent-side `tool_result` text when that is not
        a launch ack, else `None` (review p1-r3)."""
        from fr.run.telemetry import (
            _read_records,
            attribute_dispatches,
            dispatch_results,
            handback_message,
        )

        records = _read_records(self.transcript)
        if records is None:
            return None
        results = dispatch_results(records)
        found: list[ChildDispatch] = []
        for d in attribute_dispatches(self.transcript, records):
            if d.started is None or d.started < since:
                continue
            child = _read_records(d.transcript)
            handback = handback_message(child) if child is not None else None
            found.append(
                ChildDispatch(
                    agent_id=d.agent_id,
                    agent_type=d.agent_type,
                    started=d.started,
                    returned=handback if handback is not None else results.get(d.tool_use_id),
                )
            )
        return found

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
        from fr.run.telemetry import wrote_since

        return wrote_since(self.transcript, log, _iso(since), main_thread=self.main_thread)

    def ran_windows(
        self, matches: Callable[[str], bool], since: _dt.datetime
    ) -> list[tuple[_dt.datetime, _dt.datetime]] | None:
        from fr.run.telemetry import ran_since

        return ran_since(self.transcript, matches, _iso(since), main_thread=self.main_thread)


# --- OpenCode -------------------------------------------------------------

OPENCODE_QUESTION_TOOL = QUESTION_TOOL
"""OpenCode's operator-question tool: `state.input.questions[]`, answered
`status: completed` with `state.metadata.answers: [[str]]`, declined
`status: error`, pending `status: running`."""

OPENCODE_ROUND_NEUTRAL_TOOLS = frozenset({"todowrite", "todoread"})
"""OpenCode's counterpart of `telemetry.ROUND_NEUTRAL_TOOLS`: its own
progress-tracking tools, which do not close a question round."""

_TASK_RESULT = re.compile(r"<task_result>(.*)</task_result>", re.DOTALL)

ToolPart = ToolItem
"""The name the readers used before OpenCode 2 (one `part` row); now one
`tool` item of a `session_message`'s `data.content[]` (`fr.run.opencode_store`)."""


def _answered(part: ToolItem) -> bool:
    answers = part.metadata.get("answers")
    return (
        part.status == "completed"
        and isinstance(answers, list)
        and any(isinstance(a, list) and a for a in answers)
    )


def _query(db: Path, sql: str, params: tuple[object, ...]) -> list[tuple[Any, ...]] | None:
    """Rows of one read-only query on OpenCode's database; `None` when it
    cannot be read (missing, locked, another schema)."""
    return store_query(db, sql, params)


def _messages(db: Path, sql: str, params: tuple[object, ...]) -> list[StoredMessage] | None:
    rows = _query(db, sql, params)
    return None if rows is None else [stored_message(row) for row in rows]


def _wrote_windows(
    db: Path, log: Path, start: _dt.datetime, session: str | None
) -> list[tuple[_dt.datetime, _dt.datetime]] | None:
    from fr.run.telemetry import _writes

    return _ran_windows(db, lambda command: _writes(command, log), start, session, log=log)


def _ran_windows(
    db: Path,
    matches: Callable[[str], bool],
    start: _dt.datetime,
    session: str | None,
    *,
    log: Path | None = None,
) -> list[tuple[_dt.datetime, _dt.datetime]] | None:
    """The `(start, end)` of every `shell` call whose command `matches` (for the
    write-target witness: WROTE `log`), started at or
    after `start`, completed with exit 0 — in `session`, or (`None`) in any
    TOP-LEVEL session (a subagent is a child session, `parent_id` set).
    `None` when the database cannot be read.

    A READABLE database is not necessarily the right one (gh#740: OpenCode ran
    under `XDG_DATA_HOME`, fr read `~/.local/share`). The orchestrator calling
    this is itself mid-`shell`, a message of its session, so a database that
    recorded no message at all since the unit opened cannot hold it: that is
    `None` (unobserved), never `[]`, which refuses as "nobody wrote it".
    Activity is read from `session_message.time_updated`. Exit 0
    (`state.metadata.exit`) stands in for Claude Code's `is_error`. A detached
    writer's window is extended only when there is a `log` to read its `exit=`
    line from.
    """
    from fr.run.telemetry import _BashCall, _detaches, _seen_exit

    since_ms = int(start.timestamp() * 1000)
    active = _query(db, ACTIVE_SINCE, (since_ms,))
    if session is None:
        messages = _messages(db, TOP_LEVEL_MESSAGES_SINCE, (since_ms,))
    else:
        messages = _messages(db, MESSAGES_OF_SINCE, (session, since_ms))
    if active is None or messages is None or not active:
        return None
    calls: list[_BashCall] = []
    for part in tool_items(messages):
        if part.tool != SHELL_TOOL or part.status != "completed":
            continue
        command = part.input.get("command")
        exit_code = part.metadata.get("exit")
        if (
            isinstance(command, str)
            and part.began is not None
            and part.ended is not None
            and part.began >= start
        ):
            calls.append(
                _BashCall(
                    part.began,
                    part.ended,
                    command,
                    exit_code if type(exit_code) is int else None,
                    part.output or "",
                )
            )
    calls.sort(key=lambda c: (c.began, c.ended))
    windows: list[tuple[_dt.datetime, _dt.datetime]] = []
    for call in calls:
        if call.exit_code != 0 or not matches(call.command):
            continue
        windows.append((call.began, call.ended))
        if log is not None and _detaches(call.command):
            seen = _seen_exit(call, calls, log)
            if seen is not None:
                windows.append((call.began, seen))
    return windows


@dataclass(frozen=True)
class OpenCodeSession:
    """One OpenCode 2 session of `opencode.db`, read-only: its OWN
    `session_message` rows' tool items for rounds, reads, shells and writes;
    its `subagent` items for dispatches (spec 2026-10-20 §D). A child session
    is a view of the same kind, reached through `child`."""

    db: Path
    session: str
    harness: str = "opencode"

    def _known(self) -> bool:
        """Is this session a `session_v2` row — readable AND the right
        database? A readable database that does not hold it is the wrong one
        (gh#740), which reads as unobserved, never as "nothing happened"; a 1.x
        session (`v1-only`) is not known either (R14)."""
        return store_version(self.db, self.session) == "v2"

    def _parts(self) -> list[ToolItem] | None:
        messages = _messages(self.db, MESSAGES_OF, (self.session,))
        # Only an EMPTY answer needs the second question (review p1-r2): a
        # session with messages is plainly a row of this database.
        if messages is None or (not messages and not self._known()):
            return None
        return tool_items(messages)

    def answered_rounds(self, since: _dt.datetime) -> list[Round] | None:
        from fr.run.telemetry import _question_texts, question_rounds

        parts = self._parts()
        if parts is None:
            return None
        return question_rounds(
            (
                (
                    p.tool,
                    p.call_id,
                    _question_texts(p.input) if p.tool == OPENCODE_QUESTION_TOOL else [],
                    p.began,
                )
                for p in parts
            ),
            since,
            question_tool=OPENCODE_QUESTION_TOOL,
            neutral=OPENCODE_ROUND_NEUTRAL_TOOLS,
            answered=lambda: {
                p.call_id
                for p in parts
                if p.tool == OPENCODE_QUESTION_TOOL and p.call_id and _answered(p)
            },
        )

    def _children(self) -> set[str] | None:
        rows = _query(self.db, SESSION_CHILDREN, (self.session,))
        if rows is None or (not rows and not self._known()):
            return None
        return {row[0] for row in rows}

    def _final_text(self, session: str) -> str | None:
        messages = _messages(self.db, MESSAGES_OF, (session,))
        return final_text(messages or ())

    def dispatches(self, since: _dt.datetime) -> list[ChildDispatch] | None:
        parts = self._parts()
        children = self._children()
        if parts is None or children is None:
            return None
        # One child per SESSION (review p2-r1): OpenCode resumes a subagent by
        # reusing its session, so sending a reviewer back is a second dispatch
        # item for the same child. Keyed by child, the latest dispatch wins.
        found: dict[str, ChildDispatch] = {}
        for part in parts:
            child = dispatch_child(part)
            if (
                part.tool != DISPATCH_TOOL
                or part.began is None
                or part.began < since
                or child is None
                # Both keys must agree: the item's parent AND the child
                # session's row.
                or dispatch_parent(part) != self.session
                or child not in children
            ):
                continue
            returned: str | None = None
            if part.status != "running":
                returned = self._final_text(child)
                if returned is None and part.output is not None:
                    match = _TASK_RESULT.search(part.output)
                    returned = match.group(1) if match else None
            found.pop(child, None)
            found[child] = ChildDispatch(
                agent_id=child,
                agent_type=dispatch_agent(part),
                started=part.began,
                returned=returned,
            )
        return list(found.values())

    def child(self, agent_id: str) -> OpenCodeSession | Literal[False] | None:
        children = self._children()
        if children is None:
            return None
        return OpenCodeSession(self.db, agent_id) if agent_id in children else False

    def _first(
        self, tool: str, since: _dt.datetime, matches: Callable[[Mapping[str, Any]], bool]
    ) -> _dt.datetime | Literal[False] | None:
        parts = self._parts()
        if parts is None:
            return None
        for part in parts:
            if (
                part.tool == tool
                and part.began is not None
                and part.began >= since
                and matches(part.input)
            ):
                return part.began
        return False

    def first_read(
        self, path: Path, since: _dt.datetime, *, not_before: _dt.datetime | None = None
    ) -> _dt.datetime | Literal[False] | None:
        real = os.path.realpath(path)
        start = max(since, not_before) if not_before is not None else since

        def names(tool_input: Mapping[str, Any]) -> bool:
            target = tool_input.get("filePath")
            return (
                isinstance(target, str)
                and os.path.isabs(target)
                and os.path.isabs(path)
                and os.path.realpath(target) == real
            )

        return self._first(READ_TOOL, start, names)

    def first_shell_executing(
        self, script: Path, since: _dt.datetime
    ) -> _dt.datetime | Literal[False] | None:
        from fr.run.telemetry import _executes

        def runs(tool_input: Mapping[str, Any]) -> bool:
            command = tool_input.get("command")
            return isinstance(command, str) and _executes(command, script)

        return self._first(SHELL_TOOL, since, runs)

    def wrote_windows(
        self, log: Path, since: _dt.datetime
    ) -> list[tuple[_dt.datetime, _dt.datetime]] | None:
        if not self._known():
            return None
        return _wrote_windows(self.db, log, since, self.session)

    def ran_windows(
        self, matches: Callable[[str], bool], since: _dt.datetime
    ) -> list[tuple[_dt.datetime, _dt.datetime]] | None:
        if not self._known():
            return None
        return _ran_windows(self.db, matches, since, self.session)


@dataclass(frozen=True)
class OpenCodeUnscoped:
    """OpenCode with no session id (the plugin not delivered, or older than
    `shell.env`): serves `wrote_windows` and `ran_windows` only, reading every TOP-LEVEL session
    active since — today's reading, which keeps `deliver-tests-provenance`
    enforced without the plugin (spec §A). Weaker than one session; still proof
    that an orchestrator's own shell command produced the bytes."""

    db: Path

    def wrote_windows(
        self, log: Path, since: _dt.datetime
    ) -> list[tuple[_dt.datetime, _dt.datetime]] | None:
        return _wrote_windows(self.db, log, since, None)

    def ran_windows(
        self, matches: Callable[[str], bool], since: _dt.datetime
    ) -> list[tuple[_dt.datetime, _dt.datetime]] | None:
        return _ran_windows(self.db, matches, since, None)


def opencode_unscoped(env: Mapping[str, str]) -> OpenCodeUnscoped:
    from fr.run.telemetry import OpenCodeReader

    return OpenCodeUnscoped(OpenCodeReader().database(env))


# --- what a command line runs ------------------------------------------------

_NEVER_IN_A_WALK = ("$(", "`", "<<", "\n", "#")
"""Text a walk command never carries: command substitution, a here-doc, a
second line, a comment. Present anywhere — quoted or not — and it is not one."""
_OPERATOR_CHARS = frozenset("();<>|&")


def walks_run(command: str, run: str) -> bool:
    """Is `command` EXACTLY a run of `fr verification walk --run <run>`? The
    command-match witness beside the write-target one
    (`fr.run.telemetry._writes`): the walk writes its own log, so the command
    names no `>` target to match.

    An allowlist, not a denylist of writers (no list of the ways a shell can
    write a file is complete — security review of p3-r1). After shlex-splitting,
    the command is one of:

    (a) `<fr> verification walk <args…>`
    (b) `cd <path> && <fr> verification walk <args…>`

    where `<fr>` is ONLY `fr` or `uv run fr`, and the args hold exactly one
    `--run`, equal to `run`. A command that ran a different program cannot
    vouch for the walk, so there is no env-assignment prefix (`PATH=…`,
    `FR_SHIPPED_VERIFICATIONS_DIR=…`), no `env`, no path to some `fr`, no uv
    flag (`--project`, `--with`, `--python`). Anything else is not a walk:
    another segment, any other operator (redirect, pipe, `;`, `||`, background
    `&`, subshell, braces), command substitution, a here-doc, a comment,
    unbalanced quotes.

    The residual this cannot close: a process the agent started EARLIER (in
    the background) can still write the log during this command's window. That
    is the trust boundary the `tests` witness already has — the gate proves the
    orchestrator ran the walk then, not that nothing else wrote meanwhile.
    """
    import shlex

    if any(text in command for text in _NEVER_IN_A_WALK):
        return False
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return False
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token == "&&":
            segments.append([])
        elif token and set(token) <= _OPERATOR_CHARS:
            return False
        else:
            segments[-1].append(token)
    if len(segments) == 2 and len(segments[0]) == 2 and segments[0][0] == "cd":
        segments = segments[1:]
    return len(segments) == 1 and _is_walk(segments[0], run)


def _is_walk(words: list[str], run: str) -> bool:
    """`words` is `fr verification walk <args…>` or `uv run fr verification
    walk <args…>` — nothing before it, no other `fr` — with exactly one
    `--run`, equal to `run`."""
    if words[:3] == ["uv", "run", "fr"]:
        words = words[2:]
    if words[:3] != ["fr", "verification", "walk"]:
        return False
    runs: list[str | None] = []
    args = words[3:]
    for i, arg in enumerate(args):
        if arg == "--run":
            runs.append(args[i + 1] if i + 1 < len(args) else None)
        elif arg.startswith("--run="):
            runs.append(arg.removeprefix("--run="))
    return runs == [run]


_ROOT_HOPS = 32


def opencode_root(db: Path, session: str) -> str:
    """The top-level session above `session` (a command run from a child — an
    executor's `fr journal add` — carries the CHILD's id), walking `parent_id`;
    `session` itself when the database cannot say."""
    current = session
    for _ in range(_ROOT_HOPS):
        rows = _query(db, SESSION_PARENT, (current,))
        if not rows or not isinstance(rows[0][0], str) or not rows[0][0]:
            return current
        current = rows[0][0]
    return current


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
        db = OpenCodeReader().database(env)
        root = opencode_root(db, sid)
        # A readable database that does not hold the session (`absent`) is the
        # WRONG one (gh#740), and a 1.x session (`v1-only`) is refused by name
        # (R14): both unobserved. An unreadable one keeps its view, every
        # method of which is `None` anyway.
        if store_version(db, root) in ("absent", "v1-only"):
            return None
        return OpenCodeSession(db, root)
    return None


def why_unobservable(harness: str | None, env: Mapping[str, str], what: str) -> str:
    """Why fr could not observe `what` (`questions`, `subagent dispatches`,
    `commands`) on `harness` — the one wording every gate and guard prints, so
    a gate never borrows another gate's noun (#815) and an unobserved OpenCode
    session is never described by a scope note that claims verification."""
    if harness is None:
        return "no harness detected"
    if harness == "opencode":
        # OpenCode HAS a reader (above); what is missing is the session to
        # read, or the database that holds it (#837 review p1-r5). The wording
        # names the variable fr actually read (`OPENCODE_SESSION_ID`, which
        # OpenCode 2 sets itself) — never a plugin export that no longer exists
        # (2026-10-20 review p1-r2).
        from fr.run.telemetry import session_id_from

        found = session_id_from(env, harness)
        if found is None:
            return (
                f"your harness (opencode) exported no session id to fr, so its {what} "
                "cannot be read (OPENCODE_SESSION_ID is unset: fr is not running inside an "
                "OpenCode 2.x shell — super-fr supports 2.0 only)"
            )
        from fr.run.telemetry import OpenCodeReader

        db = OpenCodeReader().database(env)
        sid, key = found
        version = store_version(db, opencode_root(db, sid))
        if version == "v1-only":
            return (
                f"the session your harness (opencode) exported in {key} ({sid}) cannot have its "
                f"{what} read: {V1_ONLY_REASON}"
            )
        if version == "unreadable":
            return (
                f"the session your harness (opencode) exported ({key}) is in no OpenCode "
                f"database fr could read ({db} could not be read), so its {what} cannot be read"
                " — check FR_OPENCODE_DB / XDG_DATA_HOME"
            )
        return (
            f"the session your harness (opencode) exported ({key}) is not in the "
            f"OpenCode database fr read, so its {what} cannot be read — check "
            "FR_OPENCODE_DB / XDG_DATA_HOME"
        )
    if harness != "claude-code":
        return f"fr has no transcript reader for {harness}'s {what}"
    return "no readable transcript for this session"
