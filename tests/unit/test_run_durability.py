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
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fr.run.model import RunState, StepRecord, dump_run_state, run_path, save_run_state

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
