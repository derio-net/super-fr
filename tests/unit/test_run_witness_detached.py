"""gh#1002: a suite log written by a command that detached ITSELF with `&`.

Captured shape (run 2026-10-05-feat-batch-triage-pages-goal, the phase 2
executor's transcript; worktree and temp paths replaced): the executor started
the suite with `run_in_background` AND a trailing `&` —

    cd <wt> && (uv run pytest ... > <log> 2>&1; echo "exit=$?" >> <log>) > /dev/null 2>&1 &
    echo started

The `&` ends the tool call at once, so the harness queued the call's
`completed` notice 0.4 s after issuing it — before even its launch ack — and
the suite wrote its log 8.5 minutes later, outside every window: implement-
phase refused `evidence.tests`. OpenCode's reader closes a self-detached
writer's window at the first later command that shows the log's `exit=0`
(gh#719, `_seen_exit`); Claude Code's reader had no such path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fr.run.telemetry import parse_timestamp, wrote_since

LOG = "/tmp/scratch/p2-suite.log"
SINCE = "2026-10-05T22:00:00+00:00"
LAUNCH = (
    f'cd /wt && (uv run pytest -q --no-cov -n auto > {LOG} 2>&1; echo "exit=$?" >> {LOG})'
    " > /dev/null 2>&1 &\necho started"
)
ISSUED = "2026-10-05T22:03:23.567Z"
NOTICED = "2026-10-05T22:03:23.996Z"
ACKED = "2026-10-05T22:03:24.036Z"


def _use(stamp: str, tool_id: str, command: str, *, sidechain: bool, **extra: object) -> dict:
    return {
        "type": "assistant",
        "timestamp": stamp,
        "isSidechain": sidechain,
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": "Bash",
                    "input": {"command": command, **extra},
                }
            ],
        },
    }


def _result(
    stamp: str, tool_id: str, text: str, *, sidechain: bool, background: bool = False
) -> dict:
    row: dict = {
        "type": "user",
        "timestamp": stamp,
        "isSidechain": sidechain,
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": [{"type": "text", "text": text}],
                    "is_error": False,
                }
            ],
        },
    }
    if background:
        row["toolUseResult"] = {"backgroundTaskId": "bvtpa1okt", "stdout": "", "stderr": ""}
    return row


def _notice(stamp: str, tool_id: str, *, sidechain: bool) -> dict:
    return {
        "type": "attachment",
        "timestamp": stamp,
        "isSidechain": sidechain,
        "attachment": {
            "type": "queued_command",
            "commandMode": "task-notification",
            "prompt": (
                "<task-notification>\n<task-id>bvtpa1okt</task-id>\n"
                f"<tool-use-id>{tool_id}</tool-use-id>\n<status>completed</status>\n"
                "<summary>Background command completed (exit code 0)</summary>\n"
                "</task-notification>"
            ),
        },
    }


def _launched(*, sidechain: bool = True) -> list[dict]:
    return [
        _use(ISSUED, "toolu_launch", LAUNCH, sidechain=sidechain, run_in_background=True),
        _notice(NOTICED, "toolu_launch", sidechain=sidechain),
        _result(
            ACKED,
            "toolu_launch",
            "Command running in background with ID: bvtpa1okt.",
            sidechain=sidechain,
            background=True,
        ),
    ]


def _poll(
    issued: str, done: str, tail: str, *, n: int, sidechain: bool = True, log: str = LOG
) -> list[dict]:
    command = f"for i in $(seq 1 11); do tail -1 {log} | grep -q '^exit=' && break; sleep 10; done; tail -3 {log}"
    return [
        _use(issued, f"toolu_poll{n}", command, sidechain=sidechain),
        _result(done, f"toolu_poll{n}", tail, sidechain=sidechain),
    ]


def _windows(tmp_path: Path, rows: list[dict], *, main_thread: bool = False):  # type: ignore[no-untyped-def]
    transcript = tmp_path / "agent-x.jsonl"
    transcript.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return wrote_since(transcript, Path(LOG), SINCE, main_thread=main_thread)


def _span(start: str, end: str) -> tuple:
    return (parse_timestamp(start), parse_timestamp(end))


def test_a_self_detached_suite_runs_until_a_later_command_shows_its_exit_0(
    tmp_path: Path,
) -> None:
    rows = [
        *_launched(),
        *_poll("2026-10-05T22:05:39.698Z", "2026-10-05T22:07:20.824Z", "... [ 65%]", n=1),
        *_poll(
            "2026-10-05T22:11:10.552Z",
            "2026-10-05T22:12:01.229Z",
            "... [100%]\n8500 passed, 105 skipped in 510.05s (0:08:30)\nexit=0",
            n=2,
        ),
    ]

    windows = _windows(tmp_path, rows)

    assert _span(ISSUED, "2026-10-05T22:12:01.229Z") in windows


def test_the_orchestrators_own_self_detached_suite_is_witnessed_too(tmp_path: Path) -> None:
    """The same reader serves `deliver`'s `tests=` (main thread only)."""
    rows = [
        *_launched(sidechain=False),
        *_poll(
            "2026-10-05T22:11:10.552Z",
            "2026-10-05T22:12:01.229Z",
            "8500 passed\nexit=0",
            n=1,
            sidechain=False,
        ),
    ]

    assert _span(ISSUED, "2026-10-05T22:12:01.229Z") in _windows(tmp_path, rows, main_thread=True)


@pytest.mark.parametrize(
    "variant",
    ["failed-suite", "no-exit-line", "other-log", "not-detached", "sidechain-on-main"],
)
def test_a_self_detached_suite_is_not_witnessed_without_its_own_exit_0(
    tmp_path: Path, variant: str
) -> None:
    """Fail closed, as `_seen_exit` does for OpenCode: a non-zero exit, no
    exit line yet, an exit line read from another file, a writer that did not
    detach (its own end is its end), or a subagent's poll read as the main
    thread's — none of them stretches the window."""
    tail = "exit=1" if variant == "failed-suite" else "exit=0"
    if variant == "no-exit-line":
        tail = "... [ 99%]"
    rows = [
        *_launched(),
        *_poll(
            "2026-10-05T22:11:10.552Z",
            "2026-10-05T22:12:01.229Z",
            tail,
            n=1,
            log="/tmp/scratch/other.log" if variant == "other-log" else LOG,
        ),
    ]
    if variant == "not-detached":
        rows[0]["message"]["content"][0]["input"]["command"] = (
            f"uv run pytest -q > {LOG} 2>&1; echo exit=$? >> {LOG}"
        )

    windows = _windows(tmp_path, rows, main_thread=variant == "sidechain-on-main")

    assert _span(ISSUED, "2026-10-05T22:12:01.229Z") not in (windows or [])


def test_the_first_exit_line_seen_is_final(tmp_path: Path) -> None:
    """A later `exit=0` cannot revive a suite whose first seen exit was 1."""
    rows = [
        *_launched(),
        *_poll("2026-10-05T22:10:00.000Z", "2026-10-05T22:10:30.000Z", "exit=1", n=1),
        *_poll("2026-10-05T22:11:00.000Z", "2026-10-05T22:11:30.000Z", "exit=0", n=2),
    ]

    windows = _windows(tmp_path, rows)

    assert all(end <= parse_timestamp(ACKED) for _, end in windows)
