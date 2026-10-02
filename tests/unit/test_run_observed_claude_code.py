"""The Claude Code backend of `fr.run.observed` (spec 2026-10-02-opencode-observe-2
§A; Test Plan 2): it returns what the existing transcript readers in
`fr.run.telemetry` return on the captured fixtures — no behaviour change — and
`ChildDispatch.returned` is the `tool_result` the ORCHESTRATOR received for the
dispatch, never the subagent file's handback stub."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

import pytest
from fr.run import observed, telemetry

from tests.unit.transcript_sessions import (
    AGENT_ID,
    AGENT_TOOL_USE_LINE,
    CAPTURED_LOG,
    HANDBACK,
    HANDBACK_MESSAGE,
    ORCHESTRATOR,
    SUBAGENT,
    TOOL_USE_ID,
    agent_ack_row,
    agent_result_row,
    bash_rows,
    copy_of,
    question_rows,
    records,
    tool_rows,
    write_agent,
    write_session,
)

SINCE = "2026-09-21T00:00:00+00:00"
STUB = "Phase 1 complete and handed back to the orchestrator."
RETURNED = "Reviewed phase 1.\n\n```review-findings\np1-r1 | in | a gap\n```"


def _since() -> _dt.datetime:
    parsed = telemetry.parse_timestamp(SINCE)
    assert parsed is not None
    return parsed


def _rows(shot: Path, script: Path) -> list[dict[str, Any]]:
    read = tool_rows("2026-09-21T10:02:00.000Z", tool_use_id="toolu_read", name="Read")
    read[0]["message"]["content"][0]["input"] = {"file_path": str(shot)}
    run = tool_rows("2026-09-21T10:03:00.000Z", tool_use_id="toolu_run", name="Bash")
    run[0]["message"]["content"][0]["input"] = {"command": f"node {script}"}
    dispatch = copy_of(records(ORCHESTRATOR)[AGENT_TOOL_USE_LINE])
    dispatch["timestamp"] = "2026-09-21T10:05:00.000Z"
    return [
        *records(ORCHESTRATOR),
        *question_rows("2026-09-21T10:00:00.000Z", tool_use_id="toolu_q1"),
        *bash_rows("2026-09-21T10:01:00.000Z", tool_use_id="toolu_bash"),
        *read,
        *run,
        dispatch,
        agent_result_row("2026-09-21T10:20:00.000Z", tool_use_id=TOOL_USE_ID, text=RETURNED),
    ]


@pytest.fixture
def session(tmp_path: Path) -> tuple[dict[str, str], Path, Path, Path]:
    shot = tmp_path / "shots" / "a.png"
    script = tmp_path / "shots.cjs"
    root = tmp_path / "projects"
    transcript = write_session(root, session_id="sess-1", rows=_rows(shot, script))
    sub = copy_of(records(SUBAGENT))
    for row in sub:
        row["timestamp"] = "2026-09-21T10:06:00.000Z"
    write_agent(transcript, rows=sub)
    env = {
        "FR_HARNESS": "claude-code",
        "FR_TRANSCRIPT_ROOT": str(root),
        "CLAUDE_CODE_SESSION_ID": "sess-1",
    }
    return env, transcript, shot, script


def _view(env: dict[str, str]) -> observed.ClaudeCodeSession:
    view = observed.observed_session(env)
    assert isinstance(view, observed.ClaudeCodeSession)
    return view


def test_the_view_is_this_sessions_transcript(session: Any) -> None:
    env, transcript, _, _ = session
    view = _view(env)
    assert view.harness == "claude-code"
    assert view.session == "sess-1"
    assert view.transcript == transcript


def test_answered_rounds_are_the_transcript_readers(session: Any) -> None:
    env, transcript, _, _ = session
    rounds = _view(env).answered_rounds(_since())
    assert rounds == telemetry.answered_rounds_in(transcript, _since())
    assert rounds is not None and len(rounds) == 1


def test_dispatches_pair_by_tool_use_id_as_attribute_dispatches(session: Any) -> None:
    env, transcript, _, _ = session
    found = _view(env).dispatches(_since())
    expected = [
        (d.agent_id, d.agent_type, d.started) for d in telemetry.attribute_dispatches(transcript)
    ]
    assert found is not None
    assert [(d.agent_id, d.agent_type, d.started) for d in found] == expected
    assert [d.agent_id for d in found] == [AGENT_ID]


def test_returned_is_what_the_parent_received_not_the_handback_stub(session: Any) -> None:
    env, _, _, _ = session
    (dispatch,) = _view(env).dispatches(_since()) or []
    assert dispatch.returned == RETURNED
    assert dispatch.returned != STUB


def test_a_dispatch_with_no_result_yet_returned_none(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    rows = [r for r in _rows(tmp_path / "a.png", tmp_path / "s.cjs") if r.get("type") != "user"]
    transcript = write_session(root, session_id="sess-2", rows=rows)
    write_agent(transcript)
    env = {
        "FR_HARNESS": "claude-code",
        "FR_TRANSCRIPT_ROOT": str(root),
        "CLAUDE_CODE_SESSION_ID": "sess-2",
    }
    (dispatch,) = _view(env).dispatches(_since()) or []
    assert dispatch.returned is None


def test_dispatches_before_since_are_not_counted(session: Any) -> None:
    env, _, _, _ = session
    later = _dt.datetime(2026, 9, 22, tzinfo=_dt.UTC)
    assert _view(env).dispatches(later) == []


def test_child_is_the_subagent_files_view_or_false(session: Any) -> None:
    env, transcript, _, _ = session
    view = _view(env)
    child = view.child(AGENT_ID)
    assert isinstance(child, observed.ClaudeCodeSession)
    assert child.transcript == telemetry.witness_transcript(transcript, AGENT_ID)
    assert view.child("a-never-dispatched-id") is False


def test_first_read_and_first_shell_are_the_transcript_readers(session: Any) -> None:
    env, transcript, shot, script = session
    view = _view(env)
    read = view.first_read(shot, _since())
    assert read == telemetry.read_file_since(transcript, shot, SINCE, main_thread=True)
    assert read not in (None, False)
    ran = view.first_shell_executing(script, _since())
    assert ran == telemetry.shell_named_since(transcript, script, SINCE, main_thread=True)
    assert ran not in (None, False)
    child = view.child(AGENT_ID)
    assert isinstance(child, observed.ClaudeCodeSession)
    assert child.first_read(shot, _since()) is False


def test_wrote_windows_are_the_orchestrator_writes(session: Any) -> None:
    env, transcript, _, _ = session
    windows = _view(env).wrote_windows(Path(CAPTURED_LOG), _since())
    assert windows == telemetry.wrote_since(transcript, Path(CAPTURED_LOG), SINCE, main_thread=True)
    assert windows


def test_no_session_id_is_no_view(session: Any) -> None:
    env, _, _, _ = session
    assert observed.observed_session({**env, "CLAUDE_CODE_SESSION_ID": ""}) is None


# --- review p1-r3: a backgrounded dispatch --------------------------------


def _backgrounded(
    tmp_path: Path, *, parent: dict[str, Any] | None, handback: bool
) -> dict[str, str]:
    root = tmp_path / "projects"
    rows = [r for r in _rows(tmp_path / "a.png", tmp_path / "s.cjs") if r.get("type") != "user"]
    if parent is not None:
        rows.append(parent)
    transcript = write_session(root, session_id="sess-bg", rows=rows)
    sub = copy_of(records(HANDBACK if handback else SUBAGENT))
    for row in sub:
        row["timestamp"] = "2026-09-21T10:06:00.000Z"
    write_agent(transcript, rows=sub)
    return {
        "FR_HARNESS": "claude-code",
        "FR_TRANSCRIPT_ROOT": str(root),
        "CLAUDE_CODE_SESSION_ID": "sess-bg",
    }


def _returned(env: dict[str, str]) -> str | None:
    (dispatch,) = _view(env).dispatches(_since()) or []
    return dispatch.returned


def test_a_backgrounded_report_is_the_childs_handback(tmp_path: Path) -> None:
    ack = agent_ack_row("2026-09-21T10:05:01.000Z", tool_use_id=TOOL_USE_ID)
    assert _returned(_backgrounded(tmp_path, parent=ack, handback=True)) == HANDBACK_MESSAGE


def test_the_handback_wins_over_the_parents_result(tmp_path: Path) -> None:
    result = agent_result_row("2026-09-21T10:20:00.000Z", tool_use_id=TOOL_USE_ID, text="other")
    assert _returned(_backgrounded(tmp_path, parent=result, handback=True)) == HANDBACK_MESSAGE


def test_a_launch_ack_alone_is_no_return(tmp_path: Path) -> None:
    ack = agent_ack_row("2026-09-21T10:05:01.000Z", tool_use_id=TOOL_USE_ID)
    assert _returned(_backgrounded(tmp_path, parent=ack, handback=False)) is None
