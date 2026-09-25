"""The step-record apply engine (spec 2026-09-25-lean-cost-aware-process §5.C.2,
§7 item 10): one `fr run resolve --record` validates, gates, writes atomically,
commits once and prints one line — and an invalid record changes nothing."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.journal.model import effective_finding_states, journal_path, parse_journal
from fr.parser import parse
from fr.run import units
from fr.run.model import load_run_state

from tests.unit.record_support import (
    PLAN_REL,
    RUN,
    SLUG,
    commit_all,
    fr,
    git,
    head,
    implement_record,
    snapshot,
    started_run,
    write_record,
)


def _resolve(root: Path, record: Path, step: str = "implement-phase", item: str | None = "phase/1"):
    argv = ["run", "resolve", RUN, "--step", step, "--record", str(record)]
    if item is not None:
        argv += ["--item", item]
    return fr(root, argv)


def _journal(root: Path):
    return parse_journal(journal_path(root, "plan", SLUG).read_text())


def test_a_valid_implement_record_applies_everything_in_one_commit(tmp_path: Path) -> None:
    root = started_run(tmp_path)
    record = write_record(root, implement_record())
    commit_all(root, "executor work, record in progress")
    before = head(root)

    out = _resolve(root, record)

    assert out.exit_code == 0, out.output
    # ONE stdout line naming counts, the next unit and the commit.
    lines = out.stdout.splitlines()
    assert len(lines) == 1, out.stdout
    line = lines[0]
    assert line.startswith("implement-phase phase/1 done")
    assert "3 ticked" in line and "1 decision" in line and "1 resolved" in line
    assert "next: review-phase phase/1" in line
    assert line.endswith(head(root)[:7]) or head(root).startswith(line.rsplit(" ", 1)[-1])
    # One commit, and a clean tree for fr's paths.
    assert git(root, "rev-list", "--count", f"{before}..HEAD").strip() == "1"
    assert git(root, "status", "--porcelain", "--", "docs").strip() == ""
    # Ticks and the phase's completion.
    phase = parse(root / PLAN_REL).phases[0]
    assert {s.state for s in phase.state.steps.values()} == {"x"}
    assert phase.state.completion.at
    # Journal entries and the resolution; the refactor reason is journalled.
    entries = _journal(root)
    ids = {e.id for e in entries}
    assert {"d-p1", "p1-f1", "p1-f1-resolved"} <= ids
    assert effective_finding_states(entries)["p1-f1"] == "fixed"
    assert any("no-refactor-because P1.T1" in e.title for e in entries)
    # The cursor moved, and the record is gone in that same commit.
    state = load_run_state(root, RUN)
    assert units.unit_states(state.steps["implement"])["phase/1/implement-phase"] == "done"
    assert not record.exists()
    assert record.name in git(root, "show", "--stat", "--format=", "HEAD")


REFUSALS = {
    "unknown section": ({"acceptance": [{"id": "x", "status": "ci", "notes": "n"}]}, "acceptance"),
    "unknown tick id": ({"ticks": ["P1.T9.S1"]}, "P1.T9.S1"),
    "unknown finding id": (
        {"resolves": [{"id": "nope", "state": "fixed", "body": "b"}]},
        "nope",
    ),
    "malformed entry": ({"journal": [{"kind": "nope", "title": "t"}]}, "journal"),
    "duplicate id": (
        {
            "journal": [
                {"kind": "decision", "id": "dup", "title": "a"},
                {"kind": "decision", "id": "dup", "title": "b"},
            ]
        },
        "dup",
    ),
    "refactor gate": ({"refactor": None}, "refactor"),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_an_invalid_record_changes_nothing(tmp_path: Path, case: str) -> None:
    root = started_run(tmp_path)
    overrides, needle = REFUSALS[case]
    record = write_record(root, implement_record(**overrides))
    commit_all(root, "record")
    before, files = head(root), snapshot(root)

    out = _resolve(root, record)

    assert out.exit_code == 2, out.output
    assert needle in out.output
    assert snapshot(root) == files, "a refused record must leave every byte as it was"
    assert head(root) == before
    assert record.exists()


def _implemented(tmp_path: Path, **overrides: object) -> Path:
    root = started_run(tmp_path)
    record = write_record(root, implement_record(**overrides))
    commit_all(root, "record")
    out = _resolve(root, record)
    assert out.exit_code == 0, out.output
    adv = fr(root, ["run", "advance", RUN])
    assert adv.exit_code == 0, adv.output
    return root


def _review_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "schema_version": 1,
        "run": RUN,
        "step": "review-phase",
        "item": "phase/1",
        "outcome": "done",
        "journal": [
            {"kind": "review", "id": "r-p1", "title": "phase 1 review", "body": "clean"},
        ],
        "evidence": {"review": "r-p1", "reviewer": "reviewer-1"},
    }
    record.update(overrides)
    return {k: v for k, v in record.items() if v is not None}


def test_the_review_witness_still_fires(tmp_path: Path) -> None:
    root = _implemented(tmp_path)
    record = write_record(root, _review_record(evidence={"review": "absent", "reviewer": "x"}))
    files = snapshot(root)

    out = _resolve(root, record, step="review-phase")

    assert out.exit_code == 2, out.output
    assert "absent" in out.output
    assert snapshot(root) == files


def test_a_valid_review_record_resolves_and_warnings_print_in_full(tmp_path: Path) -> None:
    root = _implemented(tmp_path)
    record = write_record(root, _review_record())

    out = _resolve(root, record, step="review-phase")

    assert out.exit_code == 0, out.output
    assert len(out.stdout.splitlines()) == 1
    assert "next: journal-check" in out.stdout
    # The reviewer gate could not observe (no harness in a test): its warning
    # reaches stderr whole, not folded into the one line.
    assert "unobserved" in out.stderr or "could not" in out.stderr, out.stderr


def test_the_operator_guard_refuses_an_out_of_scope_finding_fixed_by_the_agent(
    tmp_path: Path,
) -> None:
    root = _implemented(
        tmp_path,
        resolves=[{"id": "p1-f1", "state": "out-of-scope", "body": "not ours"}],
    )
    record = write_record(
        root, _review_record(resolves=[{"id": "p1-f1", "state": "fixed", "body": "fixed anyway"}])
    )
    files = snapshot(root)

    out = _resolve(root, record, step="review-phase")

    assert out.exit_code == 2, out.output
    assert "p1-f1" in out.output
    assert snapshot(root) == files


def test_existing_no_refactor_because_entries_still_satisfy_the_gate(tmp_path: Path) -> None:
    """Back-compat: a run started before records justified a task by journal."""
    root = started_run(tmp_path)
    add = fr(
        root,
        [
            "journal",
            "add",
            "--scope",
            "plan",
            "--slug",
            SLUG,
            "--kind",
            "discovery",
            "--phase",
            "1",
            "--title",
            "no-refactor-because P1.T1",
            "--body",
            "nothing to clean",
        ],  # fmt: skip
    )
    assert add.exit_code == 0, add.output
    record = write_record(root, implement_record(refactor=None))

    assert _resolve(root, record).exit_code == 0


def test_self_review_no_longer_demands_a_refactor_justification(tmp_path: Path) -> None:
    from fr.plan_ops import self_review

    root = started_run(tmp_path)
    issues = self_review(parse(root / PLAN_REL))
    assert not [i for i in issues if "no-refactor-because" in i.message]
