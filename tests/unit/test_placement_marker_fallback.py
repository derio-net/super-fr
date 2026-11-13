"""A missing or unusable `.fr-isolation` marker never reads as `repo` (review pr1431-r2).

Stealth is recorded in the workspace's marker, and quiet's "sticky" check reads it too.
When the marker is gone (`git clean -fdx` removes it: it is excluded, not tracked) fr
asks the workspace's isolation state, which still records the placement, and refuses,
naming the `fr isolation up` that restores it. A marker that is there but cannot be
validated (truncated, recorded for another toplevel, a non-string placement) refuses
too. `fr isolation up` itself repairs it.

Target and tracking repos are LOCAL bare repos.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fr.artifacts.paths import outside_repo, space_for
from fr.cli import app
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.marker import MARKER
from fr.placement import quiet, stealth
from fr.settings import SettingsError
from typer.testing import CliRunner

from tests.unit.settings_repo import git, make_repo
from tests.unit.stealth_repo import make_tracking, stealth_home
from tests.unit.test_placement_quiet import QUIET, push_fr_branch

__all__ = ["stealth_home"]


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")
    quiet._CACHE.clear()


def _stealth_ws(tmp_path: Path) -> tuple[Path, Path, Path]:
    """(target clone, tracking bare repo, stealth workspace on feat/z)."""
    target = make_repo(tmp_path)
    track = make_tracking(tmp_path)
    ws = (
        HostWorktreeTarget(target)
        .up(profile=None, branch="feat/z", stealth=stealth.parse_ref(f"{track}@main"))
        .worktree
    )
    return target, track, ws


def _fr(ws: Path, *argv: str):  # type: ignore[no-untyped-def]
    return CliRunner().invoke(app, list(argv), env={**os.environ, "FR_REPO_ROOT": str(ws)})


def test_git_clean_in_a_stealth_workspace_refuses_and_nothing_reaches_the_target(
    tmp_path: Path,
) -> None:
    target, _track, ws = _stealth_ws(tmp_path)
    origin = tmp_path / "origin.git"
    head = git(ws, "rev-parse", "HEAD").strip()
    git(ws, "clean", "-q", "-fdx")
    assert not (ws / MARKER).exists()

    with pytest.raises(SettingsError, match=r"fr isolation up .*--stealth"):
        outside_repo(ws)
    added = _fr(ws, "journal", "add", "--scope", "debug", "--slug", "2026-11-13-z",
                "--kind", "discovery", "--title", "t", "--body", "b")  # fmt: skip
    assert added.exit_code != 0
    pushed = _fr(ws, "push")
    assert pushed.exit_code != 0
    assert git(ws, "rev-parse", "HEAD").strip() == head
    assert git(ws, "status", "--porcelain").strip() == ""
    assert git(origin, "for-each-ref", "--format=%(refname)", "refs/heads/feat").strip() == ""


def test_fr_isolation_up_restores_the_marker(tmp_path: Path) -> None:
    target, track, ws = _stealth_ws(tmp_path)
    git(ws, "clean", "-q", "-fdx")
    HostWorktreeTarget(target).up(
        profile=None, branch="feat/z", stealth=stealth.parse_ref(f"{track}@main")
    )
    assert (ws / MARKER).is_file()
    assert outside_repo(ws) == "stealth"


def test_a_quiet_workspace_with_its_marker_gone_refuses(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    push_fr_branch(repo, QUIET)
    ws = HostWorktreeTarget(repo).up(profile=None, branch="feat/q").worktree
    (ws / MARKER).unlink()
    with pytest.raises(SettingsError, match=r"fr isolation up --branch feat/q"):
        space_for(ws, create=False)


@pytest.mark.parametrize(
    "spoil",
    [
        lambda data, ws: '{"placement": "stea',
        lambda data, ws: json.dumps({**data, "toplevel": str(ws.parent / "elsewhere")}),
        lambda data, ws: json.dumps({**data, "placement": ["stealth"]}),
    ],
    ids=["truncated", "toplevel-mismatch", "non-string-placement"],
)
def test_a_marker_that_cannot_be_validated_refuses(tmp_path: Path, spoil) -> None:  # type: ignore[no-untyped-def]
    _target, _track, ws = _stealth_ws(tmp_path)
    marker = ws / MARKER
    marker.write_text(spoil(json.loads(marker.read_text()), ws))
    with pytest.raises(SettingsError, match="marker"):
        outside_repo(ws)


def test_the_base_clone_with_no_marker_is_still_repo(tmp_path: Path) -> None:
    target, _track, _ws = _stealth_ws(tmp_path)
    assert outside_repo(target) is None
