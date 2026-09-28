"""`AcceptanceItem.visual` and `StepRecord.visual` (spec
`2026-09-28-ui-visual-evidence-design.md` §A/§B): a record's `visual:` section
maps a row's named states/interactions to the screenshots taken for them.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.record.model import RecordError, parse_record, present_sections

# ── AcceptanceItem.visual — a row carrying `visual` through fr.record.apply ─


def test_a_created_row_carries_visual_through_apply_record(tmp_path: Path) -> None:
    from fr.acceptance.model import load_matrix
    from fr.record.apply import RecordTarget, apply_record
    from fr.record.model import AcceptanceItem, StepRecord

    from tests.unit.acceptance_helpers import make_repo, row

    root = make_repo(tmp_path, row(id="seed"))
    item = AcceptanceItem.model_validate(
        {
            "id": "basket-mode-visual",
            "capability": "Cap",
            "acceptance": "Operator can do X",
            "status": "not-implemented",
            "visual": {"states": ["a"]},
        }
    )
    apply_record(
        root, None, StepRecord(acceptance=(item,)), target=RecordTarget(message="add visual row")
    )

    matrix = load_matrix(root / "docs" / "acceptance" / "matrix.yaml")
    (added,) = [r for r in matrix.rows if r.id == "basket-mode-visual"]
    assert added.visual is not None
    assert added.visual.states == ("a",)


# ── StepRecord.visual — VisualEvidence / VisualShot ─────────────────────────

_VISUAL_TEXT = """\
outcome: done
visual:
  - row: r
    script: s.cjs
    shots:
      - {path: /x/a.png, shows: [a]}
"""


def test_visual_evidence_parses_into_step_record() -> None:
    record = parse_record(_VISUAL_TEXT)
    assert len(record.visual) == 1
    entry = record.visual[0]
    assert entry.row == "r"
    assert entry.script == "s.cjs"
    assert len(entry.shots) == 1
    assert entry.shots[0].path == "/x/a.png"
    assert entry.shots[0].shows == ("a",)


def test_visual_script_is_optional() -> None:
    text = "outcome: done\nvisual:\n  - row: r\n    shots:\n      - {path: /x/a.png, shows: [a]}\n"
    record = parse_record(text)
    assert record.visual[0].script is None


def test_present_sections_reports_visual_under_evidence() -> None:
    record = parse_record(_VISUAL_TEXT)
    assert "evidence" in present_sections(record)


def test_visual_shot_refuses_an_unknown_key() -> None:
    text = (
        "outcome: done\nvisual:\n  - row: r\n"
        "    shots:\n      - {path: /x/a.png, shows: [a], bogus: 1}\n"
    )
    with pytest.raises(RecordError, match="bogus"):
        parse_record(text)


def test_visual_evidence_refuses_empty_shots() -> None:
    text = "outcome: done\nvisual:\n  - row: r\n    shots: []\n"
    with pytest.raises(RecordError):
        parse_record(text)


def test_visual_shot_refuses_empty_shows() -> None:
    text = "outcome: done\nvisual:\n  - row: r\n    shots:\n      - {path: /x/a.png, shows: []}\n"
    with pytest.raises(RecordError):
        parse_record(text)
