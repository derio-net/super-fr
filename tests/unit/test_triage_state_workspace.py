"""`--workspace` beside `--dir`, and the per-host drive lock (spec 2026-10-07-cloud-triage
R4, §B, p3-r3), now that the state itself lives in `~/.cache/fr/triage/<scope>/` (spec
2026-11-19 R17; the move and the cache repository are `test_triage_state_home.py`).

Every repo here is a throwaway under `tmp_path`; nothing touches the checkout under
test (the cwd is moved into the sandbox before any default resolves).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.triage.errors import TriageError
from fr.triage.model import STATE_EXCLUDE, Scope, legacy_state_dir, state_dir

SCOPE = Scope(kind="repo", target="derio-net/super-fr")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _main_and_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "--quiet", "--initial-branch=main")
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(main, "config", k, v)
    (main / "a.txt").write_text("a\n")
    _git(main, "add", ".")
    _git(main, "commit", "--quiet", "-m", "seed")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "--quiet", "-b", "feat", str(wt))
    return main, wt


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    return h


def _exclude(main: Path) -> str:
    path = main / ".git" / "info" / "exclude"
    return path.read_text() if path.exists() else ""


def test_dir_keeps_winning_and_touches_no_exclude(tmp_path: Path, home: Path) -> None:
    main, wt = _main_and_worktree(tmp_path)
    before = _exclude(main)

    assert state_dir(SCOPE, tmp_path / "elsewhere", workspace=wt) == tmp_path / "elsewhere"
    assert _exclude(main) == before


def test_a_workspace_that_is_no_clone_is_refused(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "not-a-clone"
    outside.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    with pytest.raises(TriageError, match="--workspace"):
        state_dir(SCOPE, workspace=outside)


def test_the_commands_take_workspace_beside_dir(tmp_path: Path, home: Path) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    main, wt = _main_and_worktree(tmp_path)
    result = CliRunner().invoke(
        app, ["triage", "batch", "list", "--repo", SCOPE.target, "--workspace", str(wt)]
    )

    assert result.exit_code == 0, result.output
    assert "no batches" in result.output
    assert STATE_EXCLUDE not in _exclude(main).splitlines()  # S1: nothing in the clone
    assert not (wt / ".fr" / "triage-state").exists()
    assert (legacy_state_dir(SCOPE) / ".git").is_dir()


def test_a_command_outside_any_clone_uses_the_cache(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    outside = tmp_path / "not-a-clone"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    result = CliRunner().invoke(app, ["triage", "batch", "list", "--org", "derio-net"])

    assert result.exit_code == 0, result.output
    assert "no batches" in result.output
    assert not (outside / ".fr").exists()


# ------------------------------------------- drive.lock stays per host (p3-r3)


def test_the_drive_lock_lives_in_the_home_cache_whatever_the_workspace(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.cli import app
    from fr.commands import triage_batch_cmd
    from typer.testing import CliRunner

    _, wt = _main_and_worktree(tmp_path)
    taken: list[Path] = []

    class _StopError(Exception):
        pass

    def lock(where: Path) -> object:
        taken.append(where)
        raise _StopError

    monkeypatch.setattr(triage_batch_cmd, "drive_lock", lock)

    result = CliRunner().invoke(
        app, ["triage", "batch", "drive", "--repo", SCOPE.target, "--workspace", str(wt)]
    )

    assert isinstance(result.exception, _StopError), result.output
    assert taken == [legacy_state_dir(SCOPE)]


def test_a_watch_in_one_clone_sees_a_drive_from_another(tmp_path: Path, home: Path) -> None:
    import json
    import os

    from fr.cli import app
    from typer.testing import CliRunner

    _, wt = _main_and_worktree(tmp_path)
    lock = legacy_state_dir(SCOPE) / "drive.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text(json.dumps({"pid": os.getpid(), "started": "x"}))

    result = CliRunner().invoke(
        app, ["triage", "batches", "--repo", SCOPE.target, "--workspace", str(wt), "--watch"]
    )

    assert result.exit_code == 2, result.output
    assert "drive.lock" in result.output
