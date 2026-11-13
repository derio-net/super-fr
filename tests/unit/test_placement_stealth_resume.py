"""Resume and dispatch refusal (spec 2026-11-04-repo-feature-settings R24 "resume";
plan 2026-11-12-placement-resolver phase 4, task 5).

"Another host" is a fresh HOME and a second clone of the target: nothing it has comes
from the first host except what the two remotes hold. All repos are local bare repos.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fr.cli import app
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.placement import stealth
from typer.testing import CliRunner

from tests.unit.settings_repo import git
from tests.unit.stealth_repo import stealth_home, stealth_pair

__all__ = ["stealth_home"]

STATE = "local--origin/features/feat__s/docs/superpowers/runs/r1.stealth.json"


def _fr(root: Path, *argv: str, env: dict[str, str] | None = None):
    return CliRunner().invoke(
        app, list(argv), env={**os.environ, "FR_REPO_ROOT": str(root), **(env or {})}
    )


@pytest.fixture
def started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """Host one: a stealth run r1 on feat/s with one pushed code commit. Returns
    (host-one workspace, tracking bare repo, target bare origin)."""
    target, track = stealth_pair(tmp_path)
    state = HostWorktreeTarget(target).up(
        profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
    )
    monkeypatch.chdir(state.worktree)
    root = state.worktree
    (root / "code.txt").write_text("one\n")
    git(root, "add", "code.txt")
    git(root, "commit", "-qm", "feat(s): one")
    assert _fr(root, "push").exit_code == 0
    result = _fr(root, "run", "start", "fr-goal", "--branch", "feat/s", "--run-id", "r1")
    assert result.exit_code == 0, result.output
    return root, track, tmp_path / "origin.git"


def _recorded(track: Path) -> dict[str, str]:
    return json.loads(git(track, "show", f"main:{STATE}"))


def _host_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Path) -> Path:
    home = tmp_path / "home2"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    stealth.reset_caches()
    clone = tmp_path / "host2" / "origin"
    clone.parent.mkdir()
    git(tmp_path, "clone", "-q", str(origin), str(clone))
    git(clone, "config", "user.name", "t")
    git(clone, "config", "user.email", "t@example.invalid")
    monkeypatch.chdir(clone)
    return clone


def test_the_state_records_the_pushed_product_head(started: tuple[Path, Path, Path]) -> None:
    root, track, _ = started
    data = _recorded(track)
    assert data["target_branch"] == "feat/s"
    assert data["product_head"] == git(root, "rev-parse", "HEAD").strip()
    cursor = git(track, "show", f"main:{STATE.replace('.stealth.json', '.yaml')}")
    assert "product_head" not in cursor  # beside the cursor, never in it


def test_resume_on_another_host_when_equal(
    started: tuple[Path, Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, track, origin = started
    clone = _host_two(tmp_path, monkeypatch, origin)
    before = git(track, "rev-parse", "main")
    result = _fr(clone, "isolation", "up", "--stealth", f"{track}@main", "--resume", "r1",
                 env={"FR_ISOLATION_TARGET": "worktree"})  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "agree" in result.output
    assert git(track, "rev-parse", "main") == before  # nothing to redo
    wt = Path(os.environ["HOME"]) / ".cache/fr/worktrees/origin/feat__s"
    assert (wt / "code.txt").read_text() == "one\n"


def test_resume_redoes_the_bookkeeping_when_the_branch_is_ahead(
    started: tuple[Path, Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, track, origin = started
    (root / "code.txt").write_text("two\n")
    git(root, "commit", "-qam", "feat(s): two")
    git(root, "push", "-q", "origin", "feat/s")  # code pushed, no state write after it
    ahead = git(root, "rev-parse", "HEAD").strip()
    assert _recorded(track)["product_head"] != ahead
    clone = _host_two(tmp_path, monkeypatch, origin)
    result = _fr(clone, "isolation", "up", "--stealth", f"{track}@main", "--resume", "r1",
                 env={"FR_ISOLATION_TARGET": "worktree"})  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "bookkeeping was redone" in " ".join(result.output.split())
    assert _recorded(track)["product_head"] == ahead
    again = _fr(clone, "isolation", "up", "--stealth", f"{track}@main", "--resume", "r1",
                env={"FR_ISOLATION_TARGET": "worktree"})  # fmt: skip
    assert again.exit_code == 0 and "agree" in again.output  # idempotent


def test_resume_refuses_when_the_state_is_ahead_naming_the_sha(
    started: tuple[Path, Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, track, origin = started
    recorded = _recorded(track)["product_head"]
    git(root, "push", "-q", "--force", "origin", "main:feat/s")  # the code was lost
    clone = _host_two(tmp_path, monkeypatch, origin)
    result = _fr(clone, "isolation", "up", "--stealth", f"{track}@main", "--resume", "r1",
                 env={"FR_ISOLATION_TARGET": "worktree"})  # fmt: skip
    assert result.exit_code == 2, result.output
    assert recorded in " ".join(result.output.split())
    assert not (Path(os.environ["HOME"]) / ".cache/fr/worktrees/origin/feat__s").exists()


def test_apply_to_is_refused_under_stealth_naming_the_placement(
    started: tuple[Path, Path, Path],
) -> None:
    root, _, _ = started
    result = _fr(root, "apply", "--to", "vk")
    assert result.exit_code == 2, result.output
    assert "placement stealth" in " ".join(result.output.split())
