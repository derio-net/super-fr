"""`up --branch <B>` reuses `origin/<B>` end to end, real git (#438, spec §3.E).

A bare repo is origin; `feat/x` there carries one commit beyond `main`. The
clone under test has never checked `feat/x` out — the fresh-clone / resume-a-PR
state #438 misread as a cold start. No network: origin is a local path.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.types import IsolationError

_ID = ["-c", "user.email=t@t", "-c", "user.name=t"]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *_ID, *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _origin_with_feature(tmp_path: Path) -> tuple[Path, str]:
    """Bare origin: main (one commit) and feat/x (main + one). Returns (origin, tip)."""
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True)
    (seed / "README.md").write_text("x\n")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-qm", "init")
    _git(seed, "checkout", "-q", "-b", "feat/x")
    (seed / "feature.txt").write_text("only on feat/x\n")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-qm", "feature")
    tip = _git(seed, "rev-parse", "HEAD")
    _git(seed, "checkout", "-q", "main")  # origin's HEAD → main, as on a real forge
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(origin)], check=True)
    return origin, tip


def _clone(tmp_path: Path, origin: Path, *flags: str) -> Path:
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", *flags, str(origin), str(clone)], check=True)
    return clone


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HOME and every git config source under tmp_path — no operator config
    (sshCommand, url rewrites, init.defaultBranch) reaches these repos."""
    cfg = tmp_path / "gitcfg"
    cfg.mkdir()
    (cfg / "global").write_text("")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg / "global"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg / "xdg"))
    for var in ("GIT_SSH_COMMAND", "GIT_SSH"):
        monkeypatch.delenv(var, raising=False)


def test_fresh_clone_worktree_carries_the_remote_branch(tmp_path: Path) -> None:
    origin, tip = _origin_with_feature(tmp_path)
    clone = _clone(tmp_path, origin)
    assert _git(clone, "branch", "--list", "feat/x") == ""  # never checked out

    st = HostWorktreeTarget(clone).up(None, branch="feat/x")

    assert _git(st.worktree, "rev-parse", "HEAD") == tip
    assert (st.worktree / "feature.txt").is_file()


def test_single_branch_clone_still_finds_the_remote_branch(tmp_path: Path) -> None:
    origin, tip = _origin_with_feature(tmp_path)
    clone = _clone(tmp_path, origin, "--single-branch", "--branch", "main")
    assert "feat/x" not in _git(clone, "branch", "-a")

    st = HostWorktreeTarget(clone).up(None, branch="feat/x")

    assert _git(st.worktree, "rev-parse", "HEAD") == tip
    assert _git(clone, "config", "branch.feat/x.merge") == "refs/heads/feat/x"


def test_base_with_an_existing_remote_branch_is_refused(tmp_path: Path) -> None:
    origin, _tip = _origin_with_feature(tmp_path)
    clone = _clone(tmp_path, origin)

    with pytest.raises(IsolationError, match="origin/feat/x exists"):
        HostWorktreeTarget(clone).up(None, branch="feat/x", base="origin/main")

    assert _git(clone, "branch", "--list", "feat/x") == ""


def test_local_branch_behind_origin_is_used_with_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    origin, tip = _origin_with_feature(tmp_path)
    clone = _clone(tmp_path, origin)
    main = _git(clone, "rev-parse", "main")
    _git(clone, "branch", "--no-track", "feat/x", main)  # local is one behind

    st = HostWorktreeTarget(clone).up(None, branch="feat/x")

    assert _git(st.worktree, "rev-parse", "HEAD") == main  # used as-is, not rebased
    err = capsys.readouterr().err
    assert "WARNING: local feat/x" in err
    assert f"behind origin/feat/x ({tip[:12]}" in err
