"""A version-1 profiles file under quiet goes 1 -> 2 -> 3 as ONE relocation: the
configuration branch is created with the final version-3 bytes, and fr's own in-flight
1 -> 2 rewrite is never refused as "uncommitted changes" (review finding p4-r4).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.artifacts import ARTIFACT_KINDS, run_migrations
from fr.artifacts.commit import commit_migration

from tests.unit.settings_repo import git
from tests.unit.test_migration_config_kinds import _origin, _put, _quiet

V1 = "profiles:\n  dev:\n    purpose: dev\n    secrets: []\nbackend: github\n"
OLD = ".devcontainer/fr-profiles.yaml"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))


def test_quiet_v1_profiles(tmp_path: Path) -> None:
    root = _quiet(tmp_path)
    _put(root, OLD, V1)
    report = run_migrations(root, dry_run=False)
    assert report.ok, report.failed
    assert ("profiles", 1, 2) in [(a.kind, a.from_version, a.to_version) for a in report.applied]
    pushed = git(_origin(tmp_path), "show", "fr-config:.fr/profiles.yaml")
    data = yaml.safe_load(pushed)
    assert data["schema_version"] == 3 and data["forge"]["type"] == "github"
    assert "backend" not in data
    assert not (root / OLD).exists()
    outcome = commit_migration(root, report, fr_version="9.9.9")
    assert outcome.committed, outcome.reason
    assert git(root, "show", "--name-status", "--format=", "HEAD").split() == ["D", OLD]
    again = run_migrations(root, dry_run=False)
    assert again.ok and not again.applied, (again.applied, again.failed)


def test_an_operator_edit_on_top_of_a_v1_file_is_still_refused(tmp_path: Path) -> None:
    root = _quiet(tmp_path)
    _put(root, OLD, V1)
    (root / OLD).write_text(V1.replace("purpose: dev", "purpose: edited"))
    report = run_migrations(root, dry_run=False)
    assert any("uncommitted" in f.error for f in report.failed if f.kind == "profiles")
    assert "edited" in (root / OLD).read_text()


def test_the_profiles_validator_accepts_the_moved_file(tmp_path: Path) -> None:
    root = _quiet(tmp_path)
    _put(root, OLD, V1)
    assert run_migrations(root, dry_run=False).ok
    from fr.config.migrate import space_root

    moved = space_root(root) / ".fr/profiles.yaml"
    assert ARTIFACT_KINDS["profiles"].validate(moved) == []
