"""fr-isolation-guard.sh — PreToolUse(Bash) hook denies base-repo commands.

While a session sentinel exists (written by fr-pipeline-sentinel.sh), any
Bash command whose cwd resolves inside the sentinel's repo_root is denied
unless it is an `fr isolation …` command. Strict mode per the #265 Q&A:
host-side git/gh ops run from the worktree cwd instead.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None, reason="hook scripts require jq"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "fr-isolation-guard.sh"


def run_hook(payload: dict, sentinel_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, "FR_SENTINEL_DIR": str(sentinel_dir)},
    )


def write_sentinel(sentinel_dir: Path, repo_root: Path, session: str = "sess-1") -> Path:
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    sentinel = sentinel_dir / f"{session}.json"
    sentinel.write_text(json.dumps({"repo_root": str(repo_root), "skill": "fr-goal"}))
    return sentinel


def payload(command: str, cwd: Path, session: str = "sess-1") -> dict:
    return {
        "session_id": session,
        "cwd": str(cwd),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def decision(result: subprocess.CompletedProcess[str]) -> str | None:
    if not result.stdout.strip():
        return None
    out = json.loads(result.stdout)
    return out["hookSpecificOutput"]["permissionDecision"]


class TestIsolationGuard:
    def test_no_sentinel_allows(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        result = run_hook(payload("git status", repo), tmp_path / "sentinels")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_base_repo_cwd_denied(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(payload("git status", repo), sentinels)
        assert result.returncode == 0
        assert decision(result) == "deny"
        reason = json.loads(result.stdout)["hookSpecificOutput"][
            "permissionDecisionReason"
        ]
        assert "fr isolation exec" in reason

    def test_fr_isolation_command_allowed(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(
            payload("fr isolation exec -- uv run pytest -q", repo), sentinels
        )
        assert decision(result) is None

    def test_subdir_of_base_repo_denied(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        sub = repo / "src" / "deep"
        sub.mkdir(parents=True)
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(payload("ls", sub), sentinels)
        assert decision(result) == "deny"

    def test_outside_cwd_allowed(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        elsewhere = tmp_path / "worktree-standin"
        elsewhere.mkdir()
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(payload("uv run pytest -q", elsewhere), sentinels)
        assert decision(result) is None

    def test_isolation_down_allowed_and_clears_sentinel(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        sentinels = tmp_path / "sentinels"
        sentinel = write_sentinel(sentinels, repo)
        result = run_hook(
            payload("fr isolation down --branch feat/x", repo), sentinels
        )
        assert decision(result) is None
        assert not sentinel.exists(), "down clears the sentinel"

    def test_symlinked_cwd_resolves_into_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        link = tmp_path / "link-to-repo"
        link.symlink_to(repo)
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(payload("make build", link), sentinels)
        assert decision(result) == "deny"

    def test_similar_prefix_dir_not_denied(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        sibling = tmp_path / "repo-other"  # shares the string prefix only
        sibling.mkdir()
        sentinels = tmp_path / "sentinels"
        write_sentinel(sentinels, repo)
        result = run_hook(payload("ls", sibling), sentinels)
        assert decision(result) is None
