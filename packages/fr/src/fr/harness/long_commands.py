"""How to run a command that may outlast a harness's tool-call limit — gh#582.

The phase executor's agent file already says this (`**Harness — long
commands:**`, #564). On the #564 OpenCode smoke that was not enough: the
orchestrator's task prompt named the exact suite command, the executor ran it
with no `timeout`, and OpenCode killed it at 120 s — twice — before the kill
message itself taught it. The orchestrator, which reads the brief, got it
right. So `fr run advance` now puts the rule in every phase-member brief, for
the harness it detects, and fr-goal §5 relays it into the task prompt.

One line per harness, kept in step with the agent clause by
`tests/unit/test_long_command_rule.py` (each harness's load-bearing token must
appear in both). An unrecognised harness gets the neutral rule, never nothing:
not knowing the harness is when a reader most needs the warning.
"""

from __future__ import annotations

LONG_COMMAND_RULES: dict[str, str] = {
    "claude-code": (
        "A command that may run past ~2 minutes (the full test suite, a build): "
        "a foreground Bash call over ~120 s is moved to the background anyway, so "
        "start it with run_in_background deliberately and wait on it with a "
        "bounded loop."
    ),
    "opencode": (
        "A command that may run past ~2 minutes (the full test suite, a build): "
        "the bash tool KILLS a call at its timeout (default 2 minutes), so pass "
        "an explicit timeout of up to 600000 (10 minutes) on that call. For "
        'anything longer, detach it yourself — (cmd; echo "exit=$?") > log '
        "2>&1 & echo $! > log.pid — poll the log with a bounded loop, and kill "
        '"$(cat log.pid)" before you hand back.'
    ),
    "hermes": (
        "A command that may run past ~2 minutes (the full test suite, a build): "
        "start it with terminal(command, background=true, "
        'notify_on_complete=true), wait with process(action="wait"), and '
        'process(action="kill") anything of yours still running before you '
        "hand back."
    ),
}

NEUTRAL_LONG_COMMAND_RULE = (
    "A command that may run past ~2 minutes (the full test suite, a build): "
    "find out how your harness bounds a single tool call, then either raise "
    "that bound explicitly on the call or run the command in the background "
    "and wait on it with a bounded loop. Never let a tool timeout kill a "
    "suite, and stop anything of yours still running before you hand back."
)


def long_command_rule(harness: str | None) -> str:
    """The rule for `harness` (as `fr.harness.detect.detect_harness` names
    it), or the neutral rule when the harness is unknown or has none."""
    if harness is None:
        return NEUTRAL_LONG_COMMAND_RULE
    return LONG_COMMAND_RULES.get(harness, NEUTRAL_LONG_COMMAND_RULE)
