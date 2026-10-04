"""The review-phase reviewer-return check at resolve (spec
2026-10-02-opencode-observe-2 §E, R7/R8): every `review-findings` id a phase
reviewer RETURNED must be a plan-journal finding against the phase with the
reviewer's scope tag — on every harness whose return fr can read: OpenCode's
child sessions (the committed run-tree fixture, moved to the unit's clock) and
a Claude Code transcript alike.

A reviewer is a child named in the record's `reviewer` evidence, or one whose
return carries the fence. Any other child — a helper the orchestrator
dispatched while receiving the review — owes nothing.

In the fixture's window: ses_gen1 (`general`) returns a block with p2a-r1 (in)
and p2a-r2 (out); ses_gen2 (`general`) returns prose and no block; ses_exec
(the phase executor) is still running."""

from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from fr.run import units
from fr.run.model import load_run_state
from fr.run.telemetry import parse_timestamp

from tests.unit.opencode_fixture import opencode_env, shifted, with_copied_child, with_resumed_child
from tests.unit.test_run_cli import _invoke_as_harness, _invoke_measurable, _squash
from tests.unit.test_run_evidence_separate_context import _later
from tests.unit.transcript_sessions import (
    AGENT_ID,
    TOOL_USE_ID,
    agent_result_row,
    dispatched_at,
)

_PHASE_SHAPE = """
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
PLAN = "2026-05-09-two-phases"
_REVIEW_ARGV = ["run", "resolve", "r1", "--step", "peer-review", "--item"]


def _plan_journal(repo: Path, *entries: dict[str, object]) -> None:
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path

    from tests.unit.requirements_support import now

    for e in entries:
        append_journal_entry(
            journal_path(repo, "plan", PLAN),
            PLAN,
            JournalEntry(scope="plan", created=now(), **e),  # type: ignore[arg-type]
        )


def _two_phase_plan(repo: Path) -> str:
    import shutil

    from tests.unit.test_run_cli import _FIXTURE_PLAN

    plan_dir = repo / "docs" / "superpowers" / "plans" / PLAN
    shutil.copytree(_FIXTURE_PLAN, plan_dir)
    meta = plan_dir / "_meta.yaml"
    meta.write_text(meta.read_text().replace("2026-05-09-fixture-minimal", PLAN))
    second = (plan_dir / "01.yaml").read_text()
    second = second.replace("number: 1", "number: 2").replace("P1.", "P2.")
    second = second.replace("depends_on: []", "depends_on: [1]").replace("  skeleton: true\n", "")
    (plan_dir / "02.yaml").write_text(second)
    return f"docs/superpowers/plans/{PLAN}"


def _at_phase_two_review(tmp_path: Path) -> tuple[Path, Path, str]:
    """`phase/2/peer-review` opened, phase 1 implemented and reviewed. Returns
    when the phase-2 review unit opened."""
    from tests.unit.test_run_cli import _invoke, _repo, _started_grouped_with_plan, _write_shape

    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _PHASE_SHAPE)
    _started_grouped_with_plan(repo, shipped, _two_phase_plan(repo))
    _plan_journal(
        repo,
        {"kind": "review", "id": "rev-p1", "phase": 1, "title": "phase 1 review"},
        {"kind": "review", "id": "rev-p2", "phase": 2, "title": "phase 2 review"},
    )
    for n in (1, 2):
        ok = _invoke(repo, shipped, ["run", "advance", "r1"])
        assert ok.exit_code == 0, ok.output
        code = ["run", "resolve", "r1", "--step", "code", "--item", f"phase/{n}"]
        ok = _invoke(repo, shipped, [*code, "--state", "done", "--agent", f"impl-{n}"])
        assert ok.exit_code == 0, ok.output
        ok = _invoke(repo, shipped, ["run", "advance", "r1"])
        assert ok.exit_code == 0, ok.output
        if n == 1:
            argv = [*_REVIEW_ARGV, "phase/1", "--state", "done"]
            evidence = ["--evidence", "review=rev-p1", "--evidence", "reviewer=rv-1"]
            ok = _invoke(repo, shipped, [*argv, *evidence])
            assert ok.exit_code == 0, ok.output
    attempt = units.last_attempt(load_run_state(repo, "r1"), "phase/2/peer-review")
    assert attempt is not None
    return repo, shipped, attempt.dispatched


def _set_return(db: Path, child: str, text: str) -> None:
    """`child` returns `text`: its own text parts dropped and its dispatching
    `task` part's `<task_result>` rewritten (the backend's fallback)."""
    with closing(sqlite3.connect(db)) as con:
        for pid, raw in con.execute("SELECT id, data FROM part").fetchall():
            data = json.loads(raw)
            if not isinstance(data, dict):
                continue
            if (
                data.get("type") == "text"
                and con.execute(
                    "SELECT 1 FROM part WHERE id=? AND session_id=?", (pid, child)
                ).fetchone()
            ):
                con.execute("DELETE FROM part WHERE id=?", (pid,))
                continue
            state = data.get("state") or {}
            if data.get("tool") == "task" and state.get("metadata", {}).get("sessionId") == child:
                state["output"] = (
                    f'<task id="{child}" state="completed"><task_result>{text}</task_result></task>'
                )
                con.execute("UPDATE part SET data=? WHERE id=?", (json.dumps(data), pid))
        con.commit()


def _block(*lines: str) -> str:
    return "Reviewed phase 2.\n\n```review-findings\n" + "\n".join(lines) + "\n```\n"


def _review_window(tmp_path: Path, opened: str, returns: dict[str, str] | None = None) -> Path:
    """The fixture moved so ses_gen1/ses_gen2 (and the executor) fall inside the
    review window and the spec reviewer ses_rev before it; `returns` rewrites
    what a child returned."""
    start = parse_timestamp(opened)
    assert start is not None
    db = shifted(tmp_path, start - _dt.timedelta(seconds=100))
    for child, text in (returns or {}).items():
        _set_return(db, child, text)
    return db


def _phase_review(repo: Path, shipped: Path, env: dict[str, str | None], reviewer: str):
    argv = [*_REVIEW_ARGV, "phase/2", "--state", "done"]
    evidence = ["--evidence", "review=rev-p2", "--evidence", f"reviewer={reviewer}"]
    return _invoke_as_harness(repo, shipped, [*argv, *evidence], env)


def _finding(fid: str, scope: str, *, state: str = "fixed") -> list[dict[str, object]]:
    return [
        {"kind": "finding", "id": fid, "phase": 2, "title": fid, "state": "open",
         "review_scope": scope},
        {"kind": "finding", "id": f"{fid}-resolved", "phase": 2, "title": f"resolves {fid}",
         "state": state, "resolves": fid},
    ]  # fmt: skip


def _review_evidence(repo: Path) -> dict[str, str]:
    return units.evidence_of(load_run_state(repo, "r1").steps["implement"], "phase/2/peer-review")


# --- OpenCode ------------------------------------------------------------------


def test_an_honest_review_with_a_helper_child_resolves(tmp_path: Path) -> None:
    """ses_gen2 is a helper: not named, no block — it owes nothing."""
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    _plan_journal(repo, *_finding("p2a-r1", "in"), *_finding("p2a-r2", "out", state="refuted"))
    db = _review_window(tmp_path, opened)

    result = _phase_review(repo, shipped, opencode_env(db), "ses_gen1")

    assert result.exit_code == 0, result.output
    assert "unobserved" not in _review_evidence(repo)


def test_the_pr_body_renders_the_review_phase_findings_with_their_resolution(
    tmp_path: Path,
) -> None:
    """R8: once R7 puts the reviewer's findings in the plan journal, the PR
    body's findings sections carry each with how it was resolved."""
    from fr.record.pr_body import render_pr_body

    repo, shipped, opened = _at_phase_two_review(tmp_path)
    _plan_journal(repo, *_finding("p2a-r1", "in"), *_finding("p2a-r2", "out", state="refuted"))
    db = _review_window(tmp_path, opened)
    assert _phase_review(repo, shipped, opencode_env(db), "ses_gen1").exit_code == 0

    body = render_pr_body(repo, load_run_state(repo, "r1"))

    inside = body.index("p2a-r1")
    assert "fixed" in body[inside : inside + 400]
    outside = body.index("p2a-r2")
    assert "refuted" in body[outside : outside + 400]


def test_a_named_reviewer_with_no_block_is_refused(tmp_path: Path) -> None:
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    _plan_journal(repo, *_finding("p2a-r1", "in"), *_finding("p2a-r2", "out", state="refuted"))
    db = _review_window(tmp_path, opened)

    result = _phase_review(repo, shipped, opencode_env(db), "ses_gen2")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "ses_gen2 returned no review-findings block" in out
    assert "peer-review" in out
    assert "findings" not in _review_evidence(repo)


def test_a_named_reviewer_with_a_malformed_block_is_refused(tmp_path: Path) -> None:
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    db = _review_window(tmp_path, opened, {"ses_gen1": _block("p2a-r1 | maybe | x")})

    result = _phase_review(repo, shipped, opencode_env(db), "ses_gen1")

    assert result.exit_code == 2, result.output
    assert "ses_gen1: review-findings block line" in _squash(result.output)


def test_every_returned_id_missing_from_the_journal_is_named(tmp_path: Path) -> None:
    """#816, take 10 B: three reviewers raised six findings, none were filed."""
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    db = _review_window(tmp_path, opened)
    with_copied_child(db, "ses_gen2", "ses_gen3")
    _set_return(db, "ses_gen2", _block("p2b-r1 | in | z", "p2b-r2 | out | w"))
    _set_return(db, "ses_gen3", _block("p2c-r1 | in | v", "p2c-r2 | in | u"))

    result = _phase_review(repo, shipped, opencode_env(db), "ses_gen1")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    for fid in ("p2a-r1", "p2a-r2", "p2b-r1", "p2b-r2", "p2c-r1", "p2c-r2"):
        assert fid in out
    assert "not in the plan journal" in out
    assert "reviewer ses_gen1" in out


def test_an_id_returned_by_two_reviewers_is_refused(tmp_path: Path) -> None:
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    _plan_journal(repo, *_finding("p2a-r1", "in"), *_finding("p2a-r2", "out", state="refuted"))
    db = _review_window(tmp_path, opened, {"ses_gen2": _block("p2a-r1 | in | same id")})

    result = _phase_review(repo, shipped, opencode_env(db), "ses_gen1")

    assert result.exit_code == 2, result.output
    assert "p2a-r1 is returned by both ses_gen1 and ses_gen2" in _squash(result.output)


def test_a_finding_journaled_with_another_scope_is_refused(tmp_path: Path) -> None:
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    _plan_journal(repo, *_finding("p2a-r1", "out"), *_finding("p2a-r2", "out", state="refuted"))
    db = _review_window(tmp_path, opened)

    result = _phase_review(repo, shipped, opencode_env(db), "ses_gen1")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "p2a-r1" in out and "review_scope" in out


def test_a_finding_against_another_phase_does_not_count(tmp_path: Path) -> None:
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    p1 = [{**e, "phase": 1} for e in _finding("p2a-r1", "in")]
    _plan_journal(repo, *p1, *_finding("p2a-r2", "out", state="refuted"))
    db = _review_window(tmp_path, opened)

    result = _phase_review(repo, shipped, opencode_env(db), "ses_gen1")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "not in the plan journal" in out and "p2a-r1" in out


def test_an_unexported_session_notes_the_return_unobserved(tmp_path: Path) -> None:
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    db = _review_window(tmp_path, opened)

    result = _phase_review(repo, shipped, opencode_env(db, session=None), "ses_gen1")

    assert result.exit_code == 0, result.output
    assert "could not read what the phase reviewers returned" in _squash(result.stderr)
    assert "reviewer-return" in _review_evidence(repo)["unobserved"].split(",")


# --- Claude Code ---------------------------------------------------------------


def _cc_review(tmp_path: Path, returned: str):
    root = tmp_path / "projects"
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    session = dispatched_at(root, _later(opened), session_id="s-x", usage={}, agent_type="general")
    row_ = agent_result_row(_later(opened), tool_use_id=TOOL_USE_ID, text=returned)
    with session.open("a") as handle:
        handle.write(json.dumps(row_) + "\n")
    argv = [*_REVIEW_ARGV, "phase/2", "--state", "done"]
    evidence = ["--evidence", "review=rev-p2", "--evidence", f"reviewer={AGENT_ID}"]
    return repo, _invoke_measurable(repo, shipped, [*argv, *evidence], root, "s-x")


def test_a_claude_code_reviewer_with_no_block_is_refused(tmp_path: Path) -> None:
    _repo, result = _cc_review(tmp_path, "Looks fine to me.")

    assert result.exit_code == 2, result.output
    assert f"{AGENT_ID} returned no review-findings block" in _squash(result.output)


def test_a_claude_code_returned_id_missing_from_the_journal_is_refused(tmp_path: Path) -> None:
    _repo, result = _cc_review(tmp_path, "Reviewed.\n\n```review-findings\np2-r1 | in | a gap\n```")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "p2-r1" in out and "not in the plan journal" in out


def test_a_claude_code_reviewer_that_raised_nothing_resolves(tmp_path: Path) -> None:
    repo, result = _cc_review(tmp_path, "Reviewed.\n\n```review-findings\nnone\n```")

    assert result.exit_code == 0, result.output
    assert "unobserved" not in _review_evidence(repo)


# --- the brief -------------------------------------------------------------------


def test_every_shipped_review_phase_brief_carries_the_review_findings_rule() -> None:
    """Both shipped shapes share the `review-phase` step id; each one's brief
    carries the rule with this phase's N (spec §E)."""
    from types import SimpleNamespace

    from fr.commands.run_cmd import _build_member_brief
    from fr.workflow.model import parse_manifest

    shipped = Path(__file__).parents[2] / "plugins" / "super-fr" / "workflows"
    for name in ("fr-goal", "fr-goal-light"):
        manifest = parse_manifest((shipped / f"{name}.yaml").read_text())
        group = next(s for s in manifest.steps if any(m.id == "review-phase" for m in s.steps))
        member = next(m for m in group.steps if m.id == "review-phase")
        state = SimpleNamespace(run="r1", workflow=name)

        brief = _build_member_brief(member, group, "phase/3", state, None)  # type: ignore[arg-type]

        rule = brief["review_findings"]
        assert "```review-findings" in rule, name
        assert "p3-r<k>" in rule and "p3a-r<k>" in rule, name
        executor = next(m for m in group.steps if m.id == "implement-phase")
        assert "review_findings" not in _build_member_brief(
            executor,
            group,
            "phase/3",
            state,  # type: ignore[arg-type]
            None,
        ), name


def test_a_finding_filed_against_a_later_phase_counts(tmp_path: Path) -> None:
    """Review p2-r3: the manifest's convention files a finding that belongs to
    a later phase against THAT phase, where it gates that phase's review — so a
    returned id journaled against phase N or later is accounted for; only an
    EARLIER phase does not count (it could no longer gate anything)."""
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    later = [{**e, "phase": 3} for e in _finding("p2a-r1", "in")]
    _plan_journal(repo, *later, *_finding("p2a-r2", "out", state="refuted"))
    db = _review_window(tmp_path, opened)

    result = _phase_review(repo, shipped, opencode_env(db), "ses_gen1")

    assert result.exit_code == 0, result.output


def test_a_resumed_reviewer_is_one_reviewer(tmp_path: Path) -> None:
    """Review p2-r1: sending the reviewer back (a second `task` call reusing
    its session) is one child, not two — no "returned by both X and X"."""
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    _plan_journal(repo, *_finding("p2a-r1", "in"), *_finding("p2a-r2", "out", state="refuted"))
    db = with_resumed_child(_review_window(tmp_path, opened), "ses_gen1")

    result = _phase_review(repo, shipped, opencode_env(db), "ses_gen1")

    assert result.exit_code == 0, result.output
