"""The declared `tests: ci` default (spec 2026-11-19-local-suite-cost R8, §3.F).

`.fr/ci.yaml` may declare `tests: ci` beside `gate_checks`, read at HEAD. When it
does, the `deliver` brief and each phase executor's brief carry
`tests: {mode: ci, fast_tier: ...}`; when it does not, they carry no `tests` key.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.run.ci_evidence import CiEvidenceRefused, declared_tests_mode, load_gate_checks
from fr.workflow.model import Step

from tests.unit.test_run_cli import (
    _GROUPED_SHAPE,
    _brief_of,
    _invoke,
    _repo,
    _started_grouped_with_plan,
    _write_shape,
)

FAST_TIER = "uv run pytest --fr-scope origin/main -n 2 -q --no-cov"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _with_ci_yaml(tmp_path: Path, body: str | None) -> Path:
    """A repo with `origin/main` as its default ref and `.fr/ci.yaml` committed."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    origin, root = tmp_path / "origin.git", tmp_path / "work"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(tmp_path, "init", "-q", "-b", "main", str(root))
    (root / "seed").write_text("s\n")
    if body is not None:
        (root / ".fr").mkdir()
        (root / ".fr" / "ci.yaml").write_text(body)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-q", "origin", "main")
    _git(root, "remote", "set-head", "origin", "main")
    return root


def test_tests_ci_is_declared(tmp_path: Path) -> None:
    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\ntests: ci\n")
    assert declared_tests_mode(root) == "ci"


def test_no_key_and_no_file_declare_nothing(tmp_path: Path) -> None:
    assert declared_tests_mode(_with_ci_yaml(tmp_path / "a", "gate_checks: [ci-ok]\n")) is None
    assert declared_tests_mode(_with_ci_yaml(tmp_path / "b", None)) is None


@pytest.mark.parametrize("value", ["local", "true", "[ci]", "''"])
def test_any_other_value_is_refused(tmp_path: Path, value: str) -> None:
    root = _with_ci_yaml(tmp_path, f"gate_checks: [ci-ok]\ntests: {value}\n")
    with pytest.raises(CiEvidenceRefused, match="tests: ci"):
        declared_tests_mode(root)


def test_the_key_is_read_at_head_not_in_the_working_tree(tmp_path: Path) -> None:
    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\n")
    (root / ".fr" / "ci.yaml").write_text("gate_checks: [ci-ok]\ntests: ci\n")
    assert declared_tests_mode(root) is None


def test_load_gate_checks_still_ignores_unknown_keys(tmp_path: Path) -> None:
    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\ntests: ci\nother: 1\n")
    assert load_gate_checks(root) == ["ci-ok"]


def _deliver_step() -> Step:
    return Step.model_validate({"id": "deliver", "kind": "agent", "evidence": ["tests", "docs"]})


def _executor_step() -> Step:
    return Step.model_validate(
        {"id": "implement-phase", "kind": "agent", "agent": "super-fr:fr-phase-executor"}
    )


def _reviewer_step() -> Step:
    return Step.model_validate(
        {"id": "review-phase", "kind": "agent", "evidence": ["review", "reviewer"]}
    )


def test_the_briefs_carry_the_declared_mode_and_the_fast_tier(tmp_path: Path) -> None:
    from fr.commands.run_cmd import _tests_brief

    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\ntests: ci\n")
    want = {"tests": {"mode": "ci", "fast_tier": FAST_TIER}}
    assert _tests_brief(root, _deliver_step()) == want
    assert _tests_brief(root, _executor_step()) == want
    assert _tests_brief(root, _reviewer_step()) == {}


def test_without_the_key_the_briefs_carry_no_tests_key(tmp_path: Path) -> None:
    from fr.commands.run_cmd import _tests_brief

    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\n")
    assert _tests_brief(root, _deliver_step()) == {}
    assert _tests_brief(root, _executor_step()) == {}


def _member_brief(tmp_path: Path, ci_yaml: str | None) -> dict:
    repo = _repo(tmp_path)
    if ci_yaml is not None:
        (repo / ".fr").mkdir(exist_ok=True)
        (repo / ".fr" / "ci.yaml").write_text(ci_yaml)
        _git(repo, "add", ".fr/ci.yaml")
        _git(repo, "commit", "-q", "-m", "ci: declare tests evidence")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    result = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert result.exit_code == 0, result.output
    return _brief_of(result.output)


def test_the_phase_executor_brief_carries_the_key_when_declared(tmp_path: Path) -> None:
    brief = _member_brief(tmp_path, "gate_checks: [ci-ok]\ntests: ci\n")
    assert brief["step"] == "code"
    assert brief["tests"]["mode"] == "ci"
    assert brief["tests"]["fast_tier"].startswith("uv run pytest --fr-scope")
    assert brief["tests"]["fast_tier"].endswith(" -n 2 -q --no-cov")


def test_the_phase_executor_brief_has_no_key_when_undeclared(tmp_path: Path) -> None:
    assert "tests" not in _member_brief(tmp_path, None)
