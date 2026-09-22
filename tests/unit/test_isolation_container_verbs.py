"""Container verbs (spec 2026-09-23 lifecycle-container-vs-worktree, phase 2).

§3.A `rebuild` recreates the container against the existing worktree; §3.B
`exec` resumes a stopped container before running (`_ensure_running`); §3.C
`up` on an existing workspace keeps its state record's sessions/created_at.

Every devcontainer/docker call rides the FakeRunner seam from test_isolation;
git hits real throwaway repos. Nothing here needs Docker.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import isolation_cmd
from fr.isolation.external import ExternalTarget
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.local import LocalWorktreeDevcontainerTarget
from fr.isolation.types import (
    IsolationError,
    IsolationState,
    SessionBinding,
    load_state,
    save_state,
    state_path,
)
from typer.testing import CliRunner

from tests.unit.test_isolation import FakeRunner, _upped, make_repo

cli = CliRunner()


class _RebuildRunner(FakeRunner):
    """FakeRunner whose container is REPLACED by a successful
    `devcontainer up --remove-existing-container` (old id → new id), and whose
    `docker inspect <id>` answers per-container image ids."""

    def __init__(
        self,
        old: tuple[str, str] = ("cid1", "img-old"),
        new: tuple[str, str] = ("cid2", "img-new"),
        **kw,
    ) -> None:
        super().__init__(stdout={"docker": f"{old[0]} running"}, **kw)
        self.images = {old[0]: old[1], new[0]: new[1]}
        self.new_id = new[0]

    def __call__(self, argv, cwd=None, check=False, capture=True):
        result = super().__call__(argv, cwd=cwd, check=check, capture=capture)
        if (
            argv[:2] == ["devcontainer", "up"]
            and "--remove-existing-container" in argv
            and result.returncode == 0
        ):
            self.stdout["docker"] = f"{self.new_id} running"
        if argv[:2] == ["docker", "inspect"]:
            img = self.images.get(argv[-1], "")
            return subprocess.CompletedProcess(argv, 0 if img else 1, stdout=img + "\n", stderr="")
        return result


def _rebuild_setup(tmp_path, monkeypatch, **kw):
    """An upped workspace, plus a fresh target over a _RebuildRunner."""
    repo, _up_runner, up_target, st = _upped(tmp_path, monkeypatch)
    rr = _RebuildRunner(**kw)
    return repo, up_target, st, rr, LocalWorktreeDevcontainerTarget(repo, runner=rr)


def _dc(runner, sub: str) -> list[list[str]]:
    return [c for c in runner.argv_for("devcontainer") if c[1:2] == [sub]]


def _docker(runner, sub: str) -> list[list[str]]:
    return [c for c in runner.argv_for("docker") if c[1:2] == [sub]]


# ---------- §3.A rebuild ----------


class TestRebuild:
    def test_argv_is_ups_argv_plus_remove_existing(self, tmp_path, monkeypatch) -> None:
        repo, up_target, st, rr, target = _rebuild_setup(tmp_path, monkeypatch)
        # up's own argv, captured from an idempotent re-up with a plain runner
        plain = FakeRunner()
        LocalWorktreeDevcontainerTarget(repo, runner=plain).up(None, st.branch)
        (up_argv,) = _dc(plain, "up")

        target.rebuild(st, no_cache=False)
        (argv,) = _dc(rr, "up")
        assert "--remove-existing-container" in argv
        assert "--build-no-cache" not in argv
        assert [a for a in argv if a != "--remove-existing-container"] == up_argv

    def test_no_cache_adds_build_no_cache(self, tmp_path, monkeypatch) -> None:
        _repo, _ut, st, rr, target = _rebuild_setup(tmp_path, monkeypatch)
        target.rebuild(st, no_cache=True)
        (argv,) = _dc(rr, "up")
        assert "--remove-existing-container" in argv and "--build-no-cache" in argv

    def test_missing_worktree_refused_naming_up(self, tmp_path, monkeypatch) -> None:
        _repo, _ut, st, rr, target = _rebuild_setup(tmp_path, monkeypatch)
        gone = st.model_copy(update={"worktree": tmp_path / "gone"})
        with pytest.raises(IsolationError, match="fr isolation up"):
            target.rebuild(gone, no_cache=False)
        assert not rr.argv_for("devcontainer")

    def test_success_requeries_new_id_and_reclaims_changed_image(
        self, tmp_path, monkeypatch
    ) -> None:
        _repo, _ut, st, rr, target = _rebuild_setup(tmp_path, monkeypatch)
        msg = target.rebuild(st, no_cache=False)
        assert "cid1 → cid2" in msg
        assert "devcontainer.json" in msg and "worktree untouched" in msg
        assert _docker(rr, "rmi") == [["docker", "rmi", "img-old"]]
        # the new id comes from a docker ps issued AFTER the devcontainer up
        up_at = rr.calls.index(_dc(rr, "up")[0])
        assert any(c[:2] == ["docker", "ps"] for c in rr.calls[up_at + 1 :])

    def test_unchanged_image_is_not_reclaimed(self, tmp_path, monkeypatch) -> None:
        _repo, _ut, st, rr, target = _rebuild_setup(
            tmp_path, monkeypatch, old=("cid1", "img-same"), new=("cid2", "img-same")
        )
        target.rebuild(st, no_cache=False)
        assert not _docker(rr, "rmi")

    def test_failure_never_reclaims_and_names_the_retry(self, tmp_path, monkeypatch) -> None:
        _repo, _ut, st, rr, target = _rebuild_setup(tmp_path, monkeypatch, fail_on="up")
        with pytest.raises(IsolationError) as info:
            target.rebuild(st, no_cache=False)
        text = str(info.value)
        assert "fr isolation rebuild" in text
        assert "worktree" in text and "intact" in text
        assert not _docker(rr, "rmi")

    def test_state_and_marker_byte_identical(self, tmp_path, monkeypatch) -> None:
        repo, _ut, st, _rr, target = _rebuild_setup(tmp_path, monkeypatch)
        state_file = state_path(repo, st.branch)
        marker = st.worktree / ".fr-isolation"
        before = (state_file.read_bytes(), marker.read_bytes())
        target.rebuild(st, no_cache=False)
        assert (state_file.read_bytes(), marker.read_bytes()) == before

    def test_host_worktree_rebuild_is_noop_without_docker(self, tmp_path) -> None:
        runner = FakeRunner(stdout={"docker": "cid1 running"})
        repo = make_repo(tmp_path, ["dev"], default="dev")
        st = IsolationState(
            repo_root=repo,
            branch="feat/x",
            worktree=tmp_path / "wt",
            profile="host",
            created_at="2026-09-23T00:00:00Z",
        )
        msg = HostWorktreeTarget(repo, runner=runner).rebuild(st, no_cache=False)
        assert "nothing to rebuild" in msg
        assert runner.calls == []

    def test_external_rebuild_refuses(self, tmp_path) -> None:
        runner = FakeRunner(stdout={"docker": "cid1 running"})
        repo = make_repo(tmp_path, ["dev"], default="dev")
        st = IsolationState(
            repo_root=repo,
            branch="feat/x",
            worktree=repo,
            profile="external",
            created_at="2026-09-23T00:00:00Z",
        )
        with pytest.raises(IsolationError, match="externally managed"):
            ExternalTarget(repo, runner=runner).rebuild(st, no_cache=False)
        assert runner.argv_for("docker") == []


# ---------- §3.B exec resumes a stopped container ----------


def _exec_setup(tmp_path, monkeypatch, ps: str, **kw):
    repo, _runner, _target, st = _upped(tmp_path, monkeypatch)
    runner = FakeRunner(stdout={"docker": ps}, **kw)
    return st, runner, LocalWorktreeDevcontainerTarget(repo, runner=runner)


class TestExecEnsureRunning:
    @pytest.mark.parametrize("ps", ["cid1 running", "cid1 restarting"])
    def test_running_execs_directly(self, tmp_path, monkeypatch, ps) -> None:
        st, runner, target = _exec_setup(tmp_path, monkeypatch, ps)
        assert target.exec(st, ["echo", "hi"]) == 0
        assert not _dc(runner, "up") and not _docker(runner, "unpause")
        (call,) = _dc(runner, "exec")
        assert call[-2:] == ["echo", "hi"]

    @pytest.mark.parametrize("ps", ["cid1 exited", "cid1 created"])
    def test_stopped_resumes_via_devcontainer_up_then_execs(
        self, tmp_path, monkeypatch, capsys, ps
    ) -> None:
        st, runner, target = _exec_setup(tmp_path, monkeypatch, ps)
        assert target.exec(st, ["echo", "hi"]) == 0
        (up,) = _dc(runner, "up")
        (ex,) = _dc(runner, "exec")
        assert runner.calls.index(up) < runner.calls.index(ex)
        assert "--remove-existing-container" not in up
        err = capsys.readouterr().err
        assert f"container for {st.branch} was stopped — resuming (devcontainer up)" in err

    def test_paused_unpauses_then_execs(self, tmp_path, monkeypatch) -> None:
        st, runner, target = _exec_setup(tmp_path, monkeypatch, "cid1 paused")
        assert target.exec(st, ["echo", "hi"]) == 0
        assert _docker(runner, "unpause") == [["docker", "unpause", "cid1"]]
        assert not _dc(runner, "up")
        assert _dc(runner, "exec")

    @pytest.mark.parametrize("ps", ["", "cid1 dead"])
    def test_absent_or_dead_names_rebuild(self, tmp_path, monkeypatch, ps) -> None:
        st, runner, target = _exec_setup(tmp_path, monkeypatch, ps)
        with pytest.raises(IsolationError) as info:
            target.exec(st, ["echo", "hi"])
        assert f"no usable container for {st.branch}" in str(info.value)
        assert f"fr isolation rebuild --branch {st.branch}" in str(info.value)
        assert not _dc(runner, "exec") and not _dc(runner, "up")

    def test_failed_docker_ps_is_unreachable(self, tmp_path, monkeypatch) -> None:
        st, runner, target = _exec_setup(tmp_path, monkeypatch, "cid1 exited", fail_on="ps")
        with pytest.raises(IsolationError, match="docker is unreachable"):
            target.exec(st, ["echo", "hi"])
        assert not _dc(runner, "exec")

    def test_missing_docker_binary_is_unreachable(self, tmp_path, monkeypatch) -> None:
        st, _runner, target = _exec_setup(tmp_path, monkeypatch, "cid1 running")

        def no_docker(argv, cwd=None, check=False, capture=True):
            if argv[0] == "git":
                return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
            raise FileNotFoundError(argv[0])

        target.run = no_docker
        with pytest.raises(IsolationError, match="docker is unreachable"):
            target.exec(st, ["echo", "hi"])

    def test_missing_devcontainer_binary_is_an_isolation_error(self, tmp_path, monkeypatch) -> None:
        st, runner, target = _exec_setup(tmp_path, monkeypatch, "cid1 running")

        def no_devcontainer(argv, cwd=None, check=False, capture=True):
            if argv[0] == "devcontainer":
                raise FileNotFoundError(argv[0])
            return runner(argv, cwd=cwd, check=check, capture=capture)

        target.run = no_devcontainer
        with pytest.raises(IsolationError, match="devcontainer"):
            target.exec(st, ["echo", "hi"])

    def test_failed_resume_names_rebuild(self, tmp_path, monkeypatch) -> None:
        st, runner, target = _exec_setup(tmp_path, monkeypatch, "cid1 exited", fail_on="up")
        with pytest.raises(IsolationError, match=f"fr isolation rebuild --branch {st.branch}"):
            target.exec(st, ["echo", "hi"])
        assert not _dc(runner, "exec")

    def test_failed_unpause_names_rebuild(self, tmp_path, monkeypatch) -> None:
        st, runner, target = _exec_setup(tmp_path, monkeypatch, "cid1 paused", fail_on="unpause")
        with pytest.raises(IsolationError, match="fr isolation rebuild"):
            target.exec(st, ["echo", "hi"])
        assert not _dc(runner, "exec")


# ---------- §3.C up keeps its record ----------


_BOUND = SessionBinding(session_id="s-1", harness="claude", attached_at="2026-09-01T00:00:00Z")


def _bind(st: IsolationState) -> IsolationState:
    bound = st.model_copy(update={"sessions": [_BOUND], "created_at": "2026-09-01T00:00:00Z"})
    save_state(bound)
    return bound


def test_local_up_carries_sessions_and_created_at_forward(tmp_path, monkeypatch) -> None:
    repo, _runner, target, st = _upped(tmp_path, monkeypatch)
    _bind(st)
    again = target.up(None, st.branch)
    assert again.sessions == [_BOUND]
    assert again.created_at == "2026-09-01T00:00:00Z"
    assert load_state(repo, st.branch) == again


def test_host_up_carries_sessions_and_created_at_forward(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)
    target = HostWorktreeTarget(repo, runner=FakeRunner())
    st = target.up(profile=None, branch="feat/x")
    _bind(st)
    again = target.up(profile=None, branch="feat/x")
    assert again.sessions == [_BOUND]
    assert again.created_at == "2026-09-01T00:00:00Z"
    assert load_state(repo, "feat/x") == again


# ---------- CLI ----------


@pytest.fixture()
def cli_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("FR_ISOLATION_TARGET", raising=False)
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda _root: None)
    return make_repo(tmp_path, ["dev"], default="dev")


def _cli_run(ps: str, record: list):
    def run(argv, cwd=None, check=False, capture=True):
        if argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
        record.append(list(argv))
        out = ps if argv[:2] == ["docker", "ps"] else ""
        if argv[:2] == ["docker", "inspect"]:
            out = "img\n"
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

    return run


def test_cli_exec_isolation_error_exits_2_with_one_line(cli_repo, monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(isolation_cmd, "_runner", _cli_run("", calls))
    cli.invoke(app, ["isolation", "up", "--repo", str(cli_repo), "--branch", "feat/e"])
    res = cli.invoke(
        app, ["isolation", "exec", "--repo", str(cli_repo), "--branch", "feat/e", "--", "ls"]
    )
    assert res.exit_code == 2, res.output
    assert res.exception is None or isinstance(res.exception, SystemExit), res.exception
    assert "fr isolation rebuild --branch feat/e" in res.output
    assert "Traceback" not in res.output


def test_cli_rebuild_prints_recreated_line(cli_repo, monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(isolation_cmd, "_runner", _cli_run("cid1 running", calls))
    cli.invoke(app, ["isolation", "up", "--repo", str(cli_repo), "--branch", "feat/r"])
    calls.clear()
    res = cli.invoke(
        app,
        ["isolation", "rebuild", "--repo", str(cli_repo), "--branch", "feat/r", "--no-cache"],
    )
    assert res.exit_code == 0, res.output
    assert "isolation rebuild:" in res.output and "recreated" in res.output
    assert "devcontainer.json" in res.output
    (up,) = [c for c in calls if c[:2] == ["devcontainer", "up"]]
    assert "--remove-existing-container" in up and "--build-no-cache" in up


def test_cli_rebuild_help_says_branch_profile_and_restart_help_says_no_profile(
    cli_repo,
) -> None:
    rebuild_help = cli.invoke(app, ["isolation", "rebuild", "--help"]).output
    assert "branch" in rebuild_help.lower() and "profile" in rebuild_help.lower()
    restart_help = " ".join(cli.invoke(app, ["isolation", "restart", "--help"]).output.split())
    assert "rebuild" in restart_help and "stopped" in restart_help
