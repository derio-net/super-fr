"""The `fidelity` derived evidence on spec-review (spec
`2026-09-29-spec-fidelity-invention-design.md` §C, §D, §H; Test Plan 3, 7).

Derived by `fr run resolve` from the `requirement-fidelity` and
`design-inventory` blocks of the review entry `review` names, never passed.
A finding a flagged fidelity row or an `invented` inventory row names closes
only `fixed` or `refuted` (d1-remove-only).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.commands import run_cmd
from fr.requirements import REQUIREMENTS_PREDATES
from fr.run.model import load_run_state

from tests.unit.requirements_support import (
    COVERAGE_BLOCK,
    DESIGN_SECTION,
    FIDELITY_BLOCK,
    INVENTORY_BLOCK,
    REQUIREMENTS_SECTION,
    REVIEW_BLOCKS,
    seed_requirements,
)
from tests.unit.test_run_cli import _invoke, _squash
from tests.unit.test_run_evidence_requirements import (
    SLUG,
    SPEC,
    _brainstorm,
    _commit,
    _evidence,
    _record,
    _resolve_record,
    _review_entry,
    _spec,
    _spec_finding,
    _spec_review,
    _started,
)

_WITH_FIDELITY = "[review, reviewer, findings, requirements, coverage, fidelity]"


def _at_spec_review(tmp_path: Path) -> tuple[Path, Path]:
    repo, shipped = _started(tmp_path, spec_review=_WITH_FIDELITY)
    _spec(repo, DESIGN_SECTION + REQUIREMENTS_SECTION)
    seed_requirements(repo, SPEC)
    assert _brainstorm(repo, shipped).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    return repo, shipped


def _close(repo: Path, shipped: Path, fid: str, state: str) -> None:
    argv = ["journal", "resolve", "--id", fid, "--scope", "spec", "--slug", SLUG, "--state", state,
            "--note", f"closed {state}"]  # fmt: skip
    if state == "deferred":
        argv += ["--tracked-by", "#1"]
    out = _invoke(repo, shipped, argv)
    assert out.exit_code == 0, out.output


def test_fidelity_is_in_every_table_a_derived_evidence_name_needs() -> None:
    assert "fidelity" in run_cmd._VERIFIABLE_EVIDENCE
    assert "fidelity" in run_cmd._DERIVED_EVIDENCE
    assert run_cmd._DERIVED_FROM["fidelity"].startswith("from ")
    assert "fidelity" in run_cmd._REQUIREMENTS_EVIDENCE


def test_spec_review_refuses_a_review_without_the_blocks(tmp_path: Path) -> None:
    repo, shipped = _at_spec_review(tmp_path)
    _review_entry(repo, body="no findings\n\n" + COVERAGE_BLOCK)

    out = _spec_review(repo, shipped)

    assert out.exit_code == 2, out.output
    text = _squash(out.output)
    assert "fidelity" in text
    assert "requirement-fidelity" in text and "design-inventory" in text
    assert "re-dispatch the reviewer" in text
    assert load_run_state(repo, "r1").steps["spec-review"].state != "done"


def test_spec_review_records_the_fidelity_summary(tmp_path: Path) -> None:
    repo, shipped = _at_spec_review(tmp_path)
    _review_entry(repo, body="no findings\n\n" + REVIEW_BLOCKS)

    out = _spec_review(repo, shipped)

    assert out.exit_code == 0, out.output
    assert _evidence(repo, "spec-review")["fidelity"] == (
        "1 clauses over 1 requirements (kept=1 flagged=0); 1 sections, 1 behaviours (invented=0)"
    )


_INVENTED = (
    COVERAGE_BLOCK
    + FIDELITY_BLOCK
    + INVENTORY_BLOCK.replace(
        "| A. Widget | the widget counts | R1 |",
        "| A. Widget | the widget counts | R1 |\n| A. Widget | a card click | invented s7 |",
    )
)
_FLAGGED = COVERAGE_BLOCK + FIDELITY_BLOCK.replace("| kept |", "| s7 |") + INVENTORY_BLOCK


@pytest.mark.parametrize("body", [_INVENTED, _FLAGGED], ids=["invented", "reinterpreted"])
@pytest.mark.parametrize("state", ["out-of-scope", "deferred"])
def test_a_departure_closed_other_than_fixed_or_refuted_is_refused(
    tmp_path: Path, body: str, state: str
) -> None:
    repo, shipped = _at_spec_review(tmp_path)
    _spec_finding(repo, "s7")
    _close(repo, shipped, "s7", state)
    _review_entry(repo, body=body)

    out = _spec_review(repo, shipped)

    assert out.exit_code == 2, out.output
    text = _squash(out.output)
    assert "s7" in text
    assert f"fr journal resolve --scope spec --slug {SLUG} --id s7 --state fixed" in text
    assert load_run_state(repo, "r1").steps["spec-review"].state != "done"


@pytest.mark.parametrize("body", [_INVENTED, _FLAGGED], ids=["invented", "reinterpreted"])
@pytest.mark.parametrize("state", ["fixed", "refuted"])
def test_a_departure_removed_or_refuted_passes(tmp_path: Path, body: str, state: str) -> None:
    repo, shipped = _at_spec_review(tmp_path)
    _spec_finding(repo, "s7")
    _close(repo, shipped, "s7", state)
    _review_entry(repo, body=body)

    out = _spec_review(repo, shipped)

    assert out.exit_code == 0, out.output
    assert "invented=" in _evidence(repo, "spec-review")["fidelity"]


def test_a_record_resolving_the_departure_fixed_in_the_same_resolve_passes(
    tmp_path: Path,
) -> None:
    """§D reads the spec journal as the record leaves it: the record's own
    `resolves` close the finding its own review raised."""
    repo, shipped = _at_spec_review(tmp_path)
    _commit(repo)
    record = _record(
        repo,
        {
            "step": "spec-review",
            "journal": [
                {"kind": "finding", "id": "s7", "title": "invented card click",
                 "body": "no requirement backs it", "review_scope": "in"},
                {"kind": "review", "id": "sr-1", "title": "spec review", "body": _INVENTED},
            ],
            "resolves": [{"id": "s7", "state": "fixed", "body": "removed from Design"}],
            "evidence": {"review": "sr-1", "reviewer": "rv-1"},
        },
    )  # fmt: skip

    out = _resolve_record(repo, shipped, "spec-review", record)

    assert out.exit_code == 0, out.output
    assert _evidence(repo, "spec-review")["fidelity"].endswith("(invented=1)")


def test_a_run_predating_the_requirements_gate_records_the_predates_line(
    tmp_path: Path,
) -> None:
    repo, shipped = _started(tmp_path, brainstorm="[]", spec_review="[requirements, fidelity]")
    _spec(repo, "\n## Design\n\nno requirements here\n")
    assert _brainstorm(repo, shipped).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0

    out = _invoke(
        repo, shipped, ["run", "resolve", "r1", "--step", "spec-review", "--state", "done"]
    )

    assert out.exit_code == 0, out.output
    assert _evidence(repo, "spec-review")["fidelity"] == REQUIREMENTS_PREDATES


def test_a_caller_supplied_fidelity_is_refused_as_derived(tmp_path: Path) -> None:
    repo, shipped = _at_spec_review(tmp_path)
    _review_entry(repo, body=REVIEW_BLOCKS)

    out = _spec_review(repo, shipped, "--evidence", "fidelity=1 clauses")

    assert out.exit_code == 2, out.output
    assert "fidelity" in _squash(out.output)
