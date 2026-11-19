"""A run records its real merge target before review, without resetting evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr.run.model import (
    RunState,
    StepRecord,
    current_run_schema_version,
    load_run_state,
    save_run_state,
)

from tests.unit.lens_repo import git
from tests.unit.test_run_cli import _invoke, _repo


def _seed(tmp_path: Path):
    root = _repo(tmp_path)
    remote = tmp_path / "origin.git"
    git(root, "init", "-q", "--bare", str(remote))
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-q", "origin", "HEAD:management")
    git(root, "fetch", "-q", "origin")
    state = RunState(
        schema_version=current_run_schema_version(),
        run="r1",
        workflow="fr-goal@1",
        branch="b",
        started="2026-11-19T00:00:00Z",
        cursor="lens-review",
        steps={"implement": StepRecord(state="done"), "lens-review": StepRecord(state="pending")},
    )
    save_run_state(root, state)
    return root, state


def test_target_records_nondefault_branch_without_resetting_run(tmp_path: Path) -> None:
    root, before = _seed(tmp_path)
    result = _invoke(root, tmp_path / "shipped", ["run", "target", "r1", "--base", "management"])
    assert result.exit_code == 0, result.output
    after = load_run_state(root, "r1")
    assert after.base_branch == "management"
    assert after.steps == before.steps and after.cursor == before.cursor
    assert after.run == before.run and after.started == before.started


def test_target_refuses_missing_remote_branch_without_writing_run(tmp_path: Path) -> None:
    root, before = _seed(tmp_path)
    result = _invoke(root, tmp_path / "shipped", ["run", "target", "r1", "--base", "missing"])
    assert result.exit_code == 2 and "not fetched" in result.output
    assert load_run_state(root, "r1") == before


def test_target_cannot_change_after_lens_review_was_dispatched(tmp_path: Path) -> None:
    root, before = _seed(tmp_path)
    started = before.model_copy(update={"steps": {"lens-review": StepRecord(state="running")}})
    save_run_state(root, started)
    result = _invoke(root, tmp_path / "shipped", ["run", "target", "r1", "--base", "management"])
    assert result.exit_code == 2 and "review" in result.output
    assert load_run_state(root, "r1") == started


def test_run_target_schema_has_registered_migration_without_guessing_old_targets(
    tmp_path: Path,
) -> None:
    from fr.artifacts import run_migrations
    from fr.run.model import run_path

    root, before = _seed(tmp_path)
    old = before.model_copy(update={"schema_version": 11})
    save_run_state(root, old)
    report = run_migrations(root, dry_run=False)
    assert report.failed == ()
    after = load_run_state(root, "r1")
    assert after.schema_version == 12
    assert after.base_branch is None, "migration must not guess an old run's intended target"
    raw = json.dumps(after.model_dump())
    assert "management" not in raw
    assert run_path(root, "r1").exists()


@pytest.mark.parametrize("name", ["", "HEAD~1", "--all", "refs/heads/management", "x\ny", "x..y"])
def test_target_refuses_revision_expressions_and_unsafe_names(tmp_path: Path, name: str) -> None:
    root, before = _seed(tmp_path)
    result = _invoke(root, tmp_path / "shipped", ["run", "target", "r1", "--base", name])
    assert result.exit_code == 2
    assert load_run_state(root, "r1") == before


def test_missing_explicit_lens_target_never_falls_back_to_default(tmp_path: Path) -> None:
    from fr.lenses.accumulate import lens_set
    from fr.lenses.model import LensError

    root, state = _seed(tmp_path)
    # A local branch is not evidence that the remote target was fetched.
    git(root, "branch", "missing")
    with pytest.raises(LensError, match="not fetched"):
        lens_set(root, state.model_copy(update={"base_branch": "missing"}))


def test_migration_refuses_malformed_v11_without_changing_bytes(tmp_path: Path) -> None:
    from fr.artifacts import run_migrations
    from fr.run.model import run_path

    root, state = _seed(tmp_path)
    save_run_state(root, state.model_copy(update={"schema_version": 11}))
    path = run_path(root, "r1")
    before = path.read_bytes() + b"unknown_field: true\n"
    path.write_bytes(before)
    report = run_migrations(root, dry_run=False)
    assert [entry.path for entry in report.failed] == [path]
    assert path.read_bytes() == before


def test_migration_finishes_stamp_for_already_v12_body(tmp_path: Path) -> None:
    from fr.artifacts import run_migrations

    root, state = _seed(tmp_path)
    save_run_state(
        root, state.model_copy(update={"schema_version": 11, "base_branch": "management"})
    )
    report = run_migrations(root, dry_run=False)
    assert report.failed == ()
    after = load_run_state(root, "r1")
    assert after.schema_version == 12 and after.base_branch == "management"
