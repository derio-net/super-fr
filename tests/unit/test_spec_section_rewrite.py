"""`rewrite_section` — the line-rewrite helper under `fr verification set`
(spec 2026-10-14 exit-gates R8): it inserts or rewrites exactly one grammar line
and keeps every other byte."""

from __future__ import annotations

import pytest
from fr.verification.spec_section import SectionError, parse_section, rewrite_section

DOC = (
    "# Spec\n\n## Requirements\n\nR1. x\n\n## Verification\n\n"
    "strategy: candidate\n"
    "gate: security\n"
    "gate: a=devops\n"
    "- a: live — needs a release\n"
    "- b: none — covered elsewhere\n"
    "\nSome prose.\n\n## Test Plan\n\nstuff\n"
)


def _diff(old: str, new: str) -> tuple[list[str], list[str]]:
    o, n = old.splitlines(keepends=True), new.splitlines(keepends=True)
    return [x for x in o if x not in n], [x for x in n if x not in o]


def test_it_rewrites_the_strategy_line_and_nothing_else() -> None:
    new = rewrite_section(DOC, strategy="live")
    assert _diff(DOC, new) == (["strategy: candidate\n"], ["strategy: live\n"])
    assert new.count("\n") == DOC.count("\n")


def test_it_rewrites_the_run_gate_but_not_a_row_gate() -> None:
    new = rewrite_section(DOC, gate="tester")
    assert _diff(DOC, new) == (["gate: security\n"], ["gate: tester\n"])


def test_it_rewrites_a_row_gate_and_a_row_bullet() -> None:
    new = rewrite_section(DOC, row="a", gate="tester", strategy="live", reason="new reason")
    old, added = _diff(DOC, new)
    assert old == ["gate: a=devops\n", "- a: live — needs a release\n"]
    assert added == ["gate: a=tester\n", "- a: live — new reason\n"]


def test_it_inserts_a_missing_row_bullet_and_gate_beside_their_kind() -> None:
    new = rewrite_section(DOC, row="c", gate="tester", strategy="live", reason="why")
    assert "gate: a=devops\ngate: c=tester\n- a:" in new
    assert "- b: none — covered elsewhere\n- c: live — why\n" in new
    assert parse_section(new).row_gates["c"] == "tester"  # type: ignore[union-attr]


def test_it_inserts_a_missing_strategy_line_first() -> None:
    doc = "# S\n\n## Verification\n\ngate: tester\n\n## End\n"
    assert rewrite_section(doc, strategy="live") == (
        "# S\n\n## Verification\n\nstrategy: live\ngate: tester\n\n## End\n"
    )


def test_it_adds_grammar_to_a_prose_only_section_and_keeps_the_prose() -> None:
    doc = "# S\n\n## Verification\n\nWe will walk it by hand.\n\n## End\n"
    new = rewrite_section(doc, strategy="candidate")
    assert (
        new
        == "# S\n\n## Verification\n\nstrategy: candidate\n\nWe will walk it by hand.\n\n## End\n"
    )


def test_a_row_without_a_reason_writes_a_bare_bullet() -> None:
    assert "- c: candidate\n" in rewrite_section(DOC, row="c", strategy="candidate")


def test_a_fenced_quote_of_the_grammar_is_not_the_section() -> None:
    doc = "# S\n\n```\n## Verification\n\nstrategy: live\n```\n"
    with pytest.raises(SectionError, match="no `## Verification` section"):
        rewrite_section(doc, strategy="candidate")


def test_a_spec_with_no_section_is_refused_with_how_to_add_one() -> None:
    with pytest.raises(SectionError) as e:
        rewrite_section("# S\n\n## Requirements\n", strategy="live")
    assert "## Verification" in str(e.value) and "strategy: <name>" in str(e.value)


def test_crlf_files_keep_their_line_endings() -> None:
    doc = "# S\r\n\r\n## Verification\r\n\r\nstrategy: candidate\r\n"
    assert rewrite_section(doc, gate="tester") == doc + "gate: tester\r\n"


def test_a_reason_with_a_newline_is_refused() -> None:
    with pytest.raises(SectionError, match="one non-empty line"):
        rewrite_section(DOC, row="a", strategy="live", reason="a\nb")
