"""The browser-check prose spec 2026-09-28-ui-visual-evidence §E asks for —
fr-execute, fr-phase-executor, fr-goal, fr-brainstorming and fr-plan all say
something about `visual` evidence, or phase 2's gate (`fr.run.visual`) has
nothing telling an agent to fill the record's `visual:` section in the first
place.

Assertions are short discriminating tokens (`test_skill_tokens.py`'s
convention), not whole sentences, so ordinary rewording that preserves
meaning does not fail the test while dropping the guidance does. Harness-tool
neutrality (tests/unit/test_tripwire_skill_tool_neutrality.py) is a separate
gate this file does not re-check.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FR_EXECUTE = REPO_ROOT / "plugins/super-fr/skills/fr-execute/SKILL.md"
FR_GOAL = REPO_ROOT / "plugins/super-fr/skills/fr-goal/SKILL.md"
FR_BRAINSTORMING = REPO_ROOT / "plugins/super-fr/skills/fr-brainstorming/SKILL.md"
FR_PLAN = REPO_ROOT / "plugins/super-fr/skills/fr-plan/SKILL.md"
FR_PHASE_EXECUTOR = REPO_ROOT / "plugins/super-fr/agents/fr-phase-executor.md"

_GOAL_SECTION_RE = re.compile(r"\n### (\d+)\. ")


def _goal_section(n: int) -> str:
    """The body of fr-goal §n, up to the next numbered section — so a
    `visual` mention in one section cannot satisfy an assertion about
    another (fr-goal is one long file, several sections deep)."""
    text = FR_GOAL.read_text()
    matches = list(_GOAL_SECTION_RE.finditer(text))
    starts = {int(m.group(1)): m.end() for m in matches}
    assert n in starts, f"fr-goal has no numbered section {n}"
    start = starts[n]
    later = sorted(s for s in starts.values() if s > start)
    end = later[0] if later else len(text)
    return text[start:end]


# --- fr-execute: the Browser check step (R4, R5, R6) -----------------------


def test_fr_execute_has_a_browser_check_step() -> None:
    assert "Browser check" in FR_EXECUTE.read_text()


def test_fr_execute_browser_check_names_states_and_interactions_at_their_limits() -> None:
    t = FR_EXECUTE.read_text()
    assert "limits included" in t


def test_fr_execute_browser_check_prefers_a_capture_script_and_reruns_it() -> None:
    t = FR_EXECUTE.read_text().lower()
    assert "capture script" in t
    assert "re-run it" in t


def test_fr_execute_browser_check_opens_every_screenshot_with_an_image_read() -> None:
    t = FR_EXECUTE.read_text()
    assert "image read" in t


def test_fr_execute_browser_check_a_scripts_exit_code_is_never_the_evidence() -> None:
    t = FR_EXECUTE.read_text()
    assert "exit code is never the evidence" in t


def test_fr_execute_browser_check_fills_the_records_visual_section() -> None:
    t = FR_EXECUTE.read_text()
    assert "`visual:`" in t


def test_fr_execute_browser_check_says_where_shots_live() -> None:
    """Take 9 lost its screenshots in the container's own /tmp, which the host
    (where `fr run resolve` and the reading agent run) never sees (p3-r2)."""
    t = FR_EXECUTE.read_text()
    assert "git-ignored" in t
    assert "container's own `/tmp`" in t
    assert "<run>.records/" in t


# --- fr-phase-executor: the return contract names visual: ------------------


def test_fr_phase_executor_return_contract_names_visual_section() -> None:
    text = FR_PHASE_EXECUTOR.read_text()
    heading = "## What you return"
    start = text.index(heading)
    later_headings = [text.index(h) for h in ("## Long commands",) if h in text]
    end = min((h for h in later_headings if h > start), default=len(text))
    block = text[start:end]
    assert "`visual:`" in block


# --- fr-goal: visual on UI rows, browser check, reviewer, fresh deliver ----


def test_fr_goal_section1_brainstorm_names_visual_on_ui_rows() -> None:
    t = _goal_section(1).lower()
    assert "visual" in t
    assert "limits" in t


def test_fr_goal_section5_implement_names_the_browser_check() -> None:
    t = _goal_section(5).lower()
    assert "browser check" in t
    assert "visual" in t


def test_fr_goal_section6_review_phase_names_the_reviewers_own_screenshots() -> None:
    t = _goal_section(6).lower()
    assert "visual" in t
    assert "own" in t and "screenshot" in t
    assert "capture script" in t
    # the reviewer audits the script's coverage, not only its output (p3-r3)
    assert "covers every name the row declares" in t


def test_fr_goal_section5_says_where_shots_live() -> None:
    t = _goal_section(5)
    assert "git-ignored" in t and "`/tmp`" in t


def test_fr_goal_section8_deliver_names_fresh_capture() -> None:
    t = _goal_section(8).lower()
    assert "visual" in t
    assert "fresh" in t


# --- fr-brainstorming §3: visual with states/interactions, limits asked ----


def test_fr_brainstorming_section3_names_visual_states_and_interactions() -> None:
    text = FR_BRAINSTORMING.read_text()
    heading = "## 3. Acceptance rows"
    start = text.index(heading)
    end = text.index("## Scope notes")
    block = text[start:end].lower()
    assert "visual" in block
    assert "states" in block and "interactions" in block
    assert "limits" in block


# --- fr-plan: the phase that builds the UI links the visual row ------------


def test_fr_plan_links_the_visual_row_on_the_phase_that_builds_the_ui() -> None:
    text = FR_PLAN.read_text()
    heading = "**Acceptance linkage:**"
    start = text.index(heading)
    end = text.index("\n", text.index("\n", start) + 1)
    # widen to the whole bullet (ends at the next "- **" bullet)
    end = text.index("\n- **", start)
    block = text[start:end].lower()
    assert "visual" in block
    assert "browser check" in block
