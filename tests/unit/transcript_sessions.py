"""Build an on-disk Claude Code session layout from the CAPTURED fixtures.

Shared by `test_run_telemetry.py` (the reader) and `test_run_cli.py` (the
`fr run resolve` / `fr run status` path), so both exercise the same shape.

Every record here comes from `tests/fixtures/transcripts/`, captured live from
a real session (see its `NOTE.md`). Nothing is composed from a guess about the
format: these helpers COPY the captured records and edit only the fields a
test varies — timestamps, ids, usage numbers. A fixture for an external system
that was written alongside the parser proves only that the two agree with each
other.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parents[1] / "fixtures" / "transcripts"
ORCHESTRATOR = FIXTURES / "claude-code-session.jsonl"
SUBAGENT = FIXTURES / "claude-code-subagent.jsonl"
SUBAGENT_META = FIXTURES / "claude-code-subagent.meta.json"
QUESTION = FIXTURES / "claude-code-askuserquestion.jsonl"
BASH = FIXTURES / "claude-code-bash.jsonl"
"""Captured 2026-09-21 from the same live session (local and scratchpad paths
redacted): line 0 a main-thread `assistant` record whose `Bash` tool_use runs
a test suite into a log file (`.../c1.log`), line 1 its `tool_result`
(`is_error: false`)."""
"""Captured 2026-09-21 from a live Claude Code 2.1.278 session (local paths
redacted to `/home/user`): line 0 is the `assistant` record carrying an
`AskUserQuestion` tool_use, line 1 the `user` record carrying its tool_result,
whose `toolUseResult` is an object with a non-empty `answers` map. A declined
or failed tool call carries a plain STRING `toolUseResult` instead — observed
on other tools in the same transcript."""

AGENT_ID = "adc0716be5565cc07"
TOOL_USE_ID = "toolu_014ynBvFpxdbG1PXwxASc1Cu"
AGENT_TOOL_USE_LINE = 7
"""Index of the captured `assistant` record whose `Agent` tool_use id matches
the captured subagent's metadata `toolUseId`."""


def records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def copy_of(value: Any) -> Any:
    """A deep copy that cannot share structure with the captured fixture."""
    return json.loads(json.dumps(value))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def session_dir(session: Path) -> Path:
    return session.with_suffix("")


def write_session(
    root: Path,
    session_id: str = "sess-1",
    slug: str = "-home-user-repo",
    rows: list[dict[str, Any]] | None = None,
) -> Path:
    """`<root>/<slug>/<session-id>.jsonl` plus its sibling session directory."""
    project = root / slug
    project.mkdir(parents=True, exist_ok=True)
    session = project / f"{session_id}.jsonl"
    write_jsonl(session, records(ORCHESTRATOR) if rows is None else rows)
    session_dir(session).mkdir(exist_ok=True)
    return session


def write_agent(
    session: Path,
    agent_id: str = AGENT_ID,
    *,
    tool_use_id: str = TOOL_USE_ID,
    rows: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> Path:
    """One `subagents/agent-<id>.jsonl` + its `agent-<id>.meta.json` companion."""
    subagents = session_dir(session) / "subagents"
    transcript = subagents / f"agent-{agent_id}.jsonl"
    write_jsonl(transcript, records(SUBAGENT) if rows is None else rows)
    meta_obj = copy_of(json.loads(SUBAGENT_META.read_text()) if meta is None else meta)
    meta_obj["toolUseId"] = tool_use_id
    (subagents / f"agent-{agent_id}.meta.json").write_text(json.dumps(meta_obj))
    return transcript


def add_dispatch(
    session: Path,
    *,
    timestamp: str,
    agent_id: str,
    tool_use_id: str,
    usage: dict[str, int],
) -> Path:
    """Append ONE more dispatch to an existing session: the orchestrator's
    `Agent` tool_use record, and the subagent transcript it started.

    Both are COPIES of the captured records with only the fields a test varies
    re-keyed (timestamp, ids, usage) — the rule this module exists for. Two
    calls with the SAME `timestamp` build the overlap case: two dispatches
    inside one window, which no time window can separate and which selection
    by agent id resolves exactly (spec §4.D).
    """
    tool_use = copy_of(records(ORCHESTRATOR)[AGENT_TOOL_USE_LINE])
    tool_use["timestamp"] = timestamp
    tool_use["uuid"] = f"uuid-{agent_id}"
    tool_use["message"]["content"][0]["id"] = tool_use_id
    with session.open("a") as handle:
        handle.write(json.dumps(tool_use) + "\n")
    rows = copy_of(records(SUBAGENT))
    for row in rows:
        row["timestamp"] = timestamp
        row["agentId"] = agent_id
        if row["type"] == "assistant":
            row["message"]["usage"] = dict(usage)
    return write_agent(session, agent_id, tool_use_id=tool_use_id, rows=rows)


def dispatched_at(
    root: Path,
    timestamp: str,
    *,
    session_id: str,
    usage: dict[str, int],
    agent_type: str | None = None,
) -> Path:
    """A one-dispatch session whose tool_use lands exactly at `timestamp`.

    Used by the CLI tests, where the window comes from the run cursor's own
    `at` and cannot be predicted before `fr run advance` writes it.
    `agent_type` re-keys the captured metadata's `agentType` (the capture is a
    `super-fr:fr-phase-executor`; a reviewer test needs a reviewer).
    """
    orchestrator = copy_of(records(ORCHESTRATOR))
    orchestrator[AGENT_TOOL_USE_LINE]["timestamp"] = timestamp
    session = write_session(root, session_id=session_id, rows=orchestrator)
    subagent = copy_of(records(SUBAGENT))
    for row in subagent:
        row["timestamp"] = timestamp
        if row["type"] == "assistant":
            row["message"]["usage"] = dict(usage)
    meta = None
    if agent_type is not None:
        meta = json.loads(SUBAGENT_META.read_text())
        meta["agentType"] = agent_type
    write_agent(session, rows=subagent, meta=meta)
    return session


def asked_at(
    root: Path,
    timestamp: str,
    *,
    session_id: str,
    answered: bool = True,
) -> Path:
    """A session whose captured `AskUserQuestion` exchange lands at `timestamp`.

    `answered=False` swaps the captured result's `toolUseResult` object for the
    string form a declined tool call carries, keeping everything else captured.
    Timestamps are moved (the gate window comes from the cursor's own `at`,
    which a test cannot predict), never the shape.
    """
    question, answer = copy_of(records(QUESTION))
    question["timestamp"] = timestamp
    answer["timestamp"] = timestamp
    if not answered:
        answer["toolUseResult"] = "User rejected tool use"
    return write_session(
        root, session_id=session_id, rows=[*records(ORCHESTRATOR), question, answer]
    )


CAPTURED_LOG = "/tmp/scratchpad/c1.log"
"""The (redacted) path the captured `Bash` command writes its suite output to."""


def ran_at(
    root: Path,
    timestamp: str,
    *,
    session_id: str,
    until: str | None = None,
    log: Path | None = None,
) -> Path:
    """A session whose captured orchestrator `Bash` exchange runs from
    `timestamp` to `until` (default: the same instant), writing `log` (default:
    the captured path). Only the timestamps and that one path are varied."""
    call, result = copy_of(records(BASH))
    call["timestamp"] = timestamp
    result["timestamp"] = until or timestamp
    if log is not None:
        block = call["message"]["content"][0]
        block["input"]["command"] = block["input"]["command"].replace(CAPTURED_LOG, str(log))
    return write_session(root, session_id=session_id, rows=[*records(ORCHESTRATOR), call, result])


TEXT_LINE = 6
"""Index of a captured main-thread `assistant` record whose content is text
only — a turn that asks nothing and runs nothing."""


def question_rows(
    timestamp: str,
    *,
    tool_use_id: str,
    answered: bool = True,
    first_question: str | None = None,
    sidechain: bool = False,
) -> list[dict[str, Any]]:
    """The captured `AskUserQuestion` exchange (call + result), re-keyed to
    `tool_use_id` and moved to `timestamp` — the building block of a question
    ROUND (spec 2026-09-26 §3.C). `first_question` replaces the text of the
    call's first question (where a `Round 1 of 2` announcement would sit);
    `answered=False` swaps in the declined string form, as `asked_at` does;
    `sidechain=True` marks both records as a subagent's."""
    question, answer = copy_of(records(QUESTION))
    question["timestamp"] = timestamp
    answer["timestamp"] = timestamp
    question["uuid"] = f"uuid-{tool_use_id}"
    question["message"]["content"][0]["id"] = tool_use_id
    answer["message"]["content"][0]["tool_use_id"] = tool_use_id
    answer["sourceToolAssistantUUID"] = question["uuid"]
    if first_question is not None:
        question["message"]["content"][0]["input"]["questions"][0]["question"] = first_question
    if not answered:
        answer["toolUseResult"] = "User rejected tool use"
    if sidechain:
        question["isSidechain"] = True
        answer["isSidechain"] = True
    return [question, answer]


def bash_rows(timestamp: str, *, tool_use_id: str) -> list[dict[str, Any]]:
    """The captured orchestrator `Bash` exchange, re-keyed and moved — a
    non-question tool_use, which closes a question round."""
    call, result = copy_of(records(BASH))
    call["timestamp"] = timestamp
    result["timestamp"] = timestamp
    call["message"]["content"][0]["id"] = tool_use_id
    result["message"]["content"][0]["tool_use_id"] = tool_use_id
    return [call, result]


def tool_rows(timestamp: str, *, tool_use_id: str, name: str) -> list[dict[str, Any]]:
    """The captured `Bash` exchange with the tool renamed to `name` — a stand-in
    for any other main-thread tool_use (`TodoWrite`, `Read`, ...) between two
    question calls. Only the tool name matters to round splitting."""
    call, result = bash_rows(timestamp, tool_use_id=tool_use_id)
    call["message"]["content"][0]["name"] = name
    return [call, result]


def text_row(timestamp: str) -> dict[str, Any]:
    """The captured text-only assistant turn, moved to `timestamp`."""
    row = copy_of(records(ORCHESTRATOR)[TEXT_LINE])
    row["timestamp"] = timestamp
    return row


def conversation_at(root: Path, rows: list[dict[str, Any]], *, session_id: str) -> Path:
    """A session: the captured orchestrator prelude, then `rows` in order."""
    return write_session(root, session_id=session_id, rows=[*records(ORCHESTRATOR), *rows])


BACKGROUND = FIXTURES / "claude-code-background.jsonl"
"""Captured 2026-09-23/26 from live Claude Code 2.1.280 sessions (paths and
session ids redacted, `serverClassifierContext` dropped — see `NOTE.md`), six
records: 0 an `assistant` `Bash` tool_use with `run_in_background: true`, 1 its
ack `tool_result` (`toolUseResult.backgroundTaskId` set), 2 the later
`type: user` `task-notification` record, 3 a `type: attachment`
`queued_command` task-notification (the other shape a finished background
command arrives in), 4 a foreground `Bash` tool_use with a 600 s timeout, 5 its
`tool_result` reading `Command did not complete within its 600s timeout and was
moved to the background`."""

_BG = {
    "call": (0, "toolu_01Et1WhaFSFbmfw6fopvB5Uf", "b2z9y9ggq"),
    "attachment": (3, "toolu_01A65mT8gCxQDeepZgCrzqBJ", "b2818z28g"),
    "timeout": (4, "toolu_01Mvhz6gXQonQ4Uu7eQdn75m", "bw29jf8kk"),
}
_CAPTURED_LABELS = {
    False: "Run full verification suite into a log",
    True: "Strengthen the unresolvable-ref test",
}


def _map_strings(value: Any, fn: Any) -> Any:
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, list):
        return [_map_strings(v, fn) for v in value]
    if isinstance(value, dict):
        return {k: _map_strings(v, fn) for k, v in value.items()}
    return value


def background_rows(
    started: str,
    *,
    tool_use_id: str = "toolu_bg1",
    command: str = "uv run pytest -q > /tmp/scratchpad/c1.log 2>&1",
    notified: str | None = None,
    notice_id: str | None = None,
    status: str = "completed",
    exit_code: int = 0,
    text_blocks: bool = False,
    attachment: bool = False,
    timeout: bool = False,
    sidechain_notice: bool = False,
    label: str | None = None,
) -> list[dict[str, Any]]:
    """A backgrounded `Bash` exchange built by COPYING the captured records in
    `BACKGROUND` and re-keying ids, timestamps and the command: the tool_use,
    its ack `tool_result`, and — when `notified` is given — the later
    notification, whose timestamp is the finish time. `attachment` carries the
    notification as the captured `queued_command` attachment instead of the
    `type: user` record; `timeout` uses the captured foreground call that Claude
    Code moved to the background at its timeout, instead of an explicit
    `run_in_background`; `sidechain_notice` marks the notification a subagent's.
    `text_blocks` carries the ack and a user notification as lists of `text`
    blocks rather than plain strings.

    `status`/`exit_code`/`label` edit the captured summary: a `failed` status
    reads `failed with exit code N` (the wording seen live on real failures,
    edited into the captured success record), a `completed` status with a
    non-zero code `completed (exit code N)`."""
    captured = records(BACKGROUND)
    _, call_id, _ = _BG["timeout" if timeout else "call"]
    call = copy_of(captured[4 if timeout else 0])
    ack = copy_of(captured[5 if timeout else 1])
    block = call["message"]["content"][0]
    block["input"]["command"] = command
    for row in (call, ack):
        row["timestamp"] = started
    if text_blocks:
        ack["message"]["content"][0]["content"] = [
            {"type": "text", "text": ack["message"]["content"][0]["content"]}
        ]
    call, ack = _map_strings([call, ack], lambda t: t.replace(call_id, tool_use_id))
    rows = [call, ack]
    if notified is None:
        return rows
    _, note_id, _ = _BG["attachment" if attachment else "call"]
    note = copy_of(captured[3 if attachment else 2])
    reported = notice_id or tool_use_id
    tail = (
        f"failed with exit code {exit_code}"
        if status == "failed"
        else f"completed (exit code {exit_code})"
    )

    def edit(text: str) -> str:
        text = text.replace(note_id, reported)
        text = text.replace("<status>completed</status>", f"<status>{status}</status>")
        text = text.replace("completed (exit code 0)", tail)
        return text.replace(_CAPTURED_LABELS[attachment], label) if label else text

    note = _map_strings(note, edit)
    note["timestamp"] = notified
    if attachment:
        note["attachment"]["timestamp"] = notified
    elif text_blocks:
        note["message"]["content"] = [{"type": "text", "text": note["message"]["content"]}]
    if sidechain_notice:
        note["isSidechain"] = True
    rows.append(note)
    return rows
