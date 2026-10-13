"""Tripwire: nothing fr ships tells a session to add the `approved-fr` label (spec
2026-10-11-merge-train-safety §A "Briefs and the tripwire", R6).

The label is the operator's approval to merge, and the operator and every agent share
one forge identity: a brief or a skill that asked a session to add it would turn the
gate into a rubber stamp. Two checks:

1. every brief fr renders for a batch session carries `NO_APPROVAL_LINE`;
2. no shipped skill, agent or rule (canonical, or a generated OpenCode/Hermes/wheel
   mirror) has a sentence asking anyone to add the label, unless that sentence says
   never / do not / don't, or its subject is the operator.

The red hand-back brief joins check 1 when it ships (spec §C).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fr.triage.batch_dispatch import NO_APPROVAL_LINE, conflict_brief, render_brief
from fr.triage.model import Batch, Facts, Judgements

ROOT = Path(__file__).resolve().parents[2]

SHIPPED_GLOBS = (
    "plugins/*/skills/*/SKILL.md",
    "plugins/*/agents/*.md",
    "plugins/*/rules/*.md",
    ".claude/rules/*.md",
    ".claude/agents/*.md",
    "packages/fr/src/fr/agents/*.md",
    ".opencode/skills/*/SKILL.md",
    ".opencode/agent/*.md",
    ".opencode/instructions/*.md",
    ".hermes/skills/*/*/SKILL.md",
    ".hermes/SOUL.d/*.md",
)

_ASKS = (
    re.compile(r"--add-label[ =]approved-fr"),
    re.compile(r"labels\[\]=approved-fr"),  # the REST form
    re.compile(r"\b(add|apply|put|set|label)\b[^.]{0,40}approved-fr", re.IGNORECASE),
)
_EXEMPT = re.compile(r"\bnever\b|\bdo not\b|\bdon't\b|\boperator\b", re.IGNORECASE)
# A sentence ends at . ! ? or at a line end: a period-less Markdown bullet is its own
# sentence, so one bullet's "never" does not exempt the next (p1-r4).
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n")


def offending_sentences(text: str) -> list[str]:
    """The sentences of *text* that ask someone to add the approval label."""
    return [
        s.strip()
        for s in _SENTENCE.split(text)
        if any(p.search(s) for p in _ASKS) and not _EXEMPT.search(s)
    ]


def _shipped() -> list[Path]:
    return sorted({p for g in SHIPPED_GLOBS for p in ROOT.glob(g)})


# ------------------------------------------------------------------ the detector


@pytest.mark.parametrize(
    "text",
    [
        "When CI is green, add the approved-fr label.",
        "Run `gh pr edit 5 --add-label approved-fr` once green.",
        "Then put approved-fr on the PR.",
        # p1-r4: the three it used to miss
        "When it is green, label the PR approved-fr",
        "Run `gh api repos/o/r/issues/5/labels -f labels[]=approved-fr` once green.",
        "- Never push to main\n- add the approved-fr label when CI passes",
    ],
)
def test_an_instruction_to_add_the_label_is_caught(text: str) -> None:
    assert offending_sentences(text)


@pytest.mark.parametrize(
    "text",
    [
        NO_APPROVAL_LINE,
        "Do not add the approved-fr label yourself.",
        "The operator adds the approved-fr label to approve a merge.",
        "fr creates the approved-fr label when it is missing.",
    ],
)
def test_a_prohibition_or_an_operator_sentence_is_allowed(text: str) -> None:
    assert offending_sentences(text) == []


# ------------------------------------------------------------------ the shipped prose


def test_the_globs_reach_the_shipped_prose() -> None:
    names = {p.relative_to(ROOT).as_posix() for p in _shipped()}
    assert "plugins/super-fr/skills/fr-triage/SKILL.md" in names
    assert ".opencode/skills/fr-triage/SKILL.md" in names
    assert ".hermes/skills/fr/fr-triage/SKILL.md" in names


def test_no_shipped_skill_agent_or_rule_asks_for_the_label() -> None:
    found = {
        p.relative_to(ROOT).as_posix(): bad
        for p in _shipped()
        if (bad := offending_sentences(p.read_text(encoding="utf-8")))
    }
    assert found == {}, f"instructs adding the approval label outside the operator: {found}"


# ------------------------------------------------------------------ the briefs


def _inputs() -> tuple[Batch, Judgements, Facts]:
    batch = Batch.model_validate({"id": "x", "title": "t", "ids": ["widgets#1"]})
    judgements = Judgements.model_validate(
        {"schema": 9, "tiers": [{"n": 1, "title": "Now"}], "issues": {"widgets#1": {"tier": 1}},
         "batches": [batch.model_dump(mode="json")]}
    )  # fmt: skip
    facts = Facts.model_validate(
        {"scope": "o--widgets", "kind": "repo", "collected_at": "2026-10-11T00:00:00Z",
         "repos": ["o/widgets"], "issues": []}
    )  # fmt: skip
    return batch, judgements, facts


def test_every_brief_renderer_carries_the_line() -> None:
    import fr.cli  # noqa: F401 — the command modules import in the CLI's order (a cycle otherwise)
    from fr.commands.triage_batch_cmd import adopt_message

    batch, judgements, facts = _inputs()
    briefs = {
        "render_brief": render_brief(
            batch, judgements, facts, repo="o/widgets", closing_refs=[], reserved_version=None
        ),
        "conflict_brief": conflict_brief(
            batch, pr=1, head="h", paths=["a"], branch="b", base="origin/main", mirrors=[]
        ),
        "adopt_message": adopt_message(batch, "item", "old", "new", None, None),
    }
    assert {name for name, text in briefs.items() if NO_APPROVAL_LINE not in text} == set()
