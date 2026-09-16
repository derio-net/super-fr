"""codex/fr-isolation-required.sh — Codex PreToolUse edit gate (walking skeleton).

Codex reports file edits as tool_name "apply_patch" with the patch text in
`tool_input.command` (NOT `tool_input.file_path`), naming repo-relative
targets. The entrypoint stays thin — tool vocabulary, payload parsing, deny
JSON — while the allow/deny decision is the shared
lib/fr-isolation-decision.sh, unforked.

Only the two skeleton cases live here; the full matrix is phase 2. Helpers are
duplicated from test_hermes_isolation_hook_edits.py on purpose: the repo's
convention is that each hook test module keeps its own.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "codex" / "fr-isolation-required.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="codex hook needs git",
)

# A minimal single-target patch in Codex's apply_patch format. The path is
# repo-relative, which is the trap the gate must survive: passed through
# verbatim, fr_isolation_decide_edit ALLOWS it by design.
ADD_SRC = "*** Begin Patch\n*** Add File: src/a.py\n+x\n*** End Patch\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def fr_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
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


def payload(patch: str, cwd: Path, tool: str = "apply_patch") -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"command": patch},
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


def decision(r: subprocess.CompletedProcess[str]) -> str | None:
    if not r.stdout.strip():
        return None
    return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]


def test_apply_patch_in_fr_enabled_base_clone_denies(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    assert decision(run_hook(payload(ADD_SRC, repo))) == "deny"


def test_apply_patch_in_valid_worktree_allows(tmp_path: Path) -> None:
    repo = fr_repo(tmp_path)
    wt = linked_worktree(repo)
    r = run_hook(payload(ADD_SRC, wt))
    assert r.returncode == 0
    assert not r.stdout.strip()
