"""Phase 6: fr-debugging records to the debug-scope journal.

Guards that fr-debugging step 3 writes the investigation via the `fr journal`
debug scope (not a hand-written debugging/<slug>.md) and step 4 derives its PR
body from `fr journal render --scope debug`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.own_artifacts

REPO_ROOT = Path(__file__).resolve().parents[2]
FR_DEBUGGING = REPO_ROOT / "plugins/super-fr/skills/fr-debugging/SKILL.md"


def _text() -> str:
    return FR_DEBUGGING.read_text()


def test_records_to_debug_scope_journal() -> None:
    assert "fr journal add --scope debug" in _text()


def test_pr_body_rendered_from_debug_journal() -> None:
    assert "fr journal render --scope debug" in _text()


def test_new_journals_live_in_journals_tree() -> None:
    """New debug journals go under journals/, not the old debugging/ write path."""
    assert "journals/" in _text()


def test_mentions_hypothesis_trail_kinds() -> None:
    """The rejected-hypotheses trail — the crash-safe payoff — must be recorded."""
    t = _text()
    assert "hypothesis" in t and "ruled-out" in t


_COPIES = (
    FR_DEBUGGING,
    REPO_ROOT / ".opencode/skills/fr-debugging/SKILL.md",
    REPO_ROOT / ".hermes/skills/fr/fr-debugging/SKILL.md",
)


def _deliver(path: Path) -> str:
    text = path.read_text()
    start = text.index("## 4. Deliver")
    return text[start : text.index("\n## ", start + 1)]


@pytest.mark.parametrize("skill", _COPIES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_review_record_is_pushed_before_the_closeout_relay(skill: Path) -> None:
    """gh#871: `fr journal add` commits locally and never pushes, so a review
    recorded after the PR opened stays off the PR unless Deliver pushes it —
    and checks the branch is level with its upstream — before stopping."""
    deliver = _deliver(skill)
    review = deliver.index("--kind review")
    push = deliver.find("fr push", review)  # R12: the skills push through `fr push`
    relay = deliver.index("closeout: fr pickup --branch")
    assert review < push < relay, (
        f"{skill.relative_to(REPO_ROOT)}: Deliver must `fr push` after the review "
        "record and before relaying the closeout line (gh#871)."
    )
    assert "@{u}..HEAD" in deliver[push:relay], (
        f"{skill.relative_to(REPO_ROOT)}: Deliver must confirm the branch is level "
        "with its upstream before the closeout relay (gh#871)."
    )


# ------------------------------------- R10: the skill drives a run (l-tests-r5)


@pytest.mark.parametrize("skill", _COPIES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_the_skill_starts_its_own_run_only_on_a_branch_with_none(skill: Path) -> None:
    """batch-merge-readiness R10: the skill starts the shipped `fr-debugging` run on the
    fix branch, starts none on a branch that already has a run (a check the skill makes,
    since `fr run start` refuses only a second run of the same workflow), and records the
    review through the `review` step's record."""
    flat = " ".join(skill.read_text().split())
    assert "fr run start fr-debugging --branch" in flat
    assert "a branch that already has a run (a feature's fr-goal run) keeps it — start none" in flat
    assert "`fr run start` refuses only a second run of the same workflow" in flat
    assert "refuses a second run on a branch" not in flat  # the old, false claim
    assert "Record the review through `review`'s step record (§3) alone" in flat
    assert "never `fr journal add --kind review`" in flat
