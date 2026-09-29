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


def test_body_names_invented_reinterpreted_and_dropped_findings() -> None:
    body = _body(AGENT.read_text())
    for word in ("invented", "reinterpreted", "dropped"):
        assert word in body


def test_the_agent_names_both_fidelity_blocks_in_its_checks_and_return_template() -> None:
    """spec 2026-09-29 §G: clause-by-clause fidelity and the design inventory."""
    body = _body(AGENT.read_text())
    checks = body[body.index("## What you check") : body.index("## Tag every finding")]
    template = body[body.index("## What you return") :]
    for block in ("requirement-fidelity", "design-inventory"):
        assert block in checks, f"the checks name no {block} block"
        assert f"```{block}" in template, f"the return template omits the {block} block"


def test_the_agent_no_longer_resolves_invented_or_reinterpreted_unconfirmed() -> None:
    """d1-remove-only: removed (or refuted), never confirmed, never asked."""
    body = _body(AGENT.read_text())
    assert "unconfirmed" not in body.replace("never confirmed", "")
    assert "never confirmed" in body
    assert "removed" in body


def test_traceability_findings_are_always_tagged_in_scope() -> None:
    """spec §D: "All three are tagged in scope." fr's fidelity witness holds a
    finding tagged `review_scope: out` open-for-the-gate — a mistagged invented/
    reinterpreted/dropped finding would be stranded with no way to close it. The
    traceability section (not the later, general "tag every finding" section)
    must state this explicitly, with the reason."""
    body = _body(AGENT.read_text())
    trace_start = body.index("## What you check")
    scope_start = body.index("## Tag every finding")
    trace_section = body[trace_start:scope_start]

    assert "always" in trace_section.lower()
    assert "in scope" in trace_section.lower()
    assert "never" in trace_section.lower() and "out" in trace_section.lower()
    assert "review_scope" in trace_section or "out of scope" in trace_section.lower()


def _first_block(body: str, fence: str) -> str:
    start = body.index(f"```{fence}\n")
    end = body.index("```", start + 3 + len(fence))
    return body[start : end + 3] + "\n"


def test_the_agents_example_blocks_pass_frs_own_checks() -> None:
    """q3 (phase 2 review): the prose's example `requirement-fidelity` and
    `design-inventory` blocks are fed through the checks fr runs at resolve, so a
    template whose fence, header or label forms drift from `fr.fidelity`'s grammar
    fails here instead of at the first live spec-review."""
    from fr.fidelity import check_fidelity, check_inventory
    from fr.journal.model import JournalEntry

    body = _body(AGENT.read_text())
    spec = (
        "# spec\n\n## Requirements\n\n| id | requirement | source |\n|---|---|---|\n"
        '| R1 | x | input "a number field in the same style as the article view" |\n'
        '| R2 | y | input "− / + on each article card" |\n\n'
        "## Design\n\n### A. Quantities\n\n### B. Storage\n"
    )
    stamp = dict(scope="spec", created="2026-09-29T00:00:00", title="t")
    entries = [
        JournalEntry(kind="discovery", id="input-x", input=True, **stamp,  # type: ignore[arg-type]
                     body="a number field in the same style as the article view; "
                          "− / + on each article card"),
        JournalEntry(kind="finding", id="s4", state="open", **stamp),  # type: ignore[arg-type]
        JournalEntry(kind="finding", id="s7", state="open", **stamp),  # type: ignore[arg-type]
    ]  # fmt: skip

    fidelity, _ = check_fidelity(_first_block(body, "requirement-fidelity"), spec, entries)
    inventory, _ = check_inventory(_first_block(body, "design-inventory"), spec, entries)

    assert fidelity == []
    assert inventory == []
