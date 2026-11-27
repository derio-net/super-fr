"""Whether a checkout is a configuration checkout is decided by structure, never by its
directory's name (review finding p4-r5): a product repo cloned as `ci-config` keeps its
profiles crash window finished in place.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fr.artifacts import run_migrations

from tests.unit.settings_repo import make_repo
from tests.unit.test_migration_config_kinds import PROFILES_V2, _feature, _put, _quiet


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))


def test_repo_named_config_crash_window(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    named = tmp_path / "ci-config"
    shutil.move(str(root), str(named))
    _feature(named)
    _put(named, ".fr/profiles.yaml", PROFILES_V2)  # the crash window under repo
    report = run_migrations(named, dry_run=False)
    assert report.ok, report.failed
    assert "schema_version: 3" in (named / ".fr/profiles.yaml").read_text()


def test_the_quiet_configuration_worktree_is_one(tmp_path: Path) -> None:
    from fr.artifacts.config_migration import _config_checkout
    from fr.artifacts.runner import MIGRATING_ROOT
    from fr.config.migrate import ensure_space, space_root

    root = _quiet(tmp_path)
    assert ensure_space(root)
    token = MIGRATING_ROOT.set(root)
    try:
        assert _config_checkout(space_root(root))
        assert not _config_checkout(root)
    finally:
        MIGRATING_ROOT.reset(token)
