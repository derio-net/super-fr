"""Tripwire: the settle loop's wording in the skills and briefs (spec
2026-11-23-pr-readiness-wait R9, R10, §E; Test Plan 9).

fr-goal, fr-debugging and the hand-run close-out each run `fr pr settle --wait`
and fix under the same rules: a conflict by merging `origin/<base>` (never a rebase
or a force-push), a red check by an ordinary commit, at most three fix rounds. The
limit and the second settle after `deliver` are skill text, not counted by fr, so
only this test notices a paraphrase that drops them. Every match runs on normalised
text (whitespace collapsed, casefolded), so a rewrap cannot hide a phrase.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "plugins" / "super-fr" / "skills"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).casefold()


def _skill(name: str) -> str:
    return _norm((SKILLS / name / "SKILL.md").read_text())


def _assert_fix_rules(text: str, where: str) -> None:
    for phrase in (
        "fr pr settle --wait",
        "merging `origin/<base>`",
        "never rebase or force-push",
        "ordinary commit",
        "fr push",
        "three fix rounds",
    ):
        assert phrase in text, f"{where} does not name {phrase!r}"


def test_fr_goal_settles_before_deliver_and_once_more_after_its_push() -> None:
    text = _skill("fr-goal")
    _assert_fix_rules(text, "fr-goal")
    assert "before resolving `deliver`" in text
    assert "after the `deliver` resolve's push" in text
    assert "settle.<key>: <mode> — <reason>" in text


def test_fr_debugging_settles_as_its_last_step() -> None:
    text = _skill("fr-debugging")
    _assert_fix_rules(text, "fr-debugging")
    assert "last step" in text
    assert "settle-conflicts" in text and "settle-ci" in text
    # The settle step comes after `fr pr create`.
    assert text.index("fr pr settle --wait") > text.index("fr pr create")


def test_the_deliver_brief_carries_one_settle_instruction() -> None:
    from fr.commands.run_cmd import _settle_brief
    from fr.workflow.model import Step

    deliver = Step(id="deliver", kind="agent", evidence=["settle"])
    brief = _settle_brief(deliver)
    assert set(brief) == {"settle"}
    line = _norm(brief["settle"])
    assert "\n" not in brief["settle"]
    _assert_fix_rules(line, "the deliver brief's settle line")
    assert "before resolving `deliver`" in line
    assert "after the `deliver` resolve's push" in line


def test_a_step_with_no_settle_evidence_gets_no_settle_line() -> None:
    from fr.commands.run_cmd import _settle_brief
    from fr.workflow.model import Step

    assert _settle_brief(Step(id="spec", kind="agent", evidence=["tests"])) == {}


@pytest.fixture
def closeout_text(tmp_path: Path) -> str:
    from fr.run.closeout import branch_closeout_brief

    subprocess = __import__("subprocess")
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    return branch_closeout_brief(tmp_path, "fix/thing")


def test_the_closeout_brief_settles_the_housekeeping_pr_after_it_opens(
    closeout_text: str,
) -> None:
    text = _norm(closeout_text)
    _assert_fix_rules(text, "the close-out brief")
    assert text.index("fr pr settle --wait") > text.index("open the housekeeping pr")
    assert "no override" in text
