"""hermes/fr-isolation-guard.sh — Hermes terminal/execute_code git/gh gate.

Unlike the Claude fr-isolation-guard.sh (which is pipeline-sentinel-based and
blocks ALL base-repo commands), the Hermes guard is MARKER-based and
session-independent: it blocks git/gh mutations whose effective cwd is an
fr-enabled base clone lacking a valid isolation worktree. Escapes: `fr isolation
…`, a leading `cd <worktree>`, and FR_BASE_OK=1. Read-only / unknown commands
pass (a discipline backstop, not a security boundary).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "hermes" / "fr-isolation-guard.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="hermes guard needs git",
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def fr_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "README.md").write_text("x\n")
    d = repo / ".devcontainer" / "dev"
    d.mkdir(parents=True)
    (d / "devcontainer.json").write_text('{"image": "x"}\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def linked_worktree(repo: Path, branch: str = "feat/x") -> Path:
    wt = repo.parent / f"{repo.name}-wt"
    _git(repo, "worktree", "add", "-q", str(wt), "-b", branch)
    (wt / ".fr-isolation").write_text(
        f'{{"toplevel": "{wt.resolve()}", "branch": "{branch}", "mode": "worktree"}}'
    )
    return wt


def payload(command: str, cwd: Path, tool: str = "terminal") -> dict:
    return {
        "hook_event_name": "pre_tool_call",
        "tool_name": tool,
        "tool_input": {"command": command},
        "cwd": str(cwd),
    }


def run_hook(p: dict, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(p),
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def blocked(result: subprocess.CompletedProcess[str]) -> bool:
    if not result.stdout.strip():
        return False
    return json.loads(result.stdout).get("decision") == "block"


def allowed(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode == 0 and not result.stdout.strip()


def test_git_commit_in_base_clone_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert blocked(run_hook(payload("git commit -m x", repo)))


def test_git_push_in_base_clone_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert blocked(run_hook(payload("git push origin main", repo)))


def test_gh_pr_create_in_base_clone_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert blocked(run_hook(payload("gh pr create --fill", repo)))


def test_git_commit_in_worktree_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    assert allowed(run_hook(payload("git commit -m x", wt)))


def test_readonly_git_in_base_clone_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert allowed(run_hook(payload("git status", repo)))


def test_fr_isolation_command_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert allowed(run_hook(payload("fr isolation up --branch feat/y", repo)))


def test_cd_into_worktree_transition_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    assert allowed(run_hook(payload(f"cd {wt} && git push", repo)))


def test_fr_base_ok_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert allowed(run_hook(payload("git commit -m x", repo), env={"FR_BASE_OK": "1"}))


def test_non_bash_tool_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert allowed(run_hook(payload("git commit -m x", repo, tool="write_file")))


def test_execute_code_tool_is_gated(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert blocked(run_hook(payload("git push", repo, tool="execute_code")))
