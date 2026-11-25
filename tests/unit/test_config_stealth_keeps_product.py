"""Under stealth the migration never commits a deletion on the target's branch: the file
moves to the tracking repo's configuration branch, the product file stays (R4 says it is
ignored), fr prints once the exact `git rm` the operator may run, and the kept file no
longer reads as stale (review finding p4-r6, decision p4-stealth-keeps-product-file, R10
as amended). Also the stealth profiles walk of finding p4-r11: transform, structure
check, and the 2 -> 3 crash window on the configuration clone.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.artifacts import ARTIFACT_KINDS, is_stale, run_migrations
from fr.artifacts.commit import commit_migration

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_migration_config_kinds import FILES, _put

pytestmark = pytest.mark.own_artifacts

V1 = "profiles:\n  dev:\n    purpose: dev\n    secrets: []\nbackend: github\n"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    from fr.placement import stealth

    stealth.reset_caches()
    yield
    stealth.reset_caches()


def _stealth(tmp_path: Path, files: dict[str, str]) -> tuple[Path, Path]:
    from fr.isolation.hostworktree import HostWorktreeTarget
    from fr.placement import stealth

    from tests.unit.stealth_repo import make_tracking

    target = make_repo(tmp_path)
    track = make_tracking(tmp_path)
    clone = tmp_path / "push-clone"
    git(tmp_path, "clone", "-q", str(track), str(clone))
    git(clone, "config", "user.name", "t")
    git(clone, "config", "user.email", "t@example.invalid")
    (clone / "local--origin").mkdir()
    (clone / "local--origin/settings.yaml").write_text("placement: stealth\n")
    git(clone, "add", "-A")
    git(clone, "commit", "-qm", "target settings")
    git(clone, "push", "-q", "origin", "main")
    for rel, text in files.items():
        _put(target, rel, text)
    git(target, "push", "-q", "origin", "main")
    ref = stealth.parse_ref(f"{track}@main")
    state = HostWorktreeTarget(target).up(profile=None, branch="feat/s", stealth=ref)
    return Path(state.worktree), track


def test_under_stealth_the_product_file_stays_and_the_git_rm_is_printed_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new, text = FILES["models-config"]
    work, track = _stealth(tmp_path, {old: text})
    head = git(work, "rev-parse", "HEAD")
    report = run_migrations(work, dry_run=False)
    assert report.ok, report.failed
    assert git(track, "show", f"main-config:local--origin/{new}") == text
    assert (work / old).read_text() == text  # never deleted on the target's branch
    err = capsys.readouterr().err
    assert err.count(f"git -C {work} rm -- {old}") == 1
    outcome = commit_migration(work, report, fr_version="9.9.9")
    assert git(work, "rev-parse", "HEAD") == head or "D\t" not in git(
        work, "show", "--name-status", "--format=", "HEAD"
    )
    assert not outcome.committed or old not in git(work, "show", "--name-only", "--format=", "HEAD")
    assert not is_stale(work)
    again = run_migrations(work, dry_run=False)
    assert again.ok and not again.applied


def test_stealth_profiles_walk_v1_to_v3_on_the_tracking_repo(tmp_path: Path) -> None:
    old = ".devcontainer/fr-profiles.yaml"
    work, track = _stealth(tmp_path, {old: V1})
    report = run_migrations(work, dry_run=False)
    assert report.ok, report.failed
    pushed = git(track, "show", "main-config:local--origin/.fr/profiles.yaml")
    data = yaml.safe_load(pushed)
    assert data["schema_version"] == 3 and data["forge"]["type"] == "github"
    from fr.config.migrate import space_root

    moved = space_root(work) / ".fr/profiles.yaml"
    assert ARTIFACT_KINDS["profiles"].validate(moved) == []
    assert (work / old).read_text() == V1  # fr's in-flight 1 -> 2 rewrite is undone
    assert git(work, "status", "--porcelain") == ""
    assert not is_stale(work)
    head = git(work, "rev-parse", "HEAD")
    commit_migration(work, report, fr_version="9.9.9")
    assert git(work, "rev-parse", "HEAD") == head  # nothing lands on the target's branch


def test_stealth_profiles_crash_window_on_the_configuration_clone_is_refused(
    tmp_path: Path,
) -> None:
    from fr.artifacts.config_migration import _config_checkout
    from fr.artifacts.runner import MIGRATING_ROOT
    from fr.config.migrate import ensure_space, space_root

    work, _track = _stealth(tmp_path, {})
    assert ensure_space(work)
    token = MIGRATING_ROOT.set(work)
    try:
        assert _config_checkout(space_root(work))
        assert not _config_checkout(work)
    finally:
        MIGRATING_ROOT.reset(token)
