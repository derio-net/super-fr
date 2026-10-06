"""Record kind 7 -> 8 (spec 2026-10-06-verification-strategies §B): an
`AcceptanceItem` carries `verify <strategy|none>`, `scenario`, `issues`,
`harnesses` and one `walk` to append, and `apply_record` writes them to the
row. Version 7 is frozen as `fr.record.legacy.RecordV7`; live records move
7 -> 8 by stamp.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.record import legacy
from fr.record.model import RECORD_SCHEMA_VERSION, AcceptanceItem, RecordError, parse_record

from tests.unit.test_record_apply import _matrix_repo, _move

_WALK = {
    "strategy": "live",
    "harness": "claude-code",
    "model": "opus",
    "outcome": "pass",
    "at": "2026-10-06T12:00:00Z",
    "evidence": "walk.log",
}


def _row(root: Path, row_id: str = "target"):
    from fr.acceptance.model import load_matrix

    matrix = load_matrix(root / "docs" / "acceptance" / "matrix.yaml")
    return next(r for r in matrix.rows if r.id == row_id)


# --- the item -----------------------------------------------------------------


def test_an_item_takes_the_v8_fields() -> None:
    item = AcceptanceItem.model_validate(
        {
            "id": "a",
            "status": "ci",
            "verify": "candidate",
            "scenario": "tests/scenarios/a.sh",
            "issues": ["o/r#1"],
            "harnesses": ["claude-code"],
            "walk": _WALK,
        }
    )
    assert item.walk is not None and item.walk.outcome == "pass"
    assert item.issues == ("o/r#1",)


def test_an_item_refuses_the_v3_spelling_and_a_bad_issue() -> None:
    with pytest.raises(ValueError, match="post-merge"):
        AcceptanceItem(id="a", status="ci", verify="post-merge")
    with pytest.raises(ValueError, match="owner/repo#n"):
        AcceptanceItem(id="a", status="ci", issues=("#1",))


# --- the apply path -----------------------------------------------------------


def test_a_create_writes_every_new_field(tmp_path: Path) -> None:
    from fr.record.apply import RecordTarget, apply_record
    from fr.record.model import StepRecord

    root = _matrix_repo(tmp_path)
    item = AcceptanceItem.model_validate(
        {
            "id": "fresh",
            "capability": "Cap",
            "acceptance": "Operator can X",
            "status": "not-implemented",
            "verify": "candidate",
            "scenario": "tests/scenarios/x.sh",
            "issues": ["o/r#1"],
            "harnesses": ["claude-code", "opencode"],
        }
    )
    apply_record(root, None, StepRecord(acceptance=(item,)), target=RecordTarget(message="m"))

    row = _row(root, "fresh")
    assert row.verify == "candidate"
    assert row.scenario == "tests/scenarios/x.sh"
    assert row.issues == ("o/r#1",)
    assert row.harnesses == ("claude-code", "opencode")


def test_a_move_adds_issues_and_appends_a_walk(tmp_path: Path) -> None:
    from fr.record.apply import RecordTarget, apply_record

    root = _matrix_repo(tmp_path)
    apply_record(root, None, _move(issues=["o/r#1"]), target=RecordTarget(message="m1"))
    apply_record(
        root, None, _move(issues=["o/r#1", "o/r#2"], walk=_WALK), target=RecordTarget(message="m2")
    )
    apply_record(
        root, None, _move(walk={**_WALK, "outcome": "fail"}), target=RecordTarget(message="m3")
    )

    row = _row(root)
    assert row.issues == ("o/r#1", "o/r#2")
    assert [w.outcome for w in row.walks] == ["pass", "fail"]
    assert row.walks[0].harness == "claude-code"


def test_a_move_refuses_a_strategy_that_does_not_resolve(tmp_path: Path) -> None:
    from fr.record.apply import RecordRefusedError, RecordTarget, apply_record

    root = _matrix_repo(tmp_path)
    with pytest.raises(RecordRefusedError, match="bogus"):
        apply_record(root, None, _move(verify="bogus"), target=RecordTarget(message="m"))


# --- the shape change ---------------------------------------------------------

_V7 = """\
schema_version: 7
run: r1
step: implement-phase
item: phase/1
outcome: done
ticks: [P1.T1.S1]
acceptance:
  - id: a
    status: ci
    notes: n
    verify: post-merge
"""


def _record_file(root: Path, text: str, stem: str) -> Path:
    path = root / "docs" / "superpowers" / "runs" / "r1.records" / f"{stem}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_record_kind_is_at_version_eight() -> None:
    assert RECORD_SCHEMA_VERSION == 8
    assert artifact_kind("record").current_version == 8


def test_the_chain_from_one_reaches_eight_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("record", PRE_FRAMEWORK_VERSION)
    assert [s.to_version for s in chain] == [2, 3, 4, 5, 6, 7, 8]


def test_a_v7_record_is_stamped_with_no_body_rewrite(tmp_path: Path) -> None:
    plain = _V7.split("acceptance:")[0]
    path = _record_file(tmp_path, plain, "implement-phase__phase-1")

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path.read_text() == plain.replace("schema_version: 7", "schema_version: 8")


def test_the_frozen_v7_reader_reads_a_v7_record() -> None:
    record = legacy.parse_record_v7(_V7)
    assert record.schema_version == 7
    assert record.acceptance[0].verify == "post-merge"


def test_an_unreadable_v7_record_is_left_byte_identical(tmp_path: Path) -> None:
    path = _record_file(tmp_path, _V7.replace("outcome: done", "outcome: maybe"), "x")
    before = path.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [path]
    assert path.read_bytes() == before


def test_the_live_model_refuses_a_v7_stamp() -> None:
    with pytest.raises(RecordError, match="schema_version"):
        parse_record(_V7.split("acceptance:")[0])


def test_the_frozen_v7_reader_has_not_been_edited() -> None:
    frozen = {
        name for name, obj in vars(legacy).items() if inspect.isclass(obj) and name.endswith("V7")
    }
    assert frozen == set(legacy.FROZEN_V7_CLASS_SHA256)
    drifted = {
        name
        for name in frozen
        if hashlib.sha256(inspect.getsource(getattr(legacy, name)).encode()).hexdigest()
        != legacy.FROZEN_V7_CLASS_SHA256[name]
    }
    assert not drifted, f"{sorted(drifted)} changed; freeze a `…V8` beside them instead"


def test_a_v7_post_merge_entry_becomes_live(tmp_path: Path) -> None:
    """R7 for a record in flight: the entry gets what the matrix row got."""
    from fr.record.model import load_record

    path = _record_file(tmp_path, _V7, "implement-phase__phase-1")

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    record = load_record(path)
    assert record.schema_version == 8
    assert record.acceptance[0].verify == "live"
