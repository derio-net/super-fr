"""fr-spec-reviewer checks the spec as the contract (spec
`2026-09-29-spec-is-the-contract-design.md` §D, R6).

It reviews the spec against the operator's recorded decisions, the codebase it
names, and itself — never against the raw input, which only brainstorm reads.
The light path's combined spec-and-plan review keeps its plan section. This
pins the agent's front-matter and prose so an edit cannot quietly bring the
input back into the review.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT = REPO_ROOT / "plugins/super-fr/agents/fr-spec-reviewer.md"


def _frontmatter(text: str) -> dict:
    assert text.startswith("---\n"), "agent file must open with YAML frontmatter"
    _, fm, _ = text.split("---\n", 2)
    return yaml.safe_load(fm)


def _body(text: str) -> str:
    return text.split("---\n", 2)[2]


def test_it_checks_three_things_in_order() -> None:
    body = _body(AGENT.read_text())
    assert "## What you check — three things, in this order" in body
    positions = [
        body.index(label)
        for label in (
            "**Decisions vs. spec.**",
            "**Codebase reality.**",
            "**Internal consistency.**",
        )
    ]
    assert positions == sorted(positions)


def test_it_never_reviews_against_the_raw_input() -> None:
    text = AGENT.read_text()
    description = _frontmatter(text)["description"].casefold()
    assert "raw input" not in description and "traceability" not in description
    body = _body(text).casefold()
    for gone in ("input-coverage", "requirement-fidelity", "design-inventory", "traceability"):
        assert gone not in body, gone


def test_the_light_paths_plan_section_stays() -> None:
    body = _body(AGENT.read_text())
    assert "## When the brief names a plan too (`spec-plan-review`)" in body
    assert "target: spec|plan" in body
