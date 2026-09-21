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
    dispatched_at(root, _later(opened), session_id="s-x", usage={})

    result = _review(repo, shipped, root, "s-x", "review=rev-p1", f"reviewer={AGENT_ID}")

    assert result.exit_code == 0, result.output
    assert _review_evidence(repo) == {"review": "rev-p1", "reviewer": AGENT_ID}


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
        dispatched_at(root_, _later(opened.dispatched), session_id=session, usage={})
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
    ran_at(root, _later(opened), session_id="s-d")
    (repo / "c1.log").write_text("291 passed in 45.99s\n")

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
    assert "no command of YOURS" in _squash(result.output)


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
