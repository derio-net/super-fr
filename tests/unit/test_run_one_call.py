"""One bookkeeping call per step (spec 2026-09-29-fr-goal-light-path §B, R4/R5).

`fr run advance` runs consecutive `kind: cli` steps in one invocation and stops
at the first brief, gate, failure, refusal or the end of the run. `fr run
resolve --record` applies the record and then advances the same way, unless
`--no-advance` is passed — and only when the record's outcome is `done`: a
`failed` or `blocked` record leaves the cursor on its own step, and advancing
from there would open a fresh dispatch of the work that just failed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from fr.run import units
from fr.run.model import load_run_state

from tests.unit.test_run_cli import _invoke, _repo, _squash, _write_shape

RUN = "r1"


def _shape(*, c1: str = "true", gate_c2: bool = False, tail_agent: bool = True) -> str:
    text = (
        "workflow: chain\nschema: 1\nunit: run\nsteps:\n"
        "  - id: a\n    kind: agent\n"
        f"  - id: c1\n    kind: cli\n    run: {json.dumps(c1)}\n"
        '  - id: c2\n    kind: cli\n    run: "true"\n'
    )
    if gate_c2:
        text += "    gate: operator\n"
    if tail_agent:
        text += "  - id: b\n    kind: agent\n"
    return text


_DIRECT = (
    "workflow: chain\nschema: 1\nunit: run\nsteps:\n"
    "  - id: a\n    kind: agent\n  - id: b\n    kind: agent\n"
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def _subjects(root: Path) -> list[str]:
    return _git(root, "log", "--format=%s").splitlines()


def _started(tmp_path: Path, shape: str) -> tuple[Path, Path]:
    """Run `r1` started on `shape`, with `a` briefed (running)."""
    repo = _repo(tmp_path, branch="feat/x")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "chain", shape)
    start = ["run", "start", "chain", "--branch", "feat/x", "--run-id", RUN]
    assert _invoke(repo, shipped, start).exit_code == 0
    out = _invoke(repo, shipped, ["run", "advance", RUN])
    assert out.exit_code == 0, out.output
    assert "a: dispatch brief" in out.output
    return repo, shipped


def _a_done_by_flag(repo: Path, shipped: Path) -> None:
    done = ["run", "resolve", RUN, "--step", "a", "--state", "done"]
    out = _invoke(repo, shipped, done)
    assert out.exit_code == 0, out.output


def _briefs(stdout: str) -> list[dict[str, object]]:
    found = []
    for line in stdout.splitlines():
        if line.startswith("{"):
            found.append(json.loads(line))
    return found


# --- R5: `fr run advance` chains cli steps ------------------------------------


def test_a_one_advance_runs_both_cli_steps_and_briefs_the_next_agent(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path, _shape())
    _a_done_by_flag(repo, shipped)
    before = len(_subjects(repo))

    out = _invoke(repo, shipped, ["run", "advance", RUN])

    assert out.exit_code == 0, out.output
    lines = out.stdout.splitlines()
    assert "c1: done (exit 0)" in lines
    assert "c2: done (exit 0)" in lines
    assert "b: dispatch brief" in lines
    # The brief JSON is the LAST stdout line, on its own.
    assert json.loads(lines[-1])["step"] == "b"
    state = load_run_state(repo, RUN)
    assert state.cursor == "b"
    assert state.steps["c1"].state == state.steps["c2"].state == "done"
    assert state.steps["b"].state == "running"
    # One commit per step, as a single advance has always made.
    new = _subjects(repo)[: len(_subjects(repo)) - before]
    assert len(new) == 3, new
    assert any("advance c1 done" in s for s in new)
    assert any("advance c2 done" in s for s in new)
    assert any("advance b running" in s for s in new)


def test_b_a_failing_cli_step_stops_the_chain_and_exits_1(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path, _shape(c1="false"))
    _a_done_by_flag(repo, shipped)

    out = _invoke(repo, shipped, ["run", "advance", RUN])

    assert out.exit_code == 1, out.output
    assert "c1: failed (exit 1)" in out.output
    assert "dispatch brief" not in out.output
    state = load_run_state(repo, RUN)
    assert state.cursor == "c1"
    assert state.steps["c1"].state == "failed"
    assert state.steps["b"].state == "pending"


def test_c_on_an_agent_step_advance_prints_exactly_one_brief(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path, _DIRECT)
    _a_done_by_flag(repo, shipped)

    out = _invoke(repo, shipped, ["run", "advance", RUN])

    assert out.exit_code == 0, out.output
    assert out.stdout.count("dispatch brief") == 1
    assert len(_briefs(out.stdout)) == 1
    assert load_run_state(repo, RUN).cursor == "b"


def test_d_an_operator_gate_stops_the_chain(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path, _shape(gate_c2=True))
    _a_done_by_flag(repo, shipped)

    out = _invoke(repo, shipped, ["run", "advance", RUN])

    assert out.exit_code == 0, out.output
    assert "c1: done (exit 0)" in out.stdout
    assert "c2: blocked on operator gate" in _squash(out.output)
    assert "b: dispatch brief" not in out.stdout
    state = load_run_state(repo, RUN)
    assert state.cursor == "c2"
    assert state.steps["c2"].state == "blocked"
    assert state.steps["b"].state == "pending"


def test_e_a_cli_last_step_chains_to_the_run_end(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path, _shape(tail_agent=False))
    _a_done_by_flag(repo, shipped)

    out = _invoke(repo, shipped, ["run", "advance", RUN])

    assert out.exit_code == 0, out.output
    assert "c2: done (exit 0)" in out.stdout
    assert f"run {RUN} complete" in out.stdout
    state = load_run_state(repo, RUN)
    assert state.cursor == "c2"
    assert state.steps["c2"].state == "done"


# --- R4: `resolve --record` advances by default ---------------------------------


def _record(repo: Path, outcome: str = "done", **extra: object) -> Path:
    from fr.record.model import RECORD_SCHEMA_VERSION

    data: dict[str, object] = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "run": RUN,
        "step": "a",
        "outcome": outcome,
        **extra,
    }
    path = repo / "docs" / "superpowers" / "runs" / f"{RUN}.records" / "a.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "record", "--no-verify")
    return path


def _resolve(repo: Path, shipped: Path, record: Path, *flags: str):
    argv = ["run", "resolve", RUN, "--step", "a", "--record", str(record), *flags]
    return _invoke(repo, shipped, argv)


def test_f_resolve_record_prints_the_outcome_then_the_next_brief(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path, _DIRECT)
    record = _record(repo)

    out = _resolve(repo, shipped, record)

    assert out.exit_code == 0, out.output
    lines = out.stdout.splitlines()
    assert lines[0].startswith("a done"), lines
    assert lines[1] == "b: dispatch brief", lines
    assert json.loads(lines[-1])["step"] == "b"
    assert load_run_state(repo, RUN).steps["b"].state == "running"


def test_g_resolve_record_runs_the_following_cli_steps_inline(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path, _shape())
    record = _record(repo)

    out = _resolve(repo, shipped, record)

    assert out.exit_code == 0, out.output
    lines = out.stdout.splitlines()
    assert lines[0].startswith("a done"), lines
    assert "c1: done (exit 0)" in lines and "c2: done (exit 0)" in lines
    assert "b: dispatch brief" in lines
    assert json.loads(lines[-1])["step"] == "b"
    assert load_run_state(repo, RUN).cursor == "b"


def test_h_a_chained_cli_failure_exits_1_with_the_record_committed(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path, _shape(c1="exit 3"))
    record = _record(repo)

    out = _resolve(repo, shipped, record)

    assert out.exit_code == 1, out.output
    assert "record applied; c1 failed (exit 3)" in _squash(out.output)
    assert not record.exists()
    assert any("resolve a" in s for s in _subjects(repo))
    state = load_run_state(repo, RUN)
    assert state.steps["a"].state == "done"
    assert state.cursor == "c1"
    assert state.steps["c1"].state == "failed"


def test_i_no_advance_prints_only_the_outcome_line(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path, _shape())
    record = _record(repo)

    out = _resolve(repo, shipped, record, "--no-advance")

    assert out.exit_code == 0, out.output
    lines = out.stdout.splitlines()
    assert len(lines) == 1 and lines[0].startswith("a done"), lines
    state = load_run_state(repo, RUN)
    assert state.cursor == "c1"
    assert state.steps["c1"].state == "pending"


@pytest.mark.parametrize("outcome", ["failed", "blocked"])
def test_j_a_failed_or_blocked_record_opens_no_new_dispatch(tmp_path: Path, outcome: str) -> None:
    repo, shipped = _started(tmp_path, _shape())
    before = units.attempts(load_run_state(repo, RUN).steps["a"], "step/a")
    record = _record(repo, outcome)

    out = _resolve(repo, shipped, record)

    assert out.exit_code == 0, out.output
    lines = out.stdout.splitlines()
    assert len(lines) == 1, lines
    assert "dispatch brief" not in out.output
    state = load_run_state(repo, RUN)
    assert state.cursor == "a"
    assert len(units.attempts(state.steps["a"], "step/a")) == len(before)


def test_k_a_refused_record_neither_applies_nor_advances(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path, _shape())
    record = _record(repo, ticks=["P1.T1.S1"])  # `a` emits no plan:ticks

    out = _resolve(repo, shipped, record)

    assert out.exit_code == 2, out.output
    assert "nothing applied" in _squash(out.output)
    assert "dispatch brief" not in out.output
    assert record.exists()
    state = load_run_state(repo, RUN)
    assert state.cursor == "a"
    assert state.steps["a"].state == "running"
    assert state.steps["c1"].state == "pending"


def test_l_the_flag_form_does_not_advance(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path, _shape())

    out = _invoke(repo, shipped, ["run", "resolve", RUN, "--step", "a", "--state", "done"])

    assert out.exit_code == 0, out.output
    assert "c1: done" not in out.output
    assert "dispatch brief" not in out.output
    state = load_run_state(repo, RUN)
    assert state.cursor == "c1"
    assert state.steps["c1"].state == "pending"


def test_no_advance_is_refused_with_the_flag_form(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path, _shape())

    argv = ["run", "resolve", RUN, "--step", "a", "--state", "done", "--no-advance"]
    out = _invoke(repo, shipped, argv)

    assert out.exit_code == 2, out.output
    assert "--no-advance" in _squash(out.output)
    assert load_run_state(repo, RUN).steps["a"].state == "running"
