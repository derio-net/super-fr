"""The `record` kind's version-5 migration — spec
`2026-09-29-spec-fidelity-invention-design.md` §E: `JournalItem.delegated` on an `extra="forbid"` model, so a stamp bump + a
registered migration + the validator, per
`.claude/rules/artifact-versioning.md`. Nothing is removed or moved, so no
frozen legacy model; stamp only, no body rewrite.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.record.model import RECORD_SCHEMA_VERSION, parse_record

_V4_RECORD = """\
schema_version: 4
run: r1
step: implement-phase
item: phase/1
outcome: done
ticks: [P1.T1.S1]
"""


def _record_file(root: Path, text: str = _V4_RECORD, stem: str = "implement-phase__phase-1"):
    path = root / "docs" / "superpowers" / "runs" / "r1.records" / f"{stem}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_record_kind_is_at_version_five() -> None:
    assert RECORD_SCHEMA_VERSION == 5
    assert artifact_kind("record").current_version == 5


def test_a_four_to_five_migration_is_registered() -> None:
    (hop,) = MIGRATIONS.chain("record", 4)
    assert (hop.from_version, hop.to_version) == (4, 5)


def test_the_chain_from_one_reaches_five_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("record", PRE_FRAMEWORK_VERSION)
    assert [(s.from_version, s.to_version) for s in chain] == [(1, 2), (2, 3), (3, 4), (4, 5)]
    assert [s.to_version for s in chain] == [2, 3, 4, 5]


def test_a_v4_record_is_stamped_with_no_body_rewrite(tmp_path: Path) -> None:
    path = _record_file(tmp_path)
    before = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path.read_text() == before.replace("schema_version: 4\n", "schema_version: 5\n")
    assert parse_record(path.read_text()).schema_version == 5


def test_migrating_is_idempotent(tmp_path: Path) -> None:
    path = _record_file(tmp_path)
    run_migrations(tmp_path, dry_run=False)
    once = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.applied == ()
    assert path.read_text() == once


def test_an_unreadable_v4_record_is_refused_byte_identical(tmp_path: Path) -> None:
    broken = _record_file(tmp_path, "schema_version: 4\nticks: [nope]\n", stem="deliver")
    healthy = _record_file(tmp_path)
    before = broken.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [broken]
    assert broken.read_bytes() == before
    assert artifact_kind("record").read_version(healthy) == 5


def test_an_empty_v4_record_is_stamped(tmp_path: Path) -> None:
    path = _record_file(tmp_path, "schema_version: 4\n")

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert artifact_kind("record").read_version(path) == 5


def test_this_repos_own_live_records_are_current(repo_root: Path) -> None:
    from fr.artifacts import iter_artifact_paths

    kind = artifact_kind("record")
    for path in iter_artifact_paths(repo_root, "record"):
        assert kind.read_version(path) == kind.current_version, f"{path} is stale"
