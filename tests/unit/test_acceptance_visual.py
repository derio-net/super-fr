"""The `visual` acceptance-row field (spec `2026-09-28-ui-visual-evidence-design.md`
§A/§B): a UI requirement is identified structurally by its acceptance row,
which names the states and interactions visual evidence must cover.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.acceptance.model import AcceptanceError, load_matrix

HEADER = "# header comment — must survive\nrows:\n"

ROW = """\
  - id: {id}
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["fr:docs/superpowers/specs/x.md"]
    levels:
      unit: ["fr:tests/unit/test_x.py"]
    status: {status}
    notes: "n"
"""


def _write_matrix(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "docs" / "acceptance" / "matrix.yaml"
    p.parent.mkdir(parents=True)
    p.write_text(text)
    return p


# ── P1.T1: round-trip ───────────────────────────────────────────────────────


def test_row_visual_round_trips(tmp_path: Path) -> None:
    text = (
        HEADER
        + ROW.format(id="a", status="ci")
        + "    visual:\n      states: [a]\n      interactions: ['20 cap']\n"
    )
    (row,) = load_matrix(_write_matrix(tmp_path, text)).rows
    assert row.visual is not None
    assert row.visual.states == ("a",)
    assert row.visual.interactions == ("20 cap",)


def test_row_visual_defaults_to_none(tmp_path: Path) -> None:
    (row,) = load_matrix(_write_matrix(tmp_path, HEADER + ROW.format(id="a", status="ci"))).rows
    assert row.visual is None


# ── P1.T2: validation ───────────────────────────────────────────────────────


def test_visual_both_lists_empty_is_refused(tmp_path: Path) -> None:
    text = (
        HEADER
        + ROW.format(id="a", status="ci")
        + "    visual:\n      states: []\n      interactions: []\n"
    )
    with pytest.raises(AcceptanceError, match="states|interactions"):
        load_matrix(_write_matrix(tmp_path, text))


def test_visual_one_empty_list_is_accepted(tmp_path: Path) -> None:
    text = (
        HEADER
        + ROW.format(id="a", status="ci")
        + "    visual:\n      states: [a]\n      interactions: []\n"
    )
    (row,) = load_matrix(_write_matrix(tmp_path, text)).rows
    assert row.visual is not None
    assert row.visual.states == ("a",)
    assert row.visual.interactions == ()


def test_visual_duplicate_name_within_a_list_is_refused(tmp_path: Path) -> None:
    text = HEADER + ROW.format(id="a", status="ci") + "    visual:\n      states: [a, a]\n"
    with pytest.raises(AcceptanceError, match="a"):
        load_matrix(_write_matrix(tmp_path, text))


def test_visual_duplicate_name_across_lists_is_refused(tmp_path: Path) -> None:
    text = (
        HEADER
        + ROW.format(id="a", status="ci")
        + "    visual:\n      states: [a]\n      interactions: [a]\n"
    )
    with pytest.raises(AcceptanceError, match="a"):
        load_matrix(_write_matrix(tmp_path, text))


def test_a_row_with_visual_dumped_and_reparsed_is_identical(tmp_path: Path) -> None:
    from fr.acceptance.model import parse_matrix

    text = (
        HEADER
        + ROW.format(id="a", status="ci")
        + "    visual:\n      states: [a, b]\n      interactions: ['20 cap']\n"
    )
    matrix = load_matrix(_write_matrix(tmp_path, text))
    dumped = yaml.safe_dump(matrix.model_dump(mode="json"), sort_keys=False)
    reparsed = parse_matrix(dumped)
    assert reparsed == matrix
