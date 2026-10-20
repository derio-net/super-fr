"""OpenCode 2's store: the R14 probe, and the observed reader on `session_v2` /
`session_message` (spec 2026-10-20-opencode-2-support R13, R14, §D)."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from fr.run import observed
from fr.run.opencode_store import TOOL_ALIASES, canonical_tool, store_version

FIXTURE = Path(__file__).parents[1] / "fixtures" / "opencode" / "two-sessions.db"
T0 = 1792400000000
SINCE = _dt.datetime.fromtimestamp(T0 / 1000, tz=_dt.UTC)


def _env(session: str | None, db: Path = FIXTURE) -> dict[str, str]:
    env = {"FR_HARNESS": "opencode", "FR_OPENCODE_DB": str(db)}
    if session is not None:
        env["OPENCODE_SESSION_ID"] = session
    return env


def test_a_session_is_probed_as_v2_v1_only_absent_or_unreadable(tmp_path: Path) -> None:
    assert store_version(FIXTURE, "ses_v2demo") == "v2"
    assert store_version(FIXTURE, "ses_v1only") == "v1-only"
    assert store_version(FIXTURE, "ses_nowhere") == "absent"
    assert store_version(tmp_path / "missing.db", "ses_v2demo") == "unreadable"
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not sqlite at all, not even a header" * 4)
    assert store_version(junk, "ses_v2demo") == "unreadable"


def test_a_1x_only_session_is_refused_naming_1x_and_the_upgrade() -> None:
    env = _env("ses_v1only")
    assert observed.observed_session(env) is None
    why = observed.why_unobservable("opencode", env, "questions")
    assert "OpenCode 1.x" in why
    assert "upgrade opencode; super-fr supports 2.0 only" in why
    assert "FR_OPENCODE_DB" not in why


def test_an_absent_session_keeps_the_wrong_database_wording() -> None:
    env = _env("ses_nowhere")
    assert observed.observed_session(env) is None
    why = observed.why_unobservable("opencode", env, "questions")
    assert "not in the OpenCode database" in why
    assert "1.x" not in why


def test_an_unreadable_store_says_it_could_not_be_read(tmp_path: Path) -> None:
    env = _env("ses_v2demo", tmp_path / "missing.db")
    why = observed.why_unobservable("opencode", env, "commands")
    assert "could not be read" in why
    assert "1.x" not in why


def test_no_session_id_names_opencode_session_id() -> None:
    why = observed.why_unobservable("opencode", _env(None), "questions")
    assert "OPENCODE_SESSION_ID" in why


def test_the_alias_table_is_one_place() -> None:
    assert canonical_tool("bash") == "shell"
    assert canonical_tool("task") == "subagent"
    assert canonical_tool("shell") == "shell"
    assert dict(TOOL_ALIASES) == {"bash": "shell", "task": "subagent"}


def test_a_2x_session_is_observed_end_to_end() -> None:
    view = observed.observed_session(_env("ses_v2demo"))
    assert isinstance(view, observed.OpenCodeSession)
    rounds = view.answered_rounds(SINCE)
    assert rounds is not None and len(rounds) == 1
    dispatches = view.dispatches(SINCE)
    assert dispatches is not None
    assert [(d.agent_id, d.agent_type, d.returned) for d in dispatches] == [
        ("ses_v2child", "general", "child final answer")
    ]
    assert view.child("ses_v2child") not in (None, False)
    assert view.child("ses_v2demo") is False
    assert view.first_shell_executing(Path("/nowhere.sh"), SINCE) is False
    windows = view.ran_windows(lambda c: c.startswith("echo demo"), SINCE)
    assert windows is not None and len(windows) == 1
    # A migrated 1.x `bash` item still reads as a shell call.
    legacy = view.ran_windows(lambda c: c.startswith("ls "), SINCE)
    assert legacy is not None and len(legacy) == 1


def test_a_child_id_walks_to_its_2x_root() -> None:
    assert observed.opencode_root(FIXTURE, "ses_v2child") == "ses_v2demo"


def test_the_unscoped_reader_sees_only_2x_top_level_sessions() -> None:
    unscoped = observed.OpenCodeUnscoped(FIXTURE)
    windows = unscoped.ran_windows(lambda c: c == "true", SINCE)
    # `true` ran only in the 1.x session's legacy `part`, which 2.x never reads.
    assert windows == []
