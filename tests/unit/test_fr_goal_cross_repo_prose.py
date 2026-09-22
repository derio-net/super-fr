"""fr-goal §2's cross-repo agents — what the prose may and may not claim.

Review p3r-1 of the 2026-09-22 harness-argument-neutrality plan, verified
against the hook: `fr-worktree-create.sh` sends every `agent-*` worktree to
`mimic_default`, which cuts it under the toplevel of the CALLER's cwd. So on
Claude Code `isolation: "worktree"` gives a cross-repo agent a worktree of THIS
repo, never the target one — the long-standing claim that the flag gives it "a
fresh pipeline in a different repo" was false, and it rode into the rule and the
guard hook's refusal message too. Every harness's agent enters isolation in the
other repo itself, and `fr isolation up` defaults `--repo` to the cwd a
delegated agent inherits from its parent — hence `--repo`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FR_GOAL_COPIES = (
    REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-goal" / "SKILL.md",
    REPO_ROOT / ".opencode" / "skills" / "fr-goal" / "SKILL.md",
    REPO_ROOT / ".hermes" / "skills" / "fr" / "fr-goal" / "SKILL.md",
)
GUARD = REPO_ROOT / "plugins" / "super-fr" / "hooks" / "fr-phase-executor-guard.sh"


def _section_2(text: str) -> str:
    return text[text.index("### 2. spec-review") : text.index("### 3.")]


@pytest.mark.parametrize("skill", FR_GOAL_COPIES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_every_cross_repo_agent_enters_isolation_in_its_own_repo(skill: Path) -> None:
    section = " ".join(_section_2(skill.read_text()).split())
    assert "fr isolation up --repo" in section, (
        "fr-goal §2 must tell EVERY cross-repo agent to enter isolation in its own repo, "
        "with --repo (a delegated agent inherits the parent's cwd)"
    )


@pytest.mark.parametrize("skill", FR_GOAL_COPIES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_the_flag_is_not_claimed_to_reach_another_repo(skill: Path) -> None:
    section = " ".join(_section_2(skill.read_text()).split())
    assert "right *here*" not in section and "fresh pipeline in a *different* repo" not in section


def test_the_guard_refusal_cites_the_current_sections_and_no_false_premise() -> None:
    """Review p3r-3: the refusal an agent actually reads said "fr-goal §3 DOES
    pass the flag … §6's phase executors" — stale numbers AND the p3r-1 premise."""
    text = GUARD.read_text()
    assert "§3 DOES pass the flag" not in text
    assert "§6" not in text
