"""Resolve-level gates on OpenCode, over the committed run-tree fixture moved to
the unit's own clock (`tests/unit/opencode_fixture.py`) — spec
2026-09-29-opencode-observe §B, §C (review p1-r1, p1-r6).

The reviewer check names agent types through ONE normaliser,
`fr.run.observed.agent_name`: OpenCode runs a tiered agent as
`fr-spec-reviewer-hard` / `fr-phase-executor-standard`, and an exact comparison
refused the real spec reviewer while accepting a phase executor as a reviewer.
The run session is the TOP-LEVEL one wherever fr records or compares it: the
plugin exports the CALLING session, which is a child's when a subagent runs the
command.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from fr.run import units
from fr.run.model import load_run_state
from fr.run.telemetry import parse_timestamp

from tests.unit.opencode_fixture import DB, opencode_env, shifted, with_copied_child
from tests.unit.test_run_cli import (
    _GROUPED_SHAPE,
    _dispatch_of,
    _invoke_as_harness,
    _repo,
    _squash,
    _started_grouped_with_plan,
    _write_shape,
)
from tests.unit.test_run_evidence import _journal
from tests.unit.test_run_evidence_separate_context import (
    _SHAPE,
    _AGENT_SPEC_SHAPE,
    _REVIEW,
    _at_the_review,
    _at_the_spec_review,
    _review_evidence,
    _spec_journal,
    _spec_review_evidence,
)


def _shifted_to(tmp_path: Path, opened: str) -> Path:
    start = parse_timestamp(opened)
    assert start is not None
    return shifted(tmp_path, start)


def _resolve(repo: Path, shipped: Path, db: Path, argv: list[str], *evidence: str):
    extra = [x for e in evidence for x in ("--evidence", e)]
    return _invoke_as_harness(repo, shipped, [*argv, *extra], opencode_env(db))


SPEC_REVIEW = ["run", "resolve", "r1", "--step", "spec-review", "--state", "done"]
PEER_REVIEW = [
    "run",
    "resolve",
    "r1",
    "--step",
    "peer-review",
    "--item",
    "phase/1",
    "--state",
    "done",
]


def test_the_tiered_opencode_spec_reviewer_is_the_named_reviewer(tmp_path: Path) -> None:
    repo, shipped, opened = _at_the_spec_review(tmp_path, shape=_AGENT_SPEC_SHAPE)
    db = _shifted_to(tmp_path, opened)
    _spec_journal(repo, _REVIEW)

    result = _resolve(repo, shipped, db, SPEC_REVIEW, "review=sr-1", "reviewer=ses_rev")

    assert result.exit_code == 0, result.output
    assert "could not verify reviewer" not in _squash(result.stderr)
    assert _spec_review_evidence(repo)["reviewer"] == "ses_rev"


def test_an_invented_reviewer_id_is_refused_on_opencode(tmp_path: Path) -> None:
    """#816: `opencode-gpt-6-luna` names no session the run dispatched."""
    repo, shipped, opened = _at_the_spec_review(tmp_path, shape=_AGENT_SPEC_SHAPE)
    db = _shifted_to(tmp_path, opened)
    _spec_journal(repo, _REVIEW)

    result = _resolve(repo, shipped, db, SPEC_REVIEW, "review=sr-1", "reviewer=opencode-gpt-6-luna")

    assert result.exit_code == 2, result.output
    assert "names no subagent this session dispatched" in _squash(result.output)


def test_a_general_child_is_the_wrong_spec_reviewer_on_opencode(tmp_path: Path) -> None:
    """ses_gen1 is a `general` dispatch: observed, but not the step's reviewer."""
    repo, shipped, opened = _at_the_spec_review(tmp_path, shape=_AGENT_SPEC_SHAPE)
    db = _shifted_to(tmp_path, opened)
    _spec_journal(repo, _REVIEW)

    result = _resolve(repo, shipped, db, SPEC_REVIEW, "review=sr-1", "reviewer=ses_gen1")

    assert result.exit_code == 2, result.output
    out = _squash(result.output)
    assert "'general' dispatch" in out
    assert "this step's reviewer is" in out


def test_a_tiered_opencode_phase_executor_is_never_a_reviewer(tmp_path: Path) -> None:
    repo, shipped, opened = _at_the_review(tmp_path)
    db = _shifted_to(tmp_path, opened)

    result = _resolve(repo, shipped, db, PEER_REVIEW, "review=rev-p1", "reviewer=ses_exec")

    assert result.exit_code == 2, result.output
    assert "an implementer, not a reviewer" in _squash(result.output)
    assert _review_evidence(repo) == {}


# --- p1-r6: the run session is the top-level one ---------------------------


def test_advance_from_a_child_session_records_the_run_session(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)

    result = _invoke_as_harness(
        repo, shipped, ["run", "advance", "r1"], opencode_env(DB, session="ses_gen1")
    )

    assert result.exit_code == 0, result.output
    (opened,) = _dispatch_of(repo, "implement", "phase/1/code")
    assert opened.session == "ses_run"
    attempt = units.last_attempt(load_run_state(repo, "r1"), "phase/1/code")
    assert attempt is not None and attempt.session == "ses_run"


def test_run_session_walks_to_the_root_on_opencode_only(tmp_path: Path) -> None:
    from fr.run.telemetry import run_session

    child = {"FR_HARNESS": "opencode", "FR_OPENCODE_DB": str(DB), "FR_OPENCODE_SESSION_ID": ""}
    assert run_session({**child, "FR_OPENCODE_SESSION_ID": "ses_gen1"}) == "ses_run"
    assert run_session({**child, "FR_OPENCODE_SESSION_ID": "ses_run"}) == "ses_run"
    assert run_session(child) is None
    unreadable = {**child, "FR_OPENCODE_DB": str(tmp_path / "nope.db")}
    assert run_session({**unreadable, "FR_OPENCODE_SESSION_ID": "ses_gen1"}) == "ses_gen1"
    claude = {"FR_HARNESS": "claude-code", "CLAUDE_CODE_SESSION_ID": "sess-1"}
    assert run_session(claude) == "sess-1"


def test_a_child_session_binds_and_compares_as_the_run_session() -> None:
    from fr.isolation.sessions import ambient_binding
    from fr.run.telemetry import dispatched_from_this_session

    env = {
        "FR_HARNESS": "opencode",
        "FR_OPENCODE_DB": str(DB),
        "FR_OPENCODE_SESSION_ID": "ses_gen1",
    }
    assert ambient_binding(None, "unknown", env) == ("ses_run", "opencode")
    assert dispatched_from_this_session(env, "ses_run") is True
    assert dispatched_from_this_session(env, "ses_gen1") is False


def test_every_agent_type_comparison_folds_the_opencode_tier() -> None:
    from fr.commands.run_cmd import _same_agent as run_same
    from fr.run.visual import _same_agent as visual_same

    for same in (run_same, visual_same):
        assert same("fr-phase-executor-standard", "super-fr:fr-phase-executor")
        assert same("fr-spec-reviewer-hard", "super-fr:fr-spec-reviewer")
        assert not same("general", "super-fr:fr-spec-reviewer")
        assert not same(None, "super-fr:fr-spec-reviewer")


# --- p1-r5: the unobservable wording names what is missing -----------------


def test_why_unobservable_on_opencode_names_the_missing_export(monkeypatch) -> None:
    from fr.commands.run_cmd import _why_unobservable

    monkeypatch.setenv("FR_HARNESS", "opencode")
    why = _why_unobservable()
    assert "FR_OPENCODE_SESSION_ID" in why
    assert "super-fr OpenCode plugin" in why
    assert "no transcript reader" not in why
    monkeypatch.setenv("FR_HARNESS", "hermes")
    assert "hermes" in _why_unobservable()


def test_an_unexported_session_warns_with_the_plugin_wording(tmp_path: Path) -> None:
    repo, shipped, opened = _at_the_spec_review(tmp_path, shape=_AGENT_SPEC_SHAPE)
    db = _shifted_to(tmp_path, opened)
    _spec_journal(repo, _REVIEW)

    result = _invoke_as_harness(
        repo,
        shipped,
        [*SPEC_REVIEW, "--evidence", "review=sr-1", "--evidence", "reviewer=ses_rev"],
        opencode_env(db, session=None),
    )

    assert result.exit_code == 0, result.output
    assert "super-fr OpenCode plugin" in _squash(result.stderr)


# --- R3: the holder is filled from the one observed child ------------------

CODE = ["run", "resolve", "r1", "--step", "code", "--item", "phase/1", "--state", "done"]


def _at_the_code_unit(tmp_path: Path) -> tuple[Path, Path, str]:
    """`phase/1/code` opened on OpenCode, dispatched to the phase executor with
    nobody claiming it. Returns the unit's `dispatched`."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _SHAPE)
    _started_grouped_with_plan(repo, shipped)
    _journal(repo)
    advanced = _invoke_as_harness(repo, shipped, ["run", "advance", "r1"], opencode_env(DB))
    assert advanced.exit_code == 0, advanced.output
    attempt = units.last_attempt(load_run_state(repo, "r1"), "phase/1/code")
    assert attempt is not None and attempt.agent is None
    assert attempt.agent_type is not None
    return repo, shipped, attempt.dispatched


def _code_holder(repo: Path) -> str | None:
    (attempt,) = _dispatch_of(repo, "implement", "phase/1/code")
    return attempt.agent


def test_the_one_observed_executor_child_becomes_the_holder(tmp_path: Path) -> None:
    repo, shipped, opened = _at_the_code_unit(tmp_path)
    db = _shifted_to(tmp_path, opened)

    result = _resolve(repo, shipped, db, CODE)

    assert result.exit_code == 0, result.output
    assert _code_holder(repo) == "ses_exec"


def test_two_executor_children_leave_the_holder_unclaimed(tmp_path: Path) -> None:
    repo, shipped, opened = _at_the_code_unit(tmp_path)
    db = with_copied_child(_shifted_to(tmp_path, opened), "ses_exec", "ses_exec2")

    result = _resolve(repo, shipped, db, CODE)

    assert result.exit_code == 0, result.output
    assert _code_holder(repo) is None


def test_no_executor_child_since_the_unit_opened_leaves_it_unclaimed(tmp_path: Path) -> None:
    repo, shipped, opened = _at_the_code_unit(tmp_path)
    start = parse_timestamp(opened)
    assert start is not None
    db = shifted(tmp_path, start - _dt.timedelta(hours=1))

    result = _resolve(repo, shipped, db, CODE)

    assert result.exit_code == 0, result.output
    assert _code_holder(repo) is None


def test_a_claimed_holder_is_never_replaced_by_the_observed_one(tmp_path: Path) -> None:
    repo, shipped, opened = _at_the_code_unit(tmp_path)
    db = _shifted_to(tmp_path, opened)

    result = _resolve(repo, shipped, db, [*CODE, "--agent", "impl-1"])

    assert result.exit_code == 0, result.output
    assert _code_holder(repo) == "impl-1"
