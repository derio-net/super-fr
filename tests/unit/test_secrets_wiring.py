"""Phase 3/5: SecretProvider wired into the devcontainer Target (up/exec/down)
+ the `fr isolation exec --secret` CLI. The provider_factory seam (like the
Runner seam) lets these run without a live Infisical."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import isolation_cmd
from fr.isolation.local import LocalWorktreeDevcontainerTarget
from fr.isolation.secrets import (
    ExecWrap,
    InfisicalProvider,
    ProfileContext,
    UniversalAuth,
    host_token_dir,
)
from fr.isolation.types import IsolationError, IsolationState
from typer.testing import CliRunner

from tests.unit.test_isolation import make_repo

runner = CliRunner()


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv, cwd=None, check=False, capture=True):
        if argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, check=check, capture_output=True, text=True)
        self.calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def argv_for(self, binary: str) -> list[list[str]]:
        return [c for c in self.calls if c[0] == binary]


def _fake_mint(argv, env) -> str:
    return "tok-secret"


def _infisical_factory(ctx: ProfileContext) -> InfisicalProvider:
    return InfisicalProvider(auth=UniversalAuth(minter=_fake_mint), validate=lambda c: None)


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, IsolationState]:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    repo.mkdir()
    wt = tmp_path / "wt"
    d = wt / ".devcontainer" / "sec"
    d.mkdir(parents=True)
    (d / "devcontainer.json").write_text('{"image": "x"}')
    (wt / ".devcontainer" / "fr-profiles.yaml").write_text(
        "default: sec\n"
        "profiles:\n"
        "  sec:\n"
        "    secret_provider: infisical\n"
        "    secrets: [DEPLOY_KEY]\n"
        "    infisical:\n"
        "      project_id: p1\n"
        "      env: prod\n"
        "      path: /fr/x\n"
        "      auth:\n"
        "        method: universal-auth\n"
        "        client_id_env: FR_CID\n"
        "        client_secret_env: FR_CSEC\n"
    )
    st = IsolationState(repo_root=repo, branch="feat/s", worktree=wt, profile="sec", created_at="t")
    return repo, wt, st


def test_exec_with_secret_prefixes_infisical_run_and_hides_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "secret-val")
    repo, _, st = _setup(tmp_path, monkeypatch)
    fr_ = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=fr_, provider_factory=_infisical_factory)

    rc = target.exec(st, ["pytest", "-q"], keys=["DEPLOY_KEY"])

    assert rc == 0
    (call,) = fr_.argv_for("devcontainer")
    flat = " ".join(call)
    assert "infisical" in flat and "run" in flat
    assert "--path /fr/x" in flat
    assert "tok-secret" not in flat  # token rides the mounted file, never argv
    assert call[-2:] == ["pytest", "-q"]  # user command preserved at the tail


def test_exec_undeclared_secret_fails_fast(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _, st = _setup(tmp_path, monkeypatch)
    fr_ = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=fr_, provider_factory=_infisical_factory)

    with pytest.raises(IsolationError) as ei:
        target.exec(st, ["echo", "hi"], keys=["NOPE"])

    assert "NOPE" in str(ei.value)
    assert fr_.argv_for("devcontainer") == []  # fail-fast: nothing ran, nothing minted


def test_exec_secret_uses_no_remote_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The token is conveyed via the mounted file, NOT --remote-env (which is
    # host-ps-visible). Infisical's exec_env is empty → no --remote-env at all.
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "secret-val")
    repo, _, st = _setup(tmp_path, monkeypatch)
    fr_ = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=fr_, provider_factory=_infisical_factory)
    target.exec(st, ["pytest"], keys=["DEPLOY_KEY"])
    (call,) = fr_.argv_for("devcontainer")
    assert "--remote-env" not in call


class _TokenDirWatcher(FakeRunner):
    """Snapshots the host token dir's contents AT exec time, so a test can
    prove the token existed while the command ran and is gone afterwards."""

    def __init__(self, token_dir: Path, fail: bool = False) -> None:
        super().__init__()
        self.token_dir = token_dir
        self.fail = fail
        self.seen: list[str] = []

    def __call__(self, argv, cwd=None, check=False, capture=True):
        if argv[0] == "devcontainer":
            self.seen = [p.read_text() for p in self.token_dir.iterdir()]
            if self.fail:
                raise RuntimeError("boom")  # simulate the exec aborting mid-run
        return super().__call__(argv, cwd=cwd, check=check, capture=capture)


def test_exec_clears_token_after_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "secret-val")
    repo, _, st = _setup(tmp_path, monkeypatch)
    d = host_token_dir("repo", "sec")
    watcher = _TokenDirWatcher(d)
    target = LocalWorktreeDevcontainerTarget(
        repo, runner=watcher, provider_factory=_infisical_factory
    )
    target.exec(st, ["pytest"], keys=["DEPLOY_KEY"])
    assert watcher.seen == ["tok-secret"]  # exactly one per-exec file, live during the run
    assert list(d.iterdir()) == []  # post_exec unlinked it after the command returned


def test_exec_clears_token_on_abort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "secret-val")
    repo, _, st = _setup(tmp_path, monkeypatch)
    d = host_token_dir("repo", "sec")
    watcher = _TokenDirWatcher(d, fail=True)
    target = LocalWorktreeDevcontainerTarget(
        repo, runner=watcher, provider_factory=_infisical_factory
    )
    with pytest.raises(RuntimeError):
        target.exec(st, ["pytest"], keys=["DEPLOY_KEY"])
    assert watcher.seen == ["tok-secret"]
    assert list(d.iterdir()) == []  # finally → post_exec ran even though the exec aborted


def test_exec_without_secret_mints_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _, st = _setup(tmp_path, monkeypatch)  # FR_CID/FR_CSEC deliberately unset
    fr_ = FakeRunner()
    target = LocalWorktreeDevcontainerTarget(repo, runner=fr_, provider_factory=_infisical_factory)
    assert target.exec(st, ["pytest"]) == 0
    (call,) = fr_.argv_for("devcontainer")
    assert "infisical" not in " ".join(call)  # no wrap
    assert not host_token_dir("repo", "sec").exists()  # no mint, no file


class _SpyProvider:
    def __init__(self) -> None:
        self.events: list[str] = []

    def up_prepare(self, ctx: ProfileContext) -> None:
        self.events.append("up_prepare")

    def exec_wrap(self, ctx: ProfileContext, want_secrets: bool) -> ExecWrap:
        self.events.append("exec_wrap")
        return ExecWrap()

    def post_exec(self, ctx: ProfileContext) -> None:
        self.events.append("post_exec")

    def cleanup(self, ctx: ProfileContext) -> None:
        self.events.append("cleanup")


def test_up_and_down_run_provider_up_prepare_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A REAL repo + worktree: 4.x `down` verifies `git worktree remove`, so the
    # 3.x bare-directory fixture would raise after cleanup already ran.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["sec"], default="sec")
    spy = _SpyProvider()
    target = LocalWorktreeDevcontainerTarget(
        repo, runner=FakeRunner(), provider_factory=lambda c: spy
    )

    st = target.up(profile=None, branch="feat/s")
    assert spy.events == ["up_prepare"]
    target.down(st, force=True)

    assert spy.events == ["up_prepare", "cleanup"]
    assert not st.worktree.exists()


@pytest.mark.parametrize("config", ["missing", "corrupt"])
def test_down_removes_token_dir_even_when_profile_config_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, config: str
) -> None:
    """Review finding I1: with the REAL provider_for, a missing fr-profiles.yaml
    falls back to env-file (whose cleanup is a no-op) and a corrupt one raises
    — either way the provider path would skip the token dir. The devcontainer
    teardown removes host_token_dir(repo, profile) unconditionally."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path, ["sec"], default="sec")  # no secret_provider key
    target = LocalWorktreeDevcontainerTarget(repo, runner=FakeRunner())
    st = target.up(profile=None, branch="feat/s")
    cfg = st.worktree / ".devcontainer" / "fr-profiles.yaml"
    if config == "missing":
        cfg.unlink()
    else:
        cfg.write_text("profiles: [unclosed\n")
    d = host_token_dir("repo", "sec")
    d.mkdir(parents=True)
    (d / "leftover.token").write_text("tok-old")  # a crash left a token behind

    target.down(st, force=True)

    assert not d.exists()
    assert not st.worktree.exists()  # the teardown itself was not blocked


def test_cli_secret_undeclared_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    d = r / ".devcontainer" / "dev"  # env-file profile, no secrets declared
    d.mkdir(parents=True)
    (d / "devcontainer.json").write_text('{"image": "x"}')
    subprocess.run(["git", "-C", str(r), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(r), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
        check=True,
    )
    calls: list[list[str]] = []

    def run(argv, cwd=None, check=False, capture=True):
        if argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, check=check, capture_output=True, text=True)
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(isolation_cmd, "_runner", run)
    runner.invoke(app, ["isolation", "up", "--repo", str(r), "--branch", "feat/s"])

    res = runner.invoke(
        app,
        [
            "isolation",
            "exec",
            "--repo",
            str(r),
            "--branch",
            "feat/s",
            "--secret",
            "NOPE",
            "--",
            "echo",
            "hi",
        ],
    )

    assert res.exit_code == 2, res.output
    assert "NOPE" in res.output
    assert not any(c[:2] == ["devcontainer", "exec"] for c in calls)  # fail-fast
