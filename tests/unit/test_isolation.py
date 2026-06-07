"""fr isolation — Target protocol, state, profiles, and the local target.

All devcontainer/docker/gh calls go through the Runner seam; git calls hit
real throwaway repos (cheap, deterministic). Nothing here needs Docker.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import json

import pytest
from fr.isolation.local import LocalWorktreeDevcontainerTarget
from fr.isolation.types import (
    IsolationError,
    IsolationState,
    load_state,
    profiles_config,
    resolve_profile,
    save_state,
    secrets_env_file,
    state_path,
)


def make_repo(
    tmp_path: Path,
    profiles: list[str] | None = None,
    default: str | None = None,
    profiles_yaml: str = "fr-profiles.yaml",
    env_file_mount: str | None = None,
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
        config: dict = {"image": "x"}
        if env_file_mount:
            config["runArgs"] = ["--env-file", env_file_mount]
        (d / "devcontainer.json").write_text(json.dumps(config) + "\n")
    if default:
        (repo / ".devcontainer" / profiles_yaml).write_text(
            f"default: {default}\nprofiles:\n  {default}:\n    purpose: test\n"
        )
    if profiles:
        # committed, as in real repos — worktrees check out .devcontainer/
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "profiles"],
            check=True,
        )
    return repo


class FakeRunner:
    """Records non-git argv; delegates git to the real binary."""

    def __init__(self, fail_on: str | None = None, stdout: dict[str, str] | None = None):
        self.calls: list[list[str]] = []
        self.captures: list[bool] = []
        self.fail_on = fail_on
        self.stdout = stdout or {}

    def __call__(
        self, argv: list[str], cwd: Path | None = None, check: bool = False, capture: bool = True
    ):
        self.captures.append(capture)
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


def test_resolve_profile_no_devcontainer_points_at_fr_init(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    with pytest.raises(IsolationError, match="fr-init"):
        resolve_profile(repo, None)


def test_resolve_profile_unknown_lists_available(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    with pytest.raises(IsolationError, match="dev"):
        resolve_profile(repo, "nope")


def test_resolve_profile_no_default_single_profile(tmp_path: Path) -> None:
    """One profile dir, no vk-profiles.yaml → that profile is the default."""
    repo = make_repo(tmp_path, ["dev"])
    assert resolve_profile(repo, None) == "dev"


# ---------- dual-read renames (#272) ----------


def test_profiles_config_reads_fr_profiles(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")  # writes fr-profiles.yaml
    assert profiles_config(repo)["default"] == "dev"
    assert "legacy" not in capsys.readouterr().err


def test_profiles_config_vk_fallback_warns(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev", profiles_yaml="vk-profiles.yaml")
    assert profiles_config(repo)["default"] == "dev"
    err = capsys.readouterr().err
    assert "legacy" in err and "vk-profiles.yaml" in err and "fr init migrate" in err


def test_profiles_config_fr_wins_over_vk(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev", profiles_yaml="vk-profiles.yaml")
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "default: dev\nprofiles:\n  dev:\n    purpose: fr-side\n"
    )
    assert profiles_config(repo)["profiles"]["dev"]["purpose"] == "fr-side"
    assert "legacy" not in capsys.readouterr().err


def test_secrets_env_file_is_fr_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    p = secrets_env_file("myrepo", "dev")
    assert str(p).endswith(".config/fr/secrets/myrepo/dev.env")


def test_save_state_writes_fr_dir(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    st = IsolationState(
        repo_root=repo,
        branch="feat/x",
        worktree=tmp_path / "wt",
        profile="dev",
        created_at="2026-06-07T00:00:00Z",
    )
    save_state(st)
    assert str(state_path(repo, "feat/x")).startswith(str(repo / ".git" / "fr" / "isolation"))


def test_load_state_legacy_vk_dir_warns(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    legacy = repo / ".git" / "vk" / "isolation"
    legacy.mkdir(parents=True)
    st = IsolationState(
        repo_root=repo,
        branch="feat/x",
        worktree=tmp_path / "wt",
        profile="dev",
        created_at="2026-06-07T00:00:00Z",
    )
    (legacy / "feat__x.json").write_text(st.model_dump_json())
    assert load_state(repo, "feat/x") == st
    assert "legacy" in capsys.readouterr().err


def test_load_state_fr_wins_over_legacy(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    repo = make_repo(tmp_path, ["dev"], default="dev")
    legacy = repo / ".git" / "vk" / "isolation"
    legacy.mkdir(parents=True)
    old = IsolationState(
        repo_root=repo,
        branch="feat/x",
        worktree=tmp_path / "old-wt",
        profile="dev",
        created_at="2026-06-01T00:00:00Z",
    )
    (legacy / "feat__x.json").write_text(old.model_dump_json())
    new = old.model_copy(update={"worktree": tmp_path / "new-wt"})
    save_state(new)
    assert load_state(repo, "feat/x") == new
    assert "legacy" not in capsys.readouterr().err


# ---------- target.up ----------


def test_up_creates_worktree_envfile_and_devcontainer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(
        tmp_path,
        ["dev"],
        default="dev",
        env_file_mount="${localEnv:HOME}/.config/fr/secrets/repo/dev.env",
    )
    runner = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=runner)
    st = target.up(profile=None, branch="vk-iso/test")

    assert st.worktree.is_dir() and (st.worktree / "README.md").is_file()
    assert str(st.worktree).startswith(
        str(tmp_path / "home" / ".cache" / "fr" / "worktrees")
    )  # ~/.cache/fr default
    env = tmp_path / "home" / ".config" / "fr" / "secrets" / "repo" / "dev.env"
    assert env.is_file()  # mount-followed: created when missing

    (up,) = runner.argv_for("devcontainer")
    assert up[1] == "up"
    assert f"--workspace-folder={st.worktree}" in up or str(st.worktree) in up
    joined = " ".join(up)
    assert ".devcontainer/dev/devcontainer.json" in joined
    # base .git mounted rw at the same absolute path
    assert f"source={repo / '.git'},target={repo / '.git'}" in joined
    assert load_state(repo, "vk-iso/test") == st


def test_up_follows_legacy_vk_mount_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Unmigrated repo: committed devcontainer.json still mounts the vk path —
    up() ensures THAT file (the one docker will read) and warns."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(
        tmp_path,
        ["dev"],
        default="dev",
        env_file_mount="${localEnv:HOME}/.config/vk/secrets/repo/dev.env",
    )
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    target.up(profile=None, branch="vk-iso/test")
    env = tmp_path / "home" / ".config" / "vk" / "secrets" / "repo" / "dev.env"
    assert env.is_file()
    assert "legacy" in capsys.readouterr().err


def test_up_no_env_file_mount_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["dev"], default="dev")  # no runArgs in fixture
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    target.up(profile=None, branch="vk-iso/test")
    assert not (tmp_path / "home" / ".config").exists()


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
    assert runner.captures[-1] is False, "exec must inherit stdio (stream output live)"


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


def test_up_twice_is_idempotent_on_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running up() must not fail on the existing worktree (re-entrant runs)."""
    repo, runner, target, st1 = _upped(tmp_path, monkeypatch)
    st2 = target.up(None, "vk-iso/test")
    assert st2.worktree == st1.worktree
    assert st2.worktree.is_dir()
    # second up still (re)starts the devcontainer but adds no second worktree
    (up_call,) = runner.argv_for("devcontainer")
    assert up_call[1] == "up"


def test_pr_malformed_gh_json_is_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, runner, target, st = _upped(tmp_path, monkeypatch, stdout={"gh": "not-json {"})
    assert target.status(st)["pr"] is None
