"""fr.requirements — §B grammar, §C structural gate, §D coverage partition.

Spec `docs/superpowers/specs/2026-09-28-requirements-traceability-design.md`
Test Plan items 1-4, 12. Input entries are real `JournalEntry` objects
carrying the `input=true` header token (spec §A), built by `_input_entry`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.model import Matrix, Row
from fr.journal.model import JournalEntry
from fr.requirements import (
    Deferred,
    Requirement,
    Requirements,
    RequirementsError,
    Source,
    check_coverage,
    check_requirements,
    is_input_entry,
    normalise,
    parse_requirements,
    quote_matches,
)

# ── fixtures / helpers ──────────────────────────────────────────────────────


def _spec_entry(**kw: object) -> JournalEntry:
    base: dict[str, object] = dict(scope="spec", created="2026-09-28T00:00:00", title="t")
    return JournalEntry(**{**base, **kw})  # type: ignore[arg-type]


def _input_entry(id: str, body: str) -> JournalEntry:
    """A real spec-journal input entry: `kind=discovery` + `input=true` (§A)."""
    return _spec_entry(kind="discovery", id=id, body=body, input=True)


def _decision_entry(id: str) -> JournalEntry:
    return _spec_entry(kind="decision", id=id, body="")


def _finding_entry(id: str) -> JournalEntry:
    return _spec_entry(kind="finding", id=id, body="", state="open")


def _matrix(*origins: str) -> Matrix:
    return Matrix(
        org="acme",
        repo="widget",
        rows=tuple(
            Row(
                id=f"row-{i}",
                capability="cap",
                acceptance="text",
                origin=(o,),
                status="not-implemented",
            )
            for i, o in enumerate(origins)
        ),
    )


REQ_ONE = (
    "## Requirements\n\n"
    "| id | requirement | source |\n"
    "|---|---|---|\n"
    '| R1 | one thing | input "the quick brown fox" |\n'
)

# #759 replay fixture (Test Plan 4, 12): the "brief:" quote already public in
# https://github.com/derio-net/super-fr/issues/759 — only lines already
# quoted there, per third-party-privacy (nothing third-party here: it is
# this org's own issue, and the text is generic UI copy). It contains a
# literal " … " (the operator's own elision when writing the issue), which
# is exactly what pins §D's "a span is literal, never an elision" rule.
_759_INPUT = (
    (Path(__file__).parent.parent / "fixtures" / "requirements" / "759-input.md")
    .read_text()
    .strip()
)


# ── Test Plan 1: parse_requirements grammar ─────────────────────────────────


def test_well_formed_table() -> None:
    parsed = parse_requirements(REQ_ONE)
    assert parsed.items == (
        Requirement(id="R1", text="one thing", sources=(Source("input", "the quick brown fox"),)),
    )
    assert parsed.deferred == ()


def test_br_separated_sources() -> None:
    text = (
        "## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        '| R1 | x | input "a"<br>decision d1 |\n'
    )
    parsed = parse_requirements(text)
    assert parsed.items[0].sources == (
        Source("input", "a"),
        Source("decision", "d1"),
    )


def test_escaped_pipe_in_quote() -> None:
    text = (
        "## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        '| R1 | x | input "a \\| b" |\n'
    )
    parsed = parse_requirements(text)
    assert parsed.items[0].sources[0].value == "a | b"


def test_empty_source_cell_is_error() -> None:
    text = "## Requirements\n\n| id | requirement | source |\n|---|---|---|\n| R1 | x |  |\n"
    with pytest.raises(RequirementsError, match=r"line \d+.*empty `source`"):
        parse_requirements(text)


def test_wrong_cell_count_is_error() -> None:
    text = "## Requirements\n\n| id | requirement | source |\n|---|---|---|\n| R1 | x |\n"
    with pytest.raises(RequirementsError, match=r"line \d+.*columns"):
        parse_requirements(text)


def test_wrong_header_is_error() -> None:
    text = '## Requirements\n\n| id | text | src |\n|---|---|---|\n| R1 | x | input "a" |\n'
    with pytest.raises(RequirementsError, match=r"line \d+.*header"):
        parse_requirements(text)


@pytest.mark.parametrize("bad_id", ["R0", "r1", "R1a", "R", "1"])
def test_malformed_id_is_error(bad_id: str) -> None:
    text = (
        "## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        f'| {bad_id} | x | input "a" |\n'
    )
    with pytest.raises(RequirementsError, match=r"line \d+.*malformed requirement id"):
        parse_requirements(text)


def test_duplicate_id_is_error() -> None:
    text = (
        "## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        '| R1 | x | input "a" |\n'
        '| R1 | y | input "b" |\n'
    )
    with pytest.raises(RequirementsError, match=r"line \d+.*duplicate requirement id"):
        parse_requirements(text)


def test_stray_paragraph_beside_table_is_error() -> None:
    text = (
        "## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        '| R1 | x | input "a" |\n'
        "\n"
        "A stray paragraph.\n"
    )
    with pytest.raises(RequirementsError, match=r"line \d+.*unexpected content"):
        parse_requirements(text)


def test_unknown_source_form_is_error() -> None:
    text = (
        '## Requirements\n\n| id | requirement | source |\n|---|---|---|\n| R1 | x | issue "x" |\n'
    )
    with pytest.raises(RequirementsError, match=r"line \d+.*unknown source form"):
        parse_requirements(text)


def test_no_requirements_section_is_error() -> None:
    with pytest.raises(RequirementsError, match=r"no `## Requirements` section"):
        parse_requirements("# Spec\n\nsome prose\n")


def test_deferred_empty_reason_is_error() -> None:
    text = REQ_ONE + '\n## Deferred from input\n\n| input | reason |\n|---|---|\n| "x" |  |\n'
    with pytest.raises(RequirementsError, match=r"line \d+.*empty `reason`"):
        parse_requirements(text)


def test_deferred_absent_is_fine() -> None:
    assert parse_requirements(REQ_ONE).deferred == ()


def test_deferred_present() -> None:
    text = REQ_ONE + (
        '\n## Deferred from input\n\n| input | reason |\n|---|---|\n| "x" | not needed |\n'
    )
    parsed = parse_requirements(text)
    assert parsed.deferred == (Deferred(quote="x", reason="not needed"),)


# ── Test Plan 2: quote matching ─────────────────────────────────────────────


def test_whitespace_and_newline_normalisation_matches() -> None:
    assert quote_matches("the  quick\nbrown   fox", "the quick brown fox")


def test_en_dash_does_not_match_hyphen() -> None:
    assert not quote_matches("1–20", "a range of 1-20 items")
    assert quote_matches("1–20", "a range of 1–20 items")


def test_ellipsis_fragments_must_occur_in_order() -> None:
    assert quote_matches("the quick … lazy dog", "the quick brown fox jumps over the lazy dog")
    assert not quote_matches("lazy dog … the quick", "the quick brown fox jumps over the lazy dog")


def test_ellipsis_across_input_own_ellipsis() -> None:
    body = "first part … second part, verbatim"
    assert quote_matches("first part … second part", body)


def test_quote_spanning_two_entries_is_refused() -> None:
    entries = [_input_entry("i1", "part one"), _input_entry("i2", "part two")]
    matrix = _matrix("widget:spec.md#R1")
    text = (
        "## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        '| R1 | x | input "part one … part two" |\n'
    )
    problems = check_requirements(text, entries, matrix, "widget:spec.md")
    assert any("does not match any input entry" in p for p in problems)


def test_deferred_quotes_are_checked() -> None:
    entries = [_input_entry("i1", "the actual input text")]
    text = REQ_ONE + (
        "\n## Deferred from input\n\n| input | reason |\n|---|---|\n"
        '| "text nowhere in the input" | not needed |\n'
    )
    matrix = _matrix("widget:spec.md#R1")
    problems = check_requirements(
        text.replace('"the quick brown fox"', '"the actual input text"'),
        entries,
        matrix,
        "widget:spec.md",
    )
    assert any("Deferred entry" in p for p in problems)


# ── Test Plan 3: check_requirements ──────────────────────────────────────────


def test_no_input_entry_is_a_problem() -> None:
    matrix = _matrix("widget:spec.md#R1")
    text = REQ_ONE.replace('input "the quick brown fox"', "decision d1")
    entries = [_decision_entry("d1")]
    problems = check_requirements(text, entries, matrix, "widget:spec.md")
    assert any("no input entry" in p for p in problems)


def test_unknown_decision_id_is_a_problem() -> None:
    text = REQ_ONE.replace('input "the quick brown fox"', "decision nope")
    entries = [_input_entry("i1", "irrelevant")]
    matrix = _matrix("widget:spec.md#R1")
    problems = check_requirements(text, entries, matrix, "widget:spec.md")
    assert any("not a `kind=decision`" in p for p in problems)


def test_id_naming_non_decision_entry_is_a_problem() -> None:
    text = REQ_ONE.replace('input "the quick brown fox"', "decision i1")
    entries = [_input_entry("i1", "irrelevant")]
    matrix = _matrix("widget:spec.md#R1")
    problems = check_requirements(text, entries, matrix, "widget:spec.md")
    assert any("not a `kind=decision`" in p for p in problems)


def test_uncited_requirement_is_a_problem() -> None:
    entries = [_input_entry("i1", "the quick brown fox")]
    matrix = _matrix()  # no rows at all
    problems = check_requirements(REQ_ONE, entries, matrix, "widget:spec.md")
    assert any("not cited by any matrix row" in p for p in problems)


def test_row_citing_two_requirements_covers_both() -> None:
    text = (
        "## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        '| R1 | x | input "alpha" |\n'
        '| R2 | y | input "beta" |\n'
    )
    entries = [_input_entry("i1", "alpha and beta both appear here")]
    matrix = Matrix(
        org="acme",
        repo="widget",
        rows=(
            Row(
                id="row-0",
                capability="cap",
                acceptance="text",
                origin=("widget:spec.md#R1", "widget:spec.md#R2"),
                status="not-implemented",
            ),
        ),
    )
    problems = check_requirements(text, entries, matrix, "widget:spec.md")
    assert problems == []


def test_citation_to_archived_spec_twin_resolves() -> None:
    entries = [_input_entry("i1", "the quick brown fox")]
    matrix = _matrix("widget:docs/superpowers/implemented/specs/spec.md#R1")
    problems = check_requirements(REQ_ONE, entries, matrix, "widget:docs/superpowers/specs/spec.md")
    assert problems == []


def test_is_input_entry_reads_the_real_token() -> None:
    assert is_input_entry(_input_entry("i1", "x"))
    assert not is_input_entry(_decision_entry("d1"))
    assert not is_input_entry(_spec_entry(kind="discovery", id="x"))


def test_normalise_collapses_whitespace() -> None:
    assert normalise("  a\n\tb   c  ") == "a b c"


def test_sound_spec_has_no_problems() -> None:
    entries = [_input_entry("i1", "the quick brown fox")]
    matrix = _matrix("widget:spec.md#R1")
    assert check_requirements(REQ_ONE, entries, matrix, "widget:spec.md") == []


# ── Test Plan 4: #759 replay, deterministic half (check_requirements) ───────


def test_759_replay_quoting_the_range_passes() -> None:
    entries = [_input_entry("i1", _759_INPUT)]
    text = (
        "## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        '| R1 | Quantity controls support a 1-20 range. | input "(1–20)" |\n'
    )
    matrix = _matrix("widget:spec.md#R1")
    assert check_requirements(text, entries, matrix, "widget:spec.md") == []


def test_759_replay_quoting_text_absent_from_input_is_refused() -> None:
    entries = [_input_entry("i1", _759_INPUT)]
    text = (
        "## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        '| R1 | Something else. | input "the sky is blue" |\n'
    )
    matrix = _matrix("widget:spec.md#R1")
    problems = check_requirements(text, entries, matrix, "widget:spec.md")
    assert any("does not match any input entry" in p for p in problems)


def test_759_replay_dropping_no_unstyled_defaults_still_passes_structural_gate() -> None:
    """`check_requirements` is the *structural* gate (§C): it validates that
    cited quotes are real and that every requirement is cited by a row. It
    does NOT check that the spec captured everything the input said — #759's
    actual defect (silently dropping "no unstyled browser defaults" from both
    the Requirements and Deferred tables) is reviewer territory, caught by
    spec review's coverage partition (§D / `check_coverage`), not this gate
    (d4-structural-gate). This spec never mentions the dropped line in either
    table and still passes."""
    entries = [_input_entry("i1", _759_INPUT)]
    text = (
        "## Requirements\n\n"
        "| id | requirement | source |\n"
        "|---|---|---|\n"
        '| R1 | Quantity controls support a 1-20 range. | input "(1–20)" |\n'
    )
    matrix = _matrix("widget:spec.md#R1")
    assert check_requirements(text, entries, matrix, "widget:spec.md") == []


# ── Test Plan 12: check_coverage ─────────────────────────────────────────────


def _coverage_block(rows: list[tuple[str, str]]) -> str:
    body = "```input-coverage\n| span | coverage |\n|---|---|\n"
    for span, label in rows:
        body += f'| "{span}" | {label} |\n'
    body += "```\n"
    return body


def test_exact_partition_passes_and_counts() -> None:
    entries = [_input_entry("i1", "alpha beta gamma")]
    reqs = Requirements(items=(Requirement(id="R1", text="x", sources=()),))
    body = _coverage_block([("alpha beta", "R1"), (" gamma", "context")])
    problems, counts = check_coverage(body, entries, reqs, entries)
    assert problems == []
    assert counts.spans == 2
    assert counts.requirement == 1
    assert counts.context == 1
    assert counts.deferred == 0
    assert counts.missing == 0


def test_partition_cut_with_no_whitespace_at_the_boundary_passes() -> None:
    """Review c1: a cut right after `)` with no space is a sound partition.
    Joining spans with an invented space would rebuild `range(1-20) ,done`."""
    entries = [_input_entry("i1", "range(1-20),done")]
    reqs = Requirements(items=(Requirement(id="R1", text="x", sources=()),))
    body = _coverage_block([("range(1-20)", "R1"), (",done", "context")])
    problems, _ = check_coverage(body, entries, reqs, entries)
    assert problems == []


def test_partition_cut_at_whitespace_passes_though_cells_are_trimmed() -> None:
    """The other side of c1: table cells lose edge whitespace, so a plain
    `"".join` would rebuild `alphabeta` from a cut at the space."""
    entries = [_input_entry("i1", "alpha beta")]
    reqs = Requirements(items=(Requirement(id="R1", text="x", sources=()),))
    body = _coverage_block([("alpha", "R1"), ("beta", "context")])
    problems, _ = check_coverage(body, entries, reqs, entries)
    assert problems == []


def test_partition_across_entries_with_no_separator_passes() -> None:
    entries = [_input_entry("i1", "one"), _input_entry("i2", "two")]
    reqs = Requirements(items=(Requirement(id="R1", text="x", sources=()),))
    body = _coverage_block([("one", "R1"), ("two", "context")])
    problems, _ = check_coverage(body, entries, reqs, entries)
    assert problems == []


def test_partition_with_literal_ellipsis_in_input() -> None:
    body_text = "first part … second part, literally"
    entries = [_input_entry("i1", body_text)]
    reqs = Requirements(items=(Requirement(id="R1", text="x", sources=()),))
    block = _coverage_block([(body_text, "R1")])
    problems, counts = check_coverage(block, entries, reqs, entries)
    assert problems == []
    assert counts.spans == 1


def test_gap_is_refused() -> None:
    entries = [_input_entry("i1", "alpha beta gamma")]
    reqs = Requirements(items=(Requirement(id="R1", text="x", sources=()),))
    # skips " beta"
    block = _coverage_block([("alpha", "R1"), ("gamma", "context")])
    problems, _ = check_coverage(block, entries, reqs, entries)
    assert problems


def test_overlap_is_refused() -> None:
    entries = [_input_entry("i1", "alpha beta gamma")]
    reqs = Requirements(items=(Requirement(id="R1", text="x", sources=()),))
    block = _coverage_block([("alpha beta", "R1"), ("beta gamma", "context")])
    problems, _ = check_coverage(block, entries, reqs, entries)
    assert problems


def test_reordered_span_is_refused() -> None:
    entries = [_input_entry("i1", "alpha beta gamma")]
    reqs = Requirements(items=(Requirement(id="R1", text="x", sources=()),))
    block = _coverage_block([("gamma", "context"), ("alpha beta", "R1")])
    problems, _ = check_coverage(block, entries, reqs, entries)
    assert problems


def test_second_block_is_refused() -> None:
    entries = [_input_entry("i1", "alpha")]
    reqs = Requirements(items=())
    one = _coverage_block([("alpha", "context")])
    body = one + "\n" + one
    problems, counts = check_coverage(body, entries, reqs, entries)
    assert any("exactly one" in p for p in problems)
    assert counts.spans == 0


def test_no_block_is_refused() -> None:
    entries = [_input_entry("i1", "alpha")]
    reqs = Requirements(items=())
    problems, counts = check_coverage("nothing here", entries, reqs, entries)
    assert any("no `input-coverage` block" in p for p in problems)
    assert counts.spans == 0


def test_unknown_requirement_id_is_refused() -> None:
    entries = [_input_entry("i1", "alpha")]
    reqs = Requirements(items=())
    block = _coverage_block([("alpha", "R99")])
    problems, _ = check_coverage(block, entries, reqs, entries)
    assert any("unknown requirement id" in p for p in problems)


def test_missing_naming_no_finding_is_refused() -> None:
    entries = [_input_entry("i1", "alpha")]
    reqs = Requirements(items=())
    block = _coverage_block([("alpha", "missing s9")])
    problems, _ = check_coverage(block, entries, reqs, entries)
    assert any("missing s9" in p and "no `kind=finding`" in p for p in problems)


def test_missing_naming_real_finding_passes() -> None:
    entries = [_input_entry("i1", "alpha"), _finding_entry("s9")]
    reqs = Requirements(items=())
    block = _coverage_block([("alpha", "missing s9")])
    problems, counts = check_coverage(block, entries, reqs, entries)
    assert problems == []
    assert counts.missing == 1


def test_759_replay_coverage_partitions_the_literal_ellipsis() -> None:
    """The redacted #759 input, partitioned literally (Test Plan 12): the
    input's own ` … ` is the input's own character, never an elision (§D,
    review r3) — a partition that reconstructs it exactly still passes."""
    entries = [_input_entry("i1", _759_INPUT)]
    reqs = Requirements(items=(Requirement(id="R1", text="x", sources=()),))
    span1 = (
        "Quantities: − / + on each article card (1–20), styled like the cards; "
        "the card shows its quantity."
    )
    # Leading space preserved (inside the quote marks, so `_extract_quote`
    # keeps it): the exact text that follows span1 in the source.
    span2 = (
        " … Every new control uses the page's colours, font and radius — "
        "no unstyled browser defaults."
    )
    body = _coverage_block([(span1, "R1"), (span2, "context")])
    problems, counts = check_coverage(body, entries, reqs, entries)
    assert problems == []
    assert counts.spans == 2
    assert counts.requirement == 1
    assert counts.context == 1


# ── #777: the reviewer's partition is read as the reviewer wrote it ─────────
#
# Take 9 (fr 4.29.2): the spec reviewer returned one span per input line,
# with blank `""` spans, `\"` for a quote inside a span, the input's own
# Markdown table quoted with its raw `|`, and a `missing s1`. fr refused it
# (`expected 2 columns, got 6`), so the orchestrator re-cut and relabelled
# the block until it passed — recorded evidence that was not the reviewer's.
# The input below is synthetic (the real one is third-party); the SHAPE is
# take 9's, row for row.

_777_INPUT = """# Library: renew several loans at once

## Background

Today a member renews **one loan at a time**. Members say "renew all" is
what they "expect" from the app.

| Loans | Result |
|---|---|
| 3 books | renewed |

Plan this as a single phase.
"""

_777_REVIEWER_BLOCK = r"""```input-coverage
| span | coverage |
|---|---|
| "# Library: renew several loans at once" | context |
| "" | context |
| "## Background" | context |
| "" | context |
| "Today a member renews **one loan at a time**. Members say \"renew all\" is" | R1 |
| "what they \"expect\" from the app." | R1 |
| "" | context |
| "| Loans | Result |" | context |
| "|---|---|" | context |
| "| 3 books | renewed |" | R1 |
| "" | context |
| "Plan this as a single phase." | missing s1 |
```
"""


def _777_fixture() -> tuple[list[JournalEntry], Requirements]:
    entries = [_input_entry("i1", _777_INPUT), _finding_entry("s1")]
    reqs = Requirements(items=(Requirement(id="R1", text="x", sources=()),))
    return entries, reqs


def test_777_take9_reviewer_partition_is_accepted_as_written() -> None:
    entries, reqs = _777_fixture()
    problems, counts = check_coverage(_777_REVIEWER_BLOCK, entries, reqs, entries)
    assert problems == []
    assert counts.spans == 12
    assert counts.requirement == 3
    assert counts.context == 8
    assert counts.missing == 1


def test_777_raw_pipes_in_a_span_still_refuse_a_gap() -> None:
    """Reading a quoted span's raw `|` must not loosen the partition: the
    table's middle row dropped is still a gap."""
    entries, reqs = _777_fixture()
    block = _777_REVIEWER_BLOCK.replace('| "|---|---|" | context |\n', "")
    problems, _ = check_coverage(block, entries, reqs, entries)
    assert any("do not partition" in p for p in problems)


def test_777_input_carrying_a_literal_backslash_quote_still_matches() -> None:
    """`\\"` is read as `"` on BOTH sides, so an input that itself contains
    `\\"` partitions whichever way the reviewer quotes it."""
    entries = [_input_entry("i1", r"say \"hi\" now")]
    reqs = Requirements(items=())
    for span in (r"say \"hi\" now", 'say "hi" now'):
        problems, _ = check_coverage(_coverage_block([(span, "context")]), entries, reqs, entries)
        assert problems == [], span


def test_777_unreadable_block_says_to_redispatch_the_reviewer() -> None:
    """A shape fr still cannot read names the remedy: the reviewer re-writes
    it. The orchestrator never edits the reviewer's partition."""
    entries, reqs = _777_fixture()
    block = "```input-coverage\n| span | coverage |\n|---|---|\n| alpha | context |\n```\n"
    problems, _ = check_coverage(block, entries, reqs, entries)
    assert problems
    assert any("re-dispatch the reviewer" in p for p in problems)
