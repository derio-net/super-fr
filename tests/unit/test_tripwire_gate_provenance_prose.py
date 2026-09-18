"""CI tripwire: fr-goal must keep telling the ENFORCED harness to type the truth.

`--answered-by` defaults to `agent` on purpose — the honesty property of spec
§3.D.2 is that the stronger claim ("a human answered this") has to be typed
deliberately. That default only works if the one harness where an operator
really does answer is told to type it. Review finding `r4-i1` found that
nothing did: the flag appeared nowhere in `plugins/` or `.opencode/`, so every
Claude Code run would have recorded `answered_by: agent` and every PR body
would have said "no operator answered it" on runs where one did. A warning that
fires every time is a warning nobody reads.

Phase 5 added the prose. This pins it, because `r4-i1` asked for the pin and
review `r5-c1` found the journal had CLAIMED the pin existed when it did not —
and §5 of this same file was compressed for line budget twice in one phase, once
silently changing "without" to "with no" and breaking another tripwire. The
clause is one line in a file under constant line pressure; that is exactly what
a tripwire is for.

Mirrors are byte-identical copies, so asserting over all three also catches a
sync that ran against a reverted canonical.
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


@pytest.mark.parametrize("skill", FR_GOAL_COPIES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_fr_goal_tells_the_operator_path_to_record_operator_provenance(skill: Path) -> None:
    text = skill.read_text()
    assert "--answered-by operator" in text, (
        f"{skill.relative_to(REPO_ROOT)} no longer tells the orchestrator to record "
        "operator provenance. `--answered-by` defaults to `agent`, so without this "
        "clause every Claude Code run — the one harness where a human actually "
        "answers — records `answered_by: agent`, and `fr run check` and the "
        "delivered PR body both say 'no operator answered it' on runs where one "
        "did (review r4-i1). Restore it in the canonical skill and re-sync."
    )


@pytest.mark.parametrize("skill", FR_GOAL_COPIES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_the_clause_is_conditional_not_boilerplate(skill: Path) -> None:
    """The flag must be scoped to "a human actually replied", never presented as
    something to append every time — an unconditional instruction would turn the
    deliberate claim back into a default, which is the whole thing `r4-i1`
    protects."""
    text = skill.read_text()
    line = next(ln for ln in text.splitlines() if "--answered-by operator" in ln)
    assert "only if" in line or "once the operator" in line, (
        "the `--answered-by operator` clause lost its condition — it must name "
        "when NOT to type it, or it becomes boilerplate an agent appends blindly: "
        f"{line!r}"
    )
