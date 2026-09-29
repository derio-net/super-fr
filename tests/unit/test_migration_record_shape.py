"""The `record` kind's version-6 migration (5 -> 6; 4 -> 5 is `JournalItem.delegated`) — spec
`2026-09-29-fr-goal-light-path-design.md` §A: an optional `StepRecord.shape`
(the brainstorm record's rebind onto another workflow shape) on an
`extra="forbid"` model, so a stamp bump + a registered migration + the
validator, per `.claude/rules/artifact-versioning.md`. Nothing is removed or
moved, so no frozen legacy model; stamp only, no body rewrite.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.record.model import RECORD_SCHEMA_VERSION, load_record, parse_record

_V5_RECORD = """\
schema_version: 5
run: r1
step: implement-phase
item: phase/1
outcome: done
ticks: [P1.T1.S1]
"""

_V6_BRAINSTORM_RECORD = """\
schema_version: 6
run: r1
step: brainstorm
outcome: done
shape: fr-goal-light
"""


def _record_file(root: Path, text: str = _V5_RECORD, stem: str = "implement-phase__phase-1"):
    path = root / "docs" / "superpowers" / "runs" / "r1.records" / f"{stem}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_record_kind_is_at_version_six_or_later() -> None:
    assert RECORD_SCHEMA_VERSION >= 6
    assert artifact_kind("record").current_version == RECORD_SCHEMA_VERSION


def test_a_five_to_six_migration_is_registered() -> None:
    hop = MIGRATIONS.chain("record", 5)[0]
    assert (hop.from_version, hop.to_version) == (5, 6)


def test_the_chain_from_one_passes_six_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("record", PRE_FRAMEWORK_VERSION)
    # 6 -> 7 (removal) follows; test_migration_record_contract pins the whole chain.
    assert [(s.from_version, s.to_version) for s in chain][:5] == [
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 5),
        (5, 6),
    ]


def test_a_v5_record_is_stamped_with_no_body_rewrite(tmp_path: Path) -> None:
    path = _record_file(tmp_path)
    before = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    stamp = f"schema_version: {RECORD_SCHEMA_VERSION}\n"
    assert path.read_text() == before.replace("schema_version: 5\n", stamp)
    assert parse_record(path.read_text()).schema_version == RECORD_SCHEMA_VERSION


def test_migrating_is_idempotent(tmp_path: Path) -> None:
    path = _record_file(tmp_path)
    run_migrations(tmp_path, dry_run=False)
    once = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.applied == ()
    assert path.read_text() == once


def test_an_unreadable_v5_record_is_refused_byte_identical(tmp_path: Path) -> None:
    broken = _record_file(tmp_path, "schema_version: 5\nticks: [nope]\n", stem="deliver")
    healthy = _record_file(tmp_path)
    before = broken.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [broken]
    assert broken.read_bytes() == before
    assert artifact_kind("record").read_version(healthy) == RECORD_SCHEMA_VERSION


def test_a_v6_record_carrying_shape_loads(tmp_path: Path) -> None:
    path = _record_file(tmp_path, _V6_BRAINSTORM_RECORD, stem="brainstorm")
    run_migrations(tmp_path, dry_run=False)

    record = load_record(path)

    assert record.shape == "fr-goal-light"
    assert artifact_kind("record").validate(path) == []


def test_a_record_without_shape_defaults_to_none() -> None:
    current = f"schema_version: {RECORD_SCHEMA_VERSION}"
    assert parse_record(_V5_RECORD.replace("schema_version: 5", current)).shape is None
