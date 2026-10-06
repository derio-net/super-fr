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

import pytest
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


def test_a_relative_read_target_never_matches(tmp_path: Path) -> None:
    """p2-r8: the transcript carries no cwd, so `shots/accepted.png` could be
    any `accepted.png` in any `shots/` — only an absolute path is evidence."""
    shot = _shot(tmp_path)
    t = _transcript(
        tmp_path, _call(AFTER, name="Read", tool_input={"file_path": "shots/accepted.png"})
    )

    assert read_file_since(t, shot, SINCE) is False


def test_an_absolute_path_through_a_symlink_matches_the_real_file(tmp_path: Path) -> None:
    shot = _shot(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(shot.parent)
    t = _transcript(
        tmp_path, _call(AFTER, name="Read", tool_input={"file_path": str(link / shot.name)})
    )

    assert read_file_since(t, shot, SINCE) == parse_timestamp(AFTER)


def test_an_absolute_path_sharing_only_the_tail_is_false(tmp_path: Path) -> None:
    shot = _shot(tmp_path)
    elsewhere = tmp_path / "other" / "shots" / "accepted.png"
    t = _transcript(tmp_path, _call(AFTER, name="Read", tool_input={"file_path": str(elsewhere)}))

    assert read_file_since(t, shot, SINCE) is False


def test_a_read_before_not_before_is_false(tmp_path: Path) -> None:
    """p2-r2: a read issued before the shot's last write looked at other bytes."""
    shot = _shot(tmp_path)
    t = _transcript(tmp_path, _call(AFTER, name="Read", tool_input={"file_path": str(shot)}))
    later = parse_timestamp("2026-09-28T10:00:10+00:00")

    assert read_file_since(t, shot, SINCE, not_before=later) is False
    earlier = parse_timestamp("2026-09-28T10:00:01+00:00")
    assert read_file_since(t, shot, SINCE, not_before=earlier) == parse_timestamp(AFTER)


def test_a_sidechain_read_in_the_session_file_does_not_count(tmp_path: Path) -> None:
    """p2-r6: in the orchestrator's session file a sidechain record is a
    subagent's, not the orchestrator's; a subagent's own file is not filtered."""
    shot = _shot(tmp_path)
    call = _call(AFTER, name="Read", tool_input={"file_path": str(shot)})
    call["isSidechain"] = True
    t = _transcript(tmp_path, call)

    assert read_file_since(t, shot, SINCE, main_thread=True) is False
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


@pytest.mark.parametrize(
    "command",
    [
        "cat shots.cjs",
        "ls shots.cjs",
        "echo shots.cjs",
        "vim shots.cjs && node other.cjs",
        "node --check other.cjs shots.cjs",
        "grep capture shots.cjs",
    ],
)
def test_a_command_merely_naming_the_script_is_false(tmp_path: Path, command: str) -> None:
    """p2-r7: the script must be EXECUTED — the command word, or the first
    non-flag argument after an interpreter — not merely named."""
    t = _transcript(tmp_path, _call(AFTER, name="Bash", tool_input={"command": command}))

    assert shell_named_since(t, "shots.cjs", SINCE) is False


@pytest.mark.parametrize(
    "command",
    [
        "./shots.cjs",
        "node shots.cjs",
        "cd /repo && node --trace-warnings shots.cjs --out /tmp/x",
        "python3 shots.cjs",
        "python shots.cjs",
        "bash shots.cjs",
        "sh -e shots.cjs",
        "npx shots.cjs",
        "deno run -A shots.cjs",
        "bun shots.cjs",
        "uv run shots.cjs",
        "uv run python shots.cjs",
        "fr isolation exec -- node shots.cjs",
        "uv run fr isolation exec -- 'node shots.cjs'",
        "OUT=/tmp/x node shots.cjs",
        "ls /tmp; node shots.cjs | tee log",
        "cd /repo\nnode shots.cjs",
        "bash -c 'node shots.cjs'",
        "/usr/bin/node ./shots.cjs",
    ],
)
def test_a_command_executing_the_script_matches(tmp_path: Path, command: str) -> None:
    t = _transcript(tmp_path, _call(AFTER, name="Bash", tool_input={"command": command}))

    assert shell_named_since(t, "shots.cjs", SINCE) == parse_timestamp(AFTER)


@pytest.mark.parametrize(
    "command",
    [
        "uv run --with pyyaml python shots.cjs",
        "uv run -w pyyaml python shots.cjs",
        "uv run --with=pyyaml python shots.cjs",
        "uv run --isolated --no-project --with markdown --with pyyaml python shots.cjs",
        "uv run --python 3.12 --project /repo python shots.cjs",
        "uv run -p 3.12 shots.cjs",
        "fr isolation exec -- uv run --with pyyaml python shots.cjs",
    ],
)
def test_a_uv_run_flag_value_is_not_the_program(tmp_path: Path, command: str) -> None:
    """gh#999: `uv run --with <pkg> python <script>` ran the script — the
    `--with` value is the flag's, not the program `uv run` executes."""
    t = _transcript(tmp_path, _call(AFTER, name="Bash", tool_input={"command": command}))

    assert shell_named_since(t, "shots.cjs", SINCE) == parse_timestamp(AFTER)


@pytest.mark.parametrize(
    "command",
    [
        "uv run --with-requirements shots.cjs python other.py",
        "uv run --env-file shots.cjs python other.py",
    ],
)
def test_a_uv_run_flag_value_naming_the_script_is_not_a_run_of_it(
    tmp_path: Path, command: str
) -> None:
    """The other half of gh#999: a value IS the flag's, so naming the script as
    one does not execute it."""
    t = _transcript(tmp_path, _call(AFTER, name="Bash", tool_input={"command": command}))

    assert shell_named_since(t, "shots.cjs", SINCE) is False


def test_npm_run_an_alias_is_not_recognised(tmp_path: Path) -> None:
    """The documented limit: an alias names no script — name it directly."""
    t = _transcript(tmp_path, _call(AFTER, name="Bash", tool_input={"command": "npm run shots"}))

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


def test_an_agent_this_session_never_dispatched_is_false(tmp_path: Path) -> None:
    """p2-r1: a readable session that dispatched no such agent is `False` — a
    bogus id is a refusal, never `None` (unobserved)."""
    session = write_session(tmp_path / "projects")
    write_agent(session, AGENT_ID, tool_use_id=TOOL_USE_ID)

    assert witness_transcript(session, agent_id="never-dispatched") is False


def test_an_unreadable_session_is_none(tmp_path: Path) -> None:
    session = tmp_path / "projects" / "gone.jsonl"

    assert witness_transcript(session, agent_id=AGENT_ID) is None
    assert witness_transcript(session, agent_id=None) is None
