"""The evidence gate — a `review` unit cannot reach `done` without proof.

Spec `2026-09-20-unit-record-unification-design.md` §4.E, phase 5. The defect
this closes is gh#430: `review-phase` is a `kind: agent` step, so an agent that
skipped the review entirely resolved it *identically* to one that did the work.
"Review skipped" and "review passed clean" were the same state on the cursor.

After this, they are different states: `done` WITH evidence, versus a unit that
cannot reach `done` at all.

The rule the gate applies is gh#517's own (`fr.journal.model.reviews_phase`,
which `reviewed_phases` is built from) — a `kind=review` entry carrying
`phase=N`. Two gates (`fr journal check --require-reviews` for plans with no
cursor, `fr run resolve` for those with one), ONE rule, ONE verifier: any other
arrangement means a finding, or another phase's review, satisfies one gate and
not the other.

Three invariants this file exists to hold:

1. **A shape declaring no `evidence:` resolves exactly as before** — the gate
   is opt-in per step, so a consumer repo's own workflow is untouched.
2. **Reviews from before the gate are debt, never failures.** The migration
   cannot invent evidence and does not try; `fr run check` reports them and its
   EXIT CODE IS UNCHANGED (asserted literally, both ways).
3. **Manifest drift does not trip on a new FIELD.** Drift compares step and
   member IDS. A cursor in flight when the shipped shape grows `evidence:` must
   keep advancing — this branch already lost a cursor to drift once, when a
   whole new STEP was added, and a field must not repeat it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run import units
from fr.run.model import load_run_state
from fr.test_support import build_plan_journal

from tests.unit.test_run_cli import (
    _invoke,
    _repo,
    _squash,
    _started_grouped_with_plan,
    _write_shape,
)

PLAN_SLUG = "2026-05-09-fixture-minimal"


def _shape(*, evidence: bool, deliver: str = "true") -> str:
    """The grouped shape of `test_run_cli.py`, with or without an `evidence:`
    declaration on its review member — the SAME step and member ids either
    way, so the pair is exactly "one optional field appeared"."""
    review_extra = "        evidence: [review]\n" if evidence else ""
    return f"""
workflow: grouped
schema: 1
unit: run
steps:
  - id: plan
    kind: agent
    emits: [plan]
  - id: implement
    kind: agent
    needs: [plan]
    for_each: phase
    emits: [journal:plan]
    steps:
      - id: code
        kind: agent
        needs: [plan]
        emits: [journal:plan]
      - id: peer-review
        kind: agent
        needs: [journal:plan]
        emits: [journal:plan]
{review_extra}  - id: deliver
    kind: cli
    run: "{deliver}"
    needs: [journal:plan]
"""


def _journal(repo: Path) -> Path:
    """A plan journal carrying one real review of phase 1, one review of
    phase 2, and one finding tagged phase 1 — the three shapes the verifier
    has to tell apart."""
    return build_plan_journal(
        repo,
        PLAN_SLUG,
        [
            {"kind": "review", "id": "rev-p1", "phase": 1, "title": "phase 1 review"},
            {"kind": "review", "id": "rev-p2", "phase": 2, "title": "phase 2 review"},
            {
                "kind": "finding",
                "id": "f-p1",
                "phase": 1,
                "state": "open",
                "title": "a finding raised during phase 1",
            },
        ],
    )


def _at_the_review(tmp_path: Path, *, evidence: bool, deliver: str = "true") -> tuple[Path, Path]:
    """A run parked with `phase/1/peer-review` dispatched and running."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _shape(evidence=evidence, deliver=deliver))
    _started_grouped_with_plan(repo, shipped)
    _journal(repo)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0  # code
    assert (
        _invoke(
            repo,
            shipped,
            ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"],
        ).exit_code
        == 0
    )
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0  # peer-review
    return repo, shipped


def _resolve_review(repo: Path, shipped: Path, *extra: str, state: str = "done"):
    return _invoke(
        repo,
        shipped,
        [
            "run",
            "resolve",
            "r1",
            "--step",
            "peer-review",
            "--item",
            "phase/1",
            "--state",
            state,
            *extra,
        ],
    )


def _review_unit(repo: Path):
    record = load_run_state(repo, "r1").steps["implement"]
    return record, "phase/1/peer-review"


# --- the field itself ------------------------------------------------------


def test_step_evidence_parses_and_defaults_to_empty() -> None:
    from fr.workflow.model import parse_manifest

    manifest = parse_manifest(_shape(evidence=True))
    implement = next(s for s in manifest.steps if s.id == "implement")
    review = next(m for m in implement.steps if m.id == "peer-review")
    code = next(m for m in implement.steps if m.id == "code")
    assert review.evidence == ("review",)
    assert code.evidence == ()
    assert implement.evidence == ()


# --- `workflow-without-evidence-unchanged` ---------------------------------


def test_a_shape_declaring_no_evidence_resolves_exactly_as_before(tmp_path: Path) -> None:
    """The gate is opt-in per step. A repo-authored workflow that never asks
    for evidence must not acquire a new refusal — so the bare resolve that
    worked before this phase still works, and records no evidence."""
    repo, shipped = _at_the_review(tmp_path, evidence=False)

    result = _resolve_review(repo, shipped)

    assert result.exit_code == 0, result.output
    record, key = _review_unit(repo)
    assert units.unit_state(record, key) == "done"
    assert units.evidence_of(record, key) == {}


def test_evidence_offered_to_a_step_that_declares_none_is_refused(tmp_path: Path) -> None:
    """Symmetric with `--emitted` on a non-emitting step: recorded silently,
    it would read as a verified obligation the shape never asked for."""
    repo, shipped = _at_the_review(tmp_path, evidence=False)

    result = _resolve_review(repo, shipped, "--evidence", "review=rev-p1")

    assert result.exit_code == 2, result.output
    assert "declares no evidence" in _squash(result.output)


# --- `run-unit-review-evidence` --------------------------------------------


def test_resolve_done_refuses_without_evidence_and_names_the_flag(tmp_path: Path) -> None:
    """gh#430, closed: the skipped review can no longer reach `done`."""
    repo, shipped = _at_the_review(tmp_path, evidence=True)

    result = _resolve_review(repo, shipped)

    assert result.exit_code == 2, result.output
    squashed = _squash(result.output)
    assert "--evidence review=<journal-entry-id>" in squashed
    # And it wrote NOTHING: the unit is still running, not half-resolved.
    record, key = _review_unit(repo)
    assert units.unit_state(record, key) == "running"


def test_a_real_review_is_accepted_and_stored_on_the_unit(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path, evidence=True)

    result = _resolve_review(repo, shipped, "--evidence", "review=rev-p1")

    assert result.exit_code == 0, result.output
    record, key = _review_unit(repo)
    assert units.unit_state(record, key) == "done"
    assert units.evidence_of(record, key) == {"review": "rev-p1"}


def test_failed_needs_no_evidence(tmp_path: Path) -> None:
    """A failed review unit met no obligation — there is nothing to evidence."""
    repo, shipped = _at_the_review(tmp_path, evidence=True)

    result = _resolve_review(repo, shipped, state="failed")

    assert result.exit_code == 0, result.output
    record, key = _review_unit(repo)
    assert units.unit_state(record, key) == "failed"
    assert units.evidence_of(record, key) == {}


# --- `run-review-evidence-cannot-be-faked` ---------------------------------


def test_a_finding_entry_is_not_evidence_of_a_review(tmp_path: Path) -> None:
    """`f-p1` carries `phase=1` and was written during phase 1. It is still
    not a review — the same narrowing `reviewed_phases` already applies."""
    repo, shipped = _at_the_review(tmp_path, evidence=True)

    result = _resolve_review(repo, shipped, "--evidence", "review=f-p1")

    assert result.exit_code == 2, result.output
    squashed = _squash(result.output)
    assert "f-p1" in squashed
    assert "kind=review" in squashed
    record, key = _review_unit(repo)
    assert units.unit_state(record, key) == "running"


def test_another_phases_review_is_not_evidence(tmp_path: Path) -> None:
    """Otherwise ONE review would satisfy every phase a plan ever grows —
    the exact hole `--require-reviews` exists to close."""
    repo, shipped = _at_the_review(tmp_path, evidence=True)

    result = _resolve_review(repo, shipped, "--evidence", "review=rev-p2")

    assert result.exit_code == 2, result.output
    assert "rev-p2" in _squash(result.output)


def test_an_id_no_journal_entry_carries_is_refused_naming_the_journal(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path, evidence=True)

    result = _resolve_review(repo, shipped, "--evidence", "review=no-such-entry")

    assert result.exit_code == 2, result.output
    squashed = _squash(result.output)
    assert "no-such-entry" in squashed
    assert PLAN_SLUG in squashed


def test_an_obligation_the_step_never_declared_is_refused(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path, evidence=True)

    result = _resolve_review(
        repo, shipped, "--evidence", "review=rev-p1", "--evidence", "vibes=rev-p1"
    )

    assert result.exit_code == 2, result.output
    assert "vibes" in _squash(result.output)


@pytest.mark.parametrize("pair", ["review", "=rev-p1", "review="])
def test_a_malformed_evidence_pair_is_refused(tmp_path: Path, pair: str) -> None:
    repo, shipped = _at_the_review(tmp_path, evidence=True)

    result = _resolve_review(repo, shipped, "--evidence", pair)

    assert result.exit_code == 2, result.output
    assert "--evidence" in _squash(result.output)


def test_the_same_obligation_given_twice_is_refused(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path, evidence=True)

    result = _resolve_review(
        repo, shipped, "--evidence", "review=rev-p1", "--evidence", "review=rev-p2"
    )

    assert result.exit_code == 2, result.output
    assert "twice" in _squash(result.output)


def test_a_flat_step_declaring_evidence_is_refused_rather_than_recorded(tmp_path: Path) -> None:
    """Fail-closed. `review` evidence is verified against a PHASE, and a flat
    `step/<id>` unit names none — so fr says it cannot verify rather than
    storing an id nothing checked."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(
        shipped,
        "flat",
        """
workflow: flat
schema: 1
unit: spec
steps:
  - id: audit
    kind: agent
    needs: [spec]
    evidence: [review]
""",
    )
    _invoke(repo, shipped, ["run", "start", "flat", "--branch", "b", "--run-id", "r1"])
    _invoke(repo, shipped, ["run", "advance", "r1"])

    result = _invoke(repo, shipped, ["run", "resolve", "r1", "--step", "audit", "--state", "done"])

    assert result.exit_code == 2, result.output
    assert "cannot verify" in _squash(result.output)


# --- manifest drift: a FIELD is not a step ---------------------------------


def test_adding_evidence_to_a_member_does_not_strand_an_in_flight_cursor(
    tmp_path: Path,
) -> None:
    """The hazard this phase had to prove it avoids.

    Drift compares step and member IDS, not fields. A run started against the
    shape WITHOUT `evidence:` keeps advancing after the shipped shape grows it
    — and the very next review it resolves DOES need evidence, which is spec
    §4.I's "reviews still to come in that same run do need evidence".
    """
    repo, shipped = _at_the_review(tmp_path, evidence=False)

    # The plugin updates underneath the run: same ids, one new field.
    _write_shape(shipped, "grouped", _shape(evidence=True))

    bare = _resolve_review(repo, shipped)
    assert bare.exit_code == 2, bare.output
    squashed = _squash(bare.output)
    assert "different version" not in squashed  # NOT a drift refusal
    assert "--evidence review=<journal-entry-id>" in squashed

    evidenced = _resolve_review(repo, shipped, "--evidence", "review=rev-p1")
    assert evidenced.exit_code == 0, evidenced.output
    record, key = _review_unit(repo)
    assert units.evidence_of(record, key) == {"review": "rev-p1"}


# --- `run-legacy-reviews-not-retro-failed` ---------------------------------


def _pre_gate_cursor(tmp_path: Path, *, deliver: str = "true") -> tuple[Path, Path]:
    """A cursor whose review unit reached `done` BEFORE the gate existed —
    built the only honest way, by resolving it against the shape that had no
    `evidence:` and then updating the shape underneath it."""
    repo, shipped = _at_the_review(tmp_path, evidence=False, deliver=deliver)
    assert _resolve_review(repo, shipped).exit_code == 0
    _write_shape(shipped, "grouped", _shape(evidence=True, deliver=deliver))
    return repo, shipped


def test_a_pre_gate_review_is_reported_as_debt_and_check_still_exits_zero(
    tmp_path: Path,
) -> None:
    repo, shipped = _pre_gate_cursor(tmp_path)

    result = _invoke(repo, shipped, ["run", "check", "r1"])

    assert result.exit_code == 0, result.output
    assert (
        "implement: phase/1/peer-review is done, unevidenced (predates the evidence gate)"
        in _squash(result.output)
    )


def test_the_check_exit_code_is_unchanged_by_unevidenced_units(tmp_path: Path) -> None:
    """Asserted as a literal, both ways: `check` is a narrow freshness gate,
    and debt must not move its verdict in either direction. A failed cursor
    still exits 1 while carrying the same unevidenced line."""
    # `deliver` fails, so the cursor sits on a failed step while the
    # unevidenced review is still on the record.
    repo, shipped = _pre_gate_cursor(tmp_path, deliver="false")
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 1

    result = _invoke(repo, shipped, ["run", "check", "r1"])

    assert result.exit_code == 1, result.output
    assert "unevidenced (predates the evidence gate)" in _squash(result.output)


def test_status_shows_the_debt_and_the_evidence(tmp_path: Path) -> None:
    repo, shipped = _pre_gate_cursor(tmp_path)

    debt = _invoke(repo, shipped, ["run", "status", "r1"])
    assert debt.exit_code == 0, debt.output
    assert "unevidenced (predates the evidence gate)" in _squash(debt.output)

    # And a unit that DOES carry evidence names it.
    repo2, shipped2 = _at_the_review(tmp_path / "second", evidence=True)
    assert _resolve_review(repo2, shipped2, "--evidence", "review=rev-p1").exit_code == 0
    shown = _invoke(repo2, shipped2, ["run", "status", "r1"])
    assert shown.exit_code == 0, shown.output
    assert "evidence: review=rev-p1" in _squash(shown.output)


def test_a_migrated_real_cursor_reports_its_pre_gate_reviews_as_debt(tmp_path: Path) -> None:
    """End to end on the REAL captured cursor of this very feature's run,
    which carries `phase/1/review-phase: done` and `phase/2/review-phase:
    done` with no evidence — exactly spec §4.I's upgrade day.

    The shape is the SHIPPED `fr-goal`, which after this phase declares
    `evidence: [review]` on `review-phase`. Nothing invents evidence for
    those two, `check` names both, and its exit code is 0.
    """
    from tests.unit.test_run_upgrade_in_flight import HELD, _in_flight, _migrate

    repo, shipped, run_id = _in_flight(tmp_path, HELD)
    _migrate(repo)

    result = _invoke(repo, shipped, ["run", "check", run_id])

    assert result.exit_code == 0, result.output
    squashed = _squash(result.output)
    for n in (1, 2):
        assert (
            f"implement: phase/{n}/review-phase is done, unevidenced "
            "(predates the evidence gate)" in squashed
        )
