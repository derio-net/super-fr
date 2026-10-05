"""Historical review evidence — spec 2026-10-05-run-upgrade-midflight §D (R7, R9).

A run started on an older `fr` and finished after an upgrade has its phases
reviewed BEFORE the cursor that now holds them existed: the reviewer's dispatch
is in a transcript this cursor never opened. `reviewer=historical` is the one
reserved value that says so, and it is accepted only inside the bound:

1. the `review` entry predates this cursor (`created < started`);
2. it postdates the latest `returned` of this phase's implement member, when
   this cursor holds one (a review follows the work it reviews);
3. the phase owes no `visual` evidence (a historical reviewer opened no
   screenshots fr can read).

It is never accepted on a flat (spec-review) unit. Every other reviewer value
keeps every existing check — `test_run_evidence_separate_context.py` pins those.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fr.run import units
from fr.run.model import load_run_state, save_run_state
from fr.test_support import build_plan_journal

from tests.unit.test_run_cli import (
    _invoke,
    _repo,
    _squash,
    _started_grouped_with_plan,
    _write_shape,
)
from tests.unit.test_run_evidence import PLAN_SLUG

_SHAPE = """
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
        agent: super-fr:fr-phase-executor
        needs: [plan]
        emits: [journal:plan]
      - id: peer-review
        kind: agent
        needs: [journal:plan]
        emits: [journal:plan]
        evidence: [review, reviewer, findings]
  - id: deliver
    kind: agent
    needs: [journal:plan]
"""

_HOUR = timedelta(hours=1)


def _stamp(at: datetime) -> str:
    return at.replace(microsecond=0).isoformat()


def _at_the_review(
    tmp_path: Path,
    *,
    started_in: timedelta = 2 * _HOUR,
    review_at: timedelta | None = None,
    extra: list[dict[str, object]] | None = None,
    visual_row: bool = False,
) -> tuple[Path, Path]:
    """`phase/1/peer-review` opened after `code` returned, with the cursor's
    `started` moved `started_in` past now — the shape a superseded cursor has:
    its implement attempt (carried from the old cursor) returned before this
    cursor started. The plan journal holds `rev-h`, a phase-1 review created
    `review_at` from now (default: halfway to `started`)."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _SHAPE)
    _started_grouped_with_plan(repo, shipped)
    if visual_row:
        _link_visual_row(repo)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    code = ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"]
    assert _invoke(repo, shipped, [*code, "--agent", "impl-1"]).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    now = datetime.now(UTC)
    state = load_run_state(repo, "r1")
    save_run_state(repo, state.model_copy(update={"started": _stamp(now + started_in)}))
    at = now + (review_at if review_at is not None else started_in / 2)
    build_plan_journal(
        repo,
        PLAN_SLUG,
        [
            {"kind": "review", "id": "rev-h", "phase": 1, "title": "p1", "created": _stamp(at)},
            *(extra or []),
        ],
    )
    return repo, shipped


def _link_visual_row(repo: Path) -> None:
    """Phase 1 links an acceptance row that carries `visual`."""
    from tests.unit.requirements_support import row, write_matrix

    phase = repo / "docs" / "superpowers" / "plans" / PLAN_SLUG / "01.yaml"
    lines = phase.read_text().split("\n")
    lines.insert(lines.index("  tag: agentic") + 1, "  acceptance:\n    - ui-row")
    phase.write_text("\n".join(lines))
    out = row("docs/superpowers/specs/x.md", rid="ui-row", status="ci")
    out["visual"] = {"states": ["accepted"], "interactions": ["20 cap"]}
    write_matrix(repo, [out])


def _review(repo: Path, shipped: Path, *evidence: str):
    argv = ["run", "resolve", "r1", "--step", "peer-review", "--item", "phase/1"]
    extra = [x for e in evidence for x in ("--evidence", e)]
    return _invoke(repo, shipped, [*argv, "--state", "done", *extra])


def _evidence(repo: Path) -> dict[str, str]:
    record = load_run_state(repo, "r1").steps["implement"]
    return units.evidence_of(record, "phase/1/peer-review")


# --- R7: by hand ---------------------------------------------------------------


def test_a_review_between_the_implement_return_and_started_is_accepted(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path)

    result = _review(repo, shipped, "review=rev-h", "reviewer=historical")

    assert result.exit_code == 0, result.output
    assert _evidence(repo) == {"review": "rev-h", "reviewer": "historical", "findings": "none"}
    assert "unobserved" not in _squash(result.output)


def test_a_review_created_after_the_run_started_is_refused(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path, review_at=3 * _HOUR)

    result = _review(repo, shipped, "review=rev-h", "reviewer=historical")

    assert result.exit_code == 2, result.output
    assert "not before this run started" in _squash(result.output)
    assert _evidence(repo) == {}


def test_a_review_created_before_the_implement_return_is_refused(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path, review_at=-_HOUR)

    result = _review(repo, shipped, "review=rev-h", "reviewer=historical")

    assert result.exit_code == 2, result.output
    assert "before phase 1's implementation last returned" in _squash(result.output)


def test_a_phase_owing_visual_evidence_is_refused(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path, visual_row=True)

    result = _review(repo, shipped, "review=rev-h", "reviewer=historical")

    assert result.exit_code == 2, result.output
    assert "phase 1 owes `visual` evidence" in _squash(result.output)


def test_the_findings_gate_still_applies(tmp_path: Path) -> None:
    open_finding = {"kind": "finding", "id": "f-1", "phase": 1, "state": "open", "title": "f"}
    repo, shipped = _at_the_review(tmp_path, extra=[open_finding])

    result = _review(repo, shipped, "review=rev-h", "reviewer=historical")

    assert result.exit_code == 2, result.output
    assert "still open: f-1" in _squash(result.output)


def test_the_review_entry_check_still_applies(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path)

    result = _review(repo, shipped, "review=no-such-entry", "reviewer=historical")

    assert result.exit_code == 2, result.output
    assert "names no entry" in _squash(result.output)


def test_historical_is_refused_on_a_flat_spec_review_unit(tmp_path: Path) -> None:
    from tests.unit.test_run_evidence_separate_context import (
        _REVIEW,
        _at_the_spec_review,
        _spec_journal,
        _spec_review,
    )

    repo, shipped, _ = _at_the_spec_review(tmp_path)
    _spec_journal(repo, _REVIEW)

    result = _spec_review(repo, shipped, None, "s-x", "review=sr-1", "reviewer=historical")

    assert result.exit_code == 2, result.output
    assert "reviewer=historical is accepted only on a phase review unit" in _squash(result.output)


# --- R9: reported as historical, never as debt ---------------------------------

_SENTENCE = "reviewed before this cursor existed (journal rev-h) — reviewer not observed"


def test_status_and_check_say_a_review_is_historical(tmp_path: Path) -> None:
    repo, shipped = _at_the_review(tmp_path)
    assert _review(repo, shipped, "review=rev-h", "reviewer=historical").exit_code == 0

    status = _invoke(repo, shipped, ["run", "status", "r1"])
    check = _invoke(repo, shipped, ["run", "check", "r1"])

    assert _SENTENCE in _squash(status.output), status.output
    assert _SENTENCE in _squash(check.output), check.output


def test_an_adopted_historical_review_is_not_debt(tmp_path: Path, repo_root: Path) -> None:
    """The shipped `fr-goal` review member also declares `visual`, which an
    inferred historical unit does not carry: that is not debt (R9)."""
    from fr.test_support import build_plan_journal

    from tests.unit import test_run_adopt as adopt

    repo, shipped = adopt._repo(tmp_path, repo_root)
    adopt._write_spec(repo)
    plan_dir = adopt._write_plan(repo, phases=1, complete=1)
    build_plan_journal(
        repo, adopt.PLAN_SLUG, [{"kind": "review", "id": "rev-h", "phase": 1, "title": "r"}]
    )
    state = adopt.adopt_run(repo, plan_dir, branch=adopt.BRANCH, shipped_root=shipped)

    status = adopt._invoke(repo, shipped, ["run", "status", state.run])
    check = adopt._invoke(repo, shipped, ["run", "check", state.run])

    for out in (status.output, check.output):
        assert _SENTENCE in _squash(out), out
    # The implement member's own adopted debt is not this test's subject.
    review_block = status.output.split("phase/1/review-phase")[1].split("journal-check")[0]
    assert "unevidenced" not in review_block, status.output
    assert "review-phase is done, unevidenced" not in check.output, check.output
