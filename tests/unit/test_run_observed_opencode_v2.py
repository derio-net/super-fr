"""OpenCode 2's store: the R14 probe, and the observed reader on `session_v2` /
`session_message` (spec 2026-10-20-opencode-2-support R13, R14, §D)."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from fr.run import observed
from fr.run.opencode_store import (
    STORE_TOOL_ALIASES,
    STORE_TOOLS,
    store_tool_name,
    store_version,
)

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


def test_each_of_the_four_answers_words_itself(tmp_path: Path) -> None:
    """p4-r1: a healthy 2.x session is never described with the absent
    answer's 'wrong database' voice — each answer has its own sentence."""
    v2 = observed.why_unobservable("opencode", _env("ses_v2demo"), "questions")
    assert "was read, and it holds no questions yet" in v2
    assert "FR_OPENCODE_DB" not in v2 and "not in the OpenCode database" not in v2
    assert "1.x" not in v2
    v1 = observed.why_unobservable("opencode", _env("ses_v1only"), "questions")
    assert "OpenCode 1.x" in v1 and "FR_OPENCODE_DB" not in v1
    absent = observed.why_unobservable("opencode", _env("ses_nowhere"), "questions")
    assert "not in the OpenCode database" in absent and "FR_OPENCODE_DB" in absent
    bad = observed.why_unobservable("opencode", _env("ses_v2demo", tmp_path / "x.db"), "questions")
    assert "could not be read" in bad and "not in the OpenCode database" not in bad
    assert len({v2, v1, absent, bad}) == 4


def test_no_session_id_names_opencode_session_id() -> None:
    why = observed.why_unobservable("opencode", _env(None), "questions")
    assert "OPENCODE_SESSION_ID" in why


def test_the_store_alias_table_maps_1x_names_to_2x() -> None:
    assert store_tool_name("bash") == "shell"
    assert store_tool_name("task") == "subagent"
    assert store_tool_name("shell") == "shell"
    assert dict(STORE_TOOL_ALIASES) == {"bash": "shell", "task": "subagent"}


def test_every_store_tool_name_is_known_to_the_activity_vocabulary() -> None:
    """p4-r3: the two tables are different jobs; what they need is that a name
    the store readers yield never falls through `classify` as unknown."""
    from fr.usage import classify

    names = set(STORE_TOOLS) | set(STORE_TOOL_ALIASES) | set(STORE_TOOL_ALIASES.values())
    for name in sorted(names):
        assert name in classify._ALIASES, name
    assert classify.classify("shell", "ls").activity != "other_tool"
    assert classify.classify("subagent") == classify.classify("Agent")
    assert classify.canonical_tool("shell") == classify.canonical_tool("bash") == "Bash"


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


def test_an_unparseable_message_row_makes_the_session_unobservable(tmp_path: Path) -> None:
    """p4-r2: a row whose data does not parse could hold the call being looked
    for, so the observation is unreadable — never "read, found nothing"."""
    import shutil
    import sqlite3

    db = tmp_path / "bad.db"
    shutil.copy(FIXTURE, db)
    con = sqlite3.connect(db)
    con.execute(
        "UPDATE session_message SET data = '{not json' WHERE session_id = 'ses_v2demo'"
    )
    con.commit()
    con.close()
    view = observed.observed_session(_env("ses_v2demo", db))
    assert view is not None
    healthy = observed.observed_session(_env("ses_v2demo"))
    assert healthy is not None and healthy.answered_rounds(SINCE)
    assert view.answered_rounds(SINCE) is None
