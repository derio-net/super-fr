"""The fr-triage skill names every board column and states no column count.

The board's columns are moving (other PRs add and rename them), so a stated
count goes stale silently. This reads `COLUMN_TITLES` live and finds the skill
line by its content, not by its bold lead. A column-changing PR that merges
after this one goes red here until the skill follows."""

from __future__ import annotations

import re
from pathlib import Path

from fr.triage.kanban import COLUMN_TITLES

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugins" / "super-fr" / "skills" / "fr-triage" / "SKILL.md"

BOARD_LINE_MARKER = "`fr triage board` writes `board.html`"
"""Content that identifies the board paragraph; its lead may be renamed."""

COUNT_PHRASE = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
    r"(lifecycle\s+)?columns\b",
    re.IGNORECASE,
)
"""A stated column count, in digits or words."""


def _board_lines() -> list[str]:
    return [ln for ln in SKILL.read_text().splitlines() if BOARD_LINE_MARKER in ln]


def test_the_skill_has_exactly_one_board_paragraph() -> None:
    assert len(_board_lines()) == 1


def test_the_skill_names_every_column() -> None:
    (line,) = _board_lines()
    missing = [t for t in COLUMN_TITLES.values() if t not in line]
    assert not missing, f"fr-triage SKILL.md board line omits columns: {missing}"


def test_the_skill_states_no_column_count() -> None:
    (line,) = _board_lines()
    assert COUNT_PHRASE.search(line) is None


def test_the_board_command_docstring_states_no_column_count() -> None:
    from fr.commands.triage_kanban_cmd import board_command

    assert COUNT_PHRASE.search(board_command.__doc__ or "") is None
