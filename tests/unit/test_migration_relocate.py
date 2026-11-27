"""Relocating hops and location-stamped kinds (spec 2026-11-19-event-driven-a-la-carte S1
§D, R10, R12; plan 2026-11-24-s1-configuration-homes P4.T1).

A moved kind lists every locator it has had (`ArtifactKind.locators`, oldest first); a
location-stamped one reads its version from which of them a file matched, and its stamp
writer is a no-op. A `SchemaMigration(..., relocates=True)` hop moves the file to its
`destination`; the runner writes no stamp, stages the rename (`PlannedAction.moved_to`),
accepts the source gone and validates the file where it landed.

Toy kinds, in a private `MigrationRegistry`: the shipped registry is not this file's
subject (see `test_migration_config_kinds.py`).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.artifacts.commit import commit_migration
from fr.artifacts.registry import (
    ArtifactKind,
    _read_yaml_stamp,
    _write_yaml_stamp,
    iter_paths_of,
    location_stamp,
    no_stamp_write,
)
from fr.artifacts.runner import (
    MigrationRegistry,
    SchemaMigration,
    is_stale,
    relocate_file,
    run_migrations,
)

OLD, NEW = "old/*.yaml", "new/*.yaml"


def _dest(path: Path) -> Path:
    return path.parent.parent / "new" / path.name


def _move(path: Path) -> None:
    relocate_file(path, _dest(path))


def _toy(*, validate=lambda _p: []) -> MigrationRegistry:
    kind = ArtifactKind(
        name="toy",
        current_version=2,
        locator=NEW,
        locators=(OLD, NEW),
        stamp="its location",
        read_stamp=location_stamp(OLD, NEW),
        write_version=no_stamp_write,
        validate=validate,
    )
    reg = MigrationRegistry(kinds={"toy": kind})
    reg.register(SchemaMigration("toy", 1, 2, fn=_move, relocates=True, destination=_dest))
    return reg


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "work")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "user.email", "t@example.invalid")
    (root / "README.md").write_text("x\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    return root


def _file(root: Path, rel: str, text: str = "a: 1\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_location_is_the_stamp(tmp_path: Path) -> None:
    kind = _toy().kind("toy")
    old, new = _file(tmp_path, "old/a.yaml"), _file(tmp_path, "new/b.yaml")
    assert kind.read_version(old) == 1 and kind.read_version(new) == 2
    assert list(iter_paths_of(tmp_path, kind)) == [old, new]
    no_stamp_write(new, 7)
    assert new.read_text() == "a: 1\n"


def test_a_newer_more_specific_locator_wins_over_an_older_one_it_also_matches(
    tmp_path: Path,
) -> None:
    read = location_stamp("settings.yaml", ".fr/settings.yaml")
    assert read(tmp_path / "settings.yaml") == 1
    assert read(tmp_path / ".fr" / "settings.yaml") == 2


def test_a_relocating_hop_moves_the_file_and_stages_a_rename(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    old = _file(root, "old/a.yaml", "a: 1\nb: 2\nc: 3\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "old")
    reg = _toy()

    planned = run_migrations(root, registry=reg)
    assert [a.moved_to for a in planned.applied] == [root / "new" / "a.yaml"]
    assert old.exists()  # a dry run moved nothing

    report = run_migrations(root, dry_run=False, registry=reg)
    assert report.ok, report.failed
    (action,) = report.applied
    assert action.moved_to == root / "new" / "a.yaml" and action.removed == (old,)
    assert not old.exists() and (root / "new" / "a.yaml").read_text() == "a: 1\nb: 2\nc: 3\n"
    assert not is_stale(root, registry=reg)

    outcome = commit_migration(root, report, fr_version="9.9.9")
    assert outcome.committed, outcome.reason
    assert _git(root, "status", "--porcelain") == ""
    assert "R" in _git(root, "show", "--name-status", "-M", "--format=", "HEAD")
    follow = _git(root, "log", "--follow", "--format=%s", "--", "new/a.yaml").splitlines()
    assert follow == ["chore(fr): migrate 1 artifact to fr 9.9.9", "old"]


def test_an_untracked_file_is_renamed_without_a_commit(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    old = _file(root, "old/a.yaml")
    report = run_migrations(root, dry_run=False, registry=_toy())
    assert report.ok and not old.exists() and (root / "new" / "a.yaml").exists()
    head = _git(root, "rev-parse", "HEAD")
    outcome = commit_migration(root, report, fr_version="9.9.9")
    assert not outcome.committed
    assert _git(root, "rev-parse", "HEAD") == head
    assert "new/" in _git(root, "status", "--porcelain")  # still untracked, never added


def test_a_destination_that_exists_with_other_bytes_is_refused_and_the_rest_migrate(
    tmp_path: Path,
) -> None:
    clash = _file(tmp_path, "old/a.yaml", "a: 1\n")
    taken = _file(tmp_path, "new/a.yaml", "a: 2\n")
    free = _file(tmp_path, "old/b.yaml")
    reg = _toy()

    planned = run_migrations(tmp_path, registry=reg)
    assert [f.path for f in planned.failed] == [clash]
    assert str(clash) in planned.failed[0].error and str(taken) in planned.failed[0].error

    report = run_migrations(tmp_path, dry_run=False, registry=reg)
    assert [f.path for f in report.failed] == [clash] and "R12" in report.failed[0].error
    assert clash.read_text() == "a: 1\n" and taken.read_text() == "a: 2\n"
    assert not free.exists() and (tmp_path / "new" / "b.yaml").exists()


def test_a_destination_holding_the_same_bytes_finishes_the_move(tmp_path: Path) -> None:
    old = _file(tmp_path, "old/a.yaml")
    _file(tmp_path, "new/a.yaml")
    report = run_migrations(tmp_path, dry_run=False, registry=_toy())
    assert report.ok and not old.exists()


def test_a_file_invalid_at_its_destination_is_that_artifacts_failure(tmp_path: Path) -> None:
    _file(tmp_path, "old/a.yaml", "bad\n")
    good = _file(tmp_path, "old/b.yaml")

    def validate(path: Path) -> list[str]:
        return ["not a mapping"] if path.read_text() == "bad\n" else []

    report = run_migrations(tmp_path, dry_run=False, registry=_toy(validate=validate))
    assert [f.path.name for f in report.failed] == ["a.yaml"]
    assert "not valid after the move" in report.failed[0].error
    assert tmp_path / "new" / "a.yaml" in report.failed[0].also_wrote
    assert not good.exists()


def test_a_relocating_hop_need_not_be_the_last(tmp_path: Path) -> None:
    """A body-stamped kind (profiles' shape): 1 -> 2 relocates and writes its own stamp,
    2 -> 3 is an ordinary stamp hop at the destination."""
    old_loc, new_loc = "old/p.yaml", "new/p.yaml"

    def move(path: Path) -> None:
        dest = _dest(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("schema_version: 2\n" + path.read_text())
        path.unlink()

    kind = ArtifactKind(
        name="body",
        current_version=3,
        locator=new_loc,
        locators=(old_loc, new_loc),
        stamp="`schema_version`",
        read_stamp=_read_yaml_stamp,
        write_version=_write_yaml_stamp,
        validate=lambda _p: [],
    )
    reg = MigrationRegistry(kinds={"body": kind})
    reg.register(SchemaMigration("body", 1, 2, fn=move, relocates=True, destination=_dest))
    reg.register(SchemaMigration("body", 2, 3, fn=lambda _p: None))
    _file(tmp_path, old_loc, "x: 1\n")

    report = run_migrations(tmp_path, dry_run=False, registry=reg)
    assert report.ok, report.failed
    assert [(a.from_version, a.to_version) for a in report.applied] == [(1, 2), (2, 3)]
    assert report.applied[1].path == tmp_path / new_loc
    assert (tmp_path / new_loc).read_text() == "schema_version: 3\nx: 1\n"


def test_a_relocating_migration_needs_a_destination() -> None:
    with pytest.raises(ValueError, match="destination"):
        SchemaMigration("toy", 1, 2, fn=_move, relocates=True)
    with pytest.raises(ValueError, match="relocates or retires"):
        SchemaMigration("toy", 1, 2, fn=_move, relocates=True, destination=_dest, retires=True)


def test_the_uncommitted_veto_holds_back_a_move_onto_a_file_being_edited(
    tmp_path: Path,
) -> None:
    old = _file(tmp_path, "old/a.yaml")
    dest = tmp_path / "new" / "a.yaml"

    def veto(path: Path) -> str | None:
        return "has uncommitted changes" if path == dest else None

    report = run_migrations(tmp_path, dry_run=False, registry=_toy(), veto=veto)
    assert [f.path for f in report.failed] == [old] and "destination" in report.failed[0].error
    assert old.exists()
