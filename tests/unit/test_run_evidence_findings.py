"""The `findings` obligation — a review that raised findings is not done
until each is fixed or refuted.

PR #508 review: the shipped `review-phase` member named one skill,
`superpowers:requesting-code-review`. What happens to the findings a review
raises — `superpowers:receiving-code-review`: verify each, fix it with a test,
or refute it with reasoning, never drop it — lived in one parenthesis of skill
prose and was otherwise left to the implementing agent. `review` evidence
proves a review ENTRY exists; it says nothing about whether anything was done
with what the review found.

`findings` closes that, and it is enforced on the OUTCOME, because the outcome
is the only part of "was the review received properly" that fr can observe:

* it is **derived, never offered** — fr reads the plan journal itself at
  resolve time. An obligation satisfied by passing a flag is satisfied by
  anyone who can type the flag;
* it refuses `done` while any finding FILED AGAINST THIS PHASE is effectively
  open (the fold `fr journal check` uses — a resolution record closes, a later
  one can re-open);
* what it stores is the witness: the ids it saw closed, or `none`.

It moves a check that already existed — `journal-check`, once, before
`deliver` — to the moment the finding is cheapest to act on. It adds no member
step: drift compares member IDS, and a new one strands every cursor in flight.
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
from tests.unit.test_run_evidence import PLAN_SLUG, _shape

REVIEW = {"kind": "review", "id": "rev-p1", "phase": 1, "title": "phase 1 review"}


def _finding(fid: str, state: str, *, phase: int | None = 1) -> dict:
    return {"kind": "finding", "id": fid, "phase": phase, "state": state, "title": fid}


def _closes(fid: str, state: str, *, rid: str | None = None) -> dict:
    return {
        "kind": "finding",
        "id": rid or f"{fid}-res",
        "resolves": fid,
        "state": state,
        "title": f"{fid} -> {state}",
    }


def _findings_shape(declared: str = "[review, findings]") -> str:
    text = _shape(evidence=True)
    assert text.count("evidence: [review]") == 1
    return text.replace("evidence: [review]", f"evidence: {declared}")


def _at_the_review(
    tmp_path: Path, entries: list[dict], *, declared: str = "[review, findings]"
) -> tuple[Path, Path]:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _findings_shape(declared))
    _started_grouped_with_plan(repo, shipped)
    build_plan_journal(repo, PLAN_SLUG, entries)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    done = ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"]
    assert _invoke(repo, shipped, done).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    return repo, shipped


def _resolve(repo: Path, shipped: Path, *extra: str, state: str = "done"):
    base = ["run", "resolve", "r1", "--step", "peer-review", "--item", "phase/1"]
    return _invoke(repo, shipped, [*base, "--state", state, *extra])


def _unit(repo: Path):
    return load_run_state(repo, "r1").steps["implement"], "phase/1/peer-review"


# --- the refusal -----------------------------------------------------------


def test_an_open_finding_for_this_phase_refuses_done(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path, [REVIEW, _finding("f-a", "open")])

    result = _resolve(repo, shipped, "--evidence", "review=rev-p1")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "f-a" in out
    assert "still open" in out
    record, key = _unit(repo)
    assert units.unit_state(record, key) == "running"
    assert units.evidence_of(record, key) == {}


def test_the_refusal_names_every_open_finding_and_both_ways_to_close_one(
    tmp_path: Path,
) -> None:
    entries = [REVIEW, _finding("f-a", "open"), _finding("f-b", "fixed"), _finding("f-c", "open")]
    repo, shipped = _at_the_review(tmp_path, entries)

    out = _squash(_resolve(repo, shipped, "--evidence", "review=rev-p1").output)

    assert "f-a" in out and "f-c" in out
    assert "f-b" not in out
    assert f"fr journal resolve --scope plan --slug {PLAN_SLUG} --id f-a --state fixed" in out
    assert "--state refuted" in out
    # A pasteable line must not contain a shell metacharacter it does not mean.
    assert "fixed|refuted" not in out


def test_the_review_obligation_is_still_demanded_first(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path, [REVIEW, _finding("f-a", "open")])

    out = _squash(_resolve(repo, shipped).output)

    assert "--evidence review=" in out
    assert "--evidence findings=" not in out


# --- what closes it --------------------------------------------------------


def test_no_findings_at_all_resolves_and_records_none(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path, [REVIEW])

    result = _resolve(repo, shipped, "--evidence", "review=rev-p1")

    assert result.exit_code == 0, result.output
    record, key = _unit(repo)
    assert units.unit_state(record, key) == "done"
    assert units.evidence_of(record, key) == {"review": "rev-p1", "findings": "none"}


def test_findings_written_closed_are_the_witness(tmp_path: Path) -> None:
    entries = [REVIEW, _finding("f-a", "fixed"), _finding("f-b", "refuted")]
    repo, shipped = _at_the_review(tmp_path, entries)

    assert _resolve(repo, shipped, "--evidence", "review=rev-p1").exit_code == 0

    record, key = _unit(repo)
    assert units.evidence_of(record, key)["findings"] == "f-a,f-b"


def test_a_resolution_record_closes_it(tmp_path: Path) -> None:
    entries = [REVIEW, _finding("f-a", "open"), _closes("f-a", "fixed")]
    repo, shipped = _at_the_review(tmp_path, entries)

    assert _resolve(repo, shipped, "--evidence", "review=rev-p1").exit_code == 0

    record, key = _unit(repo)
    assert units.evidence_of(record, key)["findings"] == "f-a"


def test_a_finding_re_opened_by_a_later_record_is_open(tmp_path: Path) -> None:
    entries = [
        REVIEW,
        _finding("f-a", "open"),
        _closes("f-a", "fixed", rid="r1"),
        _closes("f-a", "open", rid="r2"),
    ]
    repo, shipped = _at_the_review(tmp_path, entries)

    result = _resolve(repo, shipped, "--evidence", "review=rev-p1")

    assert result.exit_code == 2, result.output
    assert "f-a" in _squash(result.output)


# --- scope: THIS phase's findings, nothing else ----------------------------


def test_another_phases_open_finding_does_not_block_this_one(tmp_path: Path) -> None:
    """Filing a finding against the phase that will fix it IS the deferral: it
    gates that phase's review instead of this one's."""
    entries = [REVIEW, _finding("f-later", "open", phase=2)]
    repo, shipped = _at_the_review(tmp_path, entries)

    assert _resolve(repo, shipped, "--evidence", "review=rev-p1").exit_code == 0

    record, key = _unit(repo)
    assert units.evidence_of(record, key)["findings"] == "none"


def test_a_global_open_finding_is_journal_checks_business_not_this_gates(
    tmp_path: Path,
) -> None:
    entries = [REVIEW, _finding("f-global", "open", phase=None)]
    repo, shipped = _at_the_review(tmp_path, entries)

    assert _resolve(repo, shipped, "--evidence", "review=rev-p1").exit_code == 0


# --- derived, never offered ------------------------------------------------


@pytest.mark.parametrize("value", ["none", "f-a", "anything"])
def test_offering_findings_is_refused_because_fr_derives_it(tmp_path: Path, value: str) -> None:
    repo, shipped = _at_the_review(tmp_path, [REVIEW])

    result = _resolve(
        repo, shipped, "--evidence", "review=rev-p1", "--evidence", f"findings={value}"
    )

    assert result.exit_code == 2, result.output
    assert "derives" in _squash(result.output)
    record, key = _unit(repo)
    assert units.unit_state(record, key) == "running"


def test_failed_needs_nothing_and_records_no_findings_witness(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path, [REVIEW, _finding("f-a", "open")])

    result = _resolve(repo, shipped, state="failed")

    assert result.exit_code == 0, result.output
    record, key = _unit(repo)
    assert units.unit_state(record, key) == "failed"
    assert units.evidence_of(record, key) == {}


def test_findings_alone_is_a_legal_declaration(tmp_path: Path) -> None:
    """A shape may want the outcome gate without the review-entry one."""
    repo, shipped = _at_the_review(tmp_path, [_finding("f-a", "fixed")], declared="[findings]")

    assert _resolve(repo, shipped).exit_code == 0

    record, key = _unit(repo)
    assert units.evidence_of(record, key) == {"findings": "f-a"}


def test_an_unknown_obligation_is_still_refused_as_unverifiable(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path, [REVIEW], declared="[review, findings, sniff]")

    result = _resolve(repo, shipped, "--evidence", "review=rev-p1")

    assert result.exit_code == 2, result.output
    assert "cannot verify 'sniff'" in _squash(result.output)


# --- debt: a unit resolved before `findings` was declared ------------------


def _resolved_under_review_only(tmp_path: Path) -> tuple[Path, Path]:
    """`phase/1/peer-review` done with `review=` under `[review]`; then the
    shape grows `findings` — what a plugin update does to a run in flight."""
    repo, shipped = _at_the_review(tmp_path, [REVIEW], declared="[review]")
    assert _resolve(repo, shipped, "--evidence", "review=rev-p1").exit_code == 0
    _write_shape(shipped, "grouped", _findings_shape())
    return repo, shipped


def test_growing_the_obligation_does_not_strand_the_cursor(tmp_path: Path) -> None:
    repo, shipped = _resolved_under_review_only(tmp_path)

    result = _invoke(repo, shipped, ["run", "advance", "r1"])

    assert result.exit_code == 0, result.output
    assert "drift" not in _squash(result.output).lower()


def test_a_unit_missing_only_findings_is_named_debt_and_check_exits_zero(
    tmp_path: Path,
) -> None:
    repo, shipped = _resolved_under_review_only(tmp_path)

    result = _invoke(repo, shipped, ["run", "check", "r1"])

    assert result.exit_code == 0, result.output
    out = _squash(result.output)
    assert "phase/1/peer-review is done, unevidenced: findings" in out


def test_status_shows_the_evidence_it_has_and_the_obligation_it_lacks(tmp_path: Path) -> None:
    repo, shipped = _resolved_under_review_only(tmp_path)

    out = _squash(_invoke(repo, shipped, ["run", "status", "r1"]).output)

    assert "evidence: review=rev-p1" in out
    assert "unevidenced: findings" in out


def test_an_out_of_scope_finding_does_not_hold_the_review(tmp_path: Path) -> None:
    """Spec 2026-09-24 §A: true, but not this change's — the gate passes and
    the witness still names it, so nothing was dropped silently."""
    record_oos = {**_closes("f-a", "open"), "out_of_scope": True}
    entries = [REVIEW, _finding("f-a", "open"), record_oos]
    repo, shipped = _at_the_review(tmp_path, entries)

    result = _resolve(repo, shipped, "--evidence", "review=rev-p1")

    assert result.exit_code == 0, result.output
    record, key = _unit(repo)
    assert units.evidence_of(record, key)["findings"] == "f-a"


def test_an_unauthorized_fix_of_an_out_of_scope_finding_refuses_done(tmp_path: Path) -> None:
    """The review-phase gate reads the same operator guard `fr journal check`
    does, so neither can pass what the other refuses."""
    record_oos = {**_closes("f-a", "open"), "out_of_scope": True}
    fixed = _closes("f-a", "fixed", rid="f-a-fix")
    entries = [REVIEW, _finding("f-a", "open"), record_oos, fixed]
    repo, shipped = _at_the_review(tmp_path, entries)

    result = _resolve(repo, shipped, "--evidence", "review=rev-p1")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "unauthorized fix" in out and "f-a" in out
    record, key = _unit(repo)
    assert units.unit_state(record, key) == "running"


def test_an_operator_authorized_fix_of_an_out_of_scope_finding_resolves(tmp_path: Path) -> None:
    record_oos = {**_closes("f-a", "open"), "out_of_scope": True}
    fixed = {**_closes("f-a", "fixed", rid="f-a-fix"), "answered_by": "operator"}
    entries = [REVIEW, _finding("f-a", "open"), record_oos, fixed]
    repo, shipped = _at_the_review(tmp_path, entries)

    assert _resolve(repo, shipped, "--evidence", "review=rev-p1").exit_code == 0
