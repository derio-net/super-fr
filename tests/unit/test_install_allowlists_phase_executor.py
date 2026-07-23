"""Phase 5: install-side allowlisting of fr-phase-executor (spec §B.1, option 3).

super-fr co-manages the org agent-worktree hook's allowlist for its own narrow
phase-executor type. The mechanism is a standalone, idempotent helper script
(`scripts/ensure-phase-executor-allowlist.sh <hook-path>`) that install.sh
invokes. It must:
  - insert `fr-phase-executor` into the allowlist `case` pattern when absent;
  - be idempotent (a second run changes nothing);
  - be a safe no-op when the hook file does not exist.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "scripts/ensure-phase-executor-allowlist.sh"

STOCK_HOOK = """\
#!/bin/bash
set -eu
subagent_type=$(printf '%s' "$input" | jq -r '.tool_input.subagent_type // "general-purpose"')

case "$subagent_type" in
  Explore|Plan|claude-code-guide|statusline-setup|hookify:conversation-analyzer)
    exit 0
    ;;
esac
echo "block"
"""


def _run(hook_path: Path):
    return subprocess.run(
        ["bash", str(HELPER), str(hook_path)],
        capture_output=True,
        text=True,
    )


def test_helper_exists() -> None:
    assert HELPER.exists(), "scripts/ensure-phase-executor-allowlist.sh must exist"


def test_inserts_type_when_absent(tmp_path: Path) -> None:
    hook = tmp_path / "agent-worktree-required.sh"
    hook.write_text(STOCK_HOOK)
    res = _run(hook)
    assert res.returncode == 0, res.stderr
    text = hook.read_text()
    assert "fr-phase-executor" in text
    # Still a single case arm (inserted into the existing pattern, not a new arm).
    assert text.count("fr-phase-executor)") == 0  # part of the pipe list, not its own arm
    assert "fr-phase-executor|" in text or "|fr-phase-executor" in text


def test_idempotent(tmp_path: Path) -> None:
    hook = tmp_path / "agent-worktree-required.sh"
    hook.write_text(STOCK_HOOK)
    _run(hook)
    once = hook.read_text()
    _run(hook)
    twice = hook.read_text()
    assert once == twice
    assert twice.count("fr-phase-executor") == 1


def test_absent_hook_is_noop(tmp_path: Path) -> None:
    hook = tmp_path / "does-not-exist.sh"
    res = _run(hook)
    assert res.returncode == 0, res.stderr
    assert not hook.exists()


def test_preserves_existing_allowlist(tmp_path: Path) -> None:
    hook = tmp_path / "agent-worktree-required.sh"
    hook.write_text(STOCK_HOOK)
    _run(hook)
    text = hook.read_text()
    for existing in ("Explore", "Plan", "claude-code-guide"):
        assert existing in text
