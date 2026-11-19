"""Run durability (batch run-durability: super-fr#1500, #1524, #1511, #1507).

Three causes, pinned separately:

1. A failed write must not destroy the last valid file (#1500, #1524):
   `Path.write_text` truncates first and writes second, so a failure between
   the two leaves a truncated cursor, plan or spec. The writers go through
   `fr.artifacts.atomic.write_text_atomic`, which leaves the original
   byte-identical on any failure.
2. Two `fr run` commands on one cursor must not lose an update (#1511).
3. A `kind: cli` step is bounded in time and in what it stores (#1507).
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fr.run.model import (
    RunState,
    StepRecord,
    dump_run_state,
    forget_observed_run_states,
    run_path,
    save_run_state,
)

_SRC = Path(__file__).resolve().parents[2] / "packages" / "fr" / "src" / "fr"
_PLAN_FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _state(cursor: str = "a") -> RunState:
    return RunState(
        run="r1",
        workflow="w@1",
        branch="b",
        started="2026-11-19T00:00:00Z",
        cursor=cursor,
        steps={"a": StepRecord(state="pending"), "b": StepRecord(state="pending")},
    )


def _fail_fsync(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(fd):  # type: ignore[no-untyped-def]
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", boom)


# --- 1. atomic writes (#1500, #1524) ----------------------------------------


def test_a_failed_cursor_save_leaves_the_last_valid_cursor_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_run_state(tmp_path, _state("a"))
    path = run_path(tmp_path, "r1")
    original = path.read_text()

    _fail_fsync(monkeypatch)
    with pytest.raises(OSError):
        save_run_state(tmp_path, _state("b"))
    monkeypatch.undo()

    assert path.read_text() == original
    assert [p.name for p in path.parent.iterdir()] == [path.name], "temp file left behind"


def _git_plan(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "T")):
        subprocess.run(["git", "-C", str(tmp_path), "config", key, value], check=True)
    plan_dir = tmp_path / "docs" / "superpowers" / "plans" / "v2_plan_minimal"
    plan_dir.parent.mkdir(parents=True)
    shutil.copytree(_PLAN_FIXTURE, plan_dir)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"], check=True)
    return plan_dir


def test_a_failed_plan_write_leaves_the_phase_file_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr import plan_ops

    plan_dir = _git_plan(tmp_path)
    phase = plan_dir / "01.yaml"
    original = phase.read_text()

    _fail_fsync(monkeypatch)
    with pytest.raises(OSError):
        plan_ops.set_tracking_issue(plan_dir, 1, "https://github.com/derio-net/test/issues/42")
    monkeypatch.undo()

    assert phase.read_text() == original


@pytest.mark.parametrize("module", ["plan_ops.py", "run/model.py"])
def test_no_plain_write_text_in_the_cursor_and_plan_writers(module: str) -> None:
    """Every write in these modules replaces a file someone relies on; a plain
    `write_text` is the truncate-then-write this batch removes."""
    tree = ast.parse((_SRC / module).read_text())
    calls = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]
    assert calls == [], f"{module}: plain write_text at lines {calls}; use write_text_atomic"


def test_the_atomic_cursor_is_byte_identical_to_the_plain_dump(tmp_path: Path) -> None:
    state = _state("a")
    save_run_state(tmp_path, state)
    assert run_path(tmp_path, "r1").read_text() == dump_run_state(state)


# --- 2. no lost cursor update (#1511) ---------------------------------------


def _other_process_writes(tmp_path: Path, state: RunState) -> str:
    """What a second `fr run` command does: write the cursor from its own
    process, which this process's read record knows nothing about."""
    text = dump_run_state(state)
    run_path(tmp_path, state.run).write_bytes(text.encode())
    return text


def test_a_save_over_a_cursor_another_command_changed_refuses(tmp_path: Path) -> None:
    from fr.run.model import RunStateConflictError, load_run_state

    save_run_state(tmp_path, _state("a"))
    forget_observed_run_states()  # a fresh command
    mine = load_run_state(tmp_path, "r1")
    theirs = _other_process_writes(tmp_path, _state("b"))

    with pytest.raises(RunStateConflictError, match="changed on disk"):
        save_run_state(tmp_path, mine.model_copy(update={"pr": "https://example.com/pr/1"}))

    assert run_path(tmp_path, "r1").read_text() == theirs, "the other command's update was lost"


def test_one_command_may_save_the_same_cursor_twice(tmp_path: Path) -> None:
    from fr.run.model import load_run_state

    save_run_state(tmp_path, _state("a"))
    forget_observed_run_states()
    state = load_run_state(tmp_path, "r1")
    save_run_state(tmp_path, state.model_copy(update={"cursor": "b"}))
    # Derived from the FIRST read, as run_cmd's step helpers do: still ours.
    save_run_state(tmp_path, state.model_copy(update={"pr": "https://example.com/pr/1"}))
    assert load_run_state(tmp_path, "r1").pr == "https://example.com/pr/1"


def test_a_cursor_read_by_scanning_is_guarded_too(tmp_path: Path) -> None:
    """`fr pr create` and the branch scans read a cursor by path, not by id."""
    from fr.run.model import RunStateConflictError, read_run_state

    save_run_state(tmp_path, _state("a"))
    forget_observed_run_states()
    mine = read_run_state(run_path(tmp_path, "r1"))
    _other_process_writes(tmp_path, _state("b"))
    with pytest.raises(RunStateConflictError):
        save_run_state(tmp_path, mine)


def test_a_cursor_removed_since_it_was_read_is_not_recreated(tmp_path: Path) -> None:
    """An archive moved it away; a late save must not resurrect it."""
    from fr.run.model import RunStateConflictError, load_run_state

    save_run_state(tmp_path, _state("a"))
    forget_observed_run_states()
    mine = load_run_state(tmp_path, "r1")
    run_path(tmp_path, "r1").unlink()
    with pytest.raises(RunStateConflictError):
        save_run_state(tmp_path, mine)
    assert not run_path(tmp_path, "r1").exists()


def test_a_new_cursor_nobody_read_is_written_unchecked(tmp_path: Path) -> None:
    forget_observed_run_states()
    save_run_state(tmp_path, _state("a"))
    assert run_path(tmp_path, "r1").is_file()


def test_the_cli_refuses_a_lost_update_with_exit_2_and_keeps_the_other_write(
    tmp_path: Path,
) -> None:
    """End to end: a cli step that itself rewrites the cursor (as a nested
    `fr run` command would) while `fr run advance` holds its read."""
    from tests.unit.test_run_cli import _invoke, _repo, _write_shape

    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(
        shipped,
        "touchy",
        "workflow: touchy\nschema: 1\nunit: run\nsteps:\n"
        "  - id: touch\n    kind: cli\n"
        "    run: echo '# touched by another command' >> docs/superpowers/runs/r1.yaml\n"
        '  - id: after\n    kind: cli\n    run: "true"\n',
    )
    started = _invoke(
        repo, shipped, ["run", "start", "touchy", "--branch", "feat/x", "--run-id", "r1"]
    )
    assert started.exit_code == 0, started.output

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 2, result.output
    assert "changed on disk" in result.output
    assert "Traceback" not in result.output
    assert "# touched by another command" in run_path(repo, "r1").read_text()


# --- 3. a bounded cli step (#1507) ------------------------------------------


def _cli_run(tmp_path: Path, run: str):
    """Start a one-cli-step run and advance it once; returns (result, state)."""
    from fr.run.model import load_run_state

    from tests.unit.test_run_cli import _invoke, _repo, _write_shape

    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(
        shipped,
        "one",
        "workflow: one\nschema: 1\nunit: run\nsteps:\n"
        f"  - id: step\n    kind: cli\n    run: {json.dumps(run)}\n"  # JSON is YAML
        '  - id: after\n    kind: cli\n    run: "true"\n',
    )
    started = _invoke(
        repo, shipped, ["run", "start", "one", "--branch", "feat/x", "--run-id", "r1"]
    )
    assert started.exit_code == 0, started.output
    result = _invoke(repo, shipped, ["run", "advance", "r1"])
    return result, load_run_state(repo, "r1")


def test_a_cli_step_that_outlives_its_timeout_fails_and_is_killed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`sleep 30 | cat`: the pipeline's children hold stdout open, so killing
    only the shell would still hang the advance."""
    import time

    monkeypatch.setenv("FR_CLI_STEP_TIMEOUT", "1")
    began = time.monotonic()
    result, state = _cli_run(tmp_path, "echo started; sleep 30 | cat")
    elapsed = time.monotonic() - began

    assert elapsed < 20, f"advance waited {elapsed:.0f}s: the step was not killed"
    assert result.exit_code != 0, result.output
    assert "timed out after 1s" in result.output
    step = state.steps["step"]
    assert step.state == "failed"
    assert step.exit == 124
    assert step.stdout is not None and "started" in step.stdout
    assert state.cursor == "step"


def test_a_cli_step_keeps_only_a_bounded_tail_of_its_stdout(tmp_path: Path) -> None:
    from fr.commands.run_cmd import CLI_STEP_STDOUT_MAX_CHARS

    result, state = _cli_run(
        tmp_path, "python3 -c \"print('x' * 1000000); print('the last line')\""
    )

    assert result.exit_code == 0, result.output
    stdout = state.steps["step"].stdout
    assert stdout is not None
    assert len(stdout) <= CLI_STEP_STDOUT_MAX_CHARS + 200
    assert stdout.endswith("the last line\n")
    assert "truncated" in stdout.splitlines()[0]


def test_a_short_cli_stdout_is_stored_unchanged(tmp_path: Path) -> None:
    _, state = _cli_run(tmp_path, "echo hello")
    assert state.steps["step"].stdout == "hello\n"


def test_a_malformed_timeout_is_refused_and_runs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FR_CLI_STEP_TIMEOUT", "soon")
    marker = tmp_path / "ran"
    result, state = _cli_run(tmp_path, f"touch {marker}")
    assert result.exit_code == 2, result.output
    assert "FR_CLI_STEP_TIMEOUT" in result.output
    assert not marker.exists()
    assert state.steps["step"].state != "done"
