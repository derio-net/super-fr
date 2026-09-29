"""`fr.run.review_return` — what a reviewer returned, read out of its final
message (spec 2026-09-29-opencode-observe §D, R5/R7)."""

from __future__ import annotations

import pytest
from fr.run.review_return import (
    FindingsBlockError,
    coverage_divergence,
    parse_findings_block,
    returned_coverage,
)

BLOCK = """```input-coverage
| span | coverage |
|---|---|
| "fr observes example sessions" | R1 |
| "for the demo" | context |
```"""

RECORD_RETURN = """schema_version: 4
journal:
  - kind: review
    id: review-1
    title: spec review, round 1
    body: |
      Reviewed the spec against the input.

      ```input-coverage
      | span | coverage |
      |---|---|
      | "fr observes example sessions" | R1 |
      | "for the demo" | context |
      ```
"""


# --- returned_coverage -------------------------------------------------------


def test_a_yaml_record_return_yields_the_review_entry_block() -> None:
    assert returned_coverage(RECORD_RETURN) == BLOCK


def test_a_yaml_record_inside_a_yaml_fence_is_read_too() -> None:
    fenced = f"Here is my record:\n\n```yaml\n{RECORD_RETURN}```\n"
    assert returned_coverage(fenced) == BLOCK


def test_a_prose_return_falls_back_to_the_dedented_fenced_block() -> None:
    prose = "I reviewed it.\n\n" + "\n".join("    " + line for line in BLOCK.split("\n")) + "\n"
    assert returned_coverage(prose) == BLOCK


def test_a_return_with_no_block_is_none() -> None:
    assert returned_coverage("Reviewed; nothing to say.") is None
    assert (
        returned_coverage("schema_version: 4\njournal:\n  - kind: review\n    body: none\n") is None
    )


# --- coverage_divergence -----------------------------------------------------


def test_equal_blocks_do_not_diverge_whatever_their_line_endings() -> None:
    crlf = BLOCK.replace("\n", "\r\n")
    trailing = "\n".join(line + "  " for line in BLOCK.split("\n")) + "\n\n"
    assert coverage_divergence(BLOCK, BLOCK) is None
    assert coverage_divergence(crlf, BLOCK) is None
    assert coverage_divergence(BLOCK, trailing) is None


def test_a_relabelled_row_is_named_with_both_lines() -> None:
    relabelled = BLOCK.replace('"for the demo" | context', '"for the demo" | R1')

    why = coverage_divergence(relabelled, BLOCK)

    assert why is not None
    assert "line 5" in why
    assert "'| \"for the demo\" | R1 |'" in why
    assert "'| \"for the demo\" | context |'" in why


def test_a_re_cut_block_names_the_first_row_it_moved() -> None:
    recut = BLOCK.replace(
        '| "fr observes example sessions" | R1 |',
        '| "fr observes" | R1 |\n| "example sessions" | R1 |',
    )

    why = coverage_divergence(recut, BLOCK)

    assert why is not None and "line 4" in why
    assert "'| \"fr observes\" | R1 |'" in why


# --- parse_findings_block ----------------------------------------------------


def test_a_findings_block_parses_to_id_scope_summary() -> None:
    text = "Reviewed phase 2.\n\n```findings\np2a-r1 | in | x\np2a-r2 | out | y | z\n```\n"
    assert parse_findings_block(text) == [("p2a-r1", "in", "x"), ("p2a-r2", "out", "y | z")]


def test_none_is_an_empty_block_and_no_block_is_none() -> None:
    assert parse_findings_block("Done.\n\n```findings\nnone\n```") == []
    assert parse_findings_block("Reviewed phase 2 and found nothing to raise.") is None


def test_the_trailing_block_is_the_one_read() -> None:
    text = "```findings\np1-r1 | in | old\n```\nthen\n```findings\np2-r1 | in | new\n```"
    assert parse_findings_block(text) == [("p2-r1", "in", "new")]


@pytest.mark.parametrize(
    "line",
    [
        "p2-r1 | maybe | bad scope",
        "p2-r1 | in",
        "p2-r1 in x",
        "finding-1 | in | not the brief's id",
        "p2ab-r1 | in | two letters",
        "p2-r1 | in |",
    ],
)
def test_a_malformed_line_raises_naming_it(line: str) -> None:
    with pytest.raises(FindingsBlockError, match="findings block"):
        parse_findings_block(f"```findings\n{line}\n```")
