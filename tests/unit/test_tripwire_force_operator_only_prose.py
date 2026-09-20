"""CI tripwire: the fr-isolation skill must keep stating decision `d3`'s
`--force` obligation, in every shipped copy.

Decision `d3` (spec `2026-09-20-isolation-reap-data-loss-guards-design.md`
§3.6) attaches an obligation the code cannot enforce: an agent may not reach
for `fr isolation down --force` on its own initiative — only when the
operator has asked for it — and when it does ask, it first names what would
be destroyed. Nothing can test "an agent decided by itself", so this is
prose, and the spec is explicit that it must be stated as *knowingly* prose
rather than borrowing the credibility of an enforced rule (the
fixture-composition defect this repo has a scar from). This test pins the
prose existing, not the obligation being followed — that half is
unenforceable by construction.

Matched on the semantic markers of the obligation, via regex, NOT on exact
sentence wording. The first version of this file asserted the literal strings
"not reach for `--force`" and "names what would be destroyed", and the very
next edit of the skill — a rewrap in the same PR — broke both on a pronoun and
a verb conjugation. A tripwire whose docstring claims robustness it does not
have is the defect class this repo keeps finding; these patterns tolerate
"it"/"`--force`", "name"/"names", and either "not" or "never".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

SKILL_COPIES = (
    REPO_ROOT / "plugins" / "super-fr" / "skills" / "fr-isolation" / "SKILL.md",
    REPO_ROOT / ".opencode" / "skills" / "fr-isolation" / "SKILL.md",
    REPO_ROOT / ".hermes" / "skills" / "fr" / "fr-isolation" / "SKILL.md",
)


@pytest.mark.parametrize("skill", SKILL_COPIES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_agent_must_not_reach_for_force_on_its_own_initiative(skill: Path) -> None:
    text = skill.read_text()
    assert re.search(r"(?:not|never) reach for .{0,60}own initiative", text, re.S), (
        f"{skill.relative_to(REPO_ROOT)} no longer states decision d3's first half — an "
        "agent may not decide to use --force on its own initiative, only when the "
        "operator asks for it. Restore it in the canonical skill and re-sync."
    )


@pytest.mark.parametrize("skill", SKILL_COPIES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_agent_must_name_what_would_be_destroyed_before_asking(skill: Path) -> None:
    text = skill.read_text()
    assert re.search(r"names? what would be destroyed", text), (
        f"{skill.relative_to(REPO_ROOT)} no longer states decision d3's second half — "
        "before an agent asks the operator to use --force, it must first name what "
        "would be destroyed. Restore it in the canonical skill and re-sync."
    )


@pytest.mark.parametrize("skill", SKILL_COPIES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_the_clause_announces_it_is_unenforced(skill: Path) -> None:
    """The repo's convention is that standing rules are enforced by tests; an
    unenforced one must say so plainly rather than imply the same standing as
    the enforced ones (spec §3.6: "stated as knowingly prose")."""
    text = skill.read_text()
    assert re.search(r"no tripwire", text, re.I), (
        f"{skill.relative_to(REPO_ROOT)} states the --force obligation but does not "
        "say plainly that nothing enforces it — restore the 'no tripwire for this' "
        "sentence alongside the obligation."
    )
