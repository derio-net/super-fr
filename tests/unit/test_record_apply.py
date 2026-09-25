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


def test_record_evidence_carries_the_holders_model(tmp_path: Path) -> None:
    """`evidence.model` is `--model`: the model the review ran on (fr-goal §6)."""
    root = _implemented(tmp_path)
    record = write_record(
        root, _review_record(evidence={"review": "r-p1", "reviewer": "rv-1", "model": "m-1"})
    )

    assert _resolve(root, record, step="review-phase").exit_code == 0
    attempt = units.last_attempt(load_run_state(root, RUN), "phase/1/review-phase")
    assert attempt is not None and attempt.model == "m-1"


# --- gh#624: RecordTarget.acceptance_drops (spec Test Plan 9, 10) ------------


def _matrix_repo(tmp_path: Path) -> Path:
    """A real git repo whose matrix has one row carrying two unit refs, with
    the three committed reports already rendered and committed."""
    from fr.record.apply import RecordTarget, apply_record
    from fr.record.model import AcceptanceItem, StepRecord

    from tests.unit.acceptance_helpers import make_repo, row

    root = make_repo(
        tmp_path, row(id="target", unit='"own:tests/test_a.py", "own:tests/test_b.py"'), git=False
    )
    (root / "tests" / "test_b.py").write_text("def test_b(): pass\n")
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    commit_all(root, "seed")
    git(root, "checkout", "-qb", "feat/drops")
    # One plain move renders and commits the three reports, so the refusal
    # cases below have something byte-identical to compare against.
    apply_record(
        root,
        None,
        StepRecord(acceptance=(AcceptanceItem(id="target", status="ci", notes="seed"),)),
        target=RecordTarget(message="seed reports"),
    )
    commit_all(root, "reports")
    return root


def _move(row_id: str = "target", **fields: object):
    from fr.record.model import AcceptanceItem, StepRecord

    return StepRecord(
        acceptance=(
            AcceptanceItem.model_validate(
                {"id": row_id, "status": "skipped", "notes": "why", **fields}
            ),
        )
    )


def _unit_refs(root: Path, row_id: str = "target") -> tuple[str, ...]:
    from fr.acceptance.model import load_matrix

    matrix = load_matrix(root / "docs" / "acceptance" / "matrix.yaml")
    return next(r for r in matrix.rows if r.id == row_id).levels.get("unit", ())


def _acceptance_files(root: Path) -> dict[str, str]:
    return {k: v for k, v in snapshot(root).items() if k.startswith("docs/acceptance/")}


def test_a_present_drop_removes_the_ref_from_the_row(tmp_path: Path) -> None:
    from fr.record.apply import RecordTarget, apply_record

    root = _matrix_repo(tmp_path)
    target = RecordTarget(
        message="m", acceptance_drops={"target": {"unit": ("own:tests/test_b.py",)}}
    )

    apply_record(root, None, _move(), target=target)

    assert _unit_refs(root) == ("own:tests/test_a.py",)


def test_a_drop_and_an_addition_re_point_the_row_in_one_pass(tmp_path: Path) -> None:
    from fr.record.apply import RecordTarget, apply_record

    root = _matrix_repo(tmp_path)
    (root / "tests" / "test_c.py").write_text("def test_c(): pass\n")
    target = RecordTarget(
        message="m", acceptance_drops={"target": {"unit": ("own:tests/test_b.py",)}}
    )

    apply_record(root, None, _move(levels={"unit": ("own:tests/test_c.py",)}), target=target)

    assert _unit_refs(root) == ("own:tests/test_a.py", "own:tests/test_c.py")


def test_an_absent_ref_drop_is_refused_and_changes_nothing(tmp_path: Path) -> None:
    from fr.record.apply import RecordRefusedError, RecordTarget, apply_record

    root = _matrix_repo(tmp_path)
    before, sha, files = _acceptance_files(root), head(root), snapshot(root)
    assert {
        f"docs/acceptance/{n}"
        for n in ("report_local.html", "report_linked.html", "report_linked.md")
    } <= set(before)
    target = RecordTarget(
        message="m", acceptance_drops={"target": {"unit": ("own:tests/nope.py",)}}
    )

    with pytest.raises(RecordRefusedError, match="target"):
        apply_record(root, None, _move(), target=target)

    assert _acceptance_files(root) == before
    assert (head(root), snapshot(root)) == (sha, files), "a refused drop must not commit or write"


def test_a_drop_keyed_by_a_row_with_no_item_is_refused(tmp_path: Path) -> None:
    from fr.record.apply import RecordRefusedError, RecordTarget, apply_record

    root = _matrix_repo(tmp_path)
    before, sha, files = _acceptance_files(root), head(root), snapshot(root)
    target = RecordTarget(
        message="m", acceptance_drops={"other": {"unit": ("own:tests/test_b.py",)}}
    )

    with pytest.raises(RecordRefusedError, match="other"):
        apply_record(root, None, _move(), target=target)

    assert _acceptance_files(root) == before
    assert (head(root), snapshot(root)) == (sha, files), "a refused drop must not commit or write"


def test_a_drop_keyed_by_a_create_item_is_refused(tmp_path: Path) -> None:
    from fr.record.apply import RecordRefusedError, RecordTarget, apply_record

    root = _matrix_repo(tmp_path)
    before, sha, files = _acceptance_files(root), head(root), snapshot(root)
    create = _move(
        "fresh",
        capability="c",
        acceptance="a",
        origin=("own:docs/superpowers/specs/s.md",),
        status="not-implemented",
    )
    target = RecordTarget(
        message="m", acceptance_drops={"fresh": {"unit": ("own:tests/test_a.py",)}}
    )

    with pytest.raises(RecordRefusedError, match="fresh"):
        apply_record(root, None, create, target=target)

    assert _acceptance_files(root) == before
    assert (head(root), snapshot(root)) == (sha, files), "a refused drop must not commit or write"


def test_drops_with_a_run_id_are_refused(tmp_path: Path) -> None:
    from fr.record.apply import RecordRefusedError, RecordTarget, apply_record

    root = _matrix_repo(tmp_path)
    before, sha = snapshot(root), head(root)
    target = RecordTarget(acceptance_drops={"target": {"unit": ("own:tests/test_b.py",)}})

    with pytest.raises(RecordRefusedError, match="verb-only"):
        apply_record(root, "some-run", _move(), target=target)

    assert (head(root), snapshot(root)) == (sha, before)


@pytest.mark.parametrize("empty", [{}, {"unit": ()}], ids=["no-levels", "no-refs"])
def test_a_drop_entry_naming_no_refs_is_refused(tmp_path: Path, empty: dict) -> None:
    """p2-r2: a drop that names a row but no ref would remove nothing."""
    from fr.record.apply import RecordRefusedError, RecordTarget, apply_record

    root = _matrix_repo(tmp_path)
    sha, files = head(root), snapshot(root)
    target = RecordTarget(message="m", acceptance_drops={"target": empty})

    with pytest.raises(RecordRefusedError, match="no ref"):
        apply_record(root, None, _move(), target=target)

    assert (head(root), snapshot(root)) == (sha, files)


def test_a_drop_on_a_row_the_record_names_twice_is_refused(tmp_path: Path) -> None:
    """p2-r1: with two items for one id the drop's target is ambiguous — judged
    by position, a create-then-move would slip past the create refusal."""
    from fr.record.apply import RecordRefusedError, RecordTarget, apply_record
    from fr.record.model import AcceptanceItem, StepRecord

    root = _matrix_repo(tmp_path)
    sha, files = head(root), snapshot(root)
    item = AcceptanceItem.model_validate({"id": "target", "status": "skipped", "notes": "why"})
    target = RecordTarget(
        message="m", acceptance_drops={"target": {"unit": ("own:tests/test_b.py",)}}
    )

    with pytest.raises(RecordRefusedError, match="more than once"):
        apply_record(root, None, StepRecord(acceptance=(item, item)), target=target)

    assert (head(root), snapshot(root)) == (sha, files)
