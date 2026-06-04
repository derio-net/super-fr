"""vk isolation — Target protocol, state, profiles, and the local target.

All devcontainer/docker/gh calls go through the Runner seam; git calls hit
real throwaway repos (cheap, deterministic). Nothing here needs Docker.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vk.isolation.local import LocalWorktreeDevcontainerTarget
from vk.isolation.types import (
    IsolationError,
    IsolationState,
    load_state,
    resolve_profile,
    save_state,
    state_path,
)


def make_repo(
    tmp_path: Path, profiles: list[str] | None = None, default: str | None = None
) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "README.md").write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "init",
        ],
        check=True,
    )
    for name in profiles or []:
        d = repo / ".devcontainer" / name
        d.mkdir(parents=True)
        (d / "devcontainer.json").write_text('{"image": "x"}\n')
    if default:
        (repo / ".devcontainer" / "vk-profiles.yaml").write_text(
            f"default: {default}\nprofiles:\n  {default}:\n    purpose: test\n"
        )
    return repo


class FakeRunner:
    """Records non-git argv; delegates git to the real binary."""

    def __init__(self, fail_on: str | None = None, stdout: dict[str, str] | None = None):
        self.calls: list[list[str]] = []
        self.fail_on = fail_on
        self.stdout = stdout or {}

    def __call__(self, argv: list[str], cwd: Path | None = None, check: bool = False):
        if argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, check=check, capture_output=True, text=True)
        self.calls.append(list(argv))
        rc = 1 if (self.fail_on and self.fail_on in argv[0:2]) else 0
        out = self.stdout.get(argv[0], "")
        return subprocess.CompletedProcess(argv, rc, stdout=out, stderr="")

    def argv_for(self, binary: str) -> list[list[str]]:
        return [c for c in self.calls if c[0] == binary]


# ---------- state ----------


def test_state_roundtrip(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    st = IsolationState(
        repo_root=repo,
        branch="vk-iso/x",
        worktree=tmp_path / "wt",
        profile="dev",
        created_at="2026-06-04T00:00:00Z",
    )
    save_state(st)
    p = state_path(repo, "vk-iso/x")
    assert p.is_file() and str(p).startswith(str(repo / ".git"))
    assert load_state(repo, "vk-iso/x") == st


def test_state_path_sanitizes_branch_slash(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    assert "/" not in state_path(repo, "feat/x").name


# ---------- profiles ----------


def test_resolve_profile_default(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["dev", "admin"], default="dev")
    assert resolve_profile(repo, None) == "dev"
    assert resolve_profile(repo, "admin") == "admin"


def test_resolve_profile_no_devcontainer_points_at_vk_init(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    with pytest.raises(IsolationError, match="vk-init"):
        resolve_profile(repo, None)


def test_resolve_profile_unknown_lists_available(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    with pytest.raises(IsolationError, match="dev"):
        resolve_profile(repo, "nope")


def test_resolve_profile_no_default_single_profile(tmp_path: Path) -> None:
    """One profile dir, no vk-profiles.yaml → that profile is the default."""
    repo = make_repo(tmp_path, ["dev"])
    assert resolve_profile(repo, None) == "dev"


# ---------- target.up ----------


def test_up_creates_worktree_envfile_and_devcontainer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    st = target.up(profile=None, branch="vk-iso/test")

    assert st.worktree.is_dir() and (st.worktree / "README.md").is_file()
    assert str(st.worktree).startswith(str(tmp_path / "home"))  # ~/.cache default
    env = tmp_path / "home" / ".config" / "vk" / "secrets" / "repo" / "dev.env"
    assert env.is_file()  # created when missing

    (up,) = runner.argv_for("devcontainer")
    assert up[1] == "up"
    assert f"--workspace-folder={st.worktree}" in up or str(st.worktree) in up
    joined = " ".join(up)
    assert ".devcontainer/dev/devcontainer.json" in joined
    # base .git mounted rw at the same absolute path
    assert f"source={repo / '.git'},target={repo / '.git'}" in joined
    assert load_state(repo, "vk-iso/test") == st


def test_up_outside_repo_exits_with_isolation_error(tmp_path: Path) -> None:
    with pytest.raises(IsolationError, match="git repo"):
        LocalWorktreeDevcontainerTarget(tmp_path / "nowhere", runner=FakeRunner()).up(None, "b")


def test_up_devcontainer_failure_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner(fail_on="devcontainer"))
    with pytest.raises(IsolationError, match="devcontainer up"):
        target.up(None, "vk-iso/test")


# ---------- target.exec / status / down ----------


def _upped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **runner_kw):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")
    runner = FakeRunner(**runner_kw)
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    st = target.up(None, "vk-iso/test")
    runner.calls.clear()
    return repo, runner, target, st


def test_exec_passthrough(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runner, target, st = _upped(tmp_path, monkeypatch)
    rc = target.exec(st, ["pytest", "-q", "--no-cov"])
    assert rc == 0
    (call,) = runner.argv_for("devcontainer")
    assert call[1] == "exec"
    assert call[-3:] == ["pytest", "-q", "--no-cov"]


def test_status_reports_worktree_container_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, runner, target, st = _upped(
        tmp_path,
        monkeypatch,
        stdout={"docker": "abc123 running\n", "gh": '{"state": "OPEN", "url": "u"}'},
    )
    s = target.status(st)
    assert s["worktree"] == str(st.worktree) and s["worktree_exists"] is True
    assert s["container"] == "running"
    assert s["pr"] == {"state": "OPEN", "url": "u"}


def test_down_refuses_open_pr_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, target, st = _upped(
        tmp_path, monkeypatch, stdout={"gh": '{"state": "OPEN", "url": "u"}'}
    )
    with pytest.raises(IsolationError, match="open"):
        target.down(st, force=False)
    assert st.worktree.is_dir()  # untouched


def test_down_force_removes_worktree_and_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, target, st = _upped(
        tmp_path,
        monkeypatch,
        stdout={"docker": "abc123 running\n", "gh": '{"state": "OPEN", "url": "u"}'},
    )
    target.down(st, force=True)
    assert not st.worktree.exists()
    assert load_state(repo, "vk-iso/test") is None
    stops = [c for c in runner.argv_for("docker") if c[1] in ("stop", "rm")]
    assert stops, "container should be stopped/removed"


def test_down_merged_pr_cleans_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, runner, target, st = _upped(
        tmp_path, monkeypatch, stdout={"gh": '{"state": "MERGED", "url": "u"}'}
    )
    target.down(st, force=False)
    assert not st.worktree.exists()
