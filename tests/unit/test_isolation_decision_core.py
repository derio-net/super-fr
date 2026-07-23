"""lib/fr-isolation-decision.sh — the pure fr-isolation edit decision.

The marker/allowlist/fr-enabled logic is shared by the Claude Code PreToolUse
hook and the Hermes pre_tool_call hook, so it lives in one sourced shell library
with no stdin/stdout protocol and no harness-specific deny shape. This test
drives the function directly: `. lib; fr_isolation_decide_edit <abs-path>` and
asserts the return code — 0 ALLOW, 1 BLOCK.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "lib" / "fr-isolation-decision.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("git") is None,
    reason="decision core needs jq + git",
)


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


def write_marker(root: Path, toplevel: Path, mode: str = "worktree") -> None:
    (root / ".fr-isolation").write_text(
        f'{{"toplevel": "{toplevel.resolve()}", "branch": "feat/x", "mode": "{mode}"}}'
    )


def decide(file: Path, env: dict[str, str] | None = None) -> int:
    """Return code of fr_isolation_decide_edit for `file` (0 allow, 1 block)."""
    script = f'. "{LIB}"; fr_isolation_decide_edit "{file}"'
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    return result.returncode


def test_blocks_edit_outside_worktree_in_fr_repo(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert decide(repo / "src.py") == 1


def test_allows_non_fr_repo(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path, fr_enabled=False)
    assert decide(repo / "src.py") == 0


def test_fr_base_ok_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert decide(repo / "src.py", env={"FR_BASE_OK": "1"}) == 0


def test_allowlist_glob_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    (repo / ".fr-isolation-allow").write_text("projects/**\n")
    assert decide(repo / "projects" / "deep" / "x.md") == 0
    assert decide(repo / "src.py") == 1


def test_valid_linked_worktree_marker_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    write_marker(wt, wt)
    assert decide(wt / "src.py") == 0


def test_stale_marker_in_primary_tree_still_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    write_marker(repo, repo)  # marker copied into the primary tree — not a linked worktree
    assert decide(repo / "src.py") == 1
