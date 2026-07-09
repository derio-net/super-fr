"""fr isolation CLI — flag mapping, exec passthrough, error UX (exit 2 + fr-init pointer)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import isolation_cmd
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_real_gc_spawn(monkeypatch: pytest.MonkeyPatch):
    """Never fork a real `fr isolation gc` during CLI tests — up/down would
    otherwise reap the developer's live workspaces (#354)."""
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda: None)


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


def test_up_plan_repo_without_validator_wrapper_exits_2(repo: Path, fake_run: list) -> None:
    plans = repo / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(repo), "add", "docs"], check=True)
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
            "plans",
        ],
        check=True,
    )

    res = runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "b"])

    assert res.exit_code == 2
    assert "scripts/validate-plans.sh" in res.output
    assert "install-validator-wrapper.sh" in res.output
    assert not fake_run


def test_up_uses_base_ref_validator_even_when_base_checkout_lacks_wrapper(
    repo: Path, fake_run: list
) -> None:
    plans = repo / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / ".gitkeep").write_text("")
    wrapper = repo / "scripts" / "validate-plans.sh"
    wrapper.parent.mkdir()
    wrapper.write_text("#!/usr/bin/env bash\nexit 0\n")
    wrapper.chmod(0o755)
    subprocess.run(["git", "-C", str(repo), "add", "docs", "scripts/validate-plans.sh"], check=True)
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
            "plans and validator",
        ],
        check=True,
    )
    base_with_wrapper = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "-C", str(repo), "rm", "-q", "scripts/validate-plans.sh"], check=True)
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
            "remove validator from current checkout",
        ],
        check=True,
    )

    res = runner.invoke(
        app,
        ["isolation", "up", "--repo", str(repo), "--branch", "b", "--base", base_with_wrapper],
    )

    assert res.exit_code == 0, res.output
    assert any(c[:2] == ["devcontainer", "up"] for c in fake_run)


def test_up_plan_repo_with_executable_validator_wrapper_continues(
    repo: Path, fake_run: list
) -> None:
    plans = repo / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(repo), "add", "docs"], check=True)
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
            "plans",
        ],
        check=True,
    )
    wrapper = repo / "scripts" / "validate-plans.sh"
    wrapper.parent.mkdir()
    wrapper.write_text("#!/usr/bin/env bash\nexit 0\n")
    wrapper.chmod(0o755)
    subprocess.run(["git", "-C", str(repo), "add", "docs", "scripts/validate-plans.sh"], check=True)
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
            "validator",
        ],
        check=True,
    )

    res = runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "b"])

    assert res.exit_code == 0, res.output
    assert any(c[:2] == ["devcontainer", "up"] for c in fake_run)


def test_up_plan_repo_with_uncommitted_validator_wrapper_exits_2(
    repo: Path, fake_run: list
) -> None:
    plans = repo / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(repo), "add", "docs"], check=True)
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
            "plans",
        ],
        check=True,
    )
    wrapper = repo / "scripts" / "validate-plans.sh"
    wrapper.parent.mkdir()
    wrapper.write_text("#!/usr/bin/env bash\nexit 0\n")
    wrapper.chmod(0o755)

    res = runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "b"])

    assert res.exit_code == 2
    assert "not in HEAD" in res.output
    assert not fake_run


def test_up_plan_repo_base_ref_without_validator_wrapper_exits_2(
    repo: Path, fake_run: list
) -> None:
    plans = repo / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(repo), "add", "docs"], check=True)
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
            "plans",
        ],
        check=True,
    )
    base_without_wrapper = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    wrapper = repo / "scripts" / "validate-plans.sh"
    wrapper.parent.mkdir()
    wrapper.write_text("#!/usr/bin/env bash\nexit 0\n")
    wrapper.chmod(0o755)
    subprocess.run(["git", "-C", str(repo), "add", "scripts/validate-plans.sh"], check=True)
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
            "validator",
        ],
        check=True,
    )

    res = runner.invoke(
        app,
        [
            "isolation",
            "up",
            "--repo",
            str(repo),
            "--branch",
            "b",
            "--base",
            base_without_wrapper,
        ],
    )

    assert res.exit_code == 2
    assert base_without_wrapper in res.output
    assert not fake_run


def test_up_existing_worktree_without_validator_wrapper_exits_2(
    repo: Path, fake_run: list, tmp_path: Path
) -> None:
    worktree = tmp_path / "existing-worktree"
    (worktree / ".devcontainer" / "dev").mkdir(parents=True)
    (worktree / ".devcontainer" / "dev" / "devcontainer.json").write_text('{"image": "x"}')
    (worktree / "docs" / "superpowers" / "plans").mkdir(parents=True)

    res = runner.invoke(
        app,
        [
            "isolation",
            "up",
            "--repo",
            str(repo),
            "--branch",
            "b",
            "--path",
            str(worktree),
        ],
    )

    assert res.exit_code == 2
    assert "existing isolation worktree" in res.output
    assert "scripts/validate-plans.sh" in res.output
    assert not fake_run


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


def test_up_forwards_base_and_no_fetch(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#322: --base / --no-fetch must reach Target.up so cold-start basing works."""
    from fr.isolation.types import IsolationState

    captured: dict = {}

    class StubTarget:
        def up(self, profile=None, branch="", path=None, base=None, no_fetch=False):
            captured.update(profile=profile, branch=branch, base=base, no_fetch=no_fetch)
            return IsolationState(
                repo_root=repo,
                branch=branch,
                worktree=repo / "wt",
                profile="dev",
                created_at="2026-06-21T00:00:00Z",
            )

    monkeypatch.setattr(isolation_cmd, "_target", lambda _repo: StubTarget())

    res = runner.invoke(
        app,
        ["isolation", "up", "--repo", str(repo), "--branch", "feat/x", "--base", "origin/main"],
    )
    assert res.exit_code == 0, res.output
    assert captured["base"] == "origin/main" and captured["no_fetch"] is False

    captured.clear()
    res = runner.invoke(
        app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/y", "--no-fetch"]
    )
    assert res.exit_code == 0, res.output
    assert captured["no_fetch"] is True and captured["base"] is None


def _sentinel(tmp_path, repo, monkeypatch, session="sess"):
    import json

    sdir = tmp_path / "sent"
    sdir.mkdir(exist_ok=True)
    monkeypatch.setenv("FR_SENTINEL_DIR", str(sdir))
    (sdir / f"{session}.json").write_text(json.dumps({"repo_root": str(repo.resolve())}))
    return sdir


def test_down_all_tears_down_and_clears_sentinels(
    repo: Path, fake_run: list, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # #341 Task 2A: `down --all` tears down every workspace and drops the
    # pipeline sentinel(s) — the explicit escape from the orphaned-sentinel
    # deadlock. gh returns MERGED here, so no open-PR safety kicks in.
    sdir = _sentinel(tmp_path, repo, monkeypatch)
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/a"])
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/b"])
    from fr.isolation.types import list_states

    assert len(list_states(repo.resolve())) == 2
    res = runner.invoke(app, ["isolation", "down", "--repo", str(repo), "--all"])
    assert res.exit_code == 0, res.output
    assert list_states(repo.resolve()) == []
    assert not (sdir / "sess.json").exists(), "pipeline sentinel cleared"
    assert "cleared" in res.output.lower()


def test_down_all_keeps_open_pr_without_force(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def run(argv, cwd=None, check=False, capture=True):
        if argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
        calls.append(list(argv))
        out = '{"state": "OPEN", "url": "u"}' if argv[0] == "gh" else ""
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

    monkeypatch.setattr(isolation_cmd, "_runner", run)
    _sentinel(tmp_path, repo, monkeypatch)
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/a"])
    from fr.isolation.types import list_states

    res = runner.invoke(app, ["isolation", "down", "--repo", str(repo), "--all"])
    assert res.exit_code == 0, res.output
    assert [s.branch for s in list_states(repo.resolve())] == ["feat/a"], "open-PR workspace kept"
    assert "kept" in res.output.lower()

    res = runner.invoke(app, ["isolation", "down", "--repo", str(repo), "--all", "--force"])
    assert res.exit_code == 0, res.output
    assert list_states(repo.resolve()) == [], "--force tears down the open-PR workspace"


def _docker_run(container: str = "cid running"):
    def run(argv, cwd=None, check=False, capture=True):
        if argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
        out = ""
        if argv[0] == "docker":
            out = container
        elif argv[0] == "gh":
            out = '{"state": "MERGED", "url": "u"}'
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

    return run


def test_restart_resolves_single_workspace_no_branch(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(isolation_cmd, "_runner", _docker_run())
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/only"])
    res = runner.invoke(app, ["isolation", "restart", "--repo", str(repo)])
    assert res.exit_code == 0, res.output
    assert "bounced" in res.output


def test_restart_multiple_workspaces_exits_2(repo: Path, fake_run: list) -> None:
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/a"])
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/b"])
    res = runner.invoke(app, ["isolation", "restart", "--repo", str(repo)])
    assert res.exit_code == 2
    assert "--branch" in res.output


def _stats_run(record: list | None = None):
    def run(argv, cwd=None, check=False, capture=True):
        if argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
        if record is not None:
            record.append(list(argv))
        if argv[:2] == ["docker", "ps"]:
            return subprocess.CompletedProcess(argv, 0, stdout="cid running", stderr="")
        if argv[:2] == ["docker", "stats"]:
            return subprocess.CompletedProcess(argv, 0, stdout="9.0%|2GiB / 4GiB|50.0%", stderr="")
        if argv[0] == "gh":
            return subprocess.CompletedProcess(
                argv, 0, stdout='{"state": "MERGED", "url": "u"}', stderr=""
            )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    return run


def test_status_stats_flag_shows_resource_row(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(isolation_cmd, "_runner", _stats_run())
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/a"])
    res = runner.invoke(
        app, ["isolation", "status", "--repo", str(repo), "--stats", "--format", "json"]
    )
    assert res.exit_code == 0, res.output
    assert '"stats"' in res.output
    assert "9.0%" in res.output


def test_status_default_makes_no_stats_call(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(isolation_cmd, "_runner", _stats_run(record=calls))
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/a"])
    calls.clear()
    res = runner.invoke(app, ["isolation", "status", "--repo", str(repo)])
    assert res.exit_code == 0, res.output
    assert not any(c[:2] == ["docker", "stats"] for c in calls), "default status skips docker stats"


# ---------- gc CLI (#354 Task B) ----------


def _stub_gc(monkeypatch: pytest.MonkeyPatch, actions, captured=None):
    from fr.isolation.local import GcAction  # noqa: F401 (referenced by callers)

    class StubTarget:
        def gc(self, dry_run=False):
            if captured is not None:
                captured["dry_run"] = dry_run
            return actions

    monkeypatch.setattr(isolation_cmd, "_target", lambda _repo: StubTarget())


def test_gc_cli_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.isolation.local import GcAction

    captured: dict = {}
    _stub_gc(
        monkeypatch,
        [
            GcAction("/wt/m", "feat/m", "merged", "would-reap"),
            GcAction("/wt/o", "feat/o", "open", "skipped"),
        ],
        captured,
    )
    res = runner.invoke(app, ["isolation", "gc", "--dry-run"])
    assert res.exit_code == 0, res.output
    assert captured["dry_run"] is True
    assert "feat/m: merged → would-reap" in res.output
    assert "feat/o: open → skipped" in res.output


def test_gc_cli_json(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    from fr.isolation.local import GcAction

    _stub_gc(monkeypatch, [GcAction("/wt/m", "feat/m", "merged", "reaped", "cX")])
    res = runner.invoke(app, ["isolation", "gc", "--format", "json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data == [
        {
            "worktree": "/wt/m",
            "branch": "feat/m",
            "verdict": "merged",
            "action": "reaped",
            "detail": "cX",
        }
    ]


def test_gc_cli_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_gc(monkeypatch, [])
    res = runner.invoke(app, ["isolation", "gc"])
    assert res.exit_code == 0, res.output
    assert "no isolation workspaces" in res.output
