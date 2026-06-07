"""fr-pipeline-sentinel.sh — PostToolUse(Skill) hook writes the session sentinel.

The scripts are plugin-shipped bash (jq), exercised here via subprocess with
hook-protocol JSON on stdin. FR_SENTINEL_DIR overrides ~/.cache/fr/sentinels
so tests never touch the real cache.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="hook scripts require jq")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "fr-pipeline-sentinel.sh"


def run_hook(payload: dict, sentinel_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, "FR_SENTINEL_DIR": str(sentinel_dir)},
    )


def make_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def payload(skill: str, cwd: Path, session: str = "sess-1") -> dict:
    return {
        "session_id": session,
        "cwd": str(cwd),
        "hook_event_name": "PostToolUse",
        "tool_name": "Skill",
        "tool_input": {"skill_name": skill},
    }


class TestSentinelWriter:
    def test_pipeline_skill_writes_sentinel(self, tmp_path: Path) -> None:
        repo = make_git_repo(tmp_path / "repo")
        sentinels = tmp_path / "sentinels"
        result = run_hook(payload("super-fr:fr-goal", repo), sentinels)
        assert result.returncode == 0
        sentinel = sentinels / "sess-1.json"
        assert sentinel.is_file()
        data = json.loads(sentinel.read_text())
        assert Path(data["repo_root"]).resolve() == repo.resolve()
        assert data["skill"] == "super-fr:fr-goal"
        assert data["started_at"]

    def test_unprefixed_skill_name_matches(self, tmp_path: Path) -> None:
        repo = make_git_repo(tmp_path / "repo")
        sentinels = tmp_path / "sentinels"
        run_hook(payload("fr-brainstorming", repo), sentinels)
        assert (sentinels / "sess-1.json").is_file()

    def test_non_pipeline_skill_is_ignored(self, tmp_path: Path) -> None:
        repo = make_git_repo(tmp_path / "repo")
        sentinels = tmp_path / "sentinels"
        result = run_hook(payload("commit-commands:commit", repo), sentinels)
        assert result.returncode == 0
        assert not (sentinels / "sess-1.json").exists()

    def test_non_git_cwd_is_noop(self, tmp_path: Path) -> None:
        plain = tmp_path / "not-a-repo"
        plain.mkdir()
        sentinels = tmp_path / "sentinels"
        result = run_hook(payload("super-fr:fr-goal", plain), sentinels)
        assert result.returncode == 0
        assert not (sentinels / "sess-1.json").exists()

    def test_linked_worktree_cwd_writes_no_sentinel(self, tmp_path: Path) -> None:
        """fr-execute may be invoked with cwd INSIDE the isolation worktree —
        the sentinel must not key on the worktree, or the guard would deny
        the very place work happens (review finding #1)."""
        repo = make_git_repo(tmp_path / "repo")
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.email=t@t",
                "-c",
                "user.name=t",
                "commit",
                "-qm",
                "init",
                "--allow-empty",
            ],
            check=True,
        )
        worktree = tmp_path / "wt"
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-q", str(worktree), "-b", "f/x"],
            check=True,
        )
        sentinels = tmp_path / "sentinels"
        result = run_hook(payload("super-fr:fr-execute", worktree), sentinels)
        assert result.returncode == 0
        assert not (sentinels / "sess-1.json").exists()

    def test_gc_removes_stale_sentinels(self, tmp_path: Path) -> None:
        repo = make_git_repo(tmp_path / "repo")
        sentinels = tmp_path / "sentinels"
        sentinels.mkdir()
        stale = sentinels / "dead-session.json"
        fresh = sentinels / "live-session.json"
        stale.write_text("{}")
        fresh.write_text("{}")
        now = time.time()
        os.utime(stale, (now - 49 * 3600, now - 49 * 3600))
        os.utime(fresh, (now - 47 * 3600, now - 47 * 3600))
        run_hook(payload("super-fr:fr-execute", repo), sentinels)
        assert not stale.exists(), "49h-old sentinel should be GC'd"
        assert fresh.exists(), "47h-old sentinel must survive"
