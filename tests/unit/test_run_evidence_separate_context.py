"""Evidence that someone OTHER than the author did the work — debug journal
`2026-09-21-fr-goal-first-run-contracts`, C5 and C6.

The first fr-goal run after the #508 refactor cleared every evidence gate while
doing none of the work the gates stand for:

- `review-phase` took `--evidence review=<id>` for a journal entry the
  orchestrator typed itself; no reviewer ran. The gate proved an entry EXISTED.
- `deliver` resolved `done` 28 seconds after it opened with a PR url, and the
  PR said "verified locally" on the phase executor's word.

Operator decision (separate-context review): a review names the dispatched
reviewer subagent (`reviewer=<agent-id>`), never the phase's own implementer and
— where the transcript is readable — one this session really dispatched after
the review opened; `deliver` names the log of a suite the orchestrator itself
ran during delivery (`tests=<log>`). Unobservable: recorded, and SAID to be
unverified, never silently.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from fr.run import units
from fr.run.model import load_run_state
from fr.run.telemetry import parse_timestamp

from tests.unit.test_run_cli import (
    _invoke,
    _invoke_measurable,
    _repo,
    _squash,
    _started_grouped_with_plan,
    _write_shape,
)
from tests.unit.test_run_evidence import PLAN_SLUG, _journal
from tests.unit.transcript_sessions import AGENT_ID, dispatched_at, ran_at, write_session

REVIEWER = "general-purpose"
"""A reviewer's agent type — anything but a phase executor."""

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
        evidence: [review, reviewer]
  - id: deliver
    kind: agent
    needs: [journal:plan]
    evidence: [tests]
"""


def _later(stamp: str) -> str:
    """A transcript stamp one second after a cursor stamp."""
    at = parse_timestamp(stamp)
    assert at is not None
    return at.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S") + ".999Z"


def _soon() -> str:
    """A transcript stamp comfortably after anything a test does next."""
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) + timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _run(repo: Path, shipped: Path, argv: list[str], root: Path | None, session: str):
    if root is None:
        return _invoke(repo, shipped, argv)
    return _invoke_measurable(repo, shipped, argv, root, session)


def _at_the_review(
    tmp_path: Path, *, root: Path | None = None, session: str = "s-x", implementer: str = "impl-1"
) -> tuple[Path, Path, str]:
    """`phase/1/peer-review` opened; `code` was done by `implementer`.
    Returns the review unit's `dispatched`."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _journal(repo)
    assert _run(repo, shipped, ["run", "advance", "r1"], root, session).exit_code == 0
    code = ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"]
    assert _run(repo, shipped, [*code, "--agent", implementer], root, session).exit_code == 0
    assert _run(repo, shipped, ["run", "advance", "r1"], root, session).exit_code == 0
    attempt = units.last_attempt(load_run_state(repo, "r1"), "phase/1/peer-review")
    assert attempt is not None
    return repo, shipped, attempt.dispatched


def _review(repo: Path, shipped: Path, root: Path | None, session: str, *evidence: str):
    argv = ["run", "resolve", "r1", "--step", "peer-review", "--item", "phase/1", "--state"]
    extra = [x for e in evidence for x in ("--evidence", e)]
    return _run(repo, shipped, [*argv, "done", *extra], root, session)


def _review_evidence(repo: Path) -> dict[str, str]:
    record = load_run_state(repo, "r1").steps["implement"]
    return units.evidence_of(record, "phase/1/peer-review")


# --- C6: the reviewer is a separate context --------------------------------


def test_a_review_without_a_reviewer_is_refused_and_names_the_flag(tmp_path: Path) -> None:
    repo, shipped, _ = _at_the_review(tmp_path)

    result = _review(repo, shipped, None, "s-x", "review=rev-p1")

    assert result.exit_code == 2, result.output
    assert "--evidence reviewer=<agent-id>" in _squash(result.output)


def test_the_implementer_cannot_review_its_own_phase(tmp_path: Path) -> None:
    """The #497 shape one step removed: the context that wrote the code
    marking it. Refused whatever the transcript says."""
    repo, shipped, _ = _at_the_review(tmp_path, implementer="impl-1")

    result = _review(repo, shipped, None, "s-x", "review=rev-p1", "reviewer=impl-1")

    assert result.exit_code == 2, result.output
    assert "IMPLEMENTED phase 1" in _squash(result.output)
    assert _review_evidence(repo) == {}


def test_a_reviewer_this_session_dispatched_is_accepted(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    write_session(root, session_id="s-x")
    repo, shipped, opened = _at_the_review(tmp_path, root=root)
    dispatched_at(root, _later(opened), session_id="s-x", usage={}, agent_type=REVIEWER)

    result = _review(repo, shipped, root, "s-x", "review=rev-p1", f"reviewer={AGENT_ID}")

    assert result.exit_code == 0, result.output
    assert _review_evidence(repo) == {"review": "rev-p1", "reviewer": AGENT_ID}


def test_a_phase_executor_dispatch_is_never_a_reviewer(tmp_path: Path) -> None:
    """Review r1-11: an executor is an implementer by construction — of ANY
    phase — so even one this session really dispatched is refused. The capture
    is exactly that: a `super-fr:fr-phase-executor` dispatch."""
    root = tmp_path / "projects"
    write_session(root, session_id="s-x")
    repo, shipped, opened = _at_the_review(tmp_path, root=root)
    dispatched_at(root, _later(opened), session_id="s-x", usage={})

    result = _review(repo, shipped, root, "s-x", "review=rev-p1", f"reviewer={AGENT_ID}")

    assert result.exit_code == 2, result.output
    assert "an implementer, not a reviewer" in _squash(result.output)


def test_a_reviewer_nobody_dispatched_is_refused(tmp_path: Path) -> None:
    """Observed, and absent: a readable transcript with no such subagent."""
    root = tmp_path / "projects"
    write_session(root, session_id="s-x")
    repo, shipped, _ = _at_the_review(tmp_path, root=root)

    result = _review(repo, shipped, root, "s-x", "review=rev-p1", "reviewer=made-up")

    assert result.exit_code == 2, result.output
    assert "names no subagent this session dispatched" in _squash(result.output)


def test_an_unobservable_reviewer_is_recorded_and_said_to_be_unverified(tmp_path: Path) -> None:
    repo, shipped, _ = _at_the_review(tmp_path)

    result = _review(repo, shipped, None, "s-x", "review=rev-p1", "reviewer=r-9")

    assert result.exit_code == 0, result.output
    assert "could not verify reviewer" in _squash(result.stderr)
    assert _review_evidence(repo)["reviewer"] == "r-9"


# --- C5: deliver names a suite the orchestrator ran -------------------------


def _at_deliver(tmp_path: Path, *, root: Path | None = None, session: str = "s-d") -> tuple:
    root_ = root
    repo, shipped, _ = _at_the_review(tmp_path, root=root_, session=session)
    if root_ is not None:
        # The review needs its own observed reviewer on this path too.
        opened = units.last_attempt(load_run_state(repo, "r1"), "phase/1/peer-review")
        assert opened is not None
        dispatched_at(
            root_, _later(opened.dispatched), session_id=session, usage={}, agent_type=REVIEWER
        )
        reviewer = AGENT_ID
    else:
        reviewer = "r-9"
    review = _review(repo, shipped, root_, session, "review=rev-p1", f"reviewer={reviewer}")
    assert review.exit_code == 0, review.output
    _journal_clean(repo)
    assert _run(repo, shipped, ["run", "advance", "r1"], root_, session).exit_code == 0
    attempt = units.last_attempt(load_run_state(repo, "r1"), "step/deliver")
    assert attempt is not None
    return repo, shipped, attempt.dispatched


def _journal_clean(repo: Path) -> None:
    """`deliver` needs `journal:plan`; the fixture journal already exists."""
    assert (repo / "docs" / "superpowers" / "journals" / "plans" / f"{PLAN_SLUG}.md").exists()


def _deliver(repo: Path, shipped: Path, root: Path | None, session: str, *evidence: str):
    extra = [x for e in evidence for x in ("--evidence", e)]
    argv = ["run", "resolve", "r1", "--step", "deliver", "--state", "done", *extra]
    return _run(repo, shipped, argv, root, session)


def test_deliver_without_a_suite_log_is_refused(tmp_path: Path) -> None:
    repo, shipped, _ = _at_deliver(tmp_path)

    result = _deliver(repo, shipped, None, "s-d")

    assert result.exit_code == 2, result.output
    assert "--evidence tests=<path-to-log>" in _squash(result.output)


def test_a_missing_or_empty_log_is_refused(tmp_path: Path) -> None:
    repo, shipped, _ = _at_deliver(tmp_path)
    (repo / "empty.log").write_text("")

    for log in ("nope.log", "empty.log"):
        result = _deliver(repo, shipped, None, "s-d", f"tests={log}")
        assert result.exit_code == 2, result.output
        assert "missing or empty" in _squash(result.output)


def test_a_suite_the_orchestrator_ran_is_accepted_with_its_hash(tmp_path: Path) -> None:
    """The captured command writes `.../c1.log`; the log on disk is that file."""
    root = tmp_path / "projects"
    write_session(root, session_id="s-d")
    repo, shipped, opened = _at_deliver(tmp_path, root=root)
    (repo / "c1.log").write_text("291 passed in 45.99s\n")
    ran_at(root, _later(opened), session_id="s-d", until=_soon(), log=repo / "c1.log")

    result = _deliver(repo, shipped, root, "s-d", "tests=c1.log")

    assert result.exit_code == 0, result.output
    record = load_run_state(repo, "r1").steps["deliver"]
    tests = units.evidence_of(record, "step/deliver")["tests"]
    assert tests.startswith("c1.log@") and len(tests) == len("c1.log@") + 12


def test_a_log_no_command_of_the_orchestrator_produced_is_refused(tmp_path: Path) -> None:
    """The #497 shape: a log exists (the executor wrote one), but this session
    never ran the suite."""
    root = tmp_path / "projects"
    write_session(root, session_id="s-d")
    repo, shipped, _ = _at_deliver(tmp_path, root=root)
    (repo / "c1.log").write_text("4051 passed\n")

    result = _deliver(repo, shipped, root, "s-d", "tests=c1.log")

    assert result.exit_code == 2, result.output
    assert "no command of YOURS wrote it" in _squash(result.output)


def test_a_log_whose_bytes_postdate_the_command_is_refused(tmp_path: Path) -> None:
    """Review r1-1: a command naming the log is not enough — the bytes on disk
    must have been written inside that command's run window. Overwriting the
    log afterwards (with a green someone else reported) is caught."""
    root = tmp_path / "projects"
    write_session(root, session_id="s-d")
    repo, shipped, opened = _at_deliver(tmp_path, root=root)
    log = repo / "c1.log"
    log.write_text("real output\n")
    ran_at(root, _later(opened), session_id="s-d", until=_later(opened), log=log)
    later = time.time() + 120
    os.utime(log, (later, later))

    result = _deliver(repo, shipped, root, "s-d", "tests=c1.log")

    assert result.exit_code == 2, result.output
    assert "not written by the command" in _squash(result.output)


def test_the_tests_witness_never_carries_an_absolute_path(tmp_path: Path) -> None:
    """Review r1-8: the witness lands in a git-tracked cursor. A log inside the
    repo is recorded repo-relative; one outside it (a scratchpad under someone's
    home) by basename only."""
    repo, shipped, _ = _at_deliver(tmp_path)
    outside = tmp_path / "home" / "someone" / "scratch"
    outside.mkdir(parents=True)
    (outside / "suite.log").write_text("ok\n")

    result = _deliver(repo, shipped, None, "s-d", f"tests={outside / 'suite.log'}")

    assert result.exit_code == 0, result.output
    record = load_run_state(repo, "r1").steps["deliver"]
    witness = units.evidence_of(record, "step/deliver")["tests"]
    assert witness.startswith("suite.log@"), witness
    assert "someone" not in witness


def test_unobservable_needs_a_fresh_log_and_says_it_could_not_verify(tmp_path: Path) -> None:
    repo, shipped, opened = _at_deliver(tmp_path)
    stale = repo / "stale.log"
    stale.write_text("old run\n")
    before = (parse_timestamp(opened) or None).timestamp() - 3600  # type: ignore[union-attr]
    os.utime(stale, (before, before))
    refused = _deliver(repo, shipped, None, "s-d", "tests=stale.log")
    assert refused.exit_code == 2, refused.output
    assert "predates this unit" in _squash(refused.output)

    time.sleep(0.01)
    (repo / "fresh.log").write_text("ok\n")
    result = _deliver(repo, shipped, None, "s-d", "tests=fresh.log")
    assert result.exit_code == 0, result.output
    assert "could not verify who ran" in _squash(result.stderr)


# --- gh#593 option 2: `spec-review` is a flat step reviewed against the SPEC journal ---
#
# 2026-09-24 spec §E. Before this, `review`, `reviewer` and `findings` were all
# phase evidence, so a flat `step/spec-review` unit could carry none of them and
# the spec was reviewed by the context that wrote it. The verifier now targets
# the journal a step reviews: `review-phase` -> plan journal + phase (above,
# unchanged); `spec-review` -> the run's emitted spec's journal, no phase.

_SPEC_SLUG = "2026-09-24-x"
_SPEC_REL = f"docs/superpowers/specs/{_SPEC_SLUG}-design.md"

_SPEC_SHAPE = """
workflow: specshape
schema: 1
unit: run
steps:
  - id: brainstorm
    kind: agent
    emits: [spec, journal:spec]
  - id: spec-review
    kind: agent
    needs: [spec]
    emits: [journal:spec]
    evidence: [review, reviewer, findings]
"""


def _at_the_spec_review(
    tmp_path: Path, *, root: Path | None = None, session: str = "s-x", shape: str = _SPEC_SHAPE
) -> tuple[Path, Path, str]:
    """`step/spec-review` opened on a run whose brainstorm emitted a spec.
    Returns the unit's `dispatched`."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "specshape", shape)
    spec = repo / _SPEC_REL
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# x\n")
    start = ["run", "start", "specshape", "--branch", "b", "--run-id", "r1"]
    assert _run(repo, shipped, start, root, session).exit_code == 0
    assert _run(repo, shipped, ["run", "advance", "r1"], root, session).exit_code == 0
    brainstorm = ["run", "resolve", "r1", "--step", "brainstorm", "--state", "done"]
    result = _run(repo, shipped, [*brainstorm, "--emitted", f"spec={_SPEC_REL}"], root, session)
    assert result.exit_code == 0, result.output
    assert _run(repo, shipped, ["run", "advance", "r1"], root, session).exit_code == 0
    attempt = units.last_attempt(load_run_state(repo, "r1"), "step/spec-review")
    assert attempt is not None
    return repo, shipped, attempt.dispatched


def _now_local() -> str:
    """`fr journal add`'s own stamp shape: local wall clock, second precision."""
    from datetime import datetime

    return datetime.now().replace(microsecond=0).isoformat()


def _spec_journal(repo: Path, *entries: dict[str, object]) -> None:
    """Spec-scope entries through the ONE journal writer (a capture, never a
    hand-formatted fixture)."""
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path

    path = journal_path(repo, "spec", _SPEC_SLUG)
    for e in entries:
        append_journal_entry(
            path,
            _SPEC_SLUG,
            JournalEntry(scope="spec", **{"created": _now_local(), "body": "", **e}),  # type: ignore[arg-type]
        )


_REVIEW = {"kind": "review", "id": "sr-1", "title": "spec review"}
_FINDING = {"kind": "finding", "id": "sf-1", "state": "open", "title": "a spec finding"}
_FIXED = {
    "kind": "finding",
    "id": "sf-1-fixed",
    "state": "fixed",
    "resolves": "sf-1",
    "title": "resolves sf-1",
}


def _spec_review(repo: Path, shipped: Path, root: Path | None, session: str, *evidence: str):
    argv = ["run", "resolve", "r1", "--step", "spec-review", "--state", "done"]
    extra = [x for e in evidence for x in ("--evidence", e)]
    return _run(repo, shipped, [*argv, *extra], root, session)


def _spec_review_evidence(repo: Path) -> dict[str, str]:
    record = load_run_state(repo, "r1").steps["spec-review"]
    return units.evidence_of(record, "step/spec-review")


def test_spec_review_happy_path_records_the_closed_findings_witness(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    write_session(root, session_id="s-x")
    repo, shipped, opened = _at_the_spec_review(tmp_path, root=root)
    dispatched_at(root, _later(opened), session_id="s-x", usage={}, agent_type=REVIEWER)
    _spec_journal(repo, _REVIEW, _FINDING, _FIXED)

    result = _spec_review(repo, shipped, root, "s-x", "review=sr-1", f"reviewer={AGENT_ID}")

    assert result.exit_code == 0, result.output
    assert "names no phase" not in _squash(result.output)
    assert _spec_review_evidence(repo) == {
        "review": "sr-1",
        "reviewer": AGENT_ID,
        "findings": "sf-1",
    }


def test_spec_review_without_a_review_entry_after_it_opened_is_refused(tmp_path: Path) -> None:
    """A `review` entry from BEFORE the step opened is not a review of this
    spec-review — the orchestrator's brainstorm notes would satisfy it."""
    repo, shipped, _ = _at_the_spec_review(tmp_path)
    _spec_journal(repo, {**_REVIEW, "created": "2026-01-01T00:00:00"})

    result = _spec_review(repo, shipped, None, "s-x", "review=sr-1", "reviewer=r-9")

    assert result.exit_code == 2, result.output
    assert "before" in _squash(result.output)
    assert _spec_review_evidence(repo) == {}


def test_spec_review_naming_a_non_review_entry_is_refused(tmp_path: Path) -> None:
    repo, shipped, _ = _at_the_spec_review(tmp_path)
    _spec_journal(repo, _FINDING)

    result = _spec_review(repo, shipped, None, "s-x", "review=sf-1", "reviewer=r-9")

    assert result.exit_code == 2, result.output
    assert "kind=review" in _squash(result.output)


def test_spec_review_is_refused_while_a_spec_finding_is_open(tmp_path: Path) -> None:
    repo, shipped, _ = _at_the_spec_review(tmp_path)
    _spec_journal(repo, _REVIEW, _FINDING)

    result = _spec_review(repo, shipped, None, "s-x", "review=sr-1", "reviewer=r-9")

    assert result.exit_code == 2, result.output
    squashed = _squash(result.output)
    assert "still open: sf-1" in squashed
    assert f"--scope spec --slug {_SPEC_SLUG} --id sf-1" in squashed


def test_spec_review_passes_when_the_only_unresolved_finding_is_out_of_scope(
    tmp_path: Path,
) -> None:
    repo, shipped, _ = _at_the_spec_review(tmp_path)
    oos = {**_FIXED, "state": "open", "out_of_scope": True, "id": "sf-1-oos"}
    _spec_journal(repo, _REVIEW, _FINDING, oos)

    result = _spec_review(repo, shipped, None, "s-x", "review=sr-1", "reviewer=r-9")

    assert result.exit_code == 0, result.output
    assert _spec_review_evidence(repo)["findings"] == "sf-1"


def test_spec_review_is_refused_on_an_unauthorized_fix(tmp_path: Path) -> None:
    repo, shipped, _ = _at_the_spec_review(tmp_path)
    oos = {**_FIXED, "state": "open", "out_of_scope": True, "id": "sf-1-oos"}
    _spec_journal(repo, _REVIEW, _FINDING, oos, _FIXED)

    result = _spec_review(repo, shipped, None, "s-x", "review=sr-1", "reviewer=r-9")

    assert result.exit_code == 2, result.output
    squashed = _squash(result.output)
    assert "unauthorized fix" in squashed
    assert "--scope spec" in squashed


def test_spec_review_reviewer_nobody_dispatched_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    write_session(root, session_id="s-x")
    repo, shipped, _ = _at_the_spec_review(tmp_path, root=root)
    _spec_journal(repo, _REVIEW)

    result = _spec_review(repo, shipped, root, "s-x", "review=sr-1", "reviewer=made-up")

    assert result.exit_code == 2, result.output
    assert "names no subagent this session dispatched" in _squash(result.output)


def test_spec_review_unreadable_transcript_records_the_reviewer_as_claimed(
    tmp_path: Path,
) -> None:
    repo, shipped, _ = _at_the_spec_review(tmp_path)
    _spec_journal(repo, _REVIEW)

    result = _spec_review(repo, shipped, None, "s-x", "review=sr-1", "reviewer=r-9")

    assert result.exit_code == 0, result.output
    assert "could not verify reviewer" in _squash(result.stderr)
    assert _spec_review_evidence(repo)["reviewer"] == "r-9"


@pytest.mark.parametrize("harness", ["opencode", "hermes"])
def test_spec_review_on_a_harness_with_no_dispatch_reader_is_claimed(
    tmp_path: Path, harness: str
) -> None:
    from tests.unit.test_run_cli import _invoke_as_harness

    repo, shipped, _ = _at_the_spec_review(tmp_path)
    _spec_journal(repo, _REVIEW)
    argv = ["run", "resolve", "r1", "--step", "spec-review", "--state", "done"]
    evidence = ["--evidence", "review=sr-1", "--evidence", "reviewer=r-9"]
    env = {"FR_HARNESS": harness, "CLAUDE_CODE_SESSION_ID": None}

    result = _invoke_as_harness(repo, shipped, [*argv, *evidence], env)

    assert result.exit_code == 0, result.output
    assert "could not verify reviewer" in _squash(result.stderr)
    assert _spec_review_evidence(repo)["reviewer"] == "r-9"


def test_spec_review_without_a_spec_journal_names_the_command(tmp_path: Path) -> None:
    repo, shipped, _ = _at_the_spec_review(tmp_path)

    result = _spec_review(repo, shipped, None, "s-x", "review=sr-1", "reviewer=r-9")

    assert result.exit_code == 2, result.output
    assert f"--scope spec --slug {_SPEC_SLUG} --kind review" in _squash(result.output)


def test_a_flat_step_reviewing_no_journal_still_refuses_phase_evidence(tmp_path: Path) -> None:
    """Only a step that reviews a journal fr can locate (`emits: [journal:spec]`)
    gets a target; any other flat step keeps the fail-closed refusal."""
    shape = _SPEC_SHAPE.replace("    emits: [journal:spec]\n    evidence", "    evidence")
    repo, shipped, _ = _at_the_spec_review(tmp_path, shape=shape)
    _spec_journal(repo, _REVIEW)

    result = _spec_review(repo, shipped, None, "s-x", "review=sr-1", "reviewer=r-9")

    assert result.exit_code == 2, result.output
    assert "names no phase" in _squash(result.output)


# --- phase 4 review: p4-f1, p4-f2, p4-f3 --------------------------------------


def test_p4_f1_adopted_spec_review_naming_an_undispatched_reviewer_is_refused(
    tmp_path: Path,
) -> None:
    """An adopted cursor's flat unit has no attempt, so `opened` is None. The
    reviewer check must date the window from the step's own `at` — the same
    `since` the review entry is dated by — or ANY id passes as "unverified"
    on a transcript that is perfectly readable."""
    from tests.unit.test_run_cli import _forget_dispatch_records

    root = tmp_path / "projects"
    write_session(root, session_id="s-x")
    repo, shipped, _ = _at_the_spec_review(tmp_path, root=root)
    _forget_dispatch_records(repo, "spec-review")
    assert units.last_attempt(load_run_state(repo, "r1"), "step/spec-review") is None
    _spec_journal(repo, _REVIEW)

    result = _spec_review(repo, shipped, root, "s-x", "review=sr-1", "reviewer=made-up")

    assert result.exit_code == 2, result.output
    assert "names no subagent this session dispatched" in _squash(result.output)
    assert _spec_review_evidence(repo) == {}


_AGENT_SPEC_SHAPE = _SPEC_SHAPE.replace(
    "  - id: spec-review\n    kind: agent\n",
    "  - id: spec-review\n    kind: agent\n    agent: super-fr:fr-spec-reviewer\n",
)


@pytest.mark.parametrize("agent_type", ["general-purpose", "Explore"])
def test_p4_f2_a_dispatch_of_another_agent_type_is_not_the_spec_reviewer(
    tmp_path: Path, agent_type: str
) -> None:
    """The step names its reviewer (`agent: super-fr:fr-spec-reviewer`); any
    other subagent this session happened to dispatch is not it."""
    root = tmp_path / "projects"
    write_session(root, session_id="s-x")
    repo, shipped, opened = _at_the_spec_review(tmp_path, root=root, shape=_AGENT_SPEC_SHAPE)
    dispatched_at(root, _later(opened), session_id="s-x", usage={}, agent_type=agent_type)
    _spec_journal(repo, _REVIEW)

    result = _spec_review(repo, shipped, root, "s-x", "review=sr-1", f"reviewer={AGENT_ID}")

    assert result.exit_code == 2, result.output
    squashed = _squash(result.output)
    assert agent_type in squashed
    assert "super-fr:fr-spec-reviewer" in squashed
    assert _spec_review_evidence(repo) == {}


@pytest.mark.parametrize("agent_type", ["super-fr:fr-spec-reviewer", "fr-spec-reviewer"])
def test_p4_f2_the_named_spec_reviewer_is_accepted_qualified_or_bare(
    tmp_path: Path, agent_type: str
) -> None:
    root = tmp_path / "projects"
    write_session(root, session_id="s-x")
    repo, shipped, opened = _at_the_spec_review(tmp_path, root=root, shape=_AGENT_SPEC_SHAPE)
    dispatched_at(root, _later(opened), session_id="s-x", usage={}, agent_type=agent_type)
    _spec_journal(repo, _REVIEW)

    result = _spec_review(repo, shipped, root, "s-x", "review=sr-1", f"reviewer={AGENT_ID}")

    assert result.exit_code == 0, result.output
    assert _spec_review_evidence(repo)["reviewer"] == AGENT_ID


def test_p4_f2_an_unreadable_transcript_still_records_the_named_step_as_claimed(
    tmp_path: Path,
) -> None:
    repo, shipped, _ = _at_the_spec_review(tmp_path, shape=_AGENT_SPEC_SHAPE)
    _spec_journal(repo, _REVIEW)

    result = _spec_review(repo, shipped, None, "s-x", "review=sr-1", "reviewer=r-9")

    assert result.exit_code == 0, result.output
    assert "could not verify reviewer" in _squash(result.stderr)
