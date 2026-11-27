"""`fr repos sync` under quiet never writes the `fr-config` worktree directly: the
plan-config goes to the configuration branch as a pull request (`fr.config.change`,
honouring `git.pr`), or the command refuses naming how to create the space (review
finding p4-r9).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fr.cli import app
from fr.config import change
from fr.config import migrate as m
from typer.testing import CliRunner

from tests.unit.settings_repo import git
from tests.unit.test_migration_config_kinds import _quiet

runner = CliRunner()


@pytest.fixture
def quiet_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    root = _quiet(tmp_path)
    repos = tmp_path / "repos"
    repos.mkdir()
    named = repos / "super-fr"
    shutil.move(str(root), str(named))
    monkeypatch.setenv("FR_REPOS_DIR", str(repos))
    monkeypatch.setenv("FR_REPOS_MANIFEST", str(tmp_path / "repos.yaml"))
    return named


def test_without_fr_config_it_refuses_naming_the_command(quiet_repo: Path) -> None:
    res = runner.invoke(app, ["repos", "sync", "derio-net/super-fr", "--yes", "--no-save"])
    assert res.exit_code == 0, res.output
    assert "REFUSED" in res.output and "fr migrate artifacts --yes" in res.output
    assert not (m.space_root(quiet_repo) / ".fr/plan-config.yaml").exists()


def test_with_fr_config_it_proposes_a_pull_request(
    quiet_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[tuple[str, str]] = []

    def fake(remote: str, head: str, base: str, title: str, body: str) -> str:
        opened.append((head, base))
        return "https://example.com/pr/3"

    monkeypatch.setattr(change, "open_pr", fake)
    assert m.ensure_space(quiet_repo)
    worktree = m.space_root(quiet_repo)
    res = runner.invoke(app, ["repos", "sync", "derio-net/super-fr", "--yes", "--no-save"])
    assert res.exit_code == 0, res.output
    assert "PROPOSED" in res.output and "https://example.com/pr/3" in res.output
    assert not (worktree / ".fr/plan-config.yaml").exists()  # nothing written directly
    ((head, base),) = opened
    assert base == "fr-config" and head.startswith("fr-config-change/plan-config-")
    assert "plan:" in git(tmp_path / "origin.git", "show", f"{head}:.fr/plan-config.yaml")
