"""fr-goal and the phase executor say how `tests: ci` works — spec
2026-10-07-cloud-triage R22, §I "Prose this changes".

The orchestrator reads only its skill and the executor only its agent file, so
the rule has to be in both: §5 names `tests: ci` beside the local log and what fr
verifies for each, plus the waiting rule for exit 75; §6 the one exception to
"never open the PR"; §8 that `deliver` may use it; the executor commits, pushes
and returns `tests_log: ci` instead of running the full suite.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "super-fr" / "skills" / "fr-goal" / "SKILL.md"
AGENT = ROOT / "plugins" / "super-fr" / "agents" / "fr-phase-executor.md"


def _section(n: int) -> str:
    text = SKILL.read_text()
    m = re.search(rf"^### {n}\. .*?(?=^### |\Z)", text, re.S | re.M)
    assert m, f"fr-goal has no section {n}"
    return " ".join(m.group(0).split())


def test_section_5_names_ci_beside_the_local_log_and_what_fr_verifies() -> None:
    s5 = _section(5)
    assert "`tests: ci`" in s5
    assert "evidence: {tests: <log>}" in s5  # the local log is still there
    for verified in (
        "pushed",
        "no uncommitted code path",
        "open, non-conflicting",
        "`.fr/ci.yaml`",
        "required checks",
        "same code tree",
        "ci:<ci sha>+<base sha>;tree=",
        "`tests: reuse`",
        "`ci none`",
    ):
        assert verified in s5, verified


def test_section_5_states_the_waiting_rule() -> None:
    s5 = _section(5)
    assert "exit 75" in s5 and "not idle" in s5
    assert "PR-activity" in s5
    assert "every 2 minutes" in s5 and "45 minutes" in s5
    assert "blocked" in s5


def test_section_6_opens_the_draft_pr_early_for_a_ci_run() -> None:
    s6 = _section(6)
    assert "never open the PR" in s6
    assert "`tests: ci`" in s6 and "R22" in s6
    assert "draft PR" in s6 and "`implement` starts" in s6


def test_section_8_lets_deliver_use_ci() -> None:
    assert "`tests: ci`" in _section(8)


def test_the_executor_returns_tests_log_ci_when_briefed() -> None:
    agent = " ".join(AGENT.read_text().split())
    assert "tests_log: ci" in agent
    m = re.search(r"\*\*CI evidence\.\*\*(.*?)(?=\*\*[A-Z]|\Z)", agent)
    assert m, "the agent has no **CI evidence.** paragraph"
    rule = m.group(1)
    for word in ("brief", "commit", "push", "instead of running the full suite"):
        assert word in rule, word
