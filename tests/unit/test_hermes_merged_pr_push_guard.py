"""hermes/fr-merged-pr-push-guard.sh — Hermes pre_tool_call push guard.

Denies a `git push` when the current branch's PR is MERGED/CLOSED (the #320
merge-race), the Hermes sibling of fr-merged-pr-push-guard.sh. Marker-based
(scoped to fr-enabled repos so the gh call is bounded) rather than
sentinel-based. Fail-open on every ambiguity.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="hook scripts require git",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "hermes" / "fr-merged-pr-push-guard.sh"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def fr_repo(tmp_path: Path, fr_enabled: bool = True) -> Path:
    repo = tmp_path / "repo"
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


def fake_gh(bin_dir: Path, *, state: str | None = None, fail: bool = False) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    gh = bin_dir / "gh"
    if fail:
        gh.write_text("#!/bin/bash\nexit 1\n")
    else:
        payload = json.dumps({"state": state})
        gh.write_text(f"#!/bin/bash\ncat <<'JSON'\n{payload}\nJSON\n")
    gh.chmod(0o755)
    return bin_dir


def payload(command: str, cwd: Path, tool: str = "terminal") -> dict:
    return {
        "hook_event_name": "pre_tool_call",
        "tool_name": tool,
        "tool_input": {"command": command},
        "cwd": str(cwd),
    }


def run_hook(p: dict, gh_bin: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ}
    if gh_bin is not None:
        env["PATH"] = f"{gh_bin}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(p),
        capture_output=True,
        text=True,
        env=env,
    )


def blocked(result: subprocess.CompletedProcess[str]) -> bool:
    if not result.stdout.strip():
        return False
    return json.loads(result.stdout).get("decision") == "block"


def allowed(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode == 0 and not result.stdout.strip()


def test_push_to_merged_pr_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    assert blocked(run_hook(payload("git push", repo), gh))


def test_push_to_closed_pr_blocks(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    gh = fake_gh(tmp_path / "bin", state="CLOSED")
    assert blocked(run_hook(payload("git push origin HEAD", repo), gh))


def test_push_to_open_pr_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    gh = fake_gh(tmp_path / "bin", state="OPEN")
    assert allowed(run_hook(payload("git push", repo), gh))


def test_no_pr_fails_open(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    gh = fake_gh(tmp_path / "bin", fail=True)
    assert allowed(run_hook(payload("git push", repo), gh))


def test_non_push_command_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    assert allowed(run_hook(payload("git commit -m x", repo), gh))


def test_push_in_non_fr_repo_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path, fr_enabled=False)
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    assert allowed(run_hook(payload("git push", repo), gh))


def test_non_bash_tool_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    assert allowed(run_hook(payload("git push", repo, tool="write_file"), gh))
