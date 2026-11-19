"""The declared `tests: ci` default (spec 2026-11-19-local-suite-cost R8, §3.F).

`.fr/ci.yaml` may declare `tests: ci` beside `gate_checks`, read at HEAD. When it
does, the `deliver` brief and each phase executor's brief carry
`tests: {mode: ci, fast_tier: ...}`; when it does not, they carry no `tests` key.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.run.ci_evidence import (
    CiEvidenceRefused,
    declared_fast_tier,
    declared_tests_mode,
    load_gate_checks,
)
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
FAST_TIER_DECL = 'fast_tier: "uv run pytest --fr-scope {base} -n 2 -q --no-cov"\n'


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


@pytest.mark.parametrize(
    "body",
    ["tests: ci\n", "gate_checks: []\ntests: ci\n", "gate_checks: ci-ok\ntests: ci\n"],
)
def test_tests_ci_without_valid_gate_checks_is_refused(tmp_path: Path, body: str) -> None:
    """p3-r6: `deliver` would refuse `tests: ci` without gate checks, so the
    declaration refuses up front, saying why."""
    root = _with_ci_yaml(tmp_path, body)
    with pytest.raises(CiEvidenceRefused, match="gate_checks") as e:
        declared_tests_mode(root)
    assert "tests: ci" in str(e.value)


def test_a_declared_fast_tier_is_read_with_its_base(tmp_path: Path) -> None:
    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\ntests: ci\n" + FAST_TIER_DECL)
    assert declared_fast_tier(root) == "uv run pytest --fr-scope {base} -n 2 -q --no-cov"


def test_no_fast_tier_declares_none(tmp_path: Path) -> None:
    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\ntests: ci\n")
    assert declared_fast_tier(root) is None
    assert declared_fast_tier(_with_ci_yaml(tmp_path / "b", None)) is None


@pytest.mark.parametrize(
    "value",
    ["3", "[a, b]", "''", '"run {other}"', '"run {base} {0}"', '"run {"', '"run {base!r}"'],
)
def test_a_fast_tier_that_is_not_a_command_with_only_base_is_refused(
    tmp_path: Path, value: str
) -> None:
    root = _with_ci_yaml(tmp_path, f"gate_checks: [ci-ok]\ntests: ci\nfast_tier: {value}\n")
    with pytest.raises(CiEvidenceRefused, match="fast_tier"):
        declared_fast_tier(root)


def test_a_fast_tier_without_tests_ci_is_refused(tmp_path: Path) -> None:
    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\n" + FAST_TIER_DECL)
    with pytest.raises(CiEvidenceRefused, match="tests: ci"):
        declared_fast_tier(root)


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

    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\ntests: ci\n" + FAST_TIER_DECL)
    want = {"tests": {"mode": "ci", "fast_tier": FAST_TIER}}
    assert _tests_brief(root, _deliver_step()) == want
    assert _tests_brief(root, _executor_step()) == want
    assert _tests_brief(root, _reviewer_step()) == {}


def test_without_a_declared_fast_tier_the_briefs_carry_the_mode_alone(tmp_path: Path) -> None:
    """p3-r1: fr ships no fast tier; the command is the repo's, so a repo that
    names none gets `tests: {mode: ci}` and runs its touched tests its own way."""
    from fr.commands.run_cmd import _tests_brief

    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\ntests: ci\n")
    assert _tests_brief(root, _deliver_step()) == {"tests": {"mode": "ci"}}
    assert _tests_brief(root, _executor_step()) == {"tests": {"mode": "ci"}}


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
    # A remote with a HEAD, so the fast tier's `{base}` resolves (l-errors-r1: a
    # base git cannot name now refuses the brief rather than going blank).
    origin = tmp_path / "member-origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")
    _git(repo, "remote", "set-head", "origin", "main")
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)
    result = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert result.exit_code == 0, result.output
    return _brief_of(result.output)


def test_the_phase_executor_brief_carries_the_key_when_declared(tmp_path: Path) -> None:
    brief = _member_brief(tmp_path, "gate_checks: [ci-ok]\ntests: ci\n" + FAST_TIER_DECL)
    assert brief["step"] == "code"
    assert brief["tests"]["mode"] == "ci"
    assert brief["tests"]["fast_tier"] == FAST_TIER


def test_the_phase_executor_brief_has_no_key_when_undeclared(tmp_path: Path) -> None:
    assert "tests" not in _member_brief(tmp_path, None)


def test_this_repo_declares_its_own_fast_tier() -> None:
    root = Path(__file__).resolve().parents[2]
    assert declared_tests_mode(root) == "ci"
    tier = declared_fast_tier(root)
    assert tier is not None and "--fr-scope {base}" in tier


# --- lens-review fixes (l-errors-r1, l-errors-r4) ------------------------------------


@pytest.mark.parametrize("break_it", ["two-remotes", "no-remote"])
def test_a_fast_tier_with_no_base_refuses_the_brief(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], break_it: str
) -> None:
    """l-errors-r1: a declared `fast_tier` whose `{base}` cannot be resolved refuses
    the brief, with git's reason and the fix, rather than emitting a blank base."""
    import typer
    from fr.commands.run_cmd import _tests_brief

    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\ntests: ci\n" + FAST_TIER_DECL)
    if break_it == "two-remotes":
        _git(root, "remote", "rename", "origin", "first")
        _git(root, "remote", "add", "upstream", str(tmp_path / "origin.git"))
    else:
        _git(root, "remote", "remove", "origin")
    with pytest.raises(typer.Exit) as exited:
        _tests_brief(root, _executor_step())
    assert exited.value.exit_code == 2
    err = " ".join(capsys.readouterr().err.split())
    assert "fast_tier" in err and "{base}" in err
    assert "git remote set-head" in err and "checkout.defaultRemote" in err
    if break_it == "two-remotes":
        assert "remote" in err and "no remote default ref" not in err


def test_a_mode_without_a_fast_tier_needs_no_base(tmp_path: Path) -> None:
    from fr.commands.run_cmd import _tests_brief

    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\ntests: ci\n")
    _git(root, "remote", "remove", "origin")
    assert _tests_brief(root, _executor_step()) == {"tests": {"mode": "ci"}}


def test_an_empty_ci_yaml_declares_nothing(tmp_path: Path) -> None:
    assert declared_tests_mode(_with_ci_yaml(tmp_path, "")) is None


@pytest.mark.parametrize("body", ["- tests\n- ci\n", "tests\n", "3\n"])
def test_a_ci_yaml_that_is_not_a_mapping_is_refused(tmp_path: Path, body: str) -> None:
    root = _with_ci_yaml(tmp_path, body)
    with pytest.raises(CiEvidenceRefused, match="mapping"):
        declared_tests_mode(root)
    with pytest.raises(CiEvidenceRefused, match="mapping"):
        declared_fast_tier(root)


def test_an_unborn_head_is_refused_not_read_as_absent(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    with pytest.raises(CiEvidenceRefused, match="could not read"):
        declared_tests_mode(tmp_path)


def test_a_corrupt_ci_yaml_object_is_refused_not_read_as_absent(tmp_path: Path) -> None:
    root = _with_ci_yaml(tmp_path, "gate_checks: [ci-ok]\ntests: ci\n")
    blob = _git(root, "rev-parse", "HEAD:.fr/ci.yaml").strip()
    (root / ".git" / "objects" / blob[:2] / blob[2:]).unlink()
    with pytest.raises(CiEvidenceRefused, match="could not read"):
        declared_tests_mode(root)
