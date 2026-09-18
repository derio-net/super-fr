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
