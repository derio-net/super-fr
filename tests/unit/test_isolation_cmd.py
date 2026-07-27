"""fr isolation CLI — flag mapping, exec passthrough, error UX (exit 2 + fr-init pointer)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import isolation_cmd
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.local import LocalWorktreeDevcontainerTarget
from fr.isolation.types import IsolationError
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_real_gc_spawn(monkeypatch: pytest.MonkeyPatch):
    """Never fork a real `fr isolation gc` during CLI tests — up/down would
    otherwise reap the developer's live workspaces (#354)."""
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda _root: None)


@pytest.fixture(autouse=True)
def _default_mode(monkeypatch: pytest.MonkeyPatch):
    """Pin target selection to devcontainer mode unless a test says otherwise.

    `FR_ISOLATION_TARGET` is a HOST-level declaration, and the docker-less pods
    this repo is developed on export `=worktree` — leaving it ambient silently
    reroutes every unqualified CLI test to `HostWorktreeTarget` and fails eight
    of them for environmental reasons. Mode tests set the var explicitly.
    """
    monkeypatch.delenv("FR_ISOLATION_TARGET", raising=False)


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


def test_target_default_is_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FR_ISOLATION_TARGET", raising=False)
    # exact type, NOT isinstance — HostWorktreeTarget subclasses the local one.
    assert type(isolation_cmd._target(tmp_path)) is LocalWorktreeDevcontainerTarget


def test_target_devcontainer_explicit_is_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FR_ISOLATION_TARGET", "devcontainer")
    assert type(isolation_cmd._target(tmp_path)) is LocalWorktreeDevcontainerTarget


def test_target_worktree_is_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    assert type(isolation_cmd._target(tmp_path)) is HostWorktreeTarget


def test_target_unknown_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_ISOLATION_TARGET", "bogus")
    with pytest.raises(IsolationError) as ei:
        isolation_cmd._target(tmp_path)
    msg = str(ei.value)
    assert "bogus" in msg
    assert "devcontainer | worktree" in msg


def _init_git_repo(path: Path) -> Path:
    """A real primary checkout (one commit) so `detect`'s `git rev-parse
    --show-toplevel` resolves — external detection now toplevel-resolves the
    CWD (finding 3) instead of probing the passed path verbatim."""
    path.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    (path / "x").write_text("x")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
        check=True,
    )
    return path


def _external_marker(repo: Path, *, toplevel: str | None = None) -> None:
    import json

    (repo / ".fr-isolation").write_text(
        json.dumps(
            {
                "toplevel": toplevel if toplevel is not None else str(repo.resolve()),
                "branch": "",
                "mode": "external",
                "created_at": "2026-07-24T00:00:00+00:00",
            }
        )
        + "\n"
    )


def test_target_valid_external_marker_beats_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.isolation.external import ExternalTarget

    monkeypatch.delenv("FR_ISOLATION_TARGET", raising=False)
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "1")  # container evidence (finding 6)
    repo = _init_git_repo(tmp_path / "repo")
    _external_marker(repo)
    assert type(isolation_cmd._target(repo)) is ExternalTarget


def test_target_valid_external_marker_beats_worktree_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """External marker outranks FR_ISOLATION_TARGET — a prepared container is a
    recognize-and-adopt, regardless of any host-level worktree declaration."""
    from fr.isolation.external import ExternalTarget

    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "1")  # container evidence (finding 6)
    repo = _init_git_repo(tmp_path / "repo")
    _external_marker(repo)
    assert type(isolation_cmd._target(repo)) is ExternalTarget


def test_target_external_marker_detected_from_subdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 3: a command issued from a SUBDIRECTORY of the prepared checkout
    still selects ExternalTarget — detect resolves the git toplevel first,
    instead of missing the marker and falling through to devcontainer."""
    from fr.isolation.external import ExternalTarget

    monkeypatch.delenv("FR_ISOLATION_TARGET", raising=False)
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "1")
    repo = _init_git_repo(tmp_path / "repo")
    _external_marker(repo)  # marker at toplevel only
    sub = repo / "pkg" / "deep"
    sub.mkdir(parents=True)
    assert type(isolation_cmd._target(sub)) is ExternalTarget


def test_target_external_marker_without_container_evidence_falls_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 6: a valid external marker on a bare host (no container evidence)
    is NOT adopted — detect returns None and selection falls through to the
    default. Skipped where a container-evidence file exists on the test host
    (the devcontainer's /.dockerenv fires unconditionally); mirrors Phase 3's
    hook skip-guard."""
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        pytest.skip("container evidence file present on host — evidence fires unconditionally")
    from fr.isolation.external import ExternalTarget

    monkeypatch.delenv("FR_ISOLATION_TARGET", raising=False)
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "")  # explicitly no evidence
    repo = _init_git_repo(tmp_path / "repo")
    _external_marker(repo)  # valid marker, matching toplevel
    assert type(isolation_cmd._target(repo)) is not ExternalTarget
    assert type(isolation_cmd._target(repo)) is LocalWorktreeDevcontainerTarget


def test_target_invalid_external_marker_falls_through_to_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    _external_marker(tmp_path, toplevel=str(tmp_path / "elsewhere"))  # toplevel mismatch
    assert type(isolation_cmd._target(tmp_path)) is HostWorktreeTarget


def test_target_invalid_external_marker_falls_through_to_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FR_ISOLATION_TARGET", raising=False)
    _external_marker(tmp_path, toplevel=str(tmp_path / "elsewhere"))
    assert type(isolation_cmd._target(tmp_path)) is LocalWorktreeDevcontainerTarget


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


def test_down_resolves_single_workspace_when_no_branch(repo: Path, fake_run: list) -> None:
    # #399: with exactly one isolation workspace, bare `down` (no --branch)
    # tears IT down instead of the hardcoded vk-iso/work default (which errored
    # even when a real workspace for the cwd existed). Mirrors exec/restart.
    from fr.isolation.types import list_states

    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/only"])
    res = runner.invoke(app, ["isolation", "down", "--repo", str(repo)])
    assert res.exit_code == 0, res.output
    assert "feat/only" in res.output
    assert list_states(repo.resolve()) == []


def test_down_no_branch_zero_workspaces_exits_2(repo: Path, fake_run: list) -> None:
    res = runner.invoke(app, ["isolation", "down", "--repo", str(repo)])
    assert res.exit_code == 2
    assert "isolation up" in res.output
    assert "vk-iso/work" not in res.output  # no misleading hardcoded default-branch name


def test_down_no_branch_multiple_workspaces_exits_2(repo: Path, fake_run: list) -> None:
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/a"])
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/b"])
    res = runner.invoke(app, ["isolation", "down", "--repo", str(repo)])
    assert res.exit_code == 2
    assert "--branch" in res.output
    assert "feat/a" in res.output and "feat/b" in res.output


def test_down_clears_sentinel_when_last_workspace_removed(
    repo: Path, fake_run: list, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # #399: bare `down` of the LAST workspace clears the pipeline sentinel, so
    # the Bash gate stops reporting 'fr pipeline active'. The guard's own clear
    # never fires here — it exits early when `down` runs from the worktree cwd
    # (the prescribed workflow), so the Python command must clear eagerly.
    sdir = _sentinel(tmp_path, repo, monkeypatch)
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/only"])
    assert (sdir / "sess.json").exists()
    res = runner.invoke(app, ["isolation", "down", "--repo", str(repo), "--branch", "feat/only"])
    assert res.exit_code == 0, res.output
    assert not (sdir / "sess.json").exists(), "sentinel cleared when zero workspaces remain"


def test_down_keeps_sentinel_when_other_workspaces_remain(
    repo: Path, fake_run: list, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # #399: tearing down ONE of several workspaces must NOT clear the sentinel —
    # the pipeline is still active for the survivors.
    sdir = _sentinel(tmp_path, repo, monkeypatch)
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/a"])
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/b"])
    res = runner.invoke(app, ["isolation", "down", "--repo", str(repo), "--branch", "feat/a"])
    assert res.exit_code == 0, res.output
    assert (sdir / "sess.json").exists(), "sentinel kept while another workspace remains"


def test_status_from_deleted_cwd_exits_2_not_traceback(
    repo: Path, fake_run: list, tmp_path: Path
) -> None:
    # #399: after `down` removes the worktree the operator's shell sat in, the
    # default repo=Path('.') resolves via os.getcwd() on a deleted directory.
    # status must fail cleanly (exit 2), not crash with an unhandled
    # FileNotFoundError traceback.
    import os

    victim = tmp_path / "gone"
    victim.mkdir()
    prev = Path.cwd()
    os.chdir(victim)
    victim.rmdir()
    try:
        res = runner.invoke(app, ["isolation", "status"])
    finally:
        os.chdir(prev)
    assert res.exit_code == 2, res.output
    assert res.exception is None or isinstance(res.exception, SystemExit), res.exception
    assert "director" in res.output.lower()  # names the gone directory


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


def test_status_push_check_flag_shows_diagnostic(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(isolation_cmd, "_runner", _stats_run())
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/a"])
    fixed = {
        "branch": "feat/a",
        "remotes": ["origin\tgit@gitlab.example.com:g/p.git (fetch)"],
        "backend": "gitlab",
        "ssh_agent_in_container": {"present": False, "detail": "unset"},
        "guidance": "push and glab PR/MR creation must run on the HOST from the worktree...",
    }
    monkeypatch.setattr(LocalWorktreeDevcontainerTarget, "push_check", lambda self, state: fixed)
    res = runner.invoke(
        app, ["isolation", "status", "--repo", str(repo), "--push-check", "--format", "json"]
    )
    assert res.exit_code == 0, res.output
    assert '"push_check"' in res.output
    assert "gitlab" in res.output


def test_status_default_makes_no_push_check_call(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(isolation_cmd, "_runner", _stats_run())
    runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/a"])

    def _boom(self: LocalWorktreeDevcontainerTarget, state: object) -> None:
        raise AssertionError("push_check must not run without --push-check")

    monkeypatch.setattr(LocalWorktreeDevcontainerTarget, "push_check", _boom)
    res = runner.invoke(app, ["isolation", "status", "--repo", str(repo)])
    assert res.exit_code == 0, res.output


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


# ---------- host-worktree & external mode CLI (isolation host modes review) ----------


def _external_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, branch: str = "feat/x") -> Path:
    """A prepared external checkout with fr already adopted (up run): git repo +
    preparer marker + container evidence, then `fr isolation up`."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "1")  # container evidence
    monkeypatch.delenv("FR_ISOLATION_TARGET", raising=False)
    repo = _init_git_repo(tmp_path / "repo")
    _external_marker(repo)
    res = runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", branch])
    assert res.exit_code == 0, res.output
    return repo


def _host_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, branch: str = "feat/x") -> Path:
    """A host-worktree host: FR_ISOLATION_TARGET=worktree, real git repo, and a
    runner that RAISES on any `docker` argv (a docker-less pod) — so any code
    path that shells out to docker fails the test loudly."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    repo = _init_git_repo(tmp_path / "repo")

    def run(argv, cwd=None, check=False, capture=True):
        if argv and argv[0] == "docker":
            raise FileNotFoundError("docker: not found (docker-less host)")
        if argv and argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, check=check, capture_output=True, text=True)
        # gh (PR lookup) → no PR
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")

    monkeypatch.setattr(isolation_cmd, "_runner", run)
    res = runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", branch])
    assert res.exit_code == 0, res.output
    return repo


# --- finding 2a: external status renders without a KeyError ---


def test_status_external_mode_text_renders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _external_up(tmp_path, monkeypatch)
    res = runner.invoke(app, ["isolation", "status", "--repo", str(repo)])
    assert res.exit_code == 0, res.output
    assert "feat/x" in res.output
    assert "external" in res.output


def test_status_external_mode_json_has_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json as _json

    repo = _external_up(tmp_path, monkeypatch)
    res = runner.invoke(app, ["isolation", "status", "--repo", str(repo), "--format", "json"])
    assert res.exit_code == 0, res.output
    row = _json.loads(res.output)[0]
    assert row["mode"] == "external"
    assert row["profile"] == "external"
    assert row["worktree"] == row["toplevel"]
    assert row["pr"] is None


# --- finding 2b: host-worktree status never probes docker ---


def test_status_host_worktree_mode_no_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _host_repo(tmp_path, monkeypatch)
    # The runner raises on docker; exit 0 proves status never shelled out to it.
    res = runner.invoke(app, ["isolation", "status", "--repo", str(repo)])
    assert res.exit_code == 0, res.output
    assert "feat/x" in res.output
    assert "n/a (host)" in res.output


def test_status_stats_host_mode_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _host_repo(tmp_path, monkeypatch)
    res = runner.invoke(app, ["isolation", "status", "--repo", str(repo), "--stats"])
    assert res.exit_code == 2
    assert "host-worktree" in res.output


def test_status_push_check_host_mode_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _host_repo(tmp_path, monkeypatch)
    res = runner.invoke(app, ["isolation", "status", "--repo", str(repo), "--push-check"])
    assert res.exit_code == 2
    assert "host-worktree" in res.output


# --- finding 4: bogus FR_ISOLATION_TARGET → clean exit 2 in every command ---


def test_status_bogus_target_exits_2(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_ISOLATION_TARGET", "bogus")
    res = runner.invoke(app, ["isolation", "status", "--repo", str(repo)])
    assert res.exit_code == 2
    assert "bogus" in res.output
    assert "devcontainer | worktree" in res.output
    assert "Traceback" not in res.output


def test_gc_bogus_target_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FR_ISOLATION_TARGET", "bogus")
    res = runner.invoke(app, ["isolation", "gc"])
    assert res.exit_code == 2
    assert "bogus" in res.output
    assert "Traceback" not in res.output


def test_down_all_bogus_target_exits_2(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_ISOLATION_TARGET", "bogus")
    res = runner.invoke(app, ["isolation", "down", "--repo", str(repo), "--all"])
    assert res.exit_code == 2
    assert "bogus" in res.output


# --- finding 5: external mode refuses worktree-ops subcommands cleanly ---


def test_verify_merge_external_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _external_up(tmp_path, monkeypatch)
    res = runner.invoke(
        app, ["isolation", "verify-merge", "--repo", str(repo), "--branch", "feat/x"]
    )
    assert res.exit_code == 2
    assert "external mode" in res.output


def test_status_push_check_external_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _external_up(tmp_path, monkeypatch)
    res = runner.invoke(app, ["isolation", "status", "--repo", str(repo), "--push-check"])
    assert res.exit_code == 2
    assert "external mode" in res.output


def test_gc_external_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.isolation.external import ExternalTarget

    et = ExternalTarget(tmp_path)
    monkeypatch.setattr(isolation_cmd, "_target", lambda _repo: et)
    res = runner.invoke(app, ["isolation", "gc"])
    assert res.exit_code == 2
    assert "external mode" in res.output


# --- finding 10: gc on a docker-less host-worktree host refuses cleanly ---


def test_gc_host_mode_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ht = HostWorktreeTarget(tmp_path)
    monkeypatch.setattr(isolation_cmd, "_target", lambda _repo: ht)
    res = runner.invoke(app, ["isolation", "gc"])
    assert res.exit_code == 2
    assert "future work" in res.output
    assert "Traceback" not in res.output
