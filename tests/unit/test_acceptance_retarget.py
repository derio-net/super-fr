"""`retarget_text` — matrix refs follow what archive moved (spec 2026-10-06 §B)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.retarget import RetargetError, retarget_text

LIVE = "docs/superpowers/specs/s.md"
DONE = "docs/superpowers/implemented/specs/s.md"
PLAN = "docs/superpowers/plans/p1"
PLAN_DONE = "docs/superpowers/implemented/plans/p1"

MATRIX = f"""\
# header comment own:{LIVE}
schema_version: 4
org: derio-net
repo: own
rows:
  - id: r1
    capability: Cap
    acceptance: mentions own:{LIVE} in prose
    origin:
    - own:{LIVE}
    - frank:{LIVE}
    levels:
      unit:
      - own:{PLAN}/x/y.yaml#frag
      - "own:tests/test_a.py"
      int: []
    status: ci
    notes: see own:{LIVE}
  - id: r2
    capability: Cap
    acceptance: second
    origin:
      - 'own:{LIVE}#sec'
    levels:
      unit:
        - own:tests/test_b.py
    status: ci
    walks:
    - strategy: live
      harness: h
      model: m
      outcome: pass
      at: '2026-01-01'
      evidence: own:{LIVE}
"""


def _moves() -> list[tuple[Path, Path]]:
    return [(Path(LIVE), Path(DONE)), (Path(PLAN), Path(PLAN_DONE))]


def test_rewrites_origin_and_level_refs_and_only_those() -> None:
    new, changes = retarget_text(MATRIX, "own", _moves())
    expected = (
        MATRIX.replace(f"    - own:{LIVE}\n    - frank", f"    - own:{DONE}\n    - frank")
        .replace(f"own:{PLAN}/x/y.yaml#frag", f"own:{PLAN_DONE}/x/y.yaml#frag")
        .replace(f"'own:{LIVE}#sec'", f"'own:{DONE}#sec'")
    )
    assert new == expected
    assert changes == [
        ("r1", f"own:{LIVE}", f"own:{DONE}"),
        ("r1", f"own:{PLAN}/x/y.yaml#frag", f"own:{PLAN_DONE}/x/y.yaml#frag"),
        ("r2", f"own:{LIVE}#sec", f"own:{DONE}#sec"),
    ]


def test_other_repo_refs_notes_walks_and_comments_stay_byte_identical() -> None:
    new, _ = retarget_text(MATRIX, "own", _moves())
    assert f"frank:{LIVE}" in new
    assert f"notes: see own:{LIVE}" in new
    assert f"mentions own:{LIVE} in prose" in new
    assert f"      evidence: own:{LIVE}\n" in new
    assert new.startswith(f"# header comment own:{LIVE}\n")


def test_no_match_is_the_identical_text() -> None:
    new, changes = retarget_text(MATRIX, "own", [(Path("elsewhere.md"), Path("x.md"))])
    assert new == MATRIX
    assert changes == []


def test_a_prefix_that_is_not_a_directory_boundary_does_not_match() -> None:
    text = MATRIX.replace(f"own:{PLAN}/x/y.yaml#frag", f"own:{PLAN}-other/y.yaml")
    new, _ = retarget_text(text, "own", _moves())
    assert f"own:{PLAN}-other/y.yaml" in new


def test_a_rewrite_that_does_not_reparse_raises() -> None:
    with pytest.raises(RetargetError):
        retarget_text(MATRIX, "own", [(Path(LIVE), Path("a: [b"))])
