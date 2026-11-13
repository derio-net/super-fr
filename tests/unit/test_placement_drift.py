"""Placement drift and `fr placement migrate-branch` (spec 2026-11-04-repo-feature-settings
R28; plan 2026-11-12-placement-resolver phase 7, task 2).

A workspace branch whose artifacts do not match the repo's current placement must
migrate before it can merge. The CLI-entry gate, `fr push`, `deliver` and `fr validate
artifacts` only detect it and refuse, naming `fr placement migrate-branch`; that command,
in a valid workspace, migrates. Every repo is a local sandbox with a bare origin.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer
from fr.artifacts.paths import KIND_DIRS
from fr.artifacts.trigger import ensure_artifacts_current
from fr.cli import app
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.marker import marker_at
from fr.placement import drift, quiet, stealth
from fr.settings import SettingsError
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.test_placement_quiet import QUIET

FRAG = f"{KIND_DIRS['acceptance-fragment']}/2026-02-01-live.yaml"
FRAG_TEXT = "schema_version: 1\nfeature: 2026-02-01-live\nrepo: derio-net/widgets\nrows: []\n"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    stealth.reset_caches()
    yield home
    stealth.reset_caches()


def _switch_to(root: Path, settings_text: str) -> None:
    """Point origin's `fr` at *settings_text* (a new commit, never forced) and fetch it."""
    probe = subprocess.run(
        ["git", "ls-remote", "--exit-code", "origin", "refs/heads/fr"], cwd=root, check=False,
        capture_output=True,
    )  # fmt: skip
    scratch = root.parent / "fr-scratch"
    if probe.returncode == 0:
        url = git(root, "remote", "get-url", "origin").strip()
        git(root.parent, "clone", "-q", "-b", "fr", url, str(scratch))
    else:
        git(root.parent, "init", "-q", "-b", "fr", str(scratch))
        git(scratch, "remote", "add", "origin", git(root, "remote", "get-url", "origin").strip())
    git(scratch, "config", "user.name", "t")
    git(scratch, "config", "user.email", "t@example.invalid")
    (scratch / "settings.yaml").write_text(settings_text)
    git(scratch, "add", "-A")
    git(scratch, "commit", "-qm", "chore(fr): switch")
    git(scratch, "push", "-q", "origin", "fr")
    subprocess.run(["rm", "-rf", str(scratch)], check=True)
    git(root, "fetch", "-q", "origin", quiet.FETCH_REFSPEC)
    quiet._CACHE.clear()


def drifted(tmp_path: Path) -> tuple[Path, Path]:
    """(base clone, workspace): feat/live was set up under repo and carries a fragment;
    then the repo went quiet."""
    root = make_repo(tmp_path)
    ws = HostWorktreeTarget(root).up(profile=None, branch="feat/live").worktree
    (ws / FRAG).parent.mkdir(parents=True, exist_ok=True)
    (ws / FRAG).write_text(FRAG_TEXT)
    git(ws, "add", "--", FRAG)
    git(ws, "commit", "-qm", "chore(fr): acceptance row")
    _switch_to(root, QUIET)
    return root, ws


def _gate(root: Path, sub: str, env: dict[str, str] | None = None) -> list[str]:
    lines: list[str] = []
    ensure_artifacts_current(
        argv=[], invoked_subcommand=sub, env=env or {}, repo_root=root, err=lines.append
    )
    return lines


# --- detection ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "env", [{}, {"CI": "true"}, {"FR_SKIP_MIGRATION": "1"}], ids=["plain", "ci", "skip"]
)
def test_the_gate_refuses_a_drifted_workspace_naming_migrate_branch(
    tmp_path: Path, env: dict[str, str]
) -> None:
    _, ws = drifted(tmp_path)
    head = git(ws, "rev-parse", "HEAD")
    lines: list[str] = []
    with pytest.raises(typer.Exit) as e:
        ensure_artifacts_current(
            argv=[], invoked_subcommand="run", env=env, repo_root=ws, err=lines.append
        )
    assert e.value.exit_code == 2
    text = "\n".join(lines)
    assert "fr placement migrate-branch" in text
    assert "placement: repo" in text and "quiet" in text
    # detection only: nothing moved
    assert git(ws, "rev-parse", "HEAD") == head
    assert git(ws, "status", "--porcelain").strip() == ""
    assert not (quiet.worktree_path(ws) / "features").exists()


def test_the_gate_lets_placement_and_exempt_commands_through(tmp_path: Path) -> None:
    _, ws = drifted(tmp_path)
    assert _gate(ws, "placement") == []
    assert _gate(ws, "status") == []


def test_detection_is_filesystem_only_without_a_marker_or_a_switch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path)
    ws = HostWorktreeTarget(root).up(profile=None, branch="feat/plain").worktree

    def no_process(*a: Any, **k: Any) -> Any:
        raise AssertionError(f"drift detection spawned a process: {a[0] if a else k}")

    monkeypatch.setattr(subprocess, "run", no_process)
    monkeypatch.setattr(subprocess, "Popen", no_process)
    assert drift.marker_drift(root) is None  # no marker
    assert drift.marker_drift(ws) is None  # a marker, no switch


def test_fr_push_refuses_a_drifted_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.commands.push_cmd import push_cmd

    root, ws = drifted(tmp_path)
    monkeypatch.setenv("FR_REPO_ROOT", str(ws))
    with pytest.raises(typer.Exit) as e:
        push_cmd()
    assert e.value.exit_code == 2
    assert "fr placement migrate-branch" in capsys.readouterr().err
    assert not git(root, "ls-remote", "origin", "refs/heads/feat/live").strip()


def test_deliver_refuses_a_drifted_branch(tmp_path: Path) -> None:
    from fr.commands.run_cmd import _deliver_placement_gate

    _, ws = drifted(tmp_path)
    with pytest.raises(typer.Exit) as e:
        _deliver_placement_gate(ws)
    assert e.value.exit_code == 2


def test_validate_artifacts_refuses_a_drifted_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, ws = drifted(tmp_path)
    monkeypatch.setenv("FR_REPO_ROOT", str(ws))
    result = CliRunner().invoke(app, ["validate", "artifacts"], env={"CI": "true"})
    assert result.exit_code == 2, result.output
    assert "fr placement migrate-branch" in result.output


def test_a_quiet_branch_carrying_fr_files_is_drift_for_validate_and_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CI has no marker: there the branch's own tree is the evidence (R28's
    `validate-artifacts` clause)."""
    root = make_repo(tmp_path)
    _switch_to(root, QUIET)
    git(root, "checkout", "-q", "-b", "feat/leak")
    (root / FRAG).parent.mkdir(parents=True, exist_ok=True)
    (root / FRAG).write_text(FRAG_TEXT)
    git(root, "add", "-A")
    git(root, "commit", "-qm", "chore(fr): leaked")
    found = drift.detect(root)
    assert found is not None and FRAG in found.files
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    result = CliRunner().invoke(app, ["validate", "artifacts"], env={"CI": "true"})
    assert result.exit_code == 2, result.output
    assert FRAG in result.output


def test_a_repo_branch_with_artifacts_is_not_drift(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    ws = HostWorktreeTarget(root).up(profile=None, branch="feat/ok").worktree
    (ws / FRAG).parent.mkdir(parents=True, exist_ok=True)
    (ws / FRAG).write_text(FRAG_TEXT)
    git(ws, "add", "-A")
    git(ws, "commit", "-qm", "chore(fr): row")
    assert drift.detect(ws) is None
    assert _gate(ws, "run") == []


# --- migrate-branch --------------------------------------------------------------------


def test_migrate_branch_moves_a_repo_branch_into_quiet_and_pushes_both_sides(
    tmp_path: Path,
) -> None:
    root, ws = drifted(tmp_path)
    head = git(ws, "rev-parse", "HEAD").strip()
    lines: list[str] = []
    drift.migrate_branch(ws, emit=lines.append)

    frwt = quiet.worktree_path(ws)
    assert (frwt / "features" / "feat__live" / FRAG).read_text() == FRAG_TEXT
    assert not (ws / FRAG).exists()
    # one commit on each side
    assert git(ws, "rev-list", "--count", f"{head}..HEAD").strip() == "1"
    subject = git(ws, "log", "-1", "--format=%s").strip()
    assert not subject.startswith("chore(fr)")
    assert FRAG in git(frwt, "log", "-2", "--name-only", "--format=")  # then the HEADS record
    # pushed where they belong
    origin = git(root, "remote", "get-url", "origin").strip()
    assert (
        git(Path(origin), "rev-parse", "feat/live").strip() == git(ws, "rev-parse", "HEAD").strip()
    )
    assert f"features/feat__live/{FRAG}" in git(Path(origin), "ls-tree", "-r", "--name-only", "fr")
    assert (marker_at(ws) or {}).get("placement") == "quiet"
    assert drift.detect(ws) is None
    assert _gate(ws, "run") == []
    # idempotent
    drift.migrate_branch(ws, emit=lines.append)
    assert git(ws, "rev-list", "--count", f"{head}..HEAD").strip() == "1"


def test_migrate_branch_refuses_outside_a_valid_workspace(tmp_path: Path) -> None:
    root, _ = drifted(tmp_path)
    with pytest.raises(SettingsError, match="valid workspace"):
        drift.migrate_branch(root, emit=lambda _: None)


def test_migrate_branch_moves_a_quiet_branch_back_into_repo(tmp_path: Path) -> None:
    from fr.artifacts.commit import commit_paths
    from fr.artifacts.paths import artifact_root

    root = make_repo(tmp_path)
    _switch_to(root, QUIET)
    ws = HostWorktreeTarget(root).up(profile=None, branch="feat/q").worktree
    path = artifact_root(ws) / FRAG
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(FRAG_TEXT)
    assert commit_paths(ws, [path], "chore(fr): row").committed
    from fr.git_policy.push import atomic_push

    atomic_push(ws, quiet.worktree_path(ws), "origin", "feat/q", code=True)  # its fr push
    _switch_to(root, QUIET.replace("placement: quiet", "placement: repo"))
    lines: list[str] = []
    with pytest.raises(typer.Exit):
        ensure_artifacts_current(
            argv=[], invoked_subcommand="run", env={}, repo_root=ws, err=lines.append
        )
    assert "fr placement migrate-branch" in "\n".join(lines)

    drift.migrate_branch(ws, emit=lines.append)

    assert (ws / FRAG).read_text() == FRAG_TEXT
    assert git(ws, "status", "--porcelain").strip() == ""
    frwt = quiet.worktree_path(ws)
    assert not (frwt / "features" / "feat__q" / FRAG).exists()
    assert (marker_at(ws) or {}).get("placement") == "repo"
    assert drift.detect(ws) is None
    origin = Path(git(root, "remote", "get-url", "origin").strip())
    assert FRAG in git(origin, "ls-tree", "-r", "--name-only", "feat/q")
