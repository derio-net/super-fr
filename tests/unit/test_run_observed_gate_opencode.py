"""The brainstorm operator gate on OpenCode (spec 2026-10-02-opencode-observe-2
§F, R9): who answered is read from the `question` tool's parts in the run
session of the committed run-tree fixture, moved to the gate's own clock."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from fr.run.model import load_run_state
from fr.run.telemetry import parse_timestamp

from tests.unit.opencode_fixture import opencode_env, shifted
from tests.unit.test_run_cli import (
    _RESOLVE_BRAINSTORM,
    _gated_agent_blocked,
    _invoke_as_harness,
    _squash,
)


def _blocked(tmp_path: Path) -> tuple[Path, Path, Path]:
    """The gate blocked (as an OpenCode session), and a fixture copy whose run
    tree starts the moment it blocked — so its question rounds come after."""
    repo, shipped, blocked_at = _gated_agent_blocked(tmp_path, tmp_path / "projects", "s-g")
    start = parse_timestamp(blocked_at)
    assert start is not None
    return repo, shipped, shifted(tmp_path, start)


def _resolve(repo: Path, shipped: Path, db: Path, *extra: str):
    return _invoke_as_harness(repo, shipped, [*_RESOLVE_BRAINSTORM, *extra], opencode_env(db))


def test_one_answered_round_since_the_block_is_the_operator(tmp_path: Path) -> None:
    repo, shipped, db = _blocked(tmp_path)

    result = _resolve(repo, shipped, db)

    assert result.exit_code == 0, result.output
    record = load_run_state(repo, "r1").steps["brainstorm"]
    assert record.state == "done"
    assert record.answered_by == "operator"


def test_a_declared_second_round_against_one_observed_is_refused(tmp_path: Path) -> None:
    repo, shipped, db = _blocked(tmp_path)

    result = _resolve(
        repo,
        shipped,
        db,
        "--question-rounds",
        "2",
        "--round-two-trigger",
        "operator-request",
        "--round-two-reason",
        "the operator asked",
    )

    assert result.exit_code == 2, result.output
    assert "shows 1 answered question round" in _squash(result.output)
    assert load_run_state(repo, "r1").steps["brainstorm"].state == "blocked"


def test_a_declined_only_round_is_no_answer(tmp_path: Path) -> None:
    repo, shipped, db = _blocked(tmp_path)
    with closing(sqlite3.connect(db)) as con:
        for part_id, raw in con.execute("SELECT id, data FROM part").fetchall():
            data = json.loads(raw)
            if data.get("tool") == "question" and data.get("callID") in {"call_q1", "call_q2"}:
                con.execute("DELETE FROM part WHERE id = ?", (part_id,))
        con.commit()

    result = _resolve(repo, shipped, db)

    assert result.exit_code == 2, result.output
    assert "no answered question" in _squash(result.output)
    assert load_run_state(repo, "r1").steps["brainstorm"].state == "blocked"
