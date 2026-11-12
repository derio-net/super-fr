"""The bootstrap state — `git init; git remote add origin <url>`, never fetched or pushed —
reads built-in defaults (spec R2 step 2b), so a new repo's first fr commands work (p2-r2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import fragments_text, make_repo, row
from tests.unit.settings_repo import git

runner = CliRunner()


def _bootstrap(root: Path) -> Path:
    git(root, "init", "-q", "-b", "main")
    git(root, "remote", "add", "origin", "https://github.com/derio-net/own.git")
    return root


def test_acceptance_init_works_on_a_never_fetched_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "own"
    root.mkdir()
    _bootstrap(root)
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    result = runner.invoke(app, ["acceptance", "init"])
    assert result.exit_code == 0, (result.output, result.exception)
    assert (root / "docs" / "acceptance" / "features").is_dir()


def test_acceptance_add_works_on_a_never_fetched_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _bootstrap(make_repo(tmp_path, row(), git=False))
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    result = runner.invoke(
        app,
        [
            "acceptance",
            "add",
            "--id",
            "boot-row",
            "--capability",
            "Cap",
            "--acceptance",
            "Operator can bootstrap",
            "--origin",
            "own:docs/superpowers/specs/s.md",
            "--level",
            "unit=own:tests/test_a.py",
            "--status",
            "unwired",
            "--notes",
            "n",
        ],
    )
    assert result.exit_code == 0, (result.output, result.exception)
    assert "boot-row" in fragments_text(root)
