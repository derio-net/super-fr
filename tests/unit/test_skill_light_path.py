"""Prose pins for the light path (spec 2026-09-29-fr-goal-light-path §C, R7).

The skill documents the light path and the one-call resolve; the phase
executor returns a fixed shape naming its suite log; the spec reviewer covers
the plan too when the brief names one. Content tests, because each of these is
an instruction an orchestrator or subagent acts on, and a lost line is a lost
behaviour nothing else would report.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "super-fr" / "skills" / "fr-goal" / "SKILL.md"
EXECUTOR = ROOT / "plugins" / "super-fr" / "agents" / "fr-phase-executor.md"
REVIEWER = ROOT / "plugins" / "super-fr" / "agents" / "fr-spec-reviewer.md"


def _flat(path: Path) -> str:
    return " ".join(path.read_text().split())


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^#+ [^\n]*{re.escape(heading)}[^\n]*\n(.*?)(?=^#+ |\Z)", text, re.M | re.S)
    assert match, f"no section headed {heading!r}"
    return " ".join(match.group(1).split())


def test_the_skill_has_a_light_path_section() -> None:
    body = _section(SKILL.read_text(), "Light path")
    for needle in ("fr-goal-light", "shape: fr-goal-light", "tests: reuse", "spec-plan-review"):
        assert needle in body, needle


def test_the_light_path_forbids_opening_a_subagent_transcript() -> None:
    body = _section(SKILL.read_text(), "Light path").lower()
    assert "never open" in body and "transcript" in body


def test_the_skill_no_longer_advances_separately_after_a_record() -> None:
    text = _flat(SKILL)
    after = re.findall(r"--record[^.]*?\bthen\b[^.]*?`fr run advance", text)
    assert after == [], after


def test_implement_and_deliver_describe_suite_reuse() -> None:
    text = SKILL.read_text()
    implement = _section(text, "5. implement")
    deliver = _section(text, "8. deliver")
    assert "tests_log" in implement and "evidence: {tests:" in implement
    assert "tests: reuse" in deliver


def test_the_executor_returns_a_fixed_shape_naming_its_suite_log() -> None:
    body = _section(EXECUTOR.read_text(), "What you return")
    for key in ("record:", "outcome:", "tests_log:", "summary:"):
        assert key in body, key
    assert "records/" in body  # the log lives outside <run>.records/


def test_the_spec_reviewer_reviews_a_plan_when_the_brief_names_one() -> None:
    text = _flat(REVIEWER)
    assert "target: spec|plan" in text
    assert "spec-plan-review" in text


def test_deliver_section_no_longer_ties_the_suite_to_a_separate_advance() -> None:
    body = _section(SKILL.read_text(), "deliver")
    assert "the `fr run advance` that opens `deliver`" not in body
    assert "AFTER the resolve that opened `deliver`" in body
