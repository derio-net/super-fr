"""The `record` kind's version-2 migration — spec
`2026-09-26-dynamic-brainstorm-question-rounds-design.md` §3.B, plus the
obligations `.claude/rules/artifact-versioning.md` attaches to every shape
change.

`StepRecord` gained `questions`, and it is `extra="forbid"`-closed: an fr
that does not know the key raises rather than ignoring it. The rule
therefore requires three things in the same PR — a stamp bump in
`fr.artifacts.registry` and nowhere else, a **registered** migration (a
migration nobody imports never runs), and a structure validator reachable as
`ArtifactKind.validate`. These tests pin all three, and the one property
that makes the migration safe to run over a live record: it rewrites no
body.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.record.model import parse_record

_V1_RECORD = """\
run: r1
step: implement-phase
item: phase/1
outcome: done
ticks: [P1.T1.S1]
"""


def _record_file(
    root: Path, text: str = _V1_RECORD, stem: str = "implement-phase__phase-1"
) -> Path:
    path = root / "docs" / "superpowers" / "runs" / "r1.records" / f"{stem}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_record_kind_moved_past_version_one() -> None:
    assert artifact_kind("record").current_version > PRE_FRAMEWORK_VERSION


def test_a_migration_off_version_one_is_registered_for_the_record_kind() -> None:
    kind = artifact_kind("record")
    chain = MIGRATIONS.chain("record", PRE_FRAMEWORK_VERSION)
    assert chain, "no registered migration moves a pre-framework record file"
    assert [step.to_version for step in chain] == [2]
    assert chain[-1].to_version == kind.current_version


@pytest.mark.parametrize(
    "stamped", [False, True], ids=["no-stamp", "template-rendered-schema_version-1"]
)
def test_migrating_a_v1_record_stamps_it_and_rewrites_no_body(
    tmp_path: Path, stamped: bool
) -> None:
    """p1-r3: every real in-flight v1 record came from the old template and
    carries `schema_version: 1`; the stamp-less file is the hand-written case."""
    path = _record_file(tmp_path, ("schema_version: 1\n" if stamped else "") + _V1_RECORD)
    before = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path in report.changed_paths
    after = path.read_text()
    kind = artifact_kind("record")
    assert kind.read_version(path) == kind.current_version
    if stamped:
        assert after == before.replace("schema_version: 1\n", "schema_version: 2\n")
    else:
        assert (
            after.splitlines()[1:] == before.splitlines()
            or after.splitlines()[:-1] == before.splitlines()
        ), after
        assert "schema_version: 2" in after
    record = parse_record(after)
    assert record.schema_version == kind.current_version
    assert record.questions is None


def test_migrating_is_idempotent(tmp_path: Path) -> None:
    path = _record_file(tmp_path)
    run_migrations(tmp_path, dry_run=False)
    once = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.applied == ()
    assert path.read_text() == once


def test_an_unreadable_v1_record_is_refused_and_left_untouched(tmp_path: Path) -> None:
    broken = _record_file(tmp_path, "run: r1\nticks: [not-a-tick-id]\n", stem="deliver")
    healthy = _record_file(tmp_path)

    before = broken.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [broken]
    assert broken.read_bytes() == before
    assert artifact_kind("record").read_version(healthy) == artifact_kind("record").current_version


def test_a_v1_record_that_is_not_yaml_is_refused_and_left_byte_identical(
    tmp_path: Path,
) -> None:
    """p1-r2: truncated mid-edit — the stamp read fails before the guard runs,
    and nothing is written."""
    broken = _record_file(
        tmp_path, "schema_version: 1\nrun: r1\nticks: [P1.T1.S1\n", stem="deliver"
    )
    before = broken.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert broken in [f.path for f in report.failed]
    assert broken.read_bytes() == before


def test_an_empty_v1_record_is_stamped_like_parse_record_reads_it(tmp_path: Path) -> None:
    """p1-r4: `parse_record` reads an empty file as `{}`, a valid record; the
    guard must agree, or the file stays stale forever and blocks the CLI gate."""
    path = _record_file(tmp_path, "# nothing yet\n")

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert artifact_kind("record").read_version(path) == artifact_kind("record").current_version


def test_this_repos_own_live_records_are_current(repo_root: Path) -> None:
    """Dogfooding, per the rule: the moment `current_version` moved, this
    repo's own live records went stale — including this phase's own step
    record. `fr migrate artifacts --yes` is run here and its result
    committed. Zero live records is a pass — the normal state between runs."""
    kind = artifact_kind("record")
    from fr.artifacts import iter_artifact_paths

    for path in iter_artifact_paths(repo_root, "record"):
        assert kind.read_version(path) == kind.current_version, f"{path} is stale"
