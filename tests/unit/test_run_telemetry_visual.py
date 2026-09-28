"""The transcript predicates behind `visual` evidence (spec
2026-09-28-ui-visual-evidence §C): `read_file_since`, `shell_named_since` and
`witness_transcript`.

Every record is a COPY of a captured one (`tests/unit/transcript_sessions.py`),
with only the fields a test varies re-keyed: the tool name, its input, the
timestamp. Three-valued like `subagent_dispatch_since`: a value when found,
`False` when the transcript was read and holds none, `None` when unreadable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fr.run.telemetry import (
    parse_timestamp,
    read_file_since,
    shell_named_since,
    witness_transcript,
)

from tests.unit.transcript_sessions import (
    AGENT_ID,
    ORCHESTRATOR,
    TOOL_USE_ID,
    bash_rows,
    records,
    write_agent,
    write_jsonl,
    write_session,
)

SINCE = "2026-09-28T10:00:00+00:00"
BEFORE = "2026-09-28T09:59:00.000Z"
AFTER = "2026-09-28T10:00:05.000Z"


def _call(timestamp: str, *, name: str, tool_input: dict[str, Any], n: int = 1) -> dict[str, Any]:
    """The captured `Bash` tool_use, renamed to `name` with `tool_input`."""
    call, _ = bash_rows(timestamp, tool_use_id=f"toolu_v{n}")
    block = call["message"]["content"][0]
    block["name"] = name
    block["input"] = tool_input
    return call


def _transcript(tmp_path: Path, *rows: dict[str, Any]) -> Path:
    path = tmp_path / "t.jsonl"
    write_jsonl(path, [*records(ORCHESTRATOR), *rows])
    return path


def _shot(tmp_path: Path, name: str = "accepted.png") -> Path:
    shot = tmp_path / "shots" / name
    shot.parent.mkdir(parents=True, exist_ok=True)
    shot.write_bytes(b"\x89PNG fake")
    return shot


# --- read_file_since -------------------------------------------------------


def test_a_read_of_the_shot_after_since_returns_when(tmp_path: Path) -> None:
    shot = _shot(tmp_path)
    t = _transcript(tmp_path, _call(AFTER, name="Read", tool_input={"file_path": str(shot)}))

    assert read_file_since(t, shot, SINCE) == parse_timestamp(AFTER)


def test_a_relative_path_naming_the_same_file_matches(tmp_path: Path) -> None:
    shot = _shot(tmp_path)
    t = _transcript(
        tmp_path, _call(AFTER, name="Read", tool_input={"file_path": "shots/accepted.png"})
    )

    assert read_file_since(t, shot, SINCE) == parse_timestamp(AFTER)


def test_an_aliased_read_tool_matches(tmp_path: Path) -> None:
    shot = _shot(tmp_path)
    t1 = _transcript(tmp_path, _call(AFTER, name="read_file", tool_input={"file_path": str(shot)}))
    assert read_file_since(t1, shot, SINCE) == parse_timestamp(AFTER)
    t2 = _transcript(tmp_path, _call(AFTER, name="view", tool_input={"path": str(shot)}))
    assert read_file_since(t2, shot, SINCE) == parse_timestamp(AFTER)


def test_a_read_before_since_is_false(tmp_path: Path) -> None:
    shot = _shot(tmp_path)
    t = _transcript(tmp_path, _call(BEFORE, name="Read", tool_input={"file_path": str(shot)}))

    assert read_file_since(t, shot, SINCE) is False


def test_a_read_of_another_file_is_false(tmp_path: Path) -> None:
    shot = _shot(tmp_path)
    other = _shot(tmp_path, "other.png")
    t = _transcript(tmp_path, _call(AFTER, name="Read", tool_input={"file_path": str(other)}))

    assert read_file_since(t, shot, SINCE) is False


def test_a_non_read_tool_naming_the_shot_is_false(tmp_path: Path) -> None:
    shot = _shot(tmp_path)
    t = _transcript(tmp_path, _call(AFTER, name="Write", tool_input={"file_path": str(shot)}))

    assert read_file_since(t, shot, SINCE) is False


def test_an_unreadable_transcript_is_none(tmp_path: Path) -> None:
    shot = _shot(tmp_path)

    assert read_file_since(tmp_path / "missing.jsonl", shot, SINCE) is None
    garbage = tmp_path / "garbage.jsonl"
    garbage.write_text("not json\n")
    assert read_file_since(garbage, shot, SINCE) is None


# --- shell_named_since -----------------------------------------------------


def test_a_bash_call_naming_the_script_returns_when(tmp_path: Path) -> None:
    t = _transcript(
        tmp_path, _call(AFTER, name="Bash", tool_input={"command": "node shots.cjs --out /tmp/x"})
    )

    assert shell_named_since(t, "shots.cjs", SINCE) == parse_timestamp(AFTER)


def test_an_aliased_shell_tool_matches(tmp_path: Path) -> None:
    t = _transcript(
        tmp_path, _call(AFTER, name="terminal", tool_input={"command": "node shots.cjs"})
    )

    assert shell_named_since(t, "shots.cjs", SINCE) == parse_timestamp(AFTER)


def test_no_bash_call_naming_the_script_is_false(tmp_path: Path) -> None:
    t = _transcript(
        tmp_path,
        _call(AFTER, name="Bash", tool_input={"command": "node other.cjs"}),
        _call(BEFORE, name="Bash", tool_input={"command": "node shots.cjs"}, n=2),
    )

    assert shell_named_since(t, "shots.cjs", SINCE) is False


def test_shell_named_since_on_an_unreadable_transcript_is_none(tmp_path: Path) -> None:
    assert shell_named_since(tmp_path / "missing.jsonl", "shots.cjs", SINCE) is None


# --- witness_transcript ----------------------------------------------------


def test_no_agent_is_the_orchestrator_stream(tmp_path: Path) -> None:
    session = write_session(tmp_path / "projects")

    assert witness_transcript(session, agent_id=None) == session


def test_a_dispatched_agent_is_its_subagent_transcript(tmp_path: Path) -> None:
    session = write_session(tmp_path / "projects")
    transcript = write_agent(session, AGENT_ID, tool_use_id=TOOL_USE_ID)

    assert witness_transcript(session, agent_id=AGENT_ID) == transcript


def test_an_agent_this_session_never_dispatched_is_none(tmp_path: Path) -> None:
    session = write_session(tmp_path / "projects")
    write_agent(session, AGENT_ID, tool_use_id=TOOL_USE_ID)

    assert witness_transcript(session, agent_id="never-dispatched") is None
