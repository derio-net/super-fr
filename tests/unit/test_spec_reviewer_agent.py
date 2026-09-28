"""spec 2026-09-28-requirements-traceability-design.md §D.

fr-spec-reviewer must check traceability to the raw input FIRST, before its
three pre-existing checks (decisions, codebase reality, internal consistency),
so the codebase lookups cannot crowd it out (d10) — #759 quoted the agent's own
`description:` as the defect (review r9). This test pins the agent's
front-matter and prose so a length-trimming edit cannot silently drop the
ordering or the partition contract.
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


def test_description_names_traceability_to_the_input() -> None:
    fm = _frontmatter(AGENT.read_text())
    assert "traceability" in fm["description"].lower()
    assert "input" in fm["description"].lower()


def test_checks_heading_says_four_things_traceability_first() -> None:
    text = AGENT.read_text()
    heading_start = text.index("## What you check")
    assert "four things" in text[heading_start : heading_start + 80]
    heading_end = text.index("\n\n", heading_start)
    heading_line = text[heading_start:heading_end]
    trace_pos = heading_line.lower().find("traceability")
    assert trace_pos != -1, "the checks heading must name traceability"

    body = _body(text)
    # The first numbered check in the body must be traceability, not decisions.
    first_numbered = body.index("\n1. ")
    following = body[first_numbered : first_numbered + 400].lower()
    assert "traceability" in following or "input" in following


def test_body_names_the_input_coverage_return_and_four_labels() -> None:
    body = _body(AGENT.read_text())
    assert "input-coverage" in body
    for label in ("covered", "deferred", "context", "missing"):
        assert label in body.lower()


def test_body_names_unconfirmed_as_the_resolution_for_invented_or_reinterpreted() -> None:
    body = _body(AGENT.read_text())
    assert "unconfirmed" in body
    assert "invented" in body
    assert "reinterpreted" in body
    assert "dropped" in body
