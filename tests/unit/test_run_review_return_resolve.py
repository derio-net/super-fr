"""The reviewer-return checks at resolve (spec 2026-09-29-opencode-observe §D):
the recorded spec-review `input-coverage` block must be the one the reviewer
RETURNED (R5), on every harness whose return fr can read — OpenCode's child
session (the committed run-tree fixture, moved to the unit's clock) and a
Claude Code transcript alike."""

from __future__ import annotations

import json
from pathlib import Path

from fr.run import units
from fr.run.model import load_run_state
from fr.run.telemetry import parse_timestamp

from tests.unit.opencode_fixture import opencode_env, shifted
from tests.unit.requirements_support import row, write_input_entry, write_matrix
from tests.unit.test_run_cli import _invoke_as_harness, _invoke_measurable, _squash
from tests.unit.test_run_evidence_requirements import (
    _WITH_COVERAGE,
    SPEC,
    _brainstorm,
    _evidence,
    _review_entry,
    _started,
)
from tests.unit.test_run_evidence_separate_context import _later
from tests.unit.transcript_sessions import (
    AGENT_ID,
    TOOL_USE_ID,
    agent_result_row,
    dispatched_at,
)

INPUT = "fr observes example sessions for the demo"
REQUIREMENTS = """
## Requirements

| id | requirement | source |
|---|---|---|
| R1 | fr observes sessions. | input "fr observes example sessions" |
"""
# ses_rev's return in the fixture (tests/fixtures/usage/opencode/build.py
# REVIEW_RETURN): its review entry's body, as the journal holds it.
RETURNED_BODY = """Reviewed the spec against the input.

```input-coverage
| span | coverage |
|---|---|
| "fr observes example sessions" | R1 |
| "for the demo" | context |
```
"""
RECUT_BODY = RETURNED_BODY.replace(
    '| "fr observes example sessions" | R1 |',
    '| "fr observes" | R1 |\n| "example sessions" | R1 |',
)
RETURN_RECORD = "schema_version: 4\njournal:\n  - kind: review\n    id: review-1\n    body: |\n" + (
    "".join(f"      {line}\n" if line else "\n" for line in RETURNED_BODY.split("\n"))
)

SPEC_REVIEW = ["run", "resolve", "r1", "--step", "spec-review", "--state", "done"]


def _at_spec_review(tmp_path: Path) -> tuple[Path, Path, str]:
    """`spec-review` opened on a spec whose input is the fixture reviewer's.
    Returns when the unit opened."""
    repo, shipped = _started(tmp_path, spec_review=_WITH_COVERAGE)
    spec = repo / SPEC
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Example\n" + REQUIREMENTS)
    write_input_entry(repo, SPEC, body=INPUT)
    write_matrix(repo, [row(SPEC)])
    assert _brainstorm(repo, shipped).exit_code == 0
    advanced = _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], {})
    assert advanced.exit_code == 0, advanced.output
    attempt = units.last_attempt(load_run_state(repo, "r1"), "step/spec-review")
    assert attempt is not None
    return repo, shipped, attempt.dispatched


def _on_opencode(tmp_path: Path, opened: str, *, session: str | None = "ses_run"):
    start = parse_timestamp(opened)
    assert start is not None
    return opencode_env(shifted(tmp_path, start), session=session)


def _resolve(repo: Path, shipped: Path, env: dict[str, str | None], reviewer: str):
    argv = [*SPEC_REVIEW, "--evidence", "review=sr-1", "--evidence", f"reviewer={reviewer}"]
    return _invoke_as_harness(repo, shipped, argv, env)


# --- OpenCode ------------------------------------------------------------------


def test_the_unedited_returned_block_resolves_on_opencode(tmp_path: Path) -> None:
    repo, shipped, opened = _at_spec_review(tmp_path)
    _review_entry(repo, body=RETURNED_BODY)

    result = _resolve(repo, shipped, _on_opencode(tmp_path, opened), "ses_rev")

    assert result.exit_code == 0, result.output
    assert _evidence(repo, "spec-review")["coverage"].startswith("2 spans")


def test_a_re_cut_block_is_refused_naming_the_row_on_opencode(tmp_path: Path) -> None:
    """#777, take 10 B: the orchestrator re-cut the reviewer's partition."""
    repo, shipped, opened = _at_spec_review(tmp_path)
    _review_entry(repo, body=RECUT_BODY)

    result = _resolve(repo, shipped, _on_opencode(tmp_path, opened), "ses_rev")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "differs from the one reviewer ses_rev returned" in out
    assert "line 4 of the block" in out
    assert "fr observes" in out
    assert "coverage" not in _evidence(repo, "spec-review")


def test_an_unexported_session_notes_the_return_unobserved(tmp_path: Path) -> None:
    repo, shipped, opened = _at_spec_review(tmp_path)
    _review_entry(repo, body=RECUT_BODY)

    result = _resolve(repo, shipped, _on_opencode(tmp_path, opened, session=None), "ses_rev")

    assert result.exit_code == 0, result.output
    assert "could not read what reviewer ses_rev returned" in _squash(result.stderr)
    assert "reviewer-return" in _evidence(repo, "spec-review")["unobserved"]


# --- Claude Code ---------------------------------------------------------------


def _cc_session(root: Path, opened: str, returned: str) -> None:
    session = dispatched_at(
        root, _later(opened), session_id="s-x", usage={}, agent_type="super-fr:fr-spec-reviewer"
    )
    row_ = agent_result_row(_later(opened), tool_use_id=TOOL_USE_ID, text=returned)
    with session.open("a") as handle:
        handle.write(json.dumps(row_) + "\n")


def _resolve_cc(repo: Path, shipped: Path, root: Path):
    argv = [*SPEC_REVIEW, "--evidence", "review=sr-1", "--evidence", f"reviewer={AGENT_ID}"]
    return _invoke_measurable(repo, shipped, argv, root, "s-x")


def test_the_unedited_returned_block_resolves_on_claude_code(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _at_spec_review(tmp_path)
    _cc_session(root, opened, RETURN_RECORD)
    _review_entry(repo, body=RETURNED_BODY)

    result = _resolve_cc(repo, shipped, root)

    assert result.exit_code == 0, result.output


def test_a_re_cut_block_is_refused_on_claude_code(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _at_spec_review(tmp_path)
    _cc_session(root, opened, RETURN_RECORD)
    _review_entry(repo, body=RECUT_BODY)

    result = _resolve_cc(repo, shipped, root)

    assert result.exit_code == 2, result.output
    assert "line 4 of the block" in _squash(result.output)


def test_a_return_with_no_block_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _at_spec_review(tmp_path)
    _cc_session(root, opened, "Reviewed the spec; it looks fine.")
    _review_entry(repo, body=RETURNED_BODY)

    result = _resolve_cc(repo, shipped, root)

    assert result.exit_code == 2, result.output
    assert "the reviewer returned no input-coverage block" in _squash(result.output)


# --- R7: the review-phase findings block must be in the journal ---------------

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

    for e in entries:
        append_journal_entry(
            journal_path(repo, "plan", PLAN),
            PLAN,
            JournalEntry(scope="plan", created=_now(), **e),  # type: ignore[arg-type]
        )


def _now() -> str:
    from tests.unit.requirements_support import now

    return now()


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


def _at_phase_two_review(tmp_path: Path, briefs: list[str] | None = None) -> tuple[Path, Path, str]:
    """`phase/2/peer-review` opened, phase 1 implemented and reviewed. Returns
    when the phase-2 review unit opened; `briefs` collects each advance's
    output."""
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
        if briefs is not None:
            briefs.append(ok.output)
        if n == 1:
            argv = [*_REVIEW_ARGV, "phase/1", "--state", "done"]
            evidence = ["--evidence", "review=rev-p1", "--evidence", "reviewer=rv-1"]
            ok = _invoke(repo, shipped, [*argv, *evidence])
            assert ok.exit_code == 0, ok.output
    attempt = units.last_attempt(load_run_state(repo, "r1"), "phase/2/peer-review")
    assert attempt is not None
    return repo, shipped, attempt.dispatched


def _review_window(tmp_path: Path, opened: str, *, gen2_block: str | None = None):
    """The fixture moved so ses_gen1/ses_gen2 (and the executor) fall inside the
    review window and the spec reviewer ses_rev before it. `gen2_block` gives
    ses_gen2's return a findings block (a copy of the fixture, edited)."""
    import datetime as _dt
    import sqlite3
    from contextlib import closing

    start = parse_timestamp(opened)
    assert start is not None
    db = shifted(tmp_path, start - _dt.timedelta(seconds=100))
    if gen2_block is not None:
        text = f"Reviewed phase 2.\n\n```findings\n{gen2_block}\n```\n"
        with closing(sqlite3.connect(db)) as con:
            for pid, raw in con.execute("SELECT id, data FROM part WHERE session_id='ses_gen2'"):
                data = json.loads(raw)
                if data.get("type") == "text":
                    data["text"] = text
                    con.execute("UPDATE part SET data=? WHERE id=?", (json.dumps(data), pid))
            con.commit()
    return opencode_env(db)


def _phase_review(repo: Path, shipped: Path, env: dict[str, str | None]):
    argv = [*_REVIEW_ARGV, "phase/2", "--state", "done"]
    evidence = ["--evidence", "review=rev-p2", "--evidence", "reviewer=ses_gen1"]
    return _invoke_as_harness(repo, shipped, [*argv, *evidence], env)


def _finding(fid: str, scope: str, *, state: str = "fixed") -> list[dict[str, object]]:
    return [
        {"kind": "finding", "id": fid, "phase": 2, "title": fid, "state": "open",
         "review_scope": scope},
        {"kind": "finding", "id": f"{fid}-resolved", "phase": 2, "title": f"resolves {fid}",
         "state": state, "resolves": fid},
    ]  # fmt: skip


def test_a_reviewer_return_with_no_findings_block_is_refused(tmp_path: Path) -> None:
    repo, shipped, opened = _at_phase_two_review(tmp_path)

    result = _phase_review(repo, shipped, _review_window(tmp_path, opened))

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "ses_gen2 returned no findings block" in out
    assert "ses_gen1" not in out.split("returned no findings block")[0].split("refused")[-1]


def test_every_returned_id_missing_from_the_journal_is_named(tmp_path: Path) -> None:
    """#816, take 10 B: reviewers raised findings, none were filed."""
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    env = _review_window(tmp_path, opened, gen2_block="p2b-r1 | in | z")

    result = _phase_review(repo, shipped, env)

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    for fid in ("p2a-r1", "p2a-r2", "p2b-r1"):
        assert fid in out
    assert "not in the plan journal" in out


def test_an_id_returned_by_two_reviewers_is_refused(tmp_path: Path) -> None:
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    _plan_journal(repo, *_finding("p2a-r1", "in"), *_finding("p2a-r2", "out", state="refuted"))
    env = _review_window(tmp_path, opened, gen2_block="p2a-r1 | in | same id")

    result = _phase_review(repo, shipped, env)

    assert result.exit_code == 2, result.output
    assert "p2a-r1 is returned by both ses_gen1 and ses_gen2" in _squash(result.output)


def test_every_returned_finding_journaled_with_its_scope_resolves(tmp_path: Path) -> None:
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    _plan_journal(repo, *_finding("p2a-r1", "in"), *_finding("p2a-r2", "out", state="refuted"))
    env = _review_window(tmp_path, opened, gen2_block="none")

    result = _phase_review(repo, shipped, env)

    assert result.exit_code == 0, result.output
    from fr.record.pr_body import render_pr_body

    body = render_pr_body(repo, load_run_state(repo, "r1"))
    assert "p2a-r1" in body and "p2a-r2" in body
    assert "fixed" in body and "refuted" in body


def test_a_finding_journaled_with_another_scope_is_refused(tmp_path: Path) -> None:
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    _plan_journal(repo, *_finding("p2a-r1", "out"), *_finding("p2a-r2", "out", state="refuted"))
    env = _review_window(tmp_path, opened, gen2_block="none")

    result = _phase_review(repo, shipped, env)

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "p2a-r1" in out and "review_scope" in out


def test_an_unexported_session_notes_the_findings_return_unobserved(tmp_path: Path) -> None:
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    env = {**_review_window(tmp_path, opened), "FR_OPENCODE_SESSION_ID": None}

    result = _phase_review(repo, shipped, env)

    assert result.exit_code == 0, result.output
    assert "could not read what the phase reviewers returned" in _squash(result.stderr)


def test_a_claude_code_reviewer_with_no_block_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    session = dispatched_at(root, _later(opened), session_id="s-x", usage={}, agent_type="general")
    row_ = agent_result_row(_later(opened), tool_use_id=TOOL_USE_ID, text="Looks fine to me.")
    with session.open("a") as handle:
        handle.write(json.dumps(row_) + "\n")
    argv = [*_REVIEW_ARGV, "phase/2", "--state", "done"]
    evidence = ["--evidence", "review=rev-p2", "--evidence", f"reviewer={AGENT_ID}"]

    result = _invoke_measurable(repo, shipped, [*argv, *evidence], root, "s-x")

    assert result.exit_code == 2, result.output
    assert f"{AGENT_ID} returned no findings block" in _squash(result.output)


def test_a_claude_code_returned_id_missing_from_the_journal_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    repo, shipped, opened = _at_phase_two_review(tmp_path)
    session = dispatched_at(root, _later(opened), session_id="s-x", usage={}, agent_type="general")
    text = "Reviewed.\n\n```findings\np2-r1 | in | a gap\n```"
    row_ = agent_result_row(_later(opened), tool_use_id=TOOL_USE_ID, text=text)
    with session.open("a") as handle:
        handle.write(json.dumps(row_) + "\n")
    argv = [*_REVIEW_ARGV, "phase/2", "--state", "done"]
    evidence = ["--evidence", "review=rev-p2", "--evidence", f"reviewer={AGENT_ID}"]

    result = _invoke_measurable(repo, shipped, [*argv, *evidence], root, "s-x")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "p2-r1" in out and "not in the plan journal" in out


def test_the_review_brief_prescribes_the_findings_block(tmp_path: Path) -> None:
    from tests.unit.test_run_cli import _brief_of

    briefs: list[str] = []
    _at_phase_two_review(tmp_path, briefs)

    rule = _brief_of(briefs[-1])["findings_block"]
    assert "```findings" in rule
    assert "p2-r<k>" in rule and "p2a-r<k>" in rule
    assert "none" in rule
