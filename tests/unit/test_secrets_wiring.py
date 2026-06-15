"""Phase 3: SecretProvider wired into the local Target (up/exec/down) + the
`fr isolation exec --secret` CLI. The provider_factory seam (like the Runner
seam) lets these run without a live Infisical."""

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
    host_token_file,
)
from fr.isolation.types import IsolationError, IsolationState
from typer.testing import CliRunner

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


def test_exec_clears_token_after_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "secret-val")
    repo, _, st = _setup(tmp_path, monkeypatch)
    target = LocalWorktreeDevcontainerTarget(
        repo, runner=FakeRunner(), provider_factory=_infisical_factory
    )
    target.exec(st, ["pytest"], keys=["DEPLOY_KEY"])
    # post_exec truncated the token-file after the command returned.
    assert host_token_file("repo", "sec").read_text() == ""


def test_exec_clears_token_on_abort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FR_CID", "id")
    monkeypatch.setenv("FR_CSEC", "secret-val")
    repo, _, st = _setup(tmp_path, monkeypatch)

    class _Boom:
        def __call__(self, argv, cwd=None, check=False, capture=True):
            raise RuntimeError("boom")  # simulate the exec aborting mid-run

    target = LocalWorktreeDevcontainerTarget(
        repo, runner=_Boom(), provider_factory=_infisical_factory
    )
    with pytest.raises(RuntimeError):
        target.exec(st, ["pytest"], keys=["DEPLOY_KEY"])
    # finally → post_exec cleared the token even though the run aborted.
    assert host_token_file("repo", "sec").read_text() == ""


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


def test_down_runs_provider_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _, st = _setup(tmp_path, monkeypatch)
    spy = _SpyProvider()
    target = LocalWorktreeDevcontainerTarget(
        repo, runner=FakeRunner(), provider_factory=lambda c: spy
    )

    target.down(st, force=True)

    assert "cleanup" in spy.events


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
