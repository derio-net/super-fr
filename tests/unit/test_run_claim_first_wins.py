"""First claim wins — a re-claim never rewrites an open attempt (#1110).

An attempt that carries an `agent` keeps the `harness`, `model` and
`agent_type` its first claim recorded: an empty field is filled, an identical
value (or the same `model_family`) is a no-op, a different one is kept with a
warning. A re-claim that changes nothing writes nothing and commits nothing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.run.model import load_run_state

from tests.unit.test_run_cli import _invoke_as_harness
from tests.unit.test_run_holder_identity import _attempt, _started

_STEP = "phase/1/implement-phase"
_X = "claude-opus-4-7"


def _commits(repo: Path) -> int:
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--count", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(out.stdout.strip())


def _cursor_bytes(repo: Path) -> bytes:
    return (repo / "docs" / "superpowers" / "runs" / "r1.yaml").read_bytes()


def _claim(repo: Path, shipped: Path, *extra: str, agent: str = "ses_a"):
    argv = ["run", "claim", "r1", "--step", _STEP, "--agent", agent, "--harness", "claude-code"]
    return _invoke_as_harness(repo, shipped, [*argv, *extra], {"FR_HARNESS": "claude-code"})


def _advanced(tmp_path: Path) -> tuple[Path, Path]:
    repo, shipped = _started(tmp_path)
    advanced = _invoke_as_harness(
        repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "claude-code"}
    )
    assert advanced.exit_code == 0, advanced.output
    return repo, shipped


def _claimed(tmp_path: Path) -> tuple[Path, Path]:
    repo, shipped = _advanced(tmp_path)
    first = _claim(repo, shipped, "--model", _X)
    assert first.exit_code == 0, first.output
    return repo, shipped


def test_an_identical_reclaim_is_a_no_change_with_no_commit(tmp_path: Path) -> None:
    repo, shipped = _claimed(tmp_path)
    before, commits = _cursor_bytes(repo), _commits(repo)

    result = _claim(repo, shipped, "--model", _X)

    assert result.exit_code == 0, result.output
    assert "already claimed by ses_a (no change)" in result.output
    assert _cursor_bytes(repo) == before
    assert _commits(repo) == commits


def test_a_reclaim_in_the_same_model_family_keeps_the_recorded_model(tmp_path: Path) -> None:
    repo, shipped = _claimed(tmp_path)
    commits = _commits(repo)

    result = _claim(repo, shipped, "--model", _X + "-20260101")

    assert result.exit_code == 0, result.output
    assert "warning" not in result.output
    assert _attempt(repo).model == _X
    assert _commits(repo) == commits


def test_a_reclaim_in_another_family_keeps_the_model_and_warns(tmp_path: Path) -> None:
    repo, shipped = _claimed(tmp_path)
    commits = _commits(repo)

    result = _claim(repo, shipped, "--model", "claude-haiku-4-5")

    assert result.exit_code == 0, result.output
    assert "warning: " in result.output
    assert "ses_a is recorded with model=" + _X in result.output
    assert "this claim said claude-haiku-4-5" in result.output
    assert "--abandoned" in result.output
    assert _attempt(repo).model == _X
    assert _commits(repo) == commits


def test_the_opencode_sequence_keeps_the_plugin_claims_model_and_tier(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "opencode"})
    plugin = _invoke_as_harness(
        repo,
        shipped,
        [
            "run",
            "claim",
            "--open-unit",
            "--agent",
            "ses_a",
            "--harness",
            "opencode",
            "--model",
            "provider/model-one",
            "--agent-type",
            "fr-phase-executor-standard",
        ],
        {},
    )
    assert plugin.exit_code == 0, plugin.output

    orchestrator = _invoke_as_harness(
        repo,
        shipped,
        [
            "run",
            "claim",
            "r1",
            "--step",
            _STEP,
            "--agent",
            "ses_a",
            "--harness",
            "opencode",
            "--model",
            "other/different-two",
        ],
        {},
    )

    assert orchestrator.exit_code == 0, orchestrator.output
    assert "warning: " in orchestrator.output
    attempt = _attempt(repo)
    assert attempt.model == "provider/model-one"
    assert attempt.agent_type == "fr-phase-executor-standard"


def test_a_resolve_model_without_agent_keeps_the_claimed_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("fr.run.telemetry.subagent_model", lambda *a, **k: None)
    repo, shipped = _claimed(tmp_path)

    result = _invoke_as_harness(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", _STEP, "--state", "done", "--model", "claude-haiku-4-5"],
        {"FR_HARNESS": "claude-code"},
    )

    assert result.exit_code == 0, result.output
    assert "warning: " in result.output
    assert _attempt(repo).model == _X


def test_a_first_claim_overrides_what_advance_prefilled(tmp_path: Path) -> None:
    repo, shipped = _advanced(tmp_path)
    assert _attempt(repo).agent is None

    result = _claim(repo, shipped, "--model", _X)

    assert result.exit_code == 0, result.output
    assert "warning" not in result.output
    attempt = _attempt(repo)
    assert (attempt.agent, attempt.harness, attempt.model) == ("ses_a", "claude-code", _X)


def test_a_different_agent_is_still_refused(tmp_path: Path) -> None:
    repo, shipped = _claimed(tmp_path)
    commits = _commits(repo)

    result = _claim(repo, shipped, "--model", _X, agent="ses_b")

    assert result.exit_code == 2, result.output
    assert "already claimed by" in result.output
    assert _attempt(repo).agent == "ses_a"
    assert _commits(repo) == commits


def test_advance_after_an_interruption_names_the_holder_and_does_not_rebrief(
    tmp_path: Path,
) -> None:
    repo, shipped = _claimed(tmp_path)
    load_run_state(repo, "r1")  # a restarted orchestrator reloads the cursor

    result = _invoke_as_harness(
        repo, shipped, ["run", "advance", "r1"], {"FR_HARNESS": "claude-code"}
    )

    assert "ses_a" in result.output
    assert len(_attempts(repo)) == 1


def _attempts(repo: Path):
    from tests.unit.test_run_cli import _attempts_by_unit

    found = _attempts_by_unit(load_run_state(repo, "r1").steps[_STEP])
    assert found is not None
    return found["step/" + _STEP]
