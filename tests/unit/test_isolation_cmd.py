"""fr isolation CLI — flag mapping, exec passthrough, error UX (exit 2 + fr-init pointer)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import isolation_cmd
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    (r / "x").write_text("x")
    # The profile must be COMMITTED — worktrees check out .devcontainer/ from the
    # committed tree (super-fr#299 part 2); an uncommitted profile is now a
    # deliberate `up` error, so the fixture commits it as real repos do.
    d = r / ".devcontainer" / "dev"
    d.mkdir(parents=True)
    (d / "devcontainer.json").write_text('{"image": "x"}')
    subprocess.run(["git", "-C", str(r), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(r), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
        check=True,
    )
    return r


@pytest.fixture()
def fake_run(monkeypatch: pytest.MonkeyPatch):
    calls: list[list[str]] = []

    def run(argv, cwd=None, check=False, capture=True):
        if argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, check=check, capture_output=True, text=True)
        calls.append(list(argv))
        out = '{"state": "MERGED", "url": "u"}' if argv[0] == "gh" else ""
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

    monkeypatch.setattr(isolation_cmd, "_runner", run)
    return calls


def test_up_exec_status_down_happy_path(repo: Path, fake_run: list) -> None:
    res = runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "vk-iso/t"])
    assert res.exit_code == 0, res.output
    assert "worktree" in res.output

    res = runner.invoke(
        app, ["isolation", "exec", "--repo", str(repo), "--branch", "vk-iso/t", "--", "echo", "hi"]
    )
    assert res.exit_code == 0, res.output
    execs = [c for c in fake_run if c[:2] == ["devcontainer", "exec"]]
    assert execs and execs[0][-2:] == ["echo", "hi"]

    res = runner.invoke(app, ["isolation", "status", "--repo", str(repo), "--format", "json"])
    assert res.exit_code == 0, res.output
    assert '"branch": "vk-iso/t"' in res.output

    res = runner.invoke(app, ["isolation", "down", "--repo", str(repo), "--branch", "vk-iso/t"])
    assert res.exit_code == 0, res.output


def test_up_without_profile_outside_repo_exits_2(tmp_path: Path, fake_run: list) -> None:
    res = runner.invoke(app, ["isolation", "up", "--repo", str(tmp_path), "--branch", "b"])
    assert res.exit_code == 2
    assert "git repo" in res.output


def test_up_no_devcontainer_points_at_fr_init(repo: Path, fake_run: list) -> None:
    import shutil

    shutil.rmtree(repo / ".devcontainer")
    res = runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "b"])
    assert res.exit_code == 2
    assert "fr-init" in res.output


def test_exec_without_up_exits_2(repo: Path, fake_run: list) -> None:
    res = runner.invoke(
        app, ["isolation", "exec", "--repo", str(repo), "--branch", "ghost", "--", "ls"]
    )
    assert res.exit_code == 2
    assert "isolation up" in res.output


def test_status_lists_all_when_no_branch(repo: Path, fake_run: list) -> None:
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "a"])
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "b"])
    res = runner.invoke(app, ["isolation", "status", "--repo", str(repo)])
    assert res.exit_code == 0
    assert "a" in res.output and "b" in res.output


def test_exec_with_no_command_exits_2(repo: Path, fake_run: list) -> None:
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "e"])
    res = runner.invoke(app, ["isolation", "exec", "--repo", str(repo), "--branch", "e"])
    assert res.exit_code == 2


def test_exec_resolves_single_workspace_when_no_branch(repo: Path, fake_run: list) -> None:
    # super-fr#299 part 3: with exactly one isolation workspace, `exec` without
    # --branch uses it instead of the hardcoded vk-iso/work default (which made
    # `exec` after a failed `up --branch feat/x` look for the wrong workspace).
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/only"])
    res = runner.invoke(app, ["isolation", "exec", "--repo", str(repo), "--", "echo", "hi"])
    assert res.exit_code == 0, res.output
    execs = [c for c in fake_run if c[:2] == ["devcontainer", "exec"]]
    assert execs and execs[0][-2:] == ["echo", "hi"]


def test_exec_no_branch_zero_workspaces_exits_2(repo: Path, fake_run: list) -> None:
    res = runner.invoke(app, ["isolation", "exec", "--repo", str(repo), "--", "ls"])
    assert res.exit_code == 2
    assert "isolation up" in res.output
    assert "vk-iso/work" not in res.output  # no misleading hardcoded default-branch name


def test_exec_no_branch_multiple_workspaces_exits_2(repo: Path, fake_run: list) -> None:
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/a"])
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/b"])
    res = runner.invoke(app, ["isolation", "exec", "--repo", str(repo), "--", "ls"])
    assert res.exit_code == 2
    assert "--branch" in res.output
    assert "feat/a" in res.output and "feat/b" in res.output


def test_up_prints_add_dir_hint_in_claude_code(repo: Path, fake_run: list) -> None:
    res = runner.invoke(
        app,
        ["isolation", "up", "--repo", str(repo), "--branch", "vk-iso/h"],
        env={"CLAUDECODE": "1"},
    )
    assert res.exit_code == 0, res.output
    assert "/add-dir " in res.output
    # the absolute worktree path is the /add-dir argument
    assert "vk-iso__h" in res.output


def test_up_omits_add_dir_hint_without_claude_code(repo: Path, fake_run: list) -> None:
    res = runner.invoke(
        app,
        ["isolation", "up", "--repo", str(repo), "--branch", "vk-iso/n"],
        env={"CLAUDECODE": None},
    )
    assert res.exit_code == 0, res.output
    assert "worktree" in res.output
    assert "/add-dir" not in res.output


class _StubTarget:
    def __init__(self, result: dict) -> None:
        self._result = result

    def verify_merge(self, state, default_branch: str = "main") -> dict:
        return self._result


def test_verify_merge_cmd_verified(
    repo: Path, fake_run: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/v"])
    monkeypatch.setattr(
        isolation_cmd,
        "_target",
        lambda root: _StubTarget(
            {
                "branch": "feat/v",
                "verified": True,
                "changes_present": True,
                "missing": [],
                "pr_state": "MERGED",
                "fetched": True,
            }
        ),
    )
    res = runner.invoke(
        app, ["isolation", "verify-merge", "--repo", str(repo), "--branch", "feat/v"]
    )
    assert res.exit_code == 0, res.output
    assert "✓" in res.output


def test_verify_merge_cmd_not_verified_exits_1(
    repo: Path, fake_run: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/v"])
    monkeypatch.setattr(
        isolation_cmd,
        "_target",
        lambda root: _StubTarget(
            {
                "branch": "feat/v",
                "verified": False,
                "changes_present": False,
                "missing": ["fix2.py"],
                "pr_state": "MERGED",
                "fetched": True,
            }
        ),
    )
    res = runner.invoke(
        app, ["isolation", "verify-merge", "--repo", str(repo), "--branch", "feat/v"]
    )
    assert res.exit_code == 1
    assert "NOT verified" in res.output
    assert "fix2.py" in res.output


def test_verify_merge_cmd_no_workspace_exits_2(repo: Path, fake_run: list) -> None:
    res = runner.invoke(
        app, ["isolation", "verify-merge", "--repo", str(repo), "--branch", "ghost"]
    )
    assert res.exit_code == 2
    assert "no isolation workspace" in res.output
