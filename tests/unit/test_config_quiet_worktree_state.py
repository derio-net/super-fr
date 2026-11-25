"""A quiet migration refuses BEFORE any product file leaves when the `fr-config` worktree
is dirty or has diverged from `origin/fr-config` (review finding p4-r7): readers read that
worktree, so a move into it that cannot be fast-forwarded would leave them reading
something else, silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.config import migrate as m
from fr.settings import SettingsError

from tests.unit.settings_repo import git
from tests.unit.test_migration_config_kinds import _put, _quiet

MODELS = "docs/superpowers/models.yaml"
TEXT = "opencode:\n  hard: m\n"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))


def _with_models_on_fr_config(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = _quiet(tmp_path)
    src = _put(root, MODELS, TEXT)
    assert m.ensure_space(root)  # carries models.yaml: the tip holds the same bytes
    return root, src, m.space_root(root)


def test_a_dirty_fr_config_worktree_refuses_before_the_unlink(tmp_path: Path) -> None:
    root, src, worktree = _with_models_on_fr_config(tmp_path)
    (worktree / ".fr/settings.yaml").write_text("placement: quiet\n# local edit\n")
    with pytest.raises(SettingsError, match="uncommitted") as refused:
        m.move_across(root, src, "models.yaml")
    assert str(worktree) in str(refused.value) and src.read_text() == TEXT


def test_a_diverged_fr_config_worktree_refuses_before_the_unlink(tmp_path: Path) -> None:
    root, src, worktree = _with_models_on_fr_config(tmp_path)
    (worktree / ".fr/extra.yaml").write_text("a: 1\n")
    git(worktree, "add", "-A")
    git(worktree, "commit", "-qm", "local only")
    with pytest.raises(SettingsError, match="diverged|not on origin") as refused:
        m.move_across(root, src, "models.yaml")
    assert str(worktree) in str(refused.value) and src.read_text() == TEXT


def test_a_clean_current_worktree_moves(tmp_path: Path) -> None:
    root, src, worktree = _with_models_on_fr_config(tmp_path)
    m.move_across(root, src, "models.yaml")
    assert not src.exists() and (worktree / ".fr/models.yaml").read_text() == TEXT
