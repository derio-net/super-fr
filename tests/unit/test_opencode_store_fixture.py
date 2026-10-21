"""The OpenCode 2 store fixture pins what the readers query (spec
2026-10-20-opencode-2-support R13): a later store change fails HERE first."""

from __future__ import annotations

import json
import re
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
    assert v2 == {"ses_v2demo", "ses_v2child", "ses_v1migrated"}
    assert v1 - v2 == {"ses_v1only"}
    assert {"shell", "question", "skill", "subagent", "bash"} <= names


_ABS_PATH = re.compile(
    r"(?:^|[\s\"')(=:])(/(?:Users|home|root|opt|srv|private|var|workspace|tmp)/[^\s\"',)]*)"
)
_URL_HOST = re.compile(r"https?://([A-Za-z0-9.\-]+)")
_EMAIL_DOMAIN = re.compile(r"[\w.+-]+@([A-Za-z0-9.\-]+)")
_RESERVED_SUFFIXES = (".invalid", ".example", ".test", ".localhost")
_RESERVED_HOSTS = {"example.com", "example.org", "example.net"}


def _fictional(host: str) -> bool:
    low = host.lower()
    return low in _RESERVED_HOSTS or low.endswith(_RESERVED_SUFFIXES)


def test_the_fixture_carries_no_real_identity() -> None:
    """p4-v3: this used to assert the DIRECTORY column and nothing else, so a
    real title, prompt, command, model id or host could be committed here and
    the test stayed green — in the one file where a leak would land, in a public
    repo. Now every text value in every table is scanned for the shapes a leak
    takes: an absolute path outside `/home/u/`, a host that is not a reserved
    (RFC 2606) name, an email whose domain is not reserved."""
    with closing(sqlite3.connect(f"{FIXTURE.as_uri()}?mode=ro", uri=True)) as con:
        dirs = {r[0] for r in con.execute("SELECT directory FROM session_v2 UNION "
                                          "SELECT directory FROM session")}  # fmt: skip
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
        values = [
            value
            for table in tables
            for row in con.execute(f"SELECT * FROM {table}")  # noqa: S608 - fixture table names
            for value in row
            if isinstance(value, str)
        ]
    assert all(d.startswith("/home/u/") for d in dirs)
    assert values, "the scan must actually read the fixture"
    for value in values:
        for path in _ABS_PATH.findall(value):
            assert path.startswith("/home/u/"), (path, value[:120])
        for host in _URL_HOST.findall(value):
            assert _fictional(host), (host, value[:120])
        for domain in _EMAIL_DOMAIN.findall(value):
            assert _fictional(domain), (domain, value[:120])


def test_a_captured_migrated_1x_session_reads_whole() -> None:
    """R13 "migration lost nothing", against rows a real 1.x -> 2.x migration
    wrote (captured, redacted — see the fixture README): every assistant row's
    cost and tokens, and its 1.x `bash` items as `shell` calls."""
    from fr.usage.readers import opencode

    record = opencode.read(FIXTURE, "ses_v1migrated")
    assert record.unavailable is None
    assert record.cost.source == "exact"
    assert record.cost.usd == 0.06
    assert len(record.messages) == 2
    assert sum(m.tokens.output for m in record.messages) == 140
    assert [c.name for m in record.messages for c in m.tool_calls] == ["shell", "shell"]
