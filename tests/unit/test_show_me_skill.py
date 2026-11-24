"""The fr-show-me skill: the visual vocabulary specs and PRs draw with
(spec 2026-11-24-show-me-visuals R1-R5, plan P2.T1).

Generic shape checks (front matter, the 120-line cap, tool neutrality, the
mirrors' sync) run over every skill by glob elsewhere; these pin what is
specific to this one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from fr.commands import skills_cmd

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "plugins" / "super-fr" / "skills" / "fr-show-me" / "SKILL.md"


def _front_matter() -> dict[str, object]:
    text = SKILL.read_text()
    assert text.startswith("---\n")
    loaded = yaml.safe_load(text.split("---\n", 2)[1])
    assert isinstance(loaded, dict)
    return loaded


def _body() -> str:
    return SKILL.read_text().split("---\n", 2)[2]


def test_the_skill_exists_with_its_name() -> None:
    assert _front_matter()["name"] == "fr-show-me"


@pytest.mark.parametrize("needle", ["show me", "visualize", "draw", "spec", "PR"])
def test_the_description_names_its_triggers_and_pipeline_uses(needle: str) -> None:
    assert needle in str(_front_matter()["description"])


def test_the_skill_is_model_invocable() -> None:
    """R2: nothing forbids an agent from loading it, so fr-goal can point to it."""
    assert "disable-model-invocation" not in _front_matter()


@pytest.mark.parametrize(
    "view",
    [
        "pseudocode",
        "call tree",
        "file tree",
        "component tree",
        "structure-diff",
        "whole target shape",
        "mermaid",
    ],
)
def test_the_body_names_every_view(view: str) -> None:
    assert view in _body().lower()


@pytest.mark.parametrize(
    "needle",
    [
        "smallest view",
        "never all",
        "none — <reason>",
        "## Design shape",
        "<run-id>.shape.md",
        "third-party privacy",
        "claim about the code",
    ],
)
def test_the_body_names_its_rules_and_uses(needle: str) -> None:
    assert needle in _body()


def test_the_body_states_the_shape_block_forms() -> None:
    """R6's two forms: at least one fenced block, or the one `none` line."""
    body = _body()
    assert "fenced" in body and "none — <reason>" in body


def test_the_skill_credits_humanlayer() -> None:
    """R5: the vocabulary is adapted from HumanLayer's show-me skill (MIT)."""
    body = _body()
    assert "HumanLayer" in body and "show-me" in body and "MIT" in body


def test_the_skill_has_no_html_or_browser_route() -> None:
    """R3: HumanLayer's last-resort HTML page opens a browser; this port has none."""
    text = SKILL.read_text()
    assert ".html" not in text
    assert not re.search(r"(^|[\s`])open ", text)


def test_both_harness_mirrors_carry_it() -> None:
    assert (REPO / ".opencode" / "skills" / "fr-show-me" / "SKILL.md").is_file()
    assert (REPO / ".hermes" / "skills" / "fr" / "fr-show-me" / "SKILL.md").is_file()


def test_fr_skills_lists_it(capsys: pytest.CaptureFixture[str]) -> None:
    skills_cmd.skills()
    out = capsys.readouterr().out
    assert re.search(r"^\s*fr-show-me\b", out, re.MULTILINE), out


# Review p2-r2: the skill's examples are claims about fr, so pin them to the code.

_FENCED = re.compile(r"^( *)(```|~~~)[^\n]*\n.*?^\1\2[ \t]*$", re.MULTILINE | re.DOTALL)
_NONE_EXAMPLE = re.compile(r"`(none — [^`]+)`")


def _example_blocks() -> list[str]:
    blocks = [m.group(0) for m in _FENCED.finditer(_body())]
    assert len(blocks) >= 4, "the views section shows at least four fenced examples"
    return blocks


def test_every_fenced_example_is_a_shape_block() -> None:
    from fr.shape import shape_block_problem

    for block in _example_blocks():
        dedented = "\n".join(line.removeprefix("   ") for line in block.splitlines())
        assert shape_block_problem(dedented) is None, block


def test_the_inline_none_example_is_a_shape_block() -> None:
    from fr.shape import shape_block_problem

    examples = [m.group(1) for m in _NONE_EXAMPLE.finditer(_body()) if "<reason>" not in m.group(1)]
    assert examples, "the skill gives a concrete `none — <reason>` example"
    for example in examples:
        assert shape_block_problem(example) is None, example


def test_the_call_tree_example_names_functions_that_exist() -> None:
    tree = next(b for b in _example_blocks() if "_deliver_pr_gate" in b)
    names = re.findall(r"^\s+([A-Za-z_]\w+)\b(?!\s+--)", tree, re.MULTILINE)
    assert names, tree
    source = "\n".join(p.read_text() for p in (REPO / "packages" / "fr" / "src").rglob("*.py"))
    for name in names:
        assert re.search(rf"^\s*def {name}\(", source, re.MULTILINE), name


@pytest.mark.parametrize(
    "page", [SKILL, REPO / "docs" / "explainers" / "fr-show-me.md"], ids=["skill", "explainer"]
)
def test_the_shape_file_timing_matches_the_lens_brief(page: Path) -> None:
    """Review p2-r1: `lens_review_brief` reads the shape file when the brief is built,
    which is the last review-phase resolve, not the lens dispatch."""
    text = " ".join(page.read_text().split())
    assert "last `review-phase` resolve" in text
    assert "before the lens reviewers are dispatched" not in text
    assert "before it sends out the lens reviewers" not in text
