"""`fr.harness.detect_harness` — 2026-09-18 harness-parity-matrix spec §3.D.1,
Phase 5.

`FR_HARNESS` is new (this spec introduces it — no such variable exists
today). It wins outright, and a value outside `HARNESSES` RAISES rather
than falling through to inference: a typo must not silently become a
guess. The fallback order mirrors the spec table exactly:
`CLAUDECODE`/`CLAUDE_PLUGIN_ROOT` -> claude-code, any `OPENCODE*` key ->
opencode, any `HERMES*` key -> hermes. An unrecognised environment returns
`None` — fail loud (the caller treats it as degraded), matching the
isolation gate's fail-closed posture.
"""

from __future__ import annotations

import pytest
from fr.harness.detect import detect_harness
from fr.harness.model import HarnessError


def test_fr_harness_wins_outright_over_every_inference_signal() -> None:
    env = {
        "FR_HARNESS": "hermes",
        "CLAUDECODE": "1",
        "OPENCODE_SOMETHING": "1",
    }
    assert detect_harness(env) == "hermes"


@pytest.mark.parametrize("harness", ["claude-code", "opencode", "hermes", "codex", "copilot-cli"])
def test_fr_harness_accepts_every_member(harness: str) -> None:
    assert detect_harness({"FR_HARNESS": harness}) == harness


def test_fr_harness_set_to_a_typo_raises_rather_than_inferring() -> None:
    with pytest.raises(HarnessError):
        detect_harness({"FR_HARNESS": "clawd-code", "CLAUDECODE": "1"})


def test_claudecode_env_key_infers_claude_code() -> None:
    assert detect_harness({"CLAUDECODE": "1"}) == "claude-code"


def test_claude_plugin_root_infers_claude_code() -> None:
    assert detect_harness({"CLAUDE_PLUGIN_ROOT": "/some/path"}) == "claude-code"


def test_an_opencode_prefixed_key_infers_opencode() -> None:
    assert detect_harness({"OPENCODE_WORKDIR": "/x"}) == "opencode"


def test_a_hermes_prefixed_key_infers_hermes() -> None:
    assert detect_harness({"HERMES_HOME": "/x"}) == "hermes"


def test_an_unrecognised_environment_returns_none() -> None:
    assert detect_harness({"PATH": "/usr/bin", "SOME_OTHER_VAR": "1"}) is None


def test_empty_environment_returns_none() -> None:
    assert detect_harness({}) is None


# --- gh#537: a MIXED environment is resolved by the nearest harness, never by
# a fixed precedence. An OpenCode started from a Claude Code shell inherits
# `CLAUDECODE=1` (and `CLAUDE_PID`, `CLAUDE_CODE_SESSION_ID`); env crosses
# process boundaries, so a marker alone says a harness ran SOMEWHERE above
# fr, not that it is the one fr runs under. Both harnesses export their own
# pid (`CLAUDE_PID`, `OPENCODE_PID` — read off the installed binaries), and
# the one nearest fr in its process ancestry is the one it runs under.

_CLAUDE_OUTER_OPENCODE_INNER = {
    "CLAUDECODE": "1",
    "CLAUDE_PID": "100",
    "CLAUDE_CODE_SESSION_ID": "d756f763-0000",
    "OPENCODE": "1",
    "OPENCODE_PID": "200",
}


def test_opencode_launched_from_a_claude_code_shell_is_opencode() -> None:
    # fr (300) <- OpenCode's bash (250) <- OpenCode (200) <- shell <- Claude Code (100)
    ancestry = [300, 250, 200, 150, 100, 1]
    assert detect_harness(_CLAUDE_OUTER_OPENCODE_INNER, ancestors=lambda: ancestry) == "opencode"


def test_claude_code_launched_from_an_opencode_shell_is_claude_code() -> None:
    env = {**_CLAUDE_OUTER_OPENCODE_INNER, "CLAUDE_PID": "200", "OPENCODE_PID": "100"}
    ancestry = [300, 250, 200, 150, 100, 1]
    assert detect_harness(env, ancestors=lambda: ancestry) == "claude-code"


def test_a_mixed_environment_whose_pids_are_not_ancestors_is_inconclusive() -> None:
    """Neither harness can be placed above fr, so neither is named: a wrong
    holder reads as an answer, an absent one reads as a gap."""
    assert detect_harness(_CLAUDE_OUTER_OPENCODE_INNER, ancestors=lambda: [300, 1]) is None


def test_a_mixed_environment_with_unreadable_ancestry_is_inconclusive() -> None:
    assert detect_harness(_CLAUDE_OUTER_OPENCODE_INNER, ancestors=lambda: []) is None


def test_a_marker_with_no_pid_cannot_outrank_a_harness_proven_above_fr() -> None:
    """A stray `OPENCODE_CONFIG` exported by a shell profile is an OPENCODE*
    key but no running OpenCode (a running one always sets `OPENCODE_PID`);
    the Claude Code proven in fr's ancestry still names the harness."""
    env = {"CLAUDECODE": "1", "CLAUDE_PID": "100", "OPENCODE_CONFIG": "/x"}
    assert detect_harness(env, ancestors=lambda: [300, 100, 1]) == "claude-code"


def test_a_single_harness_environment_never_reads_the_process_tree() -> None:
    def boom() -> list[int]:
        raise AssertionError("ancestry read for an unambiguous environment")

    assert detect_harness({"CLAUDECODE": "1", "CLAUDE_PID": "100"}, ancestors=boom) == "claude-code"
    assert detect_harness({"OPENCODE": "1"}, ancestors=boom) == "opencode"


def test_fr_harness_still_beats_a_mixed_environment() -> None:
    env = {**_CLAUDE_OUTER_OPENCODE_INNER, "FR_HARNESS": "claude-code"}
    assert detect_harness(env, ancestors=lambda: [300, 200, 100]) == "claude-code"
