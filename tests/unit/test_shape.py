"""The shape-block grammar, the spec's `## Design shape` reader and the shape
file's locator (spec 2026-11-24-show-me-visuals R6, R7, R9)."""

from __future__ import annotations

from pathlib import Path

import pytest

FENCED_TICKS = "Some text.\n\n```\nfoo/\n  bar.py\n```\n"
FENCED_TILDES = "~~~\nfoo\n~~~\n"
FENCED_MERMAID = "```mermaid\nsequenceDiagram\n  A->>B: hi\n```\n"
FENCED_DIFF = "```diff\n tree/\n+  new.py\n```\n"
FENCED_LONG_RUN = "````\nfoo\n```\nstill inside\n````\n"  # a shorter run does not close it
NONE_EM = "none — a one-line config change has no structure to draw"
NONE_HYPHEN = "\n  none - nothing moves between modules  \n\n"


@pytest.mark.parametrize(
    "text",
    [
        FENCED_TICKS,
        FENCED_TILDES,
        FENCED_MERMAID,
        FENCED_DIFF,
        FENCED_LONG_RUN,
        NONE_EM,
        NONE_HYPHEN,
    ],
)
def test_valid_shape_blocks(text: str) -> None:
    from fr.shape import is_shape_block, shape_block_problem

    assert is_shape_block(text)
    assert shape_block_problem(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   \n\n",
        "Just prose about the change, no picture.",
        "none —",
        "none — ",
        "none -   ",
        "none — x\nand another line",
        "```\nnever closed\n",
        "~~~\nopened with tildes\n```\n",
        # lens l-tests-r2: a fence with nothing in it draws nothing
        "```\n```\n",
        "```text\n   \n\n```\n",
        # a closing fence takes no info string, so this one never closes
        "```\nfoo\n```text\n",
    ],
)
def test_invalid_shape_blocks(text: str) -> None:
    from fr.shape import is_shape_block, shape_block_problem

    assert not is_shape_block(text)
    problem = shape_block_problem(text)
    assert problem
    assert "\n" not in problem


def test_two_forms_names_both_forms() -> None:
    from fr.shape import TWO_FORMS

    assert "fenced" in TWO_FORMS
    assert "none — <reason>" in TWO_FORMS
    assert "\n" not in TWO_FORMS


SPEC = """\
# A spec

## Design

Prose.

## Design shape

```diff
 tree/
## not a heading, inside a fence
+  new.py
```

## Verification

strategy: none
"""


def test_design_shape_section_stops_at_the_next_heading_outside_a_fence() -> None:
    from fr.shape import design_shape_section, is_shape_block

    body = design_shape_section(SPEC)
    assert body is not None
    assert "## not a heading, inside a fence" in body
    assert "+  new.py" in body
    assert "strategy" not in body
    assert "## Verification" not in body
    assert is_shape_block(body)


def test_design_shape_section_absent() -> None:
    from fr.shape import design_shape_section

    assert design_shape_section("# Spec\n\n## Design\n\nProse.\n") is None


def test_design_shape_section_at_end_of_file() -> None:
    from fr.shape import design_shape_section

    body = design_shape_section("# Spec\n\n## Design shape\n\nnone — trivial\n")
    assert body is not None
    assert body.strip() == "none — trivial"


def test_design_shape_heading_inside_a_fence_is_not_the_section() -> None:
    from fr.shape import design_shape_section

    text = "# Spec\n\n```\n## Design shape\n```\n\n## Other\n"
    assert design_shape_section(text) is None


def test_a_level_three_heading_does_not_end_the_section() -> None:
    from fr.shape import design_shape_section

    body = design_shape_section("## Design shape\n\n### Sub\n\n```\nx\n```\n## Next\n")
    assert body is not None
    assert "### Sub" in body
    assert "## Next" not in body


def test_shape_path_sits_beside_the_durable_pr_body(tmp_path: Path) -> None:
    from fr.record.pr_body import durable_pr_body_path
    from fr.run.model import run_path
    from fr.shape import SHAPE_FILE_SUFFIX, shape_path

    run_id = "2026-11-24-feat-x"
    path = shape_path(tmp_path, run_id)
    assert SHAPE_FILE_SUFFIX == ".shape.md"
    assert path == run_path(tmp_path, run_id).with_name(f"{run_id}.shape.md")
    assert path.parent == durable_pr_body_path(tmp_path, run_id).parent


# Lens l-security-r1: a shape is rendered verbatim above fr's own PR-body sections, so
# it must leave no fence open as the PR body's closing-keyword gate reads fences
# (`fr.record.pr_body`, list- and blockquote-aware, CommonMark info strings).
LIST_ITEM_FENCE = "```text\ntree/\n```\n- ```\n"
BACKTICK_INFO_STRING = "```a`b\ntree/\n```\n"


@pytest.mark.parametrize("text", [LIST_ITEM_FENCE, BACKTICK_INFO_STRING], ids=["list", "info"])
def test_a_shape_that_leaves_a_pr_body_fence_open_is_refused(text: str) -> None:
    from fr.shape import shape_block_problem

    problem = shape_block_problem(text)
    assert problem is not None
    assert "fence" in problem


@pytest.mark.parametrize("text", [LIST_ITEM_FENCE, BACKTICK_INFO_STRING], ids=["list", "info"])
def test_the_rendered_section_cannot_hide_a_later_closing_keyword(
    tmp_path: Path, text: str
) -> None:
    """What the refusal protects: with such a shape above it, a later `Fixes #959`
    is invisible to `closing_refs(as_github=True)` though GitHub would close #959."""
    from fr.record.pr_body import closing_refs

    body = f"## Shape of the change\n\n{text}\n## Review lenses\n\nFixes #959\n"
    assert closing_refs(body, as_github=True) == []  # the blind spot the grammar now refuses
    assert closing_refs(f"## Shape of the change\n\n{FENCED_TICKS}\nFixes #959\n", as_github=True)
