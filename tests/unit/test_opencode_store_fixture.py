"""The OpenCode 2 store fixture pins what the readers query (spec
2026-10-20-opencode-2-support R13): a later store change fails HERE first."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

FIXTURE = Path(__file__).parents[1] / "fixtures" / "opencode" / "two-sessions.db"

READ_COLUMNS = {
    "session_v2": {"id", "parent_id", "time_created", "time_updated"},
    "session_message": {"id", "session_id", "type", "seq", "time_created", "time_updated", "data"},
    "session": {"id"},
}


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}


def test_the_fixture_holds_every_table_and_column_the_readers_query() -> None:
    with closing(sqlite3.connect(f"{FIXTURE.as_uri()}?mode=ro", uri=True)) as con:
        for table, columns in READ_COLUMNS.items():
            assert columns <= _columns(con, table), table


def test_the_fixture_holds_one_2x_session_and_one_1x_only_session() -> None:
    with closing(sqlite3.connect(f"{FIXTURE.as_uri()}?mode=ro", uri=True)) as con:
        v2 = {r[0] for r in con.execute("SELECT id FROM session_v2")}
        v1 = {r[0] for r in con.execute("SELECT id FROM session")}
        names = {
            item["name"]
            for (raw,) in con.execute("SELECT data FROM session_message WHERE type = 'assistant'")
            for item in json.loads(raw).get("content", [])
            if item.get("type") == "tool"
        }
    assert v2 == {"ses_v2demo", "ses_v2child"}
    assert v1 - v2 == {"ses_v1only"}
    assert {"shell", "question", "skill", "subagent", "bash"} <= names


def test_the_fixture_carries_no_real_identity() -> None:
    with closing(sqlite3.connect(f"{FIXTURE.as_uri()}?mode=ro", uri=True)) as con:
        dirs = {r[0] for r in con.execute("SELECT directory FROM session_v2 UNION "
                                          "SELECT directory FROM session")}  # fmt: skip
    assert all(d.startswith("/home/u/") for d in dirs)
