"""Phase 5 (re-integration addendum): `--secret` is devcontainer-mode only.

`HostWorktreeTarget` and `ExternalTarget` already carry their credentials (ESO
env on the pods, whatever the preparer placed inside), and wrapping a command
there would run `infisical run` OUTSIDE the container boundary the design
depends on. So both targets refuse a non-empty `keys` with an actionable
IsolationError naming devcontainer mode, and run nothing; with `keys=()` they
behave exactly as before. The CLI maps the refusal to exit 2.

Recording runners delegate git to the real binary and record every argv, so
"the runner was never called for the user command" is asserted structurally.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from fr.commands import isolation_cmd
from fr.isolation.external import ExternalTarget
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.types import IsolationError
from typer.testing import CliRunner

from tests.unit.test_isolation import make_repo
from tests.unit.test_isolation_external import RecordingRunner as ExternalRunner
from tests.unit.test_isolation_external import _write_marker
from tests.unit.test_isolation_hostworktree import RecordingRunner as HostRunner

runner = CliRunner()


# ---------- HostWorktreeTarget ----------


def _host_upped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = make_repo(tmp_path)
    rec = HostRunner()
    target = HostWorktreeTarget(repo, runner=rec)
    st = target.up(profile=None, branch="feat/x")
    rec.calls.clear()
    return rec, target, st


def test_hostworktree_exec_with_keys_refuses_and_runs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec, target, st = _host_upped(tmp_path, monkeypatch)
    with pytest.raises(IsolationError) as ei:
        target.exec(st, ["echo", "hi"], keys=["K"])
    assert "devcontainer" in str(ei.value)
    assert rec.calls == []  # the runner was never called — nothing ran


def test_hostworktree_exec_without_keys_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec, target, st = _host_upped(tmp_path, monkeypatch)
    assert target.exec(st, ["echo", "hi"], keys=()) == 0
    assert rec.calls[-1] == ["echo", "hi"]  # verbatim, no wrapper


# ---------- ExternalTarget ----------


def _external_upped(tmp_path: Path):
    repo = make_repo(tmp_path)
    _write_marker(repo)
    rec = ExternalRunner()
    target = ExternalTarget(repo, runner=rec)
    st = target.up(profile=None, branch="feat/x")
    rec.calls.clear()
    return rec, target, st


def test_external_exec_with_keys_refuses_and_runs_nothing(tmp_path: Path) -> None:
    rec, target, st = _external_upped(tmp_path)
    with pytest.raises(IsolationError) as ei:
        target.exec(st, ["echo", "hi"], keys=["K"])
    assert "devcontainer" in str(ei.value)
    assert rec.calls == []


def test_external_exec_without_keys_unchanged(tmp_path: Path) -> None:
    rec, target, st = _external_upped(tmp_path)
    assert target.exec(st, ["echo", "hi"], keys=()) == 0
    assert rec.calls[-1] == ["echo", "hi"]


# ---------- CLI: FR_ISOLATION_TARGET=worktree ----------


def test_cli_secret_in_worktree_mode_exits_2_runs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    monkeypatch.setattr(isolation_cmd, "_gc_spawner", lambda _root: None)
    repo = make_repo(tmp_path)
    calls: list[list[str]] = []

    def run(argv, cwd=None, check=False, capture=True):
        if argv[0] == "git":
            return subprocess.run(argv, cwd=cwd, check=check, capture_output=True, text=True)
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(isolation_cmd, "_runner", run)
    res = runner.invoke(app, ["isolation", "up", "--repo", str(repo), "--branch", "feat/s"])
    assert res.exit_code == 0, res.output

    res = runner.invoke(
        app,
        ["isolation", "exec", "--repo", str(repo), "--branch", "feat/s", "--secret", "K"]
        + ["--", "echo", "hi"],
    )

    assert res.exit_code == 2, res.output
    assert "devcontainer" in res.output
    assert calls == []  # nothing ran on the host either
