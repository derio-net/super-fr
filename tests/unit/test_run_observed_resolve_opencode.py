"""Resolve-level gates on OpenCode, over the committed run-tree fixture moved to
the unit's own clock (`tests/unit/opencode_fixture.py`) — spec
2026-10-02-opencode-observe-2 §A, §B (review p1-r1, p1-r6 of #837).

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
    _AGENT_SPEC_SHAPE,
    _REVIEW,
    _SHAPE,
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


def test_an_invented_reviewer_id_is_refused_at_the_phase_review_on_opencode(
    tmp_path: Path,
) -> None:
    """#816 at the phase review: R6 routes both review steps through
    `_verify_reviewer`, so the invented id is refused here too."""
    repo, shipped, opened = _at_the_review(tmp_path)
    db = _shifted_to(tmp_path, opened)

    result = _resolve(
        repo, shipped, db, PEER_REVIEW, "review=rev-p1", "reviewer=opencode-gpt-6-luna"
    )

    assert result.exit_code == 2, result.output
    assert "names no subagent this session dispatched" in _squash(result.output)
    assert _review_evidence(repo) == {}


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
    why = _why_unobservable("questions")
    assert "FR_OPENCODE_SESSION_ID" in why
    assert "super-fr OpenCode plugin" in why
    assert "no transcript reader" not in why
    monkeypatch.setenv("FR_HARNESS", "hermes")
    assert "hermes" in _why_unobservable("questions")


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


# --- the phase `tests=` witness on OpenCode (spec §A, Test Plan 5a) ----------


def _bash_part(db: Path, session: str, log: Path, start_ms: int, end_ms: int) -> None:
    """One completed `bash` part in `session` writing `log` — the shape of the
    fixture's own `call_suite` part (`build.py`'s `_bash`), times moved."""
    import json
    import sqlite3
    from contextlib import closing

    data = {
        "type": "tool",
        "tool": "bash",
        "callID": f"call_{session}_suite",
        "state": {
            "status": "completed",
            "time": {"start": start_ms, "end": end_ms},
            "input": {"command": f"uv run pytest -q > {log} 2>&1", "description": "run"},
            "output": "",
            "metadata": {"exit": 0, "output": "", "truncated": False},
        },
    }
    with closing(sqlite3.connect(db)) as con:
        con.execute(
            "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
            (
                f"prt_{session}_suite",
                f"msg_{session[4:]}",
                session,
                start_ms,
                end_ms,
                json.dumps(data),
            ),
        )
        con.commit()


def _phase_log_in(tmp_path: Path, writer: str | None):
    """`phase/1/code` opened on OpenCode, the fixture moved to its clock, and
    `suite.log` written now — by a `bash` part of `writer` (`None`: nobody)."""
    import datetime as _dt

    from tests.unit.test_run_suite_reuse import _at_code

    repo, shipped, opened = _at_code(tmp_path)
    db = _shifted_to(tmp_path, opened)
    log = tmp_path / "suite.log"
    log.write_text("4051 passed\n")
    start = parse_timestamp(opened)
    assert start is not None
    if writer is not None:
        now = _dt.datetime.now(_dt.UTC)
        _bash_part(
            db,
            writer,
            log,
            int(start.timestamp() * 1000) + 1,
            int((now + _dt.timedelta(seconds=60)).timestamp() * 1000),
        )
    return repo, shipped, db, log


def _code(repo: Path, shipped: Path, env: dict[str, str | None], log: Path):
    from tests.unit.test_run_suite_reuse import _CODE

    argv = [*_CODE, "--agent", "ses_exec", "--evidence", f"tests={log}"]
    return _invoke_as_harness(repo, shipped, argv, env)


def test_a_phase_log_written_in_the_holders_child_session_is_witnessed(tmp_path: Path) -> None:
    from tests.unit.test_run_suite_reuse import _code_evidence

    repo, shipped, db, log = _phase_log_in(tmp_path, "ses_exec")

    result = _code(repo, shipped, opencode_env(db), log)

    assert result.exit_code == 0, result.output
    evidence = _code_evidence(repo)
    assert ";tree=" in evidence["tests"]
    assert "unobserved" not in evidence


def test_a_phase_log_written_only_by_a_sibling_session_is_refused(tmp_path: Path) -> None:
    repo, shipped, db, log = _phase_log_in(tmp_path, "ses_gen1")

    result = _code(repo, shipped, opencode_env(db), log)

    assert result.exit_code == 2, result.output
    assert "no command of the unit's holder wrote it" in _squash(result.output)


def test_a_phase_log_on_hermes_keeps_the_unobserved_message(tmp_path: Path) -> None:
    from tests.unit.test_run_suite_reuse import _code_evidence

    repo, shipped, _db, log = _phase_log_in(tmp_path, None)

    result = _code(repo, shipped, {"FR_HARNESS": "hermes"}, log)

    assert result.exit_code == 0, result.output
    assert "fr has no child-session reader for hermes" in _squash(result.stderr)
    assert "tests" in _code_evidence(repo)["unobserved"].split(",")


def test_advance_records_no_session_when_no_harness_owns_one(tmp_path: Path, monkeypatch) -> None:
    """Review p1-r1 (gh#537): with the harness undetectable (an OpenCode
    started from a Claude Code shell whose pid cannot be placed), the inherited
    `CLAUDE_CODE_SESSION_ID` names a session that never held the unit — main
    recorded nothing there, and so must this, or it becomes positive evidence
    for the run's cost (R3)."""
    import fr.commands.run_cmd as run_cmd
    import fr.run.telemetry as telemetry

    monkeypatch.setattr(run_cmd, "detect_harness", lambda env: None)
    monkeypatch.setattr(telemetry, "detect_harness", lambda env: None)
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped)

    result = _invoke_as_harness(
        repo, shipped, ["run", "advance", "r1"], {"CLAUDE_CODE_SESSION_ID": "stale-claude"}
    )

    assert result.exit_code == 0, result.output
    attempt = units.last_attempt(load_run_state(repo, "r1"), "phase/1/code")
    assert attempt is not None and attempt.session is None


# --- R5: the holder is filled from the one observed child -------------------

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
    assert "holder ses_exec observed" in _squash(result.stderr)


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
