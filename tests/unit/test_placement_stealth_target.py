"""No fr file and no forge write reaches a stealth target (spec
2026-11-04-repo-feature-settings R24 "what reaches the target"; review p4-r3, p4-r5,
p4-r9). Local bare repos only; the forge is never called (a call would be a trace).
"""

from __future__ import annotations

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


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """(stealth workspace, tracking bare repo, target's bare origin); cwd in the workspace."""
    target, track = stealth_pair(tmp_path)
    state = HostWorktreeTarget(target).up(
        profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
    )
    monkeypatch.chdir(state.worktree)
    return state.worktree, track, tmp_path / "origin.git"


def _fr(root: Path, *argv: str):
    return CliRunner().invoke(app, list(argv), env={**os.environ, "VK_REPO_ROOT": str(root)})


def _files(root: Path) -> set[str]:
    return {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


@pytest.mark.parametrize(
    "argv",
    [
        ("init", "agents"),
        ("init", "validator-wrapper"),
        ("init", "scaffold", "--profile", "dev", "--purpose", "p", "--ci", "none",
         "--tracking", "none"),
        ("init", "migrate", "--yes"),
        ("settings", "init"),
        ("settings", "init", "--quiet"),
    ],
)  # fmt: skip
def test_repo_configuration_writers_refuse_before_writing(
    ws: tuple[Path, Path, Path], argv: tuple[str, ...]
) -> None:
    root, _, origin = ws
    before = _files(root)
    refs_before = git(origin, "show-ref")
    result = _fr(root, *argv)
    assert result.exit_code == 2, result.output
    assert "placement stealth" in " ".join(result.output.split())
    assert _files(root) == before
    assert git(origin, "show-ref") == refs_before


def test_push_refuses_a_commit_carrying_an_fr_path(ws: tuple[Path, Path, Path]) -> None:
    root, _, origin = ws
    agent = root / ".claude/agents/fr-phase-executor.md"
    agent.parent.mkdir(parents=True)
    agent.write_text("an fr agent, written by hand\n")
    (root / "code.txt").write_text("code\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "feat(s): code")
    result = _fr(root, "push")
    assert result.exit_code == 2, result.output
    assert ".claude/agents/fr-phase-executor.md" in " ".join(result.output.split())
    assert "refs/heads/feat/s" not in git(origin, "show-ref")


def test_push_sends_a_code_only_commit(ws: tuple[Path, Path, Path]) -> None:
    root, _, origin = ws
    (root / "code.txt").write_text("code\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "feat(s): code")
    assert _fr(root, "push").exit_code == 0
    assert "refs/heads/feat/s" in git(origin, "show-ref")


def test_up_again_on_a_stealth_workspace_with_a_plan_needs_no_validator_wrapper(
    ws: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Review p4-r4: the plans live in the tracking repo, so the product branch owes no
    scripts/validate-plans.sh, and re-entering the workspace does not demand one."""
    root, track, _ = ws
    made = _fr(root, "plan", "create", "--slug", "2026-11-12-s", "--target-repo", "derio-net/s")
    assert made.exit_code == 0, made.output
    assert not (root / "scripts/validate-plans.sh").exists()
    again = HostWorktreeTarget(tmp_path / "work").up(
        profile=None, branch="feat/s", stealth=stealth.parse_ref(f"{track}@main")
    )
    assert again.worktree == root
