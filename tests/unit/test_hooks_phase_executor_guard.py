"""fr-phase-executor-guard.sh — PreToolUse(Agent) hook refuses the poisoned shape.

super-fr#420. The org hook `agent-worktree-required.sh` allows on
`isolation: "worktree"` BEFORE it consults its allowlist, so the allowlist can
only ever mean "you needn't pass the flag" — never "you mustn't". Dispatching
`super-fr:fr-phase-executor` WITH the flag therefore succeeds, and fr-goal looks
healthy, while the executor wakes in a locked worktree cut from `main` where the
spec/plan are invisible, every Bash command is denied by fr-isolation-guard.sh
and every Write/Edit by fr-isolation-required.sh.

This hook is the refusal nothing else provides. Claude Code runs every matching
PreToolUse hook and a `deny` wins, so a super-fr-owned deny overrides the org
hook's early `exit 0` without super-fr editing a file it does not own.
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
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "fr-phase-executor-guard.sh"

QUALIFIED = "super-fr:fr-phase-executor"
BARE = "fr-phase-executor"


def run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )


def dispatch(subagent_type: str, isolation: str | None = None, tool: str = "Agent") -> dict:
    tool_input: dict[str, str] = {"subagent_type": subagent_type, "prompt": "implement phase 2"}
    if isolation is not None:
        tool_input["isolation"] = isolation
    return {
        "session_id": "sess-1",
        "cwd": str(REPO_ROOT),
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input,
    }


def decision(result: subprocess.CompletedProcess[str]) -> str | None:
    """The hook's decision, or None for a silent pass.

    Asserts a clean exit first: without it, an ABSENT or crashing hook also
    yields empty stdout, so every "allowed" assertion would pass vacuously.
    """
    assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


def reason(result: subprocess.CompletedProcess[str]) -> str:
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]


class TestPoisonedDispatchRefused:
    def test_qualified_id_with_worktree_denied(self) -> None:
        result = run_hook(dispatch(QUALIFIED, "worktree"))
        assert result.returncode == 0, result.stderr
        assert decision(result) == "deny"

    def test_bare_id_with_worktree_denied(self) -> None:
        """Claude Code sends the plugin-qualified id, but a locally-installed
        copy of the agent sends the bare name — the same reason
        ensure-phase-executor-allowlist.sh documents. Both must be refused."""
        assert decision(run_hook(dispatch(BARE, "worktree"))) == "deny"

    def test_deny_reason_names_the_remedy_and_the_why(self) -> None:
        """A soft warning reproduces today's silent failure, so the deny must
        say what to do instead AND why the two mechanisms don't compose."""
        result = run_hook(dispatch(QUALIFIED, "worktree"))
        text = reason(result)
        assert "without" in text.lower()
        assert 'isolation: "worktree"' in text
        assert "fr-phase-executor" in text
        assert "isolation" in text.lower()


class TestCorrectDispatchAllowed:
    def test_no_isolation_key_allowed(self) -> None:
        """The correct shape: fr's worktree already IS the isolation."""
        result = run_hook(dispatch(QUALIFIED))
        assert result.returncode == 0
        assert decision(result) is None

    def test_empty_isolation_allowed(self) -> None:
        assert decision(run_hook(dispatch(QUALIFIED, ""))) is None

    def test_other_isolation_value_allowed(self) -> None:
        """Only `worktree` is the poisoned value; an unknown value is not this
        hook's business (fail-open on shape, deny only on a positive match)."""
        assert decision(run_hook(dispatch(QUALIFIED, "remote"))) is None

    def test_bare_id_without_flag_allowed(self) -> None:
        assert decision(run_hook(dispatch(BARE))) is None


class TestOutOfScopeDispatchesUntouched:
    def test_other_subagent_with_worktree_allowed(self) -> None:
        """The org rule's default — always pass the flag — stays correct for
        every OTHER code-writing subagent. This hook narrows to one agent."""
        assert decision(run_hook(dispatch("general-purpose", "worktree"))) is None

    def test_fr_goal_cross_repo_agent_shape_allowed(self) -> None:
        """fr-goal §3 dispatches one agent per repo WITH the flag, correctly —
        those agents each start a fresh pipeline in a different repo."""
        assert decision(run_hook(dispatch("claude", "worktree"))) is None

    def test_non_agent_tool_allowed(self) -> None:
        assert decision(run_hook(dispatch(QUALIFIED, "worktree", tool="Bash"))) is None

    def test_legacy_task_tool_name_still_denied(self) -> None:
        """The subagent tool is `Agent` today and was `Task` on older builds.
        A host on the old spelling must not get an inert hook."""
        assert decision(run_hook(dispatch(QUALIFIED, "worktree", tool="Task"))) == "deny"

    def test_missing_subagent_type_allowed(self) -> None:
        payload = dispatch(QUALIFIED, "worktree")
        del payload["tool_input"]["subagent_type"]
        assert decision(run_hook(payload)) is None

    def test_empty_payload_is_a_silent_pass(self) -> None:
        result = run_hook({})
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestShipping:
    def test_hook_is_executable(self) -> None:
        assert SCRIPT.is_file(), f"missing {SCRIPT}"
        assert os.access(SCRIPT, os.X_OK), f"not executable: {SCRIPT}"
