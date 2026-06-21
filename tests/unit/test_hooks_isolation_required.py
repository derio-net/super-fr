"""fr-isolation-required.sh — PreToolUse(Edit|Write|…) hook.

Blocks edits to tracked source in an fr-enabled repo unless the edit lands in a
valid isolation workspace (marker present + recorded toplevel == current
toplevel + a real linked worktree). Escapes: `.fr-isolation-allow` globlist and
`FR_BASE_OK=1`. Session-independent and complementary to the Bash sentinel
guard (#328 Task 3).

Git calls hit the real binary (cheap throwaway repos), so the hook's
linked-worktree detection is exercised for real.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("git") is None,
    reason="hook needs jq + git",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "fr-isolation-required.sh"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def fr_repo(tmp_path: Path, name: str = "repo", fr_enabled: bool = True) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "README.md").write_text("x\n")
    if fr_enabled:
        d = repo / ".devcontainer" / "dev"
        d.mkdir(parents=True)
        (d / "devcontainer.json").write_text('{"image": "x"}\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def linked_worktree(repo: Path, branch: str = "feat/x") -> Path:
    wt = repo.parent / f"{repo.name}-wt"
    _git(repo, "worktree", "add", "-q", str(wt), "-b", branch)
    return wt


def write_marker(
    root: Path, toplevel: Path, branch: str = "feat/x", mode: str = "worktree"
) -> None:
    (root / ".fr-isolation").write_text(
        json.dumps({"toplevel": str(toplevel.resolve()), "branch": branch, "mode": mode})
    )


def payload(file_path: Path, tool: str = "Edit") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": str(file_path)}}


def run_hook(p: dict, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(p),
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def decision(result: subprocess.CompletedProcess[str]) -> str | None:
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


def allowed(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode == 0 and decision(result) is None


# ---------- allow paths ----------


def test_non_edit_tool_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert allowed(run_hook(payload(repo / "a.py", tool="Bash")))


def test_fr_base_ok_env_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)  # fr-enabled, no marker → would block
    assert allowed(run_hook(payload(repo / "a.py"), env={"FR_BASE_OK": "1"}))


def test_file_outside_git_allows(tmp_path: Path) -> None:
    loose = tmp_path / "loose"
    loose.mkdir()
    assert allowed(run_hook(payload(loose / "a.py")))


def test_non_fr_repo_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path, fr_enabled=False)
    assert allowed(run_hook(payload(repo / "a.py")))


def test_valid_marker_in_worktree_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    write_marker(wt, wt)
    assert allowed(run_hook(payload(wt / "a.py")))


def test_allowlist_path_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)  # fr-enabled linked worktree, NO marker
    (wt / ".fr-isolation-allow").write_text("notes/**\n")
    (wt / "notes").mkdir()
    assert allowed(run_hook(payload(wt / "notes" / "x.md")))


# ---------- deny paths ----------


def test_no_marker_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)  # fr-enabled, no marker
    assert decision(run_hook(payload(wt / "a.py"))) == "deny"


def test_mismatched_toplevel_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    write_marker(wt, tmp_path / "somewhere-else")  # recorded toplevel ≠ current
    assert decision(run_hook(payload(wt / "a.py"))) == "deny"


def test_marker_in_main_clone_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)  # the MAIN clone, not a linked worktree
    write_marker(repo, repo)
    assert decision(run_hook(payload(repo / "a.py"))) == "deny"
