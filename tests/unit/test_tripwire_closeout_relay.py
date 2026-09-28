"""CI tripwire: every PR-ending skill relays the branch close-out line.

Spec `2026-09-28-closeout-always-design.md` §E / R6 / R8: fr-debugging's
Deliver, fr-execute's step 5 (standalone dispatched flow) and fr-isolation's
merged-PR cleanup guidance all point at `fr pickup --branch <b>` as the one
close-out brief, and fr-goal's Post-merge close-out names `fr archive
--branch <b>` rather than the old `fr archive <plan-dir>`. This is pinned in
every shipped copy — canonical plus both generated mirrors (OpenCode,
Hermes) — because a canonical-only edit that is never re-synced ships nothing
(the exact defect class `test_tripwire_opencode_skills_sync.py` /
`test_tripwire_hermes_skills_sync.py` already guard from the other side).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _copies(name: str) -> tuple[Path, ...]:
    return (
        REPO_ROOT / "plugins" / "super-fr" / "skills" / name / "SKILL.md",
        REPO_ROOT / ".opencode" / "skills" / name / "SKILL.md",
        REPO_ROOT / ".hermes" / "skills" / "fr" / name / "SKILL.md",
    )


FR_DEBUGGING = _copies("fr-debugging")
FR_EXECUTE = _copies("fr-execute")
FR_ISOLATION = _copies("fr-isolation")
FR_GOAL = _copies("fr-goal")


@pytest.mark.parametrize("skill", FR_DEBUGGING, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_fr_debugging_deliver_relays_pickup_branch(skill: Path) -> None:
    text = skill.read_text()
    assert "fr pickup --branch" in text, (
        f"{skill.relative_to(REPO_ROOT)} Deliver no longer relays `fr pickup --branch "
        "<branch>` after the PR opens (spec §E, R6). Restore it in the canonical skill "
        "and re-sync both mirrors."
    )


@pytest.mark.parametrize("skill", FR_EXECUTE, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_fr_execute_step5_relays_pickup_branch(skill: Path) -> None:
    text = skill.read_text()
    assert "fr pickup --branch" in text, (
        f"{skill.relative_to(REPO_ROOT)} step 6 no longer relays `fr pickup --branch "
        "<phase-branch>` for the standalone dispatched flow (spec §E, R8). Restore it "
        "in the canonical skill and re-sync both mirrors."
    )


@pytest.mark.parametrize("skill", FR_ISOLATION, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_fr_isolation_merged_pr_cleanup_names_pickup_branch(skill: Path) -> None:
    text = skill.read_text()
    assert "fr pickup --branch" in text, (
        f"{skill.relative_to(REPO_ROOT)} no longer names `fr pickup --branch <b>` as "
        "the route for cleaning up after a merged PR (spec §E, R8). Restore it in the "
        "canonical skill and re-sync both mirrors."
    )


@pytest.mark.parametrize("skill", FR_GOAL, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_fr_goal_post_merge_closeout_uses_archive_branch(skill: Path) -> None:
    text = skill.read_text()
    assert "fr archive --branch <b>" in text, (
        f"{skill.relative_to(REPO_ROOT)} Post-merge close-out no longer names `fr "
        "archive --branch <b>` (spec §E). Restore it in the canonical skill and "
        "re-sync both mirrors."
    )
    assert "fr archive <plan-dir>" not in text, (
        f"{skill.relative_to(REPO_ROOT)} Post-merge close-out still names the old "
        "`fr archive <plan-dir>` form — replace it with `fr archive --branch <b>` "
        "(spec §E) and re-sync both mirrors."
    )
