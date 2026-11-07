"""Coherence rules (spec R5) and `fr run start` refusing them."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.cli import app
from fr.settings import SettingsError
from fr.settings.check import RULES, Problem, check_settings
from typer.testing import CliRunner

from tests.unit.settings_repo import land_on_main as _land_on_main
from tests.unit.settings_repo import make_repo


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


def _ops_plan(root: Path, name: str = "p") -> None:
    plan = root / "docs" / "superpowers" / "plans" / name
    plan.mkdir(parents=True, exist_ok=True)
    (plan / "ops.yaml").write_text(
        "schema_version: 1\nops:\n  - id: k\n    summary: s\n    phase: pre-merge\n"
        "    check: test -e key\n"
    )


def test_rules_are_data() -> None:
    assert all(len(rule) == 3 for rule in RULES)
    assert len({rule[0] for rule in RULES}) == len(RULES)


def test_a_coherent_file_has_no_problems(repo: Path) -> None:
    _land_on_main(repo, "artifacts:\n  gates: off\n")
    assert check_settings(repo) == []


def test_gates_off_with_a_live_plan_carrying_ops_names_the_plan(repo: Path) -> None:
    _ops_plan(repo, "deploy-plan")
    _land_on_main(repo, "artifacts:\n  gates: off\n")
    problems = check_settings(repo)
    assert [p.id for p in problems] == ["gates-off-with-ops"]
    assert "deploy-plan" in problems[0].message
    assert isinstance(problems[0], Problem)


def test_gates_on_with_ops_is_fine(repo: Path) -> None:
    _ops_plan(repo)
    assert check_settings(repo) == []


def test_push_ask_with_a_driven_triage_scope_is_refused(repo: Path) -> None:
    (repo / ".fr").mkdir(exist_ok=True)
    (repo / ".fr" / "triage.yaml").write_text("post_merge: [make, release]\n")
    _land_on_main(repo, "git:\n  push: ask\n")
    assert [p.id for p in check_settings(repo)] == ["push-ask-with-driven-triage"]


def test_push_ask_without_triage_config_is_fine(repo: Path) -> None:
    _land_on_main(repo, "git:\n  push: ask\n")
    assert check_settings(repo) == []


def test_report_comment_needs_comments(repo: Path) -> None:
    _land_on_main(repo, "forge:\n  comments: off\n  report_comment: on\n")
    assert [p.id for p in check_settings(repo)] == ["report-comment-needs-comments"]


def test_a_bad_file_raises_rather_than_listing(repo: Path) -> None:
    _land_on_main(repo, "nope: 1\n")
    with pytest.raises(SettingsError):
        check_settings(repo)


def test_run_start_refuses_an_incoherent_file(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _land_on_main(repo, "forge:\n  comments: off\n  report_comment: on\n")
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))
    result = CliRunner().invoke(app, ["run", "start", "fr-goal", "--branch", "feat/x"])
    assert result.exit_code == 2
    assert "report_comment" in result.output
    assert not list((repo / "docs").glob("superpowers/runs/*.yaml"))


def test_run_start_refuses_an_invalid_file(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _land_on_main(repo, "nope: 1\n")
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))
    result = CliRunner().invoke(app, ["run", "start", "fr-goal", "--branch", "feat/x"])
    assert result.exit_code == 2
    assert "nope" in result.output
