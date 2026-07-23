"""ensure-phase-executor-allowlist.sh must allowlist the name Claude Code sends.

Claude Code dispatches a *plugin* subagent by its plugin-qualified id —
`super-fr:fr-phase-executor` — not the bare directory name. The org hook
`agent-worktree-required.sh` matches `$subagent_type` literally, so an allowlist
carrying only the bare `fr-phase-executor` never matches and every fr-goal phase
dispatch is blocked (fr-goal then silently degrades to inline execution).
`hookify:conversation-analyzer` already in that allowlist is the precedent: a
plugin agent is listed qualified.

The failure was doubly silent: the script's idempotence probe was
`grep -q fr-phase-executor`, which the stale *bare* entry satisfies — so every
reinstall reported "already done" and never self-healed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ensure-phase-executor-allowlist.sh"
QUALIFIED = "super-fr:fr-phase-executor"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")


STOCK_HOOK = """#!/bin/bash
set -eu
input=$(cat)
tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
[ "$tool_name" = "Agent" ] || exit 0
subagent_type=$(printf '%s' "$input" | jq -r '.tool_input.subagent_type // "general-purpose"')
isolation=$(printf '%s' "$input" | jq -r '.tool_input.isolation // empty')
[ "$isolation" = "worktree" ] && exit 0
case "$subagent_type" in
  Explore|Plan|claude-code-guide|statusline-setup|hookify:conversation-analyzer)
    exit 0
    ;;
esac
exit 2
"""

# The broken state this fix repairs: only the BARE name was ever inserted.
STALE_BARE_HOOK = STOCK_HOOK.replace("  Explore|Plan|", "  fr-phase-executor|Explore|Plan|")


def write_hook(tmp_path: Path, body: str) -> Path:
    hook = tmp_path / "agent-worktree-required.sh"
    hook.write_text(body)
    hook.chmod(0o755)
    return hook


def run_script(hook: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(SCRIPT), str(hook)], capture_output=True, text=True)


def hook_allows(hook: Path, subagent_type: str) -> bool:
    """Run the hook itself with a real payload; exit 0 = allowed."""
    payload = json.dumps({"tool_name": "Agent", "tool_input": {"subagent_type": subagent_type}})
    result = subprocess.run(["bash", str(hook)], input=payload, capture_output=True, text=True)
    return result.returncode == 0


@pytest.mark.skipif(shutil.which("jq") is None, reason="hook needs jq")
def test_stock_hook_gains_the_qualified_name(tmp_path: Path) -> None:
    hook = write_hook(tmp_path, STOCK_HOOK)
    assert not hook_allows(hook, QUALIFIED)  # precondition: blocked
    assert run_script(hook).returncode == 0
    assert hook_allows(hook, QUALIFIED), (
        "after allowlisting, the hook must ALLOW the plugin-qualified id Claude Code actually sends"
    )


@pytest.mark.skipif(shutil.which("jq") is None, reason="hook needs jq")
def test_stale_bare_only_hook_is_repaired(tmp_path: Path) -> None:
    """The regression that shipped: bare entry present, qualified missing."""
    hook = write_hook(tmp_path, STALE_BARE_HOOK)
    assert not hook_allows(hook, QUALIFIED)  # the live bug
    assert run_script(hook).returncode == 0
    assert hook_allows(hook, QUALIFIED), (
        "a hook carrying only the stale bare name must be REPAIRED, not treated "
        "as already-done by the idempotence probe"
    )


@pytest.mark.skipif(shutil.which("jq") is None, reason="hook needs jq")
def test_idempotent_second_run(tmp_path: Path) -> None:
    hook = write_hook(tmp_path, STOCK_HOOK)
    run_script(hook)
    once = hook.read_text()
    assert run_script(hook).returncode == 0
    assert hook.read_text() == once, "second run must be a no-op"
    assert hook_allows(hook, QUALIFIED)


def test_absent_hook_is_a_silent_success(tmp_path: Path) -> None:
    result = run_script(tmp_path / "nope.sh")
    assert result.returncode == 0, "a machine without the org hook must not fail install"


def test_anchor_drift_fails_loud(tmp_path: Path) -> None:
    hook = write_hook(tmp_path, STOCK_HOOK.replace("Explore|Plan|", "Wat|Huh|"))
    result = run_script(hook)
    assert result.returncode != 0, "unknown hook shape must fail loudly, not skip"
    assert "anchor" in result.stderr.lower() or "allowlist" in result.stderr.lower()
