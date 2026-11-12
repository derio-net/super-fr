"""Runs in flight when `lens-review` shipped (spec 2026-11-12-review-lenses R13,
§3.C "Drift"): reshaped while the cursor is before `deliver`, carried over by
`fr run adopt <plan-dir> --supersede` when it is on `deliver`, and an older
journal with no lens entry reads as an empty set."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run import units
from fr.run.adopt import adopt_run
from fr.run.model import RunState, StepRecord, load_run_state
from fr.run.reshape import ReshapeError, reshape
from fr.workflow.model import WorkflowManifest
from fr.workflow.resolve import resolve_workflow

from tests.unit.test_run_adopt import BRANCH, _commit_all, _git, _repo, _write_plan, _write_spec

REPO = Path(__file__).resolve().parents[2]
URL = "https://github.com/derio-net/super-fr/pull/451"


def _manifest() -> WorkflowManifest:
    return resolve_workflow("fr-goal", REPO)


def _pre_lens(manifest: WorkflowManifest) -> list[str]:
    return [s.id for s in manifest.steps if s.id != "lens-review"]


def _cursor_before_lenses(cursor: str) -> RunState:
    """A cursor written against the step list before `lens-review`, phase 1
    implemented and reviewed."""
    manifest = _manifest()
    order = _pre_lens(manifest)
    at = order.index(cursor)
    steps: dict[str, StepRecord] = {}
    for index, step in enumerate(s for s in manifest.steps if s.id in order):
        record = StepRecord(
            state="done" if index < at else ("running" if index == at else "pending"),
            members=[m.id for m in step.steps] or None,
        )
        if step.id == "implement":
            record = units.with_unit_state(record, "phase/1/implement-phase", "done")
            record = units.with_unit_state(record, "phase/1/review-phase", "done")
        steps[step.id] = record
    return RunState(
        run="2026-11-01-feat-x",
        workflow=f"fr-goal@{manifest.schema_version}",
        branch="feat/x",
        started="2026-11-01T10:00:00+00:00",
        cursor=cursor,
        steps=steps,
    )


@pytest.mark.parametrize("cursor", ["implement", "journal-check"])
def test_reshape_inserts_lens_review_pending_and_keeps_every_unit(cursor: str) -> None:
    manifest = _manifest()
    old = _cursor_before_lenses(cursor)

    new = reshape(old, manifest)

    assert list(new.steps) == [s.id for s in manifest.steps]
    assert new.steps["lens-review"].state == "pending"
    assert new.cursor == cursor
    assert units.unit_states(new.steps["implement"]) == units.unit_states(old.steps["implement"])
    assert all(new.steps[k] == v for k, v in old.steps.items())


def test_reshape_at_deliver_refuses_naming_adopt_supersede() -> None:
    with pytest.raises(ReshapeError, match=r"fr run adopt <plan-dir> --supersede"):
        reshape(_cursor_before_lenses("deliver"), _manifest())


def _shipped_pair(tmp_path: Path, shipped: Path) -> Path:
    """`shipped` rewritten to the pre-lens fr-goal; returns a dir holding today's."""
    current = tmp_path / "_shipped_now"
    current.mkdir()
    text = (shipped / "fr-goal.yaml").read_text()
    (current / "fr-goal.yaml").write_text(text)
    start = text.index("  - id: lens-review\n")
    end = text.index("  - id: deliver\n")
    (shipped / "fr-goal.yaml").write_text(text[:start] + text[end:])
    return current


def test_adopt_supersede_at_deliver_owes_the_lens_review(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped = _repo(tmp_path, repo_root)
    current = _shipped_pair(tmp_path, shipped)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2, complete=2)
    _commit_all(repo)
    _git(repo, "checkout", "-q", "-b", "feat/old")
    old = adopt_run(
        repo, plan_dir, branch=BRANCH, run_id="old-run", shipped_root=shipped,
        pr_url=URL, pr_state=lambda _u: "OPEN",
    )  # fmt: skip
    assert old.cursor == "deliver" and "lens-review" not in old.steps
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "old cursor")

    new = adopt_run(
        repo, plan_dir, branch=BRANCH, run_id="new-run", shipped_root=current,
        pr_url=URL, pr_state=lambda _u: "OPEN", supersede=True,
    )  # fmt: skip

    assert new.cursor == "lens-review"
    assert new.steps["lens-review"].state == "pending"
    assert new.steps["deliver"].state == "pending"
    assert new.steps["deliver"].emitted == {"pr": URL}
    assert units.unit_states(new.steps["implement"]) == units.unit_states(old.steps["implement"])
    assert load_run_state(repo, "new-run").cursor == "lens-review"


def test_a_journal_with_no_lens_entry_reads_as_an_empty_set(tmp_path: Path) -> None:
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path
    from fr.lenses.accumulate import lens_set_for

    from tests.unit.lens_repo import lens_repo

    root = lens_repo(tmp_path)
    append_journal_entry(
        journal_path(root, "plan", "p"),
        "p",
        JournalEntry(
            kind="decision", scope="plan", id="d1", created="2026-10-01T00:00:00+00:00",
            title="an older journal", body="no lens anywhere",
        ),
    )  # fmt: skip

    assert lens_set_for(root, spec_slug=None, plan_slug="p").lenses == ()
