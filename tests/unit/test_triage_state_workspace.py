"""A scope's state lives in the workspace that runs the driver (spec
2026-10-07-cloud-triage R4, §B, Test Plan 4).

Every repo here is a throwaway under `tmp_path`; nothing touches the checkout under
test (the cwd is moved into the sandbox before any default resolves).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.triage.errors import TriageError
from fr.triage.model import STATE_EXCLUDE, Scope, state_dir

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
    return (main / ".git" / "info" / "exclude").read_text()


def test_state_lives_in_the_workspace_and_is_excluded_through_the_common_dir(
    tmp_path: Path, home: Path
) -> None:
    main, wt = _main_and_worktree(tmp_path)

    got = state_dir(SCOPE, workspace=wt)

    assert got == wt / ".fr" / "triage-state" / SCOPE.name
    assert STATE_EXCLUDE == ".fr/triage-state/"
    assert _exclude(main).splitlines().count(STATE_EXCLUDE) == 1
    got.mkdir(parents=True, exist_ok=True)
    (got / "judgements.yaml").write_text("schema: 6\n")
    assert _git(wt, "status", "--porcelain", "--untracked-files=all") == ""
    assert _git(main, "status", "--porcelain", "--untracked-files=all") == ""


def test_the_exclude_entry_is_written_once(tmp_path: Path, home: Path) -> None:
    main, wt = _main_and_worktree(tmp_path)

    state_dir(SCOPE, workspace=wt)
    state_dir(SCOPE, workspace=wt)
    state_dir(SCOPE, workspace=main)

    assert _exclude(main).splitlines().count(STATE_EXCLUDE) == 1


def test_the_workspace_defaults_to_the_toplevel_of_the_working_directory(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, wt = _main_and_worktree(tmp_path)
    sub = wt / "deep" / "er"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)

    assert state_dir(SCOPE) == wt / ".fr" / "triage-state" / SCOPE.name


def test_a_workspace_given_below_its_toplevel_resolves_to_the_toplevel(
    tmp_path: Path, home: Path
) -> None:
    _, wt = _main_and_worktree(tmp_path)
    (wt / "sub").mkdir()

    assert state_dir(SCOPE, workspace=wt / "sub") == wt / ".fr" / "triage-state" / SCOPE.name


def test_dir_keeps_winning_and_touches_no_exclude(tmp_path: Path, home: Path) -> None:
    main, wt = _main_and_worktree(tmp_path)
    before = _exclude(main)

    assert state_dir(SCOPE, tmp_path / "elsewhere", workspace=wt) == tmp_path / "elsewhere"
    assert _exclude(main) == before


def test_the_home_cache_is_imported_once_and_left_in_place(tmp_path: Path, home: Path) -> None:
    _, wt = _main_and_worktree(tmp_path)
    cache = home / ".cache" / "fr" / "triage" / SCOPE.name
    (cache / "board").mkdir(parents=True)
    (cache / "judgements.yaml").write_text("schema: 6\nissues: {}\n")
    (cache / "board" / "manifest.yaml").write_text("fragments: []\n")

    got = state_dir(SCOPE, workspace=wt)

    assert (got / "judgements.yaml").read_text() == "schema: 6\nissues: {}\n"
    assert (got / "board" / "manifest.yaml").read_text() == "fragments: []\n"
    assert (cache / "judgements.yaml").read_text() == "schema: 6\nissues: {}\n"  # left in place

    (got / "judgements.yaml").write_text("schema: 6\nissues: {edited: true}\n")
    (cache / "judgements.yaml").write_text("schema: 6\nissues: {later: true}\n")
    state_dir(SCOPE, workspace=wt)

    assert (got / "judgements.yaml").read_text() == "schema: 6\nissues: {edited: true}\n"


def test_no_cache_means_nothing_is_created_beyond_the_exclude(tmp_path: Path, home: Path) -> None:
    _, wt = _main_and_worktree(tmp_path)

    got = state_dir(SCOPE, workspace=wt)

    assert not got.exists()


@pytest.mark.parametrize(
    "scope",
    [
        Scope(kind="org", target="derio-net"),
        Scope.group(["derio-net/a", "derio-net/b"]),
        SCOPE,
    ],
)
def test_outside_any_clone_with_no_workspace_is_refused_naming_the_flag(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch, scope: Scope
) -> None:
    outside = tmp_path / "not-a-clone"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    with pytest.raises(TriageError, match="--workspace"):
        state_dir(scope)


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
    assert STATE_EXCLUDE in _exclude(main).splitlines()


def test_a_command_outside_any_clone_exits_2_naming_workspace(
    tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    outside = tmp_path / "not-a-clone"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    result = CliRunner().invoke(app, ["triage", "check", "--org", "derio-net"])

    assert result.exit_code == 2
    assert "--workspace" in result.output
