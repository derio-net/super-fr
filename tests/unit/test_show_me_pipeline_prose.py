"""The pipeline tells the agent to draw: fr-brainstorming and fr-goal point to
fr-show-me for the spec's design shape and the run's shape file (spec
2026-11-24-show-me-visuals R14), and the spec reviewer checks the shape (R13).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "plugins" / "super-fr" / "skills"
BRAINSTORMING = SKILLS / "fr-brainstorming" / "SKILL.md"
GOAL = SKILLS / "fr-goal" / "SKILL.md"
SPEC_REVIEWER = REPO / "plugins" / "super-fr" / "agents" / "fr-spec-reviewer.md"


def _section(path: Path, heading: str) -> str:
    """The text under the heading line starting with *heading*, up to the next
    heading of the same or a higher level."""
    lines = path.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(heading))
    level = len(heading) - len(heading.lstrip("#"))
    out: list[str] = []
    for line in lines[start + 1 :]:
        hashes = len(line) - len(line.lstrip("#"))
        if 0 < hashes <= level and line[hashes : hashes + 1] == " ":
            break
        out.append(line)
    return "\n".join(out)


@pytest.mark.parametrize("needle", ["## Design shape", "fr-show-me", "none — <reason>"])
def test_brainstorming_hand_off_asks_for_the_design_shape(needle: str) -> None:
    assert needle in _section(BRAINSTORMING, "## 2. Hand off")


@pytest.mark.parametrize("needle", ["## Design shape", "fr-show-me"])
def test_goal_brainstorm_step_asks_for_the_design_shape(needle: str) -> None:
    assert needle in _section(GOAL, "### 1. brainstorm")


@pytest.mark.parametrize("needle", ["<run-id>.shape.md", "fr-show-me", "`shape`", "commit"])
def test_goal_lens_review_writes_the_shape_file_and_passes_it(needle: str) -> None:
    assert needle in _section(GOAL, "### 7a. lens-review")


def test_goal_lens_review_writes_the_file_before_the_dispatch() -> None:
    text = _section(GOAL, "### 7a. lens-review")
    assert text.index("<run-id>.shape.md") < text.index("dispatch ONE reviewer per lens")


@pytest.mark.parametrize("needle", ["## Shape of the change", "<run-id>.shape.md"])
def test_goal_deliver_renders_the_section_and_refuses_without_it(needle: str) -> None:
    assert needle in _section(GOAL, "### 8. deliver")


def test_goal_deliver_names_the_refusal() -> None:
    text = _section(GOAL, "### 8. deliver")
    at = text.index("## Shape of the change")
    assert "refuses" in text[at - 400 : at + 400]


@pytest.mark.parametrize("needle", ["## Design shape", "shape file"])
def test_goal_light_path_says_the_same_applies(needle: str) -> None:
    assert needle in _section(GOAL, "### Light path")


@pytest.mark.parametrize(
    "needle", ["## Design shape", "exists", "the spec creates", "## Design", "finding"]
)
def test_spec_reviewer_checks_the_design_shape(needle: str) -> None:
    text = SPEC_REVIEWER.read_text()
    at = text.index("## Design shape")
    assert needle in text[at - 200 : at + 900]


def test_goal_names_when_the_brief_reads_the_shape_file() -> None:
    """Review p2-r2: pin §7a's timing to `lens_review_brief`, which gives `shape: null`
    when the file is absent at brief build (the last review-phase resolve)."""
    text = " ".join(_section(GOAL, "### 7a. lens-review").split())
    assert "before the last `review-phase` resolve" in text
    assert "did not exist when the" in text
