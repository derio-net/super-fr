"""No default `answered_by`, and honest gate wording (spec
2026-10-02-opencode-observe-2 §F, R10 and R11).

A gate fr cannot observe used to record `agent` for a caller that said nothing
— a claim nobody made. Now the caller must say which: the record form, the
flag form and the in-process body all refuse. An UNGATED step has no gate to
answer and resolves as it always did.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run.model import load_run_state

from tests.unit.test_run_cli import (
    _RESOLVE_BRAINSTORM,
    _clear_cli_gate,
    _gated_agent_blocked,
    _invoke,
    _invoke_measurable,
    _repo,
    _write_shape,
)


def _squash(text: str) -> str:
    return " ".join(text.split())


def test_the_flag_form_refuses_an_unobservable_gate_with_no_answered_by(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"

    result = _clear_cli_gate(repo, shipped, claimed=False)

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "could not verify who answered this gate" in out
    assert "operator" in out and "agent" in out
    assert load_run_state(repo, "r1").steps["brainstorm"].state == "blocked"


def test_the_record_form_refuses_an_unobservable_gate_with_no_answered_by(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_run_question_rounds import _blocked, _resolve_brainstorm

    root, _ = _blocked(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s-missing")

    out = _resolve_brainstorm(root, "record", None)()

    assert out.exit_code == 2, out.output
    assert "could not verify who answered this gate" in _squash(out.output)


@pytest.mark.parametrize("claim", ["operator", "agent"])
def test_a_stated_claim_is_still_recorded_as_claimed(tmp_path: Path, claim: str) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"

    result = _clear_cli_gate(repo, shipped, "--answered-by", claim)

    assert result.exit_code == 0, result.output
    assert load_run_state(repo, "r1").steps["brainstorm"].answered_by == claim


def test_a_third_value_is_still_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"

    result = _clear_cli_gate(repo, shipped, "--answered-by", "committee")

    assert result.exit_code == 2, result.output
    assert "must be 'operator' or 'agent'" in _squash(result.output)


def test_an_ungated_step_resolves_with_no_answered_by(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(
        shipped,
        "plain",
        "workflow: plain\nschema: 1\nunit: run\nsteps:\n"
        "  - id: work\n    kind: agent\n    skill: super-fr:fr-execute\n",
    )
    _invoke(repo, shipped, ["run", "start", "plain", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(repo, shipped, ["run", "resolve", "r1", "--step", "work", "--state", "done"])

    assert result.exit_code == 0, result.output
    record = load_run_state(repo, "r1").steps["work"]
    assert record.state == "done"
    assert record.answered_by is None


# --- R11: the wording says what fr could and could not see -------------------


def test_a_claimed_agent_on_an_unobserved_gate_says_fr_could_not_read_who_answered(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _clear_cli_gate(repo, shipped, "--answered-by", "agent")

    for verb in ("check", "gates"):
        result = _invoke(repo, shipped, ["run", verb, "r1"])
        out = _squash(result.output)
        assert result.exit_code == 0, result.output
        assert "cleared by the agent, as claimed" in out, verb
        assert "unobserved: fr could not read who answered" in out, verb
        assert "no operator answered it" not in out, verb


def test_a_claimed_operator_on_an_unobserved_gate_says_so(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _clear_cli_gate(repo, shipped, "--answered-by", "operator")

    # p3-r2: `check` reports it too, in the same sentence `gates` uses.
    for verb in ("check", "gates"):
        result = _invoke(repo, shipped, ["run", verb, "r1"])
        assert result.exit_code == 0, result.output
        out = _squash(result.output)
        expected = "brainstorm: operator gate answered by the operator, as claimed — unobserved"
        assert expected in out, verb


def test_an_observed_agent_keeps_no_operator_answered_it(tmp_path: Path) -> None:
    from tests.unit.transcript_sessions import write_session

    root = tmp_path / "projects"
    write_session(root, session_id="s-g")
    repo, shipped, _ = _gated_agent_blocked(tmp_path, root, "s-g")
    cleared = _invoke_measurable(
        repo, shipped, [*_RESOLVE_BRAINSTORM, "--no-questions", "--reason", "all in the ask"],
        root, "s-g",
    )  # fmt: skip
    assert cleared.exit_code == 0, cleared.output

    for verb in ("check", "gates"):
        out = _squash(_invoke(repo, shipped, ["run", verb, "r1"]).output)
        assert "no operator answered it" in out, verb
        assert "as claimed" not in out, verb
