"""The record kind's amendment shape, 10 -> 11 (spec 2026-11-04 R16, R19, §5).

A step record's `acceptance:` section carries an amendment item — `{row, op,
base?, why, <op fields>}` — beside the create and move items. `base` omitted is the
row's revision when the record applies; the amendment is written to the run's (or
the verb's) feature fragment. The record model is closed-world and read by
released fr versions, so the kind moves, with a stamp-only migration.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.record.model import (
    RECORD_SCHEMA_VERSION,
    AcceptanceItem,
    AmendmentItem,
    RecordError,
    parse_record,
)

from tests.unit.acceptance_helpers import FRAGMENTS_REL
from tests.unit.test_acceptance_amend import SLUG_B, fragment, merged_repo

_V10 = """\
schema_version: 10
run: r1
step: implement-phase
item: phase/1
outcome: done
ticks: [P1.T1.S1]
acceptance:
  - {id: x, status: ci, notes: wired}
"""


def _record_file(root: Path, text: str = _V10) -> Path:
    path = root / "docs" / "superpowers" / "runs" / "r1.records" / "implement-phase__phase-1.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _record(acceptance: list[dict]) -> str:
    return yaml.safe_dump({"schema_version": RECORD_SCHEMA_VERSION, "acceptance": acceptance})


def test_the_acceptance_section_takes_an_amendment_beside_create_and_move_items() -> None:
    rec = parse_record(
        _record(
            [
                {"id": "x", "status": "ci", "notes": "wired"},
                {"row": "r", "op": "reword", "acceptance": "better", "why": "clearer"},
                {
                    "row": "r",
                    "op": "set-status",
                    "base": 3,
                    "status": "ci",
                    "notes": "n",
                    "why": "wired",
                },
            ]  # fmt: skip
        )
    )

    move, reword, status = rec.acceptance
    assert isinstance(move, AcceptanceItem)
    assert isinstance(reword, AmendmentItem) and reword.base is None
    assert isinstance(status, AmendmentItem) and status.base == 3
    assert reword.to_amendment(5).base == 5


@pytest.mark.parametrize(
    "item",
    [
        {"row": "r", "op": "rename", "why": "w"},
        {"row": "r", "op": "reword", "acceptance": "a"},
        {"row": "r", "op": "reword", "why": "w"},
        {"row": "r", "op": "retire", "why": "w", "level": "unit"},
    ],
)
def test_an_unknown_op_a_missing_why_or_a_wrong_field_is_refused(item: dict) -> None:
    with pytest.raises(RecordError):
        parse_record(_record([item]))


def test_apply_fills_the_base_and_writes_the_feature_fragment(tmp_path: Path) -> None:
    from fr.acceptance.fold import clear_fold_cache, fold
    from fr.record import apply as engine
    from fr.record.model import StepRecord

    root = merged_repo(tmp_path)
    items = (
        AmendmentItem(row="r", op="reword", acceptance="r, better", why="clearer"),
        AmendmentItem(row="r", op="add-level", level="int",
                      ref="widget:tests/test_w.py#test_v", why="wired"),
    )  # fmt: skip

    outcome = engine.apply_record(
        root,
        None,
        StepRecord(acceptance=items),
        target=engine.RecordTarget(message="chore(fr): acceptance — amend r", feature=SLUG_B),
    )

    assert outcome.committed
    amendments = fragment(root, SLUG_B)["amendments"]
    assert [(a["op"], a["base"]) for a in amendments] == [("reword", 0), ("add-level", 1)]
    clear_fold_cache()
    (row,) = fold(root).matrix.rows
    assert row.acceptance == "r, better"


def test_a_run_record_amendment_goes_to_the_runs_feature_fragment(tmp_path: Path) -> None:
    from fr.record.apply import _acceptance_writes, _Overlay
    from fr.record.model import StepRecord

    root = merged_repo(tmp_path)
    overlay = _Overlay()
    record = StepRecord(
        acceptance=(AmendmentItem(row="r", op="retire", notes="gone", why="superseded"),)
    )

    _acceptance_writes(record, overlay, root, {}, default_feature=SLUG_B)

    written = overlay.read(root / FRAGMENTS_REL / f"{SLUG_B}.yaml")
    assert written is not None
    assert yaml.safe_load(written)["amendments"][0]["op"] == "retire"


def test_an_amendment_with_no_feature_is_refused(tmp_path: Path) -> None:
    from fr.record import apply as engine
    from fr.record.model import StepRecord

    root = merged_repo(tmp_path)
    with pytest.raises(engine.RecordRefusedError, match="feature"):
        engine.apply_record(
            root,
            None,
            StepRecord(acceptance=(AmendmentItem(row="r", op="retire", notes="n", why="w"),)),
            target=engine.RecordTarget(message="m"),
        )


def test_the_record_kind_is_at_version_eleven() -> None:
    assert RECORD_SCHEMA_VERSION == 11
    assert artifact_kind("record").current_version == 11


def test_the_chain_from_one_reaches_eleven_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("record", PRE_FRAMEWORK_VERSION)
    assert [s.to_version for s in chain] == [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    hop = MIGRATIONS.chain("record", 10)[0]
    assert (hop.from_version, hop.to_version) == (10, 11)
    assert hop.fn.__module__ == "fr.artifacts.record_amendments"


def test_a_v10_record_is_stamped_with_no_body_rewrite(tmp_path: Path) -> None:
    path = _record_file(tmp_path)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path.read_text() == _V10.replace("schema_version: 10\n", "schema_version: 11\n")
    assert parse_record(path.read_text()).schema_version == 11


def test_an_unreadable_v10_record_is_refused_and_left_alone(tmp_path: Path) -> None:
    bad = _V10.replace("outcome: done", "outcome: done\nnot_a_field: 1")
    path = _record_file(tmp_path, bad)

    report = run_migrations(tmp_path, dry_run=False)

    assert not report.ok
    assert path.read_text() == bad


def test_the_validator_accepts_an_amendment_item(tmp_path: Path) -> None:
    text = _V10.replace("schema_version: 10", "schema_version: 11").replace(
        "{id: x, status: ci, notes: wired}", "{row: r, op: retire, notes: n, why: w}"
    )
    path = _record_file(tmp_path, text)
    assert artifact_kind("record").validate(path) == []


def test_the_template_shows_the_amendment_shape() -> None:
    from fr.record.template import render_template

    text = render_template(
        run="r", step="s", item=None, allowed=frozenset({"acceptance"}), tick_ids=[],
        refactor_tasks=[], evidence=[], emitted=[], resolve="fr run resolve r --step s",
    )  # fmt: skip

    assert "#   - {row: <row>, op: reword|set-status|add-level|drop-level|retire" in text
