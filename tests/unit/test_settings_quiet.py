"""`fr settings init --quiet`, `fr settings check` under quiet, and runner dispatch refused
under quiet (spec 2026-11-04 R3, R5, R22, R23 "known limitation", "not available here";
plan phase 3, task 5). Origins are LOCAL bare repos.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.artifacts.paths import KIND_DIRS, space_for
from fr.cli import app
from fr.settings import load_settings
from fr.settings.check import check_settings
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import push_fr_branch


def _fr(repo: Path, *argv: str):  # type: ignore[no-untyped-def]
    return CliRunner().invoke(app, list(argv), env={**os.environ, "VK_REPO_ROOT": str(repo)})


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_repo(tmp_path)
    monkeypatch.chdir(root)
    return root


def test_init_quiet_creates_and_pushes_the_orphan_fr_branch(repo: Path, tmp_path: Path) -> None:
    head_before = git(repo, "rev-parse", "HEAD").strip()
    result = _fr(repo, "settings", "init", "--quiet")
    assert result.exit_code == 0, result.output
    origin = tmp_path / "origin.git"
    sha = git(origin, "rev-parse", "refs/heads/fr").strip()
    assert git(origin, "rev-list", "--parents", "-n1", sha).split() == [sha]  # orphan
    assert git(origin, "ls-tree", "--name-only", sha).split() == ["settings.yaml"]
    text = git(origin, "show", f"{sha}:settings.yaml")
    assert "\nplacement: quiet\n" in text
    assert "#  labels: on" in text or "#forge:" in text  # every other key commented
    flat = " ".join(text.split())
    assert "predates" in flat  # the known limitation
    assert "branch protection" in flat or "protect" in flat
    # nothing in the product checkout moved
    assert git(repo, "rev-parse", "HEAD").strip() == head_before
    assert not git(repo, "status", "--porcelain").strip()
    assert load_settings(repo).settings.placement == "quiet"
    assert space_for(repo).placement == "quiet"


def test_init_quiet_states_the_known_limitation_on_stdout(repo: Path) -> None:
    result = _fr(repo, "settings", "init", "--quiet")
    assert result.exit_code == 0, result.output
    assert "predates" in " ".join(result.output.split())


def test_init_quiet_refuses_when_origin_already_has_fr(repo: Path, tmp_path: Path) -> None:
    push_fr_branch(repo, None)
    before = git(tmp_path / "origin.git", "rev-parse", "refs/heads/fr").strip()
    result = _fr(repo, "settings", "init", "--quiet")
    assert result.exit_code == 2
    assert "already" in result.output
    assert git(tmp_path / "origin.git", "rev-parse", "refs/heads/fr").strip() == before
    assert _fr(repo, "settings", "init", "--quiet", "--force").exit_code == 2


def test_init_quiet_refuses_without_origin(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    solo = tmp_path / "solo"
    git(tmp_path, "init", "-q", "-b", "main", str(solo))
    git(
        solo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@e.invalid",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "s",
    )
    monkeypatch.chdir(solo)
    result = _fr(solo, "settings", "init", "--quiet")
    assert result.exit_code == 2
    assert "origin" in result.output


def test_apply_to_a_runner_is_refused_under_quiet(repo: Path) -> None:
    push_fr_branch(repo, "schema: 1\nplacement: quiet\n")
    git(repo, "checkout", "-q", "-b", "feat/q")
    result = _fr(repo, "apply", "--all", "--to", "vk")
    assert result.exit_code == 2
    assert "quiet" in result.output


def test_check_accepts_the_quiet_file(repo: Path) -> None:
    push_fr_branch(repo, "schema: 1\nplacement: quiet\n")
    git(repo, "checkout", "-q", "-b", "feat/q")
    assert check_settings(repo) == []
    assert _fr(repo, "settings", "check").exit_code == 0


def test_check_applies_r22_under_quiet(repo: Path) -> None:
    push_fr_branch(repo, "schema: 1\nplacement: quiet\nforge:\n  report_comment: on\n")
    git(repo, "checkout", "-q", "-b", "feat/q")
    assert [p.id for p in check_settings(repo)] == ["report-comment-needs-repo-placement"]


def test_check_applies_r5_across_every_quiet_feature(repo: Path) -> None:
    push_fr_branch(repo, "schema: 1\nplacement: quiet\nartifacts:\n  gates: off\n")
    git(repo, "checkout", "-q", "-b", "feat/q")
    fr_root = space_for(repo).root
    plan = fr_root / "features" / "feat__other" / KIND_DIRS["plan"] / "deploy"
    plan.mkdir(parents=True)
    (plan / "ops.yaml").write_text(
        "schema_version: 1\nops:\n  - id: k\n    summary: s\n    phase: pre-merge\n"
        "    check: test -e key\n"
    )
    problems = check_settings(repo)
    assert [p.id for p in problems] == ["gates-off-with-ops"]
    assert "deploy" in problems[0].message
