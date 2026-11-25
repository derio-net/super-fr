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

pytestmark = pytest.mark.own_artifacts

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
        "printed line says",
        "exit 2",
        "not a fix round",
        "fr push",
        "three fix rounds",
    ):
        assert phrase in text, f"{where} does not name {phrase!r}"


def test_fr_goal_settles_before_deliver_and_once_more_after_its_push() -> None:
    text = _skill("fr-goal")
    _assert_fix_rules(text, "fr-goal")
    assert "before resolving `deliver`" in text
    assert "after the `deliver` resolve's push" in text
    assert "under the same loop" in text
    assert "settle.<key>: <mode> — <reason>" in text


def test_fr_debugging_settles_as_its_last_step() -> None:
    text = _skill("fr-debugging")
    _assert_fix_rules(text, "fr-debugging")
    assert "last step" in text
    assert "settle-conflicts" in text and "settle-ci" in text
    # p3-r4: the override decision is a journal commit; left unpushed it is #871.
    override = text[text.index("settle-conflicts") :]
    assert "fr push" in override[: override.index(".") + 200]
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
    assert "under the same loop" in line


@pytest.mark.parametrize("manifest", ["fr-goal.yaml", "fr-goal-light.yaml"])
def test_the_shipped_deliver_brief_carries_the_settle_line(
    manifest: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p3-r5: built by the real brief builder from the SHIPPED manifest, so a
    manifest that drops `settle` from deliver's evidence fails here."""
    import subprocess

    from fr.commands.run_cmd import _build_brief
    from fr.run.model import RunState
    from fr.settle.instructions import DELIVER_LINE
    from fr.workflow.model import parse_manifest

    shape = parse_manifest(
        (REPO_ROOT / "plugins" / "super-fr" / "workflows" / manifest).read_text()
    )
    (deliver,) = [s for s in shape.steps if s.id == "deliver"]
    git = ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    monkeypatch.chdir(tmp_path)
    state = RunState(
        run="r1",
        workflow=f"{shape.workflow}@1",
        branch="b",
        started="2026-11-23T00:00:00Z",
        cursor="deliver",
        steps={},
    )
    assert _build_brief(deliver, state)["settle"] == DELIVER_LINE


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
    assert "exits 0 `managed`" in text
