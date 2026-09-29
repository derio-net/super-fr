"""`fr.run.review_return` — what a reviewer returned, read out of its final
message (spec 2026-09-29-opencode-observe §D, R5/R7)."""

from __future__ import annotations

from fr.run.review_return import coverage_divergence, returned_coverage

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
