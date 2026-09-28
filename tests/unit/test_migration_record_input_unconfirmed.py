"""The `record` kind's version-3 migration — spec
`2026-09-28-requirements-traceability-design.md` §H: `JournalItem.input`,
`AcceptanceItem.verify` and `ResolutionState` + `unconfirmed`, on an
`extra="forbid"` model, so a stamp bump + a registered migration + the
validator, per `.claude/rules/artifact-versioning.md`. Nothing is removed or
moved, so no frozen legacy model; stamp only, no body rewrite.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.record.model import RECORD_SCHEMA_VERSION, parse_record

_V2_RECORD = """\
schema_version: 2
run: r1
step: implement-phase
item: phase/1
outcome: done
ticks: [P1.T1.S1]
"""


def _record_file(root: Path, text: str = _V2_RECORD, stem: str = "implement-phase__phase-1"):
    path = root / "docs" / "superpowers" / "runs" / "r1.records" / f"{stem}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_record_kind_is_at_version_three() -> None:
    assert RECORD_SCHEMA_VERSION == 3
    assert artifact_kind("record").current_version == 3


def test_a_two_to_three_migration_is_registered() -> None:
    (hop,) = MIGRATIONS.chain("record", 2)
    assert (hop.from_version, hop.to_version) == (2, 3)


def test_the_chain_from_one_reaches_three_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("record", PRE_FRAMEWORK_VERSION)
    assert [(s.from_version, s.to_version) for s in chain] == [(1, 2), (2, 3)]


def test_a_v2_record_is_stamped_with_no_body_rewrite(tmp_path: Path) -> None:
    path = _record_file(tmp_path)
    before = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path.read_text() == before.replace("schema_version: 2\n", "schema_version: 3\n")
    assert parse_record(path.read_text()).schema_version == 3


def test_migrating_is_idempotent(tmp_path: Path) -> None:
    path = _record_file(tmp_path)
    run_migrations(tmp_path, dry_run=False)
    once = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.applied == ()
    assert path.read_text() == once


def test_an_unreadable_v2_record_is_refused_byte_identical(tmp_path: Path) -> None:
    broken = _record_file(tmp_path, "schema_version: 2\nticks: [nope]\n", stem="deliver")
    healthy = _record_file(tmp_path)
    before = broken.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [broken]
    assert broken.read_bytes() == before
    assert artifact_kind("record").read_version(healthy) == 3


def test_a_truncated_v2_record_is_refused_byte_identical(tmp_path: Path) -> None:
    broken = _record_file(tmp_path, "schema_version: 2\nticks: [P1.T1.S1\n", stem="deliver")
    before = broken.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert broken in [f.path for f in report.failed]
    assert broken.read_bytes() == before


def test_an_empty_v2_record_is_stamped(tmp_path: Path) -> None:
    path = _record_file(tmp_path, "schema_version: 2\n")

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert artifact_kind("record").read_version(path) == 3


def test_this_repos_own_live_records_are_current(repo_root: Path) -> None:
    from fr.artifacts import iter_artifact_paths

    kind = artifact_kind("record")
    for path in iter_artifact_paths(repo_root, "record"):
        assert kind.read_version(path) == kind.current_version, f"{path} is stale"


def test_a_migrated_v2_record_applies_through_the_record_engine(tmp_path: Path) -> None:
    """Code review finding d4 (spec Test Plan 10): a record written before
    `input`/`verify`/`unconfirmed` existed — `schema_version: 2`, no trace of
    any of the three — for a real run's open unit. Migrated in place, it must
    still apply cleanly through `fr run resolve --record`, the same engine
    `test_record_apply.py`'s implement-record tests drive via
    `tests.unit.record_support`."""
    import yaml
    from fr.run import units
    from fr.run.model import load_run_state

    from tests.unit.record_support import RUN, commit_all, fr, started_run

    root = started_run(tmp_path)
    record_path = (
        root / "docs" / "superpowers" / "runs" / f"{RUN}.records" / "implement-phase__phase-1.yaml"
    )
    v2_data = {
        "schema_version": 2,
        "run": RUN,
        "step": "implement-phase",
        "item": "phase/1",
        "outcome": "done",
        "ticks": ["P1.T1.S1", "P1.T1.S2", "P1.T2.S1"],
        "refactor": {"P1.T1": "none: one function, nothing to extract"},
        "journal": [
            {"kind": "decision", "id": "d-p1", "title": "kept it flat", "body": "why"},
        ],
    }
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(yaml.safe_dump(v2_data, sort_keys=False))
    commit_all(root, "executor work, v2 record in progress")

    report = run_migrations(root, dry_run=False)

    assert report.ok, report.failed
    assert parse_record(record_path.read_text()).schema_version == 3
    commit_all(root, "migrate record to schema_version 3")

    out = fr(
        root,
        [
            "run",
            "resolve",
            RUN,
            "--step",
            "implement-phase",
            "--record",
            str(record_path),
            "--item",
            "phase/1",
        ],
    )

    assert out.exit_code == 0, out.output
    assert not record_path.exists()
    state = load_run_state(root, RUN)
    assert units.unit_states(state.steps["implement"])["phase/1/implement-phase"] == "done"
