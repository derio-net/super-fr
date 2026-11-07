"""A clone of a bare origin, shared by the settings tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env={**os.environ, **_ENV},
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def make_repo(tmp_path: Path) -> Path:
    """A clone of a bare origin with one commit on main, HEAD on main."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "work"
    git(tmp_path, "init", "-q", "-b", "main", str(work))
    git(work, "remote", "add", "origin", str(origin))
    (work / "README.md").write_text("x\n")
    git(work, "add", "-A")
    git(work, "commit", "-qm", "seed")
    git(work, "push", "-q", "-u", "origin", "main")
    git(work, "remote", "set-head", "origin", "main")
    return work


def land_on_main(repo: Path, text: str) -> None:
    (repo / ".fr").mkdir(exist_ok=True)
    (repo / ".fr" / "settings.yaml").write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "settings")
    git(repo, "push", "-q", "origin", "main")


def seed_origin_default(root: Path, branch: str = "main") -> None:
    """Give a repo whose `origin` is unreachable a resolvable default ref (the loader refuses
    a remote whose default it cannot name). Commits an empty seed when HEAD has none."""
    try:
        git(root, "rev-parse", "-q", "--verify", "HEAD")
    except subprocess.CalledProcessError:
        git(root, "commit", "-q", "--allow-empty", "-m", "seed")
    git(root, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")
    git(root, "symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/origin/{branch}")
