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

import yaml
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


def test_migrating_a_v1_record_stamps_it_and_rewrites_no_body(tmp_path: Path) -> None:
    path = _record_file(tmp_path)
    before = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path in report.changed_paths
    after = path.read_text()
    kind = artifact_kind("record")
    assert kind.read_version(path) == kind.current_version
    stripped = "\n".join(
        line for line in after.splitlines() if not line.startswith("schema_version:")
    )
    assert stripped.strip() == before.strip()
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

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [broken]
    assert yaml.safe_load(broken.read_text()).get("schema_version") is None
    assert artifact_kind("record").read_version(healthy) == artifact_kind("record").current_version


def test_this_repos_own_live_records_are_current(repo_root: Path) -> None:
    """Dogfooding, per the rule: the moment `current_version` moved, this
    repo's own live records went stale — including this phase's own step
    record. `fr migrate artifacts --yes` is run here and its result
    committed. Zero live records is a pass — the normal state between runs."""
    kind = artifact_kind("record")
    from fr.artifacts import iter_artifact_paths

    for path in iter_artifact_paths(repo_root, "record"):
        assert kind.read_version(path) == kind.current_version, f"{path} is stale"
