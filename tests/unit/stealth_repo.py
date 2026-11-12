"""A target clone and a separate tracking repo, both LOCAL bare repos (stealth tests).

Nothing here touches the network or a forge: the tracking repo is a bare repo on disk,
and every visibility is answered by the injected port (a local path is private).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.placement import stealth

from tests.unit.settings_repo import git, make_repo


def make_tracking(tmp_path: Path, branch: str = "main") -> Path:
    """A bare tracking repo with one seed commit on *branch*."""
    bare = tmp_path / "track.git"
    git(tmp_path, "init", "-q", "--bare", "-b", branch, str(bare))
    seed = tmp_path / "track-seed"
    git(tmp_path, "init", "-q", "-b", branch, str(seed))
    git(seed, "config", "user.name", "t")
    git(seed, "config", "user.email", "t@example.invalid")
    (seed / "README.md").write_text("tracking\n")
    git(seed, "add", "-A")
    git(seed, "commit", "-qm", "seed")
    git(seed, "remote", "add", "origin", str(bare))
    git(seed, "push", "-q", "origin", branch)
    return bare


def stealth_pair(tmp_path: Path) -> tuple[Path, Path]:
    """(target clone, tracking bare repo)."""
    return make_repo(tmp_path), make_tracking(tmp_path)


def tracked_files(bare: Path, branch: str = "main") -> list[str]:
    return git(bare, "ls-tree", "-r", "--name-only", branch).splitlines()


@pytest.fixture(autouse=True)
def stealth_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    stealth.reset_caches()
    yield home
    stealth.reset_caches()
