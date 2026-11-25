"""R13's old-path fallback under quiet and stealth is decided by the configuration
branch's fetched TIP, never by the worktree (review finding p4-r2, plan decision
p4-legacy-by-tip; spec 2026-11-19-event-driven-a-la-carte S1 R4, R13).

- The configuration branch exists: the product's old path is ignored (one notice names it),
  so a feature branch cannot shadow the configuration space by adding an old-path file.
- No configuration branch yet: the old path is read only as the product's default branch
  has it COMMITTED (a feature-branch edit is ignored), and executable or trust content
  from it never runs unguarded.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.config import protection, space

from tests.unit.settings_repo import git
from tests.unit.test_migration_config_kinds import _put, _quiet

MODELS = "docs/superpowers/models.yaml"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    space._OLD_NOTICED.clear()
    protection.forget()
    return home


def _with_config(tmp_path: Path) -> Path:
    from fr.config.migrate import ensure_space

    root = _quiet(tmp_path)
    assert ensure_space(root)  # fr-config exists, holding settings only
    return root


def test_quiet_old_path_shadow(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """fr-config exists without `.fr/workflows`; a feature branch adds an old-path workflow:
    it is ignored, and `fr-goal` resolves to the shipped shape."""
    from fr.workflow.resolve import resolve_workflow

    root = _with_config(tmp_path)
    _put(root, "docs/superpowers/workflows/fr-goal.yaml", "x: 1\n")
    found = space.located(root, "workflow")
    assert found == space.config_space(root).dir / "workflows"
    assert "docs/superpowers/workflows" in capsys.readouterr().err
    manifest = resolve_workflow("fr-goal", root)
    assert manifest.workflow == "fr-goal"


def test_with_a_configuration_branch_an_old_file_is_ignored_with_a_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _with_config(tmp_path)
    _put(root, MODELS, "opencode:\n  hard: shadow\n")
    git(root, "push", "-q", "origin", "HEAD:main")  # even committed on the default branch
    assert space.located(root, "models") == space.config_space(root).file("models.yaml")
    err = capsys.readouterr().err
    assert MODELS in err and "ignoring" in err


def test_without_a_configuration_branch_only_the_default_branchs_bytes_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _quiet(tmp_path)
    _put(root, MODELS, "opencode:\n  hard: feature\n")  # on the feature branch only
    assert space.located(root, "models") != root / MODELS
    assert "ignoring" in capsys.readouterr().err

    git(root, "push", "-q", "origin", "HEAD:main")
    git(root, "fetch", "-q", "origin")
    space._OLD_NOTICED.clear()
    assert space.located(root, "models") == root / MODELS
    (root / MODELS).write_text("opencode:\n  hard: edited\n")  # an uncommitted edit
    space._OLD_NOTICED.clear()
    assert space.located(root, "models") != root / MODELS


def test_an_old_path_executable_under_quiet_never_runs_from_the_worktree(
    tmp_path: Path,
) -> None:
    root = _quiet(tmp_path)
    path = _put(root, "docs/superpowers/workflows/mine.yaml", "workflow: mine\n")
    with pytest.raises(protection.ProtectionError, match="old path"):
        space.read_checked_bytes(root, path, "run workflow shape 'mine'")
