"""No phase-4 move, write or delete of an old-path or configuration-space file follows a
symlink, at the file or at any directory between it and the checkout (security review of
p4-r9): a `docs/superpowers` that links outside the checkout is refused, and nothing
outside is touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.artifacts import run_migrations
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_migration_config_kinds import _feature


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))


def _linked_docs(root: Path, outside: Path, name: str, text: str) -> Path:
    """`<root>/docs/superpowers` -> *outside*, which holds *name*."""
    (outside).mkdir(parents=True)
    (outside / name).write_text(text)
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs/superpowers").symlink_to(outside, target_is_directory=True)
    return outside / name


def test_repos_sync_refuses_a_symlinked_old_path_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repos = tmp_path / "repos"
    root = repos / "super-fr"
    (root / ".git").mkdir(parents=True)
    victim = _linked_docs(root, tmp_path / "outside", "plan-config.yaml", "keep: me\n")
    monkeypatch.setenv("FR_REPOS_DIR", str(repos))
    monkeypatch.setenv("FR_REPOS_MANIFEST", str(tmp_path / "repos.yaml"))
    res = CliRunner().invoke(
        app, ["repos", "sync", "derio-net/super-fr", "--yes", "--force", "--no-save"]
    )
    assert "symlink" in res.output, res.output
    assert victim.read_text() == "keep: me\n"
    assert not (root / ".fr/plan-config.yaml").exists()


def test_a_relocation_under_repo_refuses_a_symlinked_old_path_parent(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _feature(root)
    victim = _linked_docs(root, tmp_path / "outside", "models.yaml", "opencode:\n  hard: m\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "a linked docs dir")
    report = run_migrations(root, dry_run=False)
    assert any("symlink" in f.error for f in report.failed if f.kind == "models-config")
    assert victim.read_text() == "opencode:\n  hard: m\n"
    assert not (root / ".fr/models.yaml").exists()


def test_a_relocation_refuses_a_symlinked_destination_parent(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _feature(root)
    (root / "docs/superpowers").mkdir(parents=True)
    (root / "docs/superpowers/models.yaml").write_text("opencode:\n  hard: m\n")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (root / ".fr").symlink_to(outside, target_is_directory=True)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "a linked .fr")
    report = run_migrations(root, dry_run=False)
    assert any("symlink" in f.error for f in report.failed if f.kind == "models-config")
    assert not (outside / "models.yaml").exists()
    assert (root / "docs/superpowers/models.yaml").exists()
