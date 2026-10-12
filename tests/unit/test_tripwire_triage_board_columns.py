"""The fr-triage skill names every board column and states no column count.

The board's columns are moving (other PRs add and rename them), so a stated
count goes stale silently. This reads `COLUMN_TITLES` live and finds the skill
line by its content, not by its bold lead. A column-changing PR that merges
after this one goes red here until the skill follows."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from fr.triage.kanban import COLUMN_TITLES

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "super-fr" / "skills" / "fr-triage" / "SKILL.md"

BOARD_LINE_MARKER = "`fr triage board` writes `board.html`"
"""Content that identifies the board paragraph; its lead may be renamed."""

COUNT_PHRASE = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[\s-]+"
    r"(\w+\s+)?columns?\b",
    re.IGNORECASE,
)
"""A stated column count, in digits or words: "seven lifecycle columns",
"seven board columns", "six-column"."""

COLUMN_LIST = re.compile(r"across its columns \(([^)]*)\)")
"""The board paragraph's column list. Compared to `COLUMN_TITLES` exactly and
in order, so a title cannot pass by appearing elsewhere on the line (the line
also carries the runner and cloud-driver paragraphs) or inside another title."""


def _board_lines() -> list[str]:
    return [ln for ln in SKILL.read_text().splitlines() if BOARD_LINE_MARKER in ln]


def test_the_skill_has_exactly_one_board_paragraph() -> None:
    assert len(_board_lines()) == 1


def test_the_skill_names_every_column() -> None:
    (line,) = _board_lines()
    lists = COLUMN_LIST.findall(line)
    assert len(lists) == 1, "the board line must carry one `across its columns (…)` list"
    named = [t.strip() for t in lists[0].split(",")]
    assert named == list(COLUMN_TITLES.values()), (
        f"fr-triage SKILL.md board columns {named} != COLUMN_TITLES {list(COLUMN_TITLES.values())}"
    )


@pytest.mark.parametrize(
    "phrase", ["six lifecycle columns", "seven board columns", "a six-column board", "9 columns"]
)
def test_the_count_pattern_catches_each_phrasing(phrase: str) -> None:
    assert COUNT_PHRASE.search(phrase) is not None


def test_the_skill_states_no_column_count() -> None:
    (line,) = _board_lines()
    assert COUNT_PHRASE.search(line) is None


def test_the_board_command_docstring_states_no_column_count() -> None:
    # Read from the source, not by import: importing triage_kanban_cmd alone
    # trips a circular import that only test-suite import order hides.
    src = (
        ROOT / "packages" / "fr" / "src" / "fr" / "commands" / "triage_kanban_cmd.py"
    ).read_text()
    fn = next(
        n
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.FunctionDef) and n.name == "board_command"
    )
    doc = ast.get_docstring(fn) or ""
    assert COUNT_PHRASE.search(doc) is None
    assert COLUMN_LIST.search(doc) is None
    assert not [t for t in COLUMN_TITLES.values() if t in doc and t != "Done"], (
        "the docstring names column titles; it should point at COLUMN_TITLES instead"
    )
