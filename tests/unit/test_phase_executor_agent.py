"""Phase 5: the fr-phase-executor agent definition (spec §B.1, option 3).

fr-goal dispatches each phase to this narrow, named subagent type. It is safe to
allowlist in the org agent-worktree hook precisely because it is defined to run
serially inside the already-isolated fr workspace — not a general code-writing
agent. This test pins the file's existence and the frontmatter the dispatch and
the allowlist rely on.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT = REPO_ROOT / "plugins/super-fr/agents/fr-phase-executor.md"


def _frontmatter(text: str) -> dict:
    assert text.startswith("---\n"), "agent file must open with YAML frontmatter"
    _, fm, _ = text.split("---\n", 2)
    return yaml.safe_load(fm)


def test_agent_file_exists() -> None:
    assert AGENT.exists(), f"missing {AGENT.relative_to(REPO_ROOT)}"


def test_name_is_fr_phase_executor() -> None:
    fm = _frontmatter(AGENT.read_text())
    assert fm["name"] == "fr-phase-executor"


def test_grants_edit_and_write() -> None:
    fm = _frontmatter(AGENT.read_text())
    tools = fm["tools"]
    tool_set = {t.strip() for t in (tools.split(",") if isinstance(tools, str) else tools)}
    assert {"Edit", "Write"} <= tool_set, f"needs Edit+Write to implement a phase, got {tool_set}"


def test_body_names_journal_and_fr_execute() -> None:
    """The brief must point the subagent at fr-execute + the journal handoff."""
    body = AGENT.read_text().split("---\n", 2)[2]
    assert "fr-execute" in body
    assert "fr journal" in body


def test_the_journal_example_carries_the_phase_flag() -> None:
    """The prose that caused the untagged-entry problem, pinned.

    `fr journal add --scope plan` now requires `--phase N` or `--global`
    (spec §5.A2), and the root cause of the entries that made it necessary was
    this contract's own example omitting the flag: an executor copies what it
    is shown. Without this assertion the example can be dropped in a
    length-trimming edit with every test still green, and executors resume
    writing entries that render in full at every phase forever — the exact
    regression path §5.A2 describes. The four `.opencode/agent/*` mirrors are
    covered by the sync tripwire, so pinning the canonical file is enough.
    """
    body = AGENT.read_text()
    assert "fr journal add --scope plan" in body
    assert "--phase N" in body, (
        "the journal example must show --phase N; without it the contract "
        "instructs executors to run a command that now exits 2"
    )


_LONG_COMMANDS_LEAD = "**Harness — long commands:**"


def _long_commands_clause(body: str) -> str:
    """The `**Harness — long commands:**` clause, bounded the way
    `fr.harness.prose` bounds a clause: up to a blank line that is followed by
    a non-indented line."""
    start = body.index(_LONG_COMMANDS_LEAD)
    lines = body[start:].splitlines()
    kept: list[str] = []
    for i, line in enumerate(lines):
        if line.strip() == "":
            following = lines[i + 1] if i + 1 < len(lines) else ""
            if not following[:1].isspace():
                break
        kept.append(line)
    return "\n".join(kept)


def test_long_commands_tell_each_harness_what_to_do() -> None:
    """2026-09-22 harness-argument-neutrality spec §1.1 / §3.D, row
    `executor-long-commands-per-harness`.

    The paragraph used to tell every reader to use `run_in_background`, which
    exists on Claude Code only. On OpenCode the bash tool KILLS a command at its
    `timeout` (default 2 min) and has no background argument, so the ~6-minute
    suite died; Hermes backgrounds through `terminal`/`process`. Each arm must
    carry the concrete mechanism its reader needs — a clause that merely names
    all three harnesses passes the tripwire and helps nobody.
    """
    clause = _long_commands_clause(AGENT.read_text())
    arms = _arms(clause)
    # Review p3r-4: needles are checked PER ARM, with forbidden ones — searched
    # across the whole clause, OpenCode's "kill" was satisfied by Hermes'
    # process(kill), and "On OpenCode pass background=true" would have passed.
    required = {
        "Claude Code": ("run_in_background",),
        # Review p3r-m1: the detach recipe must keep the exit code and say how
        # to stop the job — the paragraph below it says to read the real exit
        # code, and the handback rule says nothing may be left running.
        # Each bash call is a fresh shell, so `$!` is gone by the next call:
        # the PID is written to a file and killed from it.
        "OpenCode": ("timeout", "600000", "kills", 'echo "exit=$?"', "echo $! >", 'kill "$(cat'),
        "Hermes": ("background=true", 'process(action="wait"', 'process(action="kill")'),
    }
    forbidden = {
        "Claude Code": ("process(", "600000", "background=true"),
        "OpenCode": ("run_in_background", "background=true", "process("),
        "Hermes": ("run_in_background", "600000"),
    }
    assert set(arms) == set(required), f"expected one arm per harness, got {sorted(arms)}"
    for harness, arm in arms.items():
        for needle in required[harness]:
            assert needle in arm, f"the {harness} arm must say {needle!r}: {arm!r}"
        for needle in forbidden[harness]:
            assert needle not in arm, f"the {harness} arm must NOT say {needle!r}: {arm!r}"


def _arms(clause: str) -> dict[str, str]:
    """The clause split at its `On **<Harness>**` leads, one segment each."""
    import re

    parts = re.split(r"On\s+\*\*(Claude Code|OpenCode|Hermes)\*\*", clause)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def test_the_harness_neutral_long_command_rules_stay_unscoped() -> None:
    """The rules true on EVERY harness must not be buried in the per-harness
    clause (spec §3.D): bounded waits, nothing left running at handback (the
    #503 11.5-hour executor), and reading the command's own exit code."""
    body = AGENT.read_text()
    clause = _long_commands_clause(body)
    outside = body.replace(clause, "")
    for needle in ("**bounded**", "#503", "11.5 hours", "PIPESTATUS"):
        assert needle in outside, f"{needle!r} must stay outside the harness clause"
