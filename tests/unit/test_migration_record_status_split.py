"""Record kind 8 -> 9 (spec 2026-10-11-debt-engine §D, R27): a record carries
the acceptance `Status`, so the `skipped` split moves it too. An in-flight
record's `status: skipped` entry is rewritten by R6's rule; a v9 record still
saying `skipped` is refused by name. Version 8 is frozen as
`fr.record.legacy.RecordV8`, and every record hop reads through a frozen model.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.record import legacy
from fr.record.model import RECORD_SCHEMA_VERSION, RecordError, load_record, parse_record

from tests.unit.acceptance_helpers import MATRIX_HEADER, make_repo, row

_V4_HEADER = "schema_version: 4\n" + MATRIX_HEADER

_WALK = """\
    walk:
      strategy: live
      harness: claude-code
      model: opus
      outcome: pass
      at: "2026-10-06T12:00:00Z"
      evidence: walk.log
"""


def _v8(entry: str = "") -> str:
    return (
        "schema_version: 8\nrun: r1\nstep: implement-phase\nitem: phase/1\noutcome: done\n"
        "ticks: [P1.T1.S1]\nacceptance:\n  - id: r1\n    status: skipped\n    notes: why\n" + entry
    )


def _record_file(root: Path, text: str, stem: str = "implement-phase__phase-1") -> Path:
    path = root / "docs" / "superpowers" / "runs" / "r1.records" / f"{stem}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_record_kind_is_at_version_nine_or_later() -> None:
    assert RECORD_SCHEMA_VERSION >= 9
    assert artifact_kind("record").current_version == RECORD_SCHEMA_VERSION


def test_the_chain_from_one_passes_nine_hop_by_hop() -> None:
    # 9 -> 10 follows; test_migration_record_exit_gates pins the whole chain.
    chain = MIGRATIONS.chain("record", PRE_FRAMEWORK_VERSION)
    assert [s.to_version for s in chain][:8] == [2, 3, 4, 5, 6, 7, 8, 9]


@pytest.mark.parametrize(
    ("entry", "row_verify", "want"),
    [
        (_WALK, None, "walked"),
        ("    verify: live\n", None, "walk-owed"),
        ("", "live", "walk-owed"),  # the row's own verify, kept by a move
        ("    verify: candidate\n", "live", "unwired"),  # the entry's verify wins
        ("", None, "unwired"),
    ],
)
def test_a_v8_skipped_entry_moves_by_the_r6_rule(
    tmp_path: Path, entry: str, row_verify: str | None, want: str
) -> None:
    rows = row(id="r1")
    if row_verify is not None:
        rows += f"    verify: {row_verify}\n"
    root = make_repo(tmp_path, rows, header=_V4_HEADER)
    path = _record_file(root, _v8(entry))

    report = run_migrations(root, dry_run=False)

    assert report.ok, report.failed
    record = load_record(path)
    assert record.schema_version == RECORD_SCHEMA_VERSION
    assert record.acceptance[0].status == want


def test_a_migrated_record_then_applies(tmp_path: Path) -> None:
    from fr.acceptance.model import load_matrix
    from fr.record.apply import RecordTarget, apply_record

    from tests.unit.test_record_apply import _matrix_repo

    root = _matrix_repo(tmp_path)
    path = _record_file(root, _v8().replace("id: r1", "id: target"))

    report = run_migrations(root, dry_run=False)
    assert report.ok, report.failed
    record = load_record(path)
    apply_record(
        root,
        None,
        record.model_copy(
            update={"run": None, "step": None, "item": None, "outcome": None, "ticks": ()}
        ),
        target=RecordTarget(message="m"),
    )

    matrix = load_matrix(root / "docs" / "acceptance" / "matrix.yaml")
    assert next(r for r in matrix.rows if r.id == "target").status == "unwired"


def test_an_unresolvable_verify_leaves_the_record_byte_identical(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(id="r1"))
    path = _record_file(root, _v8("    verify: no-such-strategy\n"))
    before = path.read_bytes()

    report = run_migrations(root, dry_run=False)

    assert [f.path for f in report.failed] == [path]
    assert path.read_bytes() == before


def test_a_wholly_v9_body_under_a_v8_stamp_is_only_stamped(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row(id="r1"))
    body = _v8().replace("status: skipped", "status: manual")
    path = _record_file(root, body)

    report = run_migrations(root, dry_run=False)

    assert report.ok, report.failed
    stamp = f"schema_version: {RECORD_SCHEMA_VERSION}"
    assert path.read_text() == body.replace("schema_version: 8", stamp)


def test_a_v9_record_saying_skipped_is_refused_by_name() -> None:
    with pytest.raises(RecordError, match="fr migrate artifacts --yes"):
        parse_record(_v8().replace("schema_version: 8", f"schema_version: {RECORD_SCHEMA_VERSION}"))


def test_the_frozen_v8_reader_reads_a_v8_record() -> None:
    record = legacy.parse_record_v8(_v8(_WALK))
    assert record.schema_version == 8
    assert record.acceptance[0].status == "skipped"


def test_the_frozen_v8_reader_has_not_been_edited() -> None:
    frozen = {
        name for name, obj in vars(legacy).items() if inspect.isclass(obj) and name.endswith("V8")
    }
    assert frozen == set(legacy.FROZEN_V8_CLASS_SHA256)
    drifted = {
        name
        for name in frozen
        if hashlib.sha256(inspect.getsource(getattr(legacy, name)).encode()).hexdigest()
        != legacy.FROZEN_V8_CLASS_SHA256[name]
    }
    assert not drifted, f"{sorted(drifted)} changed; freeze a `…V9` beside them instead"


def test_no_record_migration_reads_with_the_live_model() -> None:
    """Every record hop reads through a frozen model; only the newest hop's
    crash-window question may ask the live one."""
    import fr.artifacts.record_contract as contract
    import fr.artifacts.record_questions as questions
    import fr.artifacts.record_strategies as strategies

    for mod in (contract, questions, strategies):
        assert "fr.record.model" not in inspect.getsource(mod), mod.__name__
