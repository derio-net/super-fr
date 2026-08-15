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
echo "agent-worktree: '$subagent_type' must pass isolation: \\"worktree\\". Exempt: \
Explore, Plan, claude-code-guide, statusline-setup, hookify:conversation-analyzer" >&2
exit 2
"""

# The broken state this fix repairs: only the BARE name was ever inserted.
STALE_BARE_HOOK = STOCK_HOOK.replace("  Explore|Plan|", "  fr-phase-executor|Explore|Plan|")

# A hook whose `case` arm is already correct but whose human-readable message
# still lists the pre-fix five — the contradiction super-fr#420 reports.
CASE_FIXED_MESSAGE_STALE_HOOK = STOCK_HOOK.replace(
    "  Explore|Plan|", f"  {QUALIFIED}|Explore|Plan|"
)

# Some hosts have no such message at all. The repair must be a silent no-op
# there — unlike the `case` anchor, the message is not super-fr's to require.
NO_MESSAGE_HOOK = "\n".join(
    line for line in STOCK_HOOK.splitlines() if not line.startswith(("echo ", "Explore, Plan,"))
)


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


class TestStaleStderrMessage:
    """super-fr#420 checklist item 4: after the script edits the `case` arm, the
    hook's human-readable "Exempt: …" message three lines below still lists the
    pre-fix five — so the hook contradicts itself. Anyone reading the denial to
    find out what IS allowed is told the wrong thing.
    """

    def _message(self, hook: Path) -> str:
        """The line carrying the human-readable exempt list.

        Keyed on `Explore, Plan,` rather than the line's start: the repair
        prepends the qualified name, so after it the line no longer begins
        with `Explore,`.
        """
        return next(line for line in hook.read_text().splitlines() if "Explore, Plan," in line)

    def test_message_gains_the_qualified_name(self, tmp_path: Path) -> None:
        hook = write_hook(tmp_path, STOCK_HOOK)
        assert QUALIFIED not in self._message(hook)  # precondition
        assert run_script(hook).returncode == 0
        assert QUALIFIED in self._message(hook), (
            "the exempt-list message must name the type the case arm now admits"
        )

    def test_message_repaired_even_when_case_already_correct(self, tmp_path: Path) -> None:
        """The two probes are independent: a hook whose `case` already carries
        the qualified name must NOT short-circuit out of the message repair.
        This is the same shape as the idempotence bug this file records — a
        probe satisfied by one surface reporting 'done' for another."""
        hook = write_hook(tmp_path, CASE_FIXED_MESSAGE_STALE_HOOK)
        assert QUALIFIED not in self._message(hook)  # the live contradiction
        assert run_script(hook).returncode == 0
        assert QUALIFIED in self._message(hook)

    def test_absent_message_is_a_silent_no_op(self, tmp_path: Path) -> None:
        """Unlike the `case` anchor, the message is not super-fr's to require —
        a hook without one is repaired silently, not failed loud."""
        hook = write_hook(tmp_path, NO_MESSAGE_HOOK)
        result = run_script(hook)
        assert result.returncode == 0, result.stderr
        assert QUALIFIED in hook.read_text(), "the case arm is still fixed"

    def test_message_repair_is_idempotent(self, tmp_path: Path) -> None:
        hook = write_hook(tmp_path, STOCK_HOOK)
        run_script(hook)
        once = hook.read_text()
        assert run_script(hook).returncode == 0
        assert hook.read_text() == once, "second run must be byte-identical"
        assert once.count(QUALIFIED) == 2, "exactly one case entry + one message entry"


# ---------------------------------------------------------------------------
# Review findings rev2-f5 / rev2-f6 (2026-08-15 fr-goal review run).
#
# This script edits a file super-fr does NOT own. The real
# ~/.claude/hooks/agent-worktree-required.sh on an operator machine carries the
# exempt list TWICE — once in a header comment explaining the rationale, once in
# the stderr message — and both repairs were file-wide and unanchored.
# ---------------------------------------------------------------------------

# The shape that actually ships: a rationale comment naming the read-only types,
# and further down the real `case` arm plus the stderr message.
REAL_WORLD_HOOK = (
    "#!/bin/bash\n"
    "# Enforce worktree isolation for code-writing subagents.\n"
    "# Read-only subagent types (Explore, Plan, claude-code-guide, …) bypass — see\n"
    "# the allowlist below.\n" + STOCK_HOOK.split("\n", 1)[1]
)


def _line_with(hook: Path, needle: str, *, comment: bool) -> str:
    for line in hook.read_text().splitlines():
        if needle in line and line.lstrip().startswith("#") == comment:
            return line
    raise AssertionError(f"no {'comment' if comment else 'code'} line containing {needle!r}")


class TestDoesNotRewriteLinesItDoesNotOwn:
    def test_rationale_comment_is_left_alone(self, tmp_path: Path) -> None:
        """The comment says these types are READ-ONLY. fr-phase-executor writes
        code — super-fr's own rule says so in as many words — so inserting it
        there asserts something the rule contradicts, in a file we don't own."""
        hook = write_hook(tmp_path, REAL_WORLD_HOOK)
        before = _line_with(hook, "Explore, Plan,", comment=True)
        assert run_script(hook).returncode == 0
        assert _line_with(hook, "Explore, Plan,", comment=True) == before, (
            "the read-only rationale comment must not gain a code-writing agent"
        )

    def test_stderr_message_is_still_repaired(self, tmp_path: Path) -> None:
        hook = write_hook(tmp_path, REAL_WORLD_HOOK)
        assert run_script(hook).returncode == 0
        assert QUALIFIED in _line_with(hook, "Explore, Plan,", comment=False)

    def test_comment_carrying_the_name_does_not_mask_a_stale_message(self, tmp_path: Path) -> None:
        """The probe was file-wide, so ONE already-qualified line satisfied it
        for every other — the exact 'one surface reports done for another'
        failure this script's header says the two-probe design prevents."""
        hook = write_hook(
            tmp_path,
            REAL_WORLD_HOOK.replace(
                "# Read-only subagent types (Explore, Plan,",
                f"# Read-only subagent types ({QUALIFIED}, Explore, Plan,",
            ),
        )
        assert run_script(hook).returncode == 0
        assert QUALIFIED in _line_with(hook, "Explore, Plan,", comment=False), (
            "a pre-qualified comment must not permanently mask the real message"
        )

    def test_foreign_plugin_id_is_not_mangled(self, tmp_path: Path) -> None:
        """`s/fr-phase-executor, Explore, Plan,/…/` matched mid-token, erasing a
        real entry and inventing `someplugin:super-fr:fr-phase-executor`."""
        hook = write_hook(
            tmp_path,
            STOCK_HOOK.replace(
                "Explore, Plan, claude-code-guide",
                "someplugin:fr-phase-executor, Explore, Plan, claude-code-guide",
            ),
        )
        assert run_script(hook).returncode == 0
        text = hook.read_text()
        assert "someplugin:super-fr:" not in text, "must not invent a nonexistent id"
        assert "someplugin:fr-phase-executor" in text, "must not erase a real entry"

    def test_real_world_shape_is_idempotent(self, tmp_path: Path) -> None:
        hook = write_hook(tmp_path, REAL_WORLD_HOOK)
        run_script(hook)
        once = hook.read_text()
        assert run_script(hook).returncode == 0
        assert hook.read_text() == once


class TestCaseArmProbeIgnoresComments:
    def test_comment_quoting_the_allowlist_does_not_defeat_the_repair(self, tmp_path: Path) -> None:
        """A hook documenting its own allowlist verbatim satisfied the file-wide
        probe, so the real `case` arm was never patched — the script reported
        success while dispatch stayed blocked, re-creating the silent
        inline-degradation incident this file exists to end."""
        hook = write_hook(
            tmp_path,
            STOCK_HOOK.replace(
                "#!/bin/bash\n",
                f"#!/bin/bash\n#   {QUALIFIED}|Explore|Plan|claude-code-guide)\n",
            ),
        )
        assert run_script(hook).returncode == 0
        assert hook_allows(hook, QUALIFIED), (
            "the real case arm must be repaired even when a comment quotes the fixed form"
        )

    def test_bare_entry_not_at_head_is_still_stripped(self, tmp_path: Path) -> None:
        """The strip was anchored to the head of the arm, so a stale bare entry
        elsewhere survived alongside the prepended qualified one — which the
        comment claims cannot happen."""
        hook = write_hook(
            tmp_path,
            STOCK_HOOK.replace(
                "Explore|Plan|claude-code-guide|statusline-setup",
                "Explore|Plan|claude-code-guide|fr-phase-executor|statusline-setup",
            ),
        )
        assert run_script(hook).returncode == 0
        arm = next(line for line in hook.read_text().splitlines() if "Explore|Plan|" in line)
        assert "|fr-phase-executor|" not in arm, "the stale bare entry must be removed"
        assert f"{QUALIFIED}|Explore|Plan|" in arm
