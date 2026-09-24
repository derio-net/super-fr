"""Every runnable `fr journal resolve` example a shipped skill prints carries
the flags the command requires (review p4-f4).

`--scope` and `--slug` are required options, so an example without them is an
instruction that fails the first time an agent copies it. A bare mention
(`fr journal resolve`) or an elided one (`fr journal resolve … --state fixed`)
is prose, not an example, and is not checked.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = sorted((REPO_ROOT / "plugins" / "super-fr" / "skills").glob("*/SKILL.md"))

# An example is the command immediately followed by a flag, up to the closing
# backtick of its inline code span.
_EXAMPLE = re.compile(r"`(fr journal resolve --[^`]*)`")


def _examples() -> list[tuple[str, str]]:
    return [
        (f"{path.parent.name}:{m.group(1)[:60]}", m.group(1))
        for path in SKILLS
        for m in _EXAMPLE.finditer(path.read_text())
    ]


@pytest.mark.parametrize(("where", "example"), _examples(), ids=[w for w, _ in _examples()])
def test_a_resolve_example_names_its_scope_and_slug(where: str, example: str) -> None:
    assert "--scope " in example, where
    assert "--slug " in example, where


def test_the_scan_finds_the_fr_goal_examples() -> None:
    assert sum(1 for where, _ in _examples() if where.startswith("fr-goal:")) >= 3
