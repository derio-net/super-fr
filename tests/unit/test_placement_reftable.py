"""A reftable clone reads its placement through git (review pr1431-r3).

The quiet switch, HEAD and the branch names are read from the filesystem for speed, as
loose refs and `packed-refs`. A reftable clone has neither, so that fast path read every
quiet repo as `repo`. Under reftable fr asks git instead. Skipped only when the installed
git cannot make a reftable repository (a capability probe, never a version string).

Every repo is a local sandbox with a bare origin; nothing reaches a network.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.artifacts.paths import outside_repo
from fr.placement import quiet

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_drift import _switch_to
from tests.unit.test_placement_quiet import QUIET


def _reftable_supported(tmp_path: Path) -> bool:
    probe = subprocess.run(
        ["git", "init", "-q", "--ref-format=reftable", str(tmp_path / "probe")],
        capture_output=True,
        check=False,
    )
    return probe.returncode == 0


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    quiet._CACHE.clear()
    yield home
    quiet._CACHE.clear()


def _reftable_clone(tmp_path: Path) -> Path:
    if not _reftable_supported(tmp_path):
        pytest.skip("this git cannot create a reftable repository")
    root = make_repo(tmp_path)
    _switch_to(root, QUIET)
    clone = tmp_path / "rt"
    url = git(root, "remote", "get-url", "origin").strip()
    git(tmp_path, "clone", "-q", "--ref-format=reftable", url, str(clone))
    assert (clone / ".git" / "reftable").is_dir()
    return clone


def test_a_reftable_clone_of_a_quiet_repo_is_quiet(tmp_path: Path) -> None:
    clone = _reftable_clone(tmp_path)
    assert quiet.read_switch(clone) is not None
    assert outside_repo(clone) == "quiet"


def test_head_and_branch_names_are_read_through_git_under_reftable(tmp_path: Path) -> None:
    clone = _reftable_clone(tmp_path)
    git(clone, "switch", "-q", "-c", "feat/x")
    assert quiet.head_branch(clone) == "feat/x"
    common = clone / ".git"
    assert {"main", "feat/x"} <= quiet._branch_names(common)
    git(clone, "branch", "-q", "feat__x")
    with pytest.raises(Exception, match="share the feature id"):
        quiet.check_feature_id(clone, "feat/x")


def test_a_files_repo_keeps_the_filesystem_fast_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path)
    _switch_to(root, QUIET)
    quiet._CACHE.clear()

    def no_git(*_a: object, **_k: object) -> None:
        raise AssertionError("a files-backend ref read must not spawn git")

    monkeypatch.setattr(quiet, "_git_ref_read", no_git)
    assert quiet._ref_sha(root / ".git", "refs/remotes/origin/fr") is not None
    assert quiet.head_branch(root) == "main"
