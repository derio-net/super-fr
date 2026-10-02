"""The OpenCode backend of `fr.run.observed` (spec 2026-10-02-opencode-observe-2
§A, §B, §H; Test Plan 1), over the committed run-tree fixture
`tests/fixtures/usage/opencode/opencode.db` (built by its `build.py`; shapes
follow a live OpenCode 1.18.33 capture, every identity fictional — see
`tests/fixtures/usage/NOTE.md`)."""

from __future__ import annotations

import datetime as _dt
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from fr.run import observed

DB = Path(__file__).parents[1] / "fixtures" / "usage" / "opencode" / "opencode.db"


def _env(session: str | None = "ses_run", db: Path = DB) -> dict[str, str]:
    env = {"FR_HARNESS": "opencode", "FR_OPENCODE_DB": str(db)}
    if session is not None:
        env["FR_OPENCODE_SESSION_ID"] = session
    return env


def test_fixture_opens() -> None:
    view = observed.observed_session(_env())
    assert view is not None
    assert view.session == "ses_run"


# --- the run tree's clock (tests/fixtures/usage/opencode/build.py) -----------

T0 = 1790328511802
TR = T0 + 3_600_000
SHOT = Path("/work/example/wt/shots/a.png")
LOG = Path("/tmp/example/full-suite.log")


def _at(offset_ms: int) -> _dt.datetime:
    return _dt.datetime.fromtimestamp((TR + offset_ms) / 1000, tz=_dt.UTC)


SINCE = _at(-1)


def _run() -> observed.OpenCodeSession:
    view = observed.observed_session(_env())
    assert isinstance(view, observed.OpenCodeSession)
    return view


def _child(agent_id: str) -> observed.OpenCodeSession:
    view = _run().child(agent_id)
    assert isinstance(view, observed.OpenCodeSession)
    return view


def test_one_answered_round_spans_the_todowrite_and_carries_its_texts() -> None:
    rounds = _run().answered_rounds(SINCE)
    assert rounds is not None
    assert [r.question_texts for r in rounds] == [
        ("Ship the first half?", "Scope", "Keep the old flag?", "Compat")
    ]


def test_declined_and_pending_questions_are_no_round() -> None:
    assert _run().answered_rounds(_at(31_500)) == []


def test_dispatches_are_the_agreeing_task_parts() -> None:
    found = _run().dispatches(SINCE)
    assert found is not None
    assert [(d.agent_id, d.agent_type) for d in found] == [
        ("ses_rev", "fr-spec-reviewer-hard"),
        ("ses_gen1", "general"),
        ("ses_gen2", "general"),
        ("ses_exec", "fr-phase-executor-standard"),
    ]
    assert found[0].started == _at(90_000)


def test_returned_is_the_childs_final_text_and_none_while_running() -> None:
    by_id = {d.agent_id: d for d in _run().dispatches(SINCE) or []}
    rev = by_id["ses_rev"].returned
    assert rev is not None and rev.startswith("schema_version: 7")
    assert "review-findings" not in rev
    gen1 = by_id["ses_gen1"].returned
    assert gen1 is not None and "```review-findings\np2a-r1 | in | x" in gen1
    assert by_id["ses_gen2"].returned == "Reviewed phase 2 and found nothing to raise."
    assert by_id["ses_exec"].returned is None


def test_returned_falls_back_to_the_task_result_body(tmp_path: Path) -> None:
    db = tmp_path / "opencode.db"
    shutil.copy(DB, db)
    with closing(sqlite3.connect(db)) as con:
        con.execute("DELETE FROM part WHERE id = 'prt_gen2_1'")
        con.commit()
    view = observed.observed_session(_env(db=db))
    assert view is not None
    by_id = {d.agent_id: d for d in view.dispatches(SINCE) or []}
    assert by_id["ses_gen2"].returned == "Reviewed phase 2 and found nothing to raise."


def test_dispatches_before_since_are_not_counted() -> None:
    found = _run().dispatches(_at(140_000))
    assert [d.agent_id for d in found or []] == ["ses_gen2", "ses_exec"]


def test_child_is_a_dispatched_child_session_or_false() -> None:
    child = _child("ses_gen1")
    assert child.session == "ses_gen1"
    assert _run().child("ses_nope") is False
    # ses_stray's own row names ses_other as its parent.
    assert _run().child("ses_stray") is False


def test_first_read_is_keyed_per_session() -> None:
    assert _run().first_read(SHOT, SINCE) == _at(40_000)
    assert _child("ses_gen1").first_read(SHOT, SINCE) == _at(135_000)
    assert _child("ses_gen2").first_read(SHOT, SINCE) is False
    assert _run().first_read(SHOT, SINCE, not_before=_at(41_000)) is False
    assert _run().first_read(Path("shots/a.png"), SINCE) is False  # relative never matches


def test_first_shell_executing_is_keyed_per_session() -> None:
    script = Path("/work/example/wt/shots.cjs")
    assert _run().first_shell_executing(script, SINCE) == _at(41_000)
    assert _child("ses_gen1").first_shell_executing(script, SINCE) is False


def test_wrote_windows_are_the_run_sessions_own() -> None:
    assert _run().wrote_windows(LOG, SINCE) == [(_at(50_000), _at(80_000))]


def test_without_a_session_id_every_top_level_session_counts() -> None:
    assert observed.observed_session(_env(session=None)) is None
    windows = observed.opencode_unscoped(_env(session=None)).wrote_windows(LOG, SINCE)
    assert windows == [(_at(50_000), _at(80_000)), (_at(60_000), _at(65_000))]


def test_a_child_id_walks_to_the_run_session() -> None:
    view = observed.observed_session(_env(session="ses_gen1"))
    assert view is not None
    assert view.session == "ses_run"
    assert view.wrote_windows(LOG, SINCE) == [(_at(50_000), _at(80_000))]


def test_a_missing_database_is_unobserved_everywhere(tmp_path: Path) -> None:
    view = observed.observed_session(_env(db=tmp_path / "nope.db"))
    assert view is not None
    assert view.answered_rounds(SINCE) is None
    assert view.dispatches(SINCE) is None
    assert view.child("ses_gen1") is None
    assert view.first_read(SHOT, SINCE) is None
    assert view.first_shell_executing(Path("shots.cjs"), SINCE) is None
    assert view.wrote_windows(LOG, SINCE) is None


def test_agent_name_drops_qualifier_and_tier() -> None:
    assert observed.agent_name("fr-phase-executor-hard") == "fr-phase-executor"
    assert observed.agent_name("super-fr:fr-phase-executor") == "fr-phase-executor"
    assert observed.agent_name("fr-spec-reviewer-mechanical") == "fr-spec-reviewer"
    assert observed.agent_name("general") == "general"


# --- the run session: harness-keyed (spec §B, gh#537) ----------------------


def test_current_session_reads_the_key_its_harness_owns() -> None:
    from fr.run.telemetry import current_session

    both = {"FR_OPENCODE_SESSION_ID": "ses_run", "CLAUDE_CODE_SESSION_ID": "stale-claude"}
    assert current_session({"FR_HARNESS": "opencode", **both}) == "ses_run"
    assert current_session({"FR_HARNESS": "claude-code", **both}) == "stale-claude"
    assert current_session({"FR_HARNESS": "opencode", "CLAUDE_CODE_SESSION_ID": "x"}) is None
    assert current_session({"FR_HARNESS": "hermes", **both}) is None
    assert current_session({"FR_HARNESS": "not-a-harness", **both}) is None


# --- review p1-r2 / p1-r4 ---------------------------------------------------


def test_a_session_the_database_does_not_hold_is_unobserved() -> None:
    """gh#740: a readable database that is not the run's (OpenCode ran under
    another `XDG_DATA_HOME`) must read as unobserved, never as `[]` — which
    the gates refuse as "nobody did it"."""
    from fr.run.telemetry import orchestrator_wrote_since

    env = _env(session="ses_not_in_this_db")
    assert observed.observed_session(env) is None
    view = observed.OpenCodeSession(DB, "ses_not_in_this_db")
    assert view.answered_rounds(SINCE) is None
    assert view.dispatches(SINCE) is None
    assert view.child("ses_gen1") is None
    assert view.first_read(SHOT, SINCE) is None
    assert view.wrote_windows(LOG, SINCE) is None
    # ...and the `tests=` gate does not fall back to every top-level session.
    assert orchestrator_wrote_since(env, LOG, SINCE.isoformat()) is None


def test_a_non_mapping_part_does_not_break_the_final_text(tmp_path: Path) -> None:
    db = tmp_path / "opencode.db"
    shutil.copy(DB, db)
    with closing(sqlite3.connect(db)) as con:
        con.execute(
            "INSERT INTO part VALUES ('prt_gen2_9', 'msg_gen2', 'ses_gen2', ?, ?, '[1, 2]')",
            (TR + 164_500, TR + 164_500),
        )
        con.commit()
    view = observed.observed_session(_env(db=db))
    assert view is not None
    by_id = {d.agent_id: d for d in view.dispatches(SINCE) or []}
    assert by_id["ses_gen2"].returned == "Reviewed phase 2 and found nothing to raise."
