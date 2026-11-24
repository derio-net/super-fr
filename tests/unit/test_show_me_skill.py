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
