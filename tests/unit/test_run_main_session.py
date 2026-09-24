"""Main-session cost per step — spec
`2026-09-24-fr-goal-scope-proportion-cost-design.md` §D (gh#593 option 0).

Three layers, each tested on its own:

1. the Claude Code reader over ONE transcript file and a window — sidechain,
   out-of-window, duplicated and placeholder records all excluded, with the
   window edges compared at second precision;
2. the candidate set and the sum over it — every session is measured, and one
   unreadable candidate makes the whole step unmeasured (gh#514: a partial sum
   reported as a measurement is the one thing ruled out);
3. the hook in `_complete_step` — every `done` path writes `main_session`,
   `failed` writes none, and a reader that raises never fails the completion.

Every transcript record is a COPY of a captured one
(`tests/fixtures/transcripts/`), with only the fields a test varies re-keyed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.run.model import Attempt, MainSessionUsage, RunState, StepRecord, UnitRecord
from fr.run.telemetry import (
    ClaudeCodeReader,
    SessionUsage,
    candidate_sessions,
    measure_step_main_session,
)
from fr.workflow.model import parse_manifest

from tests.unit.transcript_sessions import ORCHESTRATOR, copy_of, records, write_session

FIRST, SECOND = [r for r in records(ORCHESTRATOR) if r["type"] == "assistant"]
START = "2026-09-24T10:00:00+00:00"
END = "2026-09-24T10:10:00+00:00"


def _usage(record: dict[str, Any]) -> dict[str, int]:
    u = record["message"]["usage"]
    return {
        k: u[k]
        for k in (
            "input_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
            "output_tokens",
        )
    }


def _row(
    source: dict[str, Any],
    *,
    ts: str,
    msg_id: str,
    sidechain: bool = False,
    model: str | None = None,
) -> dict[str, Any]:
    row = copy_of(source)
    row["timestamp"] = ts
    row["uuid"] = f"u-{msg_id}-{ts}"
    row["isSidechain"] = sidechain
    row["message"]["id"] = msg_id
    if model is not None:
        row["message"]["model"] = model
    return row


def _window_rows() -> list[dict[str, Any]]:
    """Main-thread A (twice — one message, two content-block records) and B
    inside the window; everything else outside it or not the main thread."""
    return [
        # 10:00:00.500 truncates to 10:00:00 — the window's OPEN edge, excluded
        _row(SECOND, ts="2026-09-24T10:00:00.500Z", msg_id="msg-edge"),
        _row(FIRST, ts="2026-09-24T10:05:00.000Z", msg_id="msg-A"),
        _row(FIRST, ts="2026-09-24T10:05:00.100Z", msg_id="msg-A"),
        # 10:10:00.900 truncates to 10:10:00 — the CLOSED edge, included
        _row(SECOND, ts="2026-09-24T10:10:00.900Z", msg_id="msg-B"),
        _row(SECOND, ts="2026-09-24T10:05:00.000Z", msg_id="msg-side", sidechain=True),
        _row(SECOND, ts="2026-09-24T10:06:00.000Z", msg_id="msg-synth", model="<synthetic>"),
        _row(SECOND, ts="2026-09-24T10:10:01.000Z", msg_id="msg-after"),
    ]


def _expected(sessions: int = 1) -> MainSessionUsage:
    a, b = _usage(FIRST), _usage(SECOND)
    return MainSessionUsage(
        **{k: sessions * (a[k] + b[k]) for k in a}, turns=sessions * 2, sessions=sessions
    )


# --- 1. the reader over one file --------------------------------------------


def test_the_main_thread_inside_the_window_is_summed_once_per_message(tmp_path: Path) -> None:
    path = write_session(tmp_path / "projects", "s1", rows=_window_rows())

    got = ClaudeCodeReader().measure_main_session(path, START, END)

    a, b = _usage(FIRST), _usage(SECOND)
    assert got == SessionUsage(**{k: a[k] + b[k] for k in a}, turns=2, cost_usd=None)


def test_an_unreadable_transcript_is_no_measurement(tmp_path: Path) -> None:
    assert ClaudeCodeReader().measure_main_session(tmp_path / "nope.jsonl", START, END) is None


def test_a_window_with_nothing_in_it_is_a_measured_zero(tmp_path: Path) -> None:
    path = write_session(tmp_path / "projects", "s1", rows=_window_rows())
    got = ClaudeCodeReader().measure_main_session(
        path, "2026-09-24T11:00:00+00:00", "2026-09-24T12:00:00+00:00"
    )
    assert got == SessionUsage(0, 0, 0, 0, turns=0, cost_usd=None)


# --- 2. the candidate set and its sum ---------------------------------------


def _env(root: Path, session: str | None = None) -> dict[str, str]:
    env = {"FR_HARNESS": "claude-code", "FR_TRANSCRIPT_ROOT": str(root)}
    if session:
        env["CLAUDE_CODE_SESSION_ID"] = session
    return env


def test_two_candidate_sessions_are_summed(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    write_session(root, "s1", rows=_window_rows())
    write_session(root, "s2", slug="-other", rows=_window_rows())

    got = ClaudeCodeReader().measure_step(_env(root), ["s1", "s2"], START, END, directories=())

    assert got == _expected(sessions=2)


def test_one_unreadable_candidate_means_nothing_is_recorded(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    write_session(root, "s1", rows=_window_rows())

    got = ClaudeCodeReader().measure_step(_env(root), ["s1", "gone"], START, END, directories=())

    assert got is None


def test_no_candidate_at_all_is_no_measurement(tmp_path: Path) -> None:
    assert ClaudeCodeReader().measure_step(_env(tmp_path), [], START, END, directories=()) is None


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    return path


def _state(branch: str = "feat/x", sessions: tuple[str | None, ...] = ()) -> RunState:
    attempts = tuple(
        Attempt(dispatched=START, session=s, outcome="done", returned=END) for s in sessions
    )
    return RunState(
        schema_version=6,
        run="r1",
        workflow="w@1",
        branch=branch,
        started=START,
        cursor="a",
        steps={
            "a": StepRecord(state="running", units={"step/a": UnitRecord(attempts=attempts)}),
        },
    )


def test_the_candidate_set_is_attempts_plus_bindings_plus_this_session(tmp_path: Path) -> None:
    from fr.isolation.types import IsolationState, SessionBinding, save_state

    repo = _git_repo(tmp_path / "repo")
    save_state(
        IsolationState(
            repo_root=repo,
            branch="feat/x",
            worktree=repo,
            profile="host",
            created_at=START,
            sessions=[SessionBinding(session_id="bound", harness="claude", attached_at=START)],
        )
    )
    state = _state(sessions=("s-att", None, "s-att"))

    got = candidate_sessions(state, {"CLAUDE_CODE_SESSION_ID": "s-now"}, repo)

    assert got == ["s-att", "bound", "s-now"]


def test_a_binding_of_another_harness_is_not_a_claude_code_candidate(tmp_path: Path) -> None:
    from fr.isolation.types import IsolationState, SessionBinding, save_state

    repo = _git_repo(tmp_path / "repo")
    save_state(
        IsolationState(
            repo_root=repo,
            branch="feat/x",
            worktree=repo,
            profile="host",
            created_at=START,
            sessions=[SessionBinding(session_id="oc", harness="opencode", attached_at=START)],
        )
    )

    assert candidate_sessions(_state(), {}, repo, harness="claude-code") == []
    assert candidate_sessions(_state(), {}, repo, harness="opencode") == ["oc"]


def test_no_isolation_state_means_no_bindings_not_a_failure(tmp_path: Path) -> None:
    assert candidate_sessions(_state(sessions=("s1",)), {}, tmp_path) == ["s1"]


def test_measure_step_main_session_ties_it_together(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    write_session(root, "s-now", rows=_window_rows())

    got = measure_step_main_session(_state(), _env(root, "s-now"), tmp_path, START, END)

    assert got == _expected()


def test_a_harness_with_no_reader_measures_nothing(tmp_path: Path) -> None:
    got = measure_step_main_session(_state(), {"FR_HARNESS": "hermes"}, tmp_path, START, END)
    assert got is None


# --- 3. the `_complete_step` hook -------------------------------------------

_SHAPE = parse_manifest(
    "workflow: w\nschema: 1\nunit: run\nsteps:\n"
    "  - id: a\n    kind: agent\n    skill: s:a\n"
    "  - id: b\n    kind: agent\n    skill: s:b\n"
)
FIXED = MainSessionUsage(
    input_tokens=1,
    cache_creation_input_tokens=2,
    cache_read_input_tokens=3,
    output_tokens=4,
    turns=5,
    sessions=1,
)


@pytest.fixture
def windows(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Replace the measurement with a recorder, so the hook's WINDOW is what
    these tests observe."""
    import fr.run.telemetry as telemetry

    seen: list[tuple[str, str]] = []

    def fake(state: RunState, env: object, repo_root: Path, start: str, end: str):
        seen.append((start, end))
        return FIXED

    monkeypatch.setattr(telemetry, "measure_step_main_session", fake)
    return seen


def test_done_writes_main_session_over_the_window_since_run_start(
    windows: list[tuple[str, str]],
) -> None:
    from fr.commands.run_cmd import _complete_step

    new = _complete_step(_state(), _SHAPE, "a", "done")

    assert new.steps["a"].main_session == FIXED
    assert windows == [(START, new.steps["a"].at)]


def test_the_window_opens_at_the_previous_top_level_steps_at(
    windows: list[tuple[str, str]],
) -> None:
    from fr.commands.run_cmd import _complete_step

    state = _state().model_copy(
        update={
            "cursor": "b",
            "steps": {
                "a": StepRecord(state="done", at="2026-09-24T10:03:00+00:00"),
                "b": StepRecord(state="running"),
            },
        }
    )

    new = _complete_step(state, _SHAPE, "b", "done")

    assert windows == [("2026-09-24T10:03:00+00:00", new.steps["b"].at)]


def test_failed_writes_no_main_session(windows: list[tuple[str, str]]) -> None:
    from fr.commands.run_cmd import _complete_step

    new = _complete_step(_state(), _SHAPE, "a", "failed")

    assert new.steps["a"].main_session is None
    assert windows == []


def test_a_reader_that_raises_never_fails_the_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fr.run.telemetry as telemetry
    from fr.commands.run_cmd import _complete_step

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("transcript exploded")

    monkeypatch.setattr(telemetry, "measure_step_main_session", boom)

    new = _complete_step(_state(), _SHAPE, "a", "done")

    assert new.steps["a"].state == "done"
    assert new.steps["a"].main_session is None


# --- every `done` path reaches the hook, end to end through the CLI -----------


def test_a_cli_advance_writes_main_session(tmp_path: Path, windows: list[tuple[str, str]]) -> None:
    from fr.run.model import load_run_state

    from tests.unit.test_run_cli import _invoke, _started_two_step

    repo, shipped = _started_two_step(tmp_path)

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    assert load_run_state(repo, "r1").steps["hello"].main_session == FIXED


def test_an_agent_resolve_writes_main_session(
    tmp_path: Path, windows: list[tuple[str, str]]
) -> None:
    from fr.run.model import load_run_state

    from tests.unit.test_run_cli import _THREE_AGENT_SHAPE, _invoke, _repo, _write_shape

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "three-agents", _THREE_AGENT_SHAPE)
    _invoke(repo, shipped, ["run", "start", "three-agents", "--branch", "b", "--run-id", "r1"])
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0

    result = _invoke(repo, shipped, ["run", "resolve", "r1", "--step", "first", "--state", "done"])

    assert result.exit_code == 0, result.output
    assert load_run_state(repo, "r1").steps["first"].main_session == FIXED


def test_the_group_completion_writes_main_session(
    tmp_path: Path, windows: list[tuple[str, str]]
) -> None:
    from fr.run.model import load_run_state

    from tests.unit.test_run_cli import (
        _GROUPED_SHAPE,
        _drive_the_group,
        _repo,
        _started_grouped_with_plan,
        _write_shape,
    )

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)

    _drive_the_group(repo, shipped)

    state = load_run_state(repo, "r1")
    assert state.steps["implement"].state == "done"
    assert state.steps["implement"].main_session == FIXED
    assert state.steps["plan"].main_session == FIXED


def test_the_group_completed_by_advance_writes_main_session(
    tmp_path: Path, windows: list[tuple[str, str]]
) -> None:
    """The third `done` path: `advance` finds no outstanding unit (every phase
    `[manual]`) and completes the group itself, with no resolve involved."""
    from fr.run.model import load_run_state

    from tests.unit.test_run_cli import (
        _GROUPED_SHAPE,
        _invoke,
        _plan_with_tags,
        _repo,
        _started_grouped_with_plan,
        _write_shape,
    )

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped, _plan_with_tags(repo, [(1, "manual", ())]))

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "r1")
    assert state.steps["implement"].state == "done", result.output
    assert state.steps["implement"].main_session == FIXED
