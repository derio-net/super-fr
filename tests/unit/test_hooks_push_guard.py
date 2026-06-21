"""fr-merged-pr-push-guard.sh — PreToolUse(Bash) hook denies pushes to a
MERGED/CLOSED PR's branch while an fr pipeline is active (#320). Fail-open on
every ambiguity.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="hook scripts require jq")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "fr-merged-pr-push-guard.sh"


def fake_gh(
    bin_dir: Path, *, state: str | None = None, fail: bool = False, empty: bool = False
) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    gh = bin_dir / "gh"
    if fail:
        gh.write_text("#!/bin/bash\nexit 1\n")
    elif empty:
        gh.write_text("#!/bin/bash\nprintf ''\n")
    else:
        payload = json.dumps({"state": state, "mergedAt": None})
        gh.write_text(f"#!/bin/bash\ncat <<'JSON'\n{payload}\nJSON\n")
    gh.chmod(0o755)
    return bin_dir


def run_hook(
    payload: dict, sentinel_dir: Path, gh_bin: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "FR_SENTINEL_DIR": str(sentinel_dir)}
    if gh_bin is not None:
        env["PATH"] = f"{gh_bin}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def write_sentinel(sentinel_dir: Path, session: str = "sess-1") -> None:
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    (sentinel_dir / f"{session}.json").write_text(
        json.dumps({"repo_root": "/x", "skill": "fr-goal"})
    )


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
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


def test_no_sentinel_allows(tmp_path: Path) -> None:
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    r = run_hook(payload("git push", tmp_path), tmp_path / "sent", gh)
    assert decision(r) is None


def test_non_push_command_allows(tmp_path: Path) -> None:
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    r = run_hook(payload("git status", tmp_path), tmp_path / "sent", gh)
    assert decision(r) is None


def test_push_open_pr_allows(tmp_path: Path) -> None:
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", state="OPEN")
    r = run_hook(payload("git push", tmp_path), tmp_path / "sent", gh)
    assert decision(r) is None


def test_push_merged_pr_denies(tmp_path: Path) -> None:
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    r = run_hook(payload("git push", tmp_path), tmp_path / "sent", gh)
    assert decision(r) == "deny"


def test_push_closed_pr_denies(tmp_path: Path) -> None:
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", state="CLOSED")
    r = run_hook(payload("git push", tmp_path), tmp_path / "sent", gh)
    assert decision(r) == "deny"


def test_push_gh_error_fails_open(tmp_path: Path) -> None:
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", fail=True)
    r = run_hook(payload("git push", tmp_path), tmp_path / "sent", gh)
    assert decision(r) is None


def test_force_push_merged_denies(tmp_path: Path) -> None:
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    cmd = "cd /tmp && git push --force-with-lease origin HEAD"
    r = run_hook(payload(cmd, tmp_path), tmp_path / "sent", gh)
    assert decision(r) == "deny"


def test_git_c_push_merged_denies(tmp_path: Path) -> None:
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    r = run_hook(payload("git -C /tmp push", tmp_path), tmp_path / "sent", gh)
    assert decision(r) == "deny"


def test_mygit_not_matched(tmp_path: Path) -> None:
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    r = run_hook(payload("mygit push", tmp_path), tmp_path / "sent", gh)
    assert decision(r) is None


def test_push_semicolon_terminator_merged_denies(tmp_path: Path) -> None:
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    r = run_hook(payload("git push;", tmp_path), tmp_path / "sent", gh)
    assert decision(r) == "deny"


def test_push_pipe_terminator_merged_denies(tmp_path: Path) -> None:
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    r = run_hook(payload("git push|tee log", tmp_path), tmp_path / "sent", gh)
    assert decision(r) == "deny"


def test_git_c_config_push_merged_denies(tmp_path: Path) -> None:
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    r = run_hook(payload("git -c foo=bar push", tmp_path), tmp_path / "sent", gh)
    assert decision(r) == "deny"


def test_push_hyphen_suffix_not_matched(tmp_path: Path) -> None:
    # `git push-foo` is not a push; the trailing anchor excludes `-`.
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", state="MERGED")
    r = run_hook(payload("git push-foo", tmp_path), tmp_path / "sent", gh)
    assert decision(r) is None


def test_empty_pr_json_fails_open(tmp_path: Path) -> None:
    write_sentinel(tmp_path / "sent")
    gh = fake_gh(tmp_path / "bin", empty=True)
    r = run_hook(payload("git push", tmp_path), tmp_path / "sent", gh)
    assert decision(r) is None
