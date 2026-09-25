"""`OpenCodeReader` — OpenCode's session database as a transcript source
(spec `2026-09-24-fr-goal-scope-proportion-cost-design.md` §D). Its
main-session measurement went with run 7 (usage moved to `fr.usage`, whose
OpenCode reader has its own tests).

The fixture database is built here with the REAL schema subset the reader
touches. Column names, the epoch-MILLISECOND `time_created`, and the `data`
JSON's shape (`role`, `tokens{total,input,output,reasoning,cache{read,write}}`,
`cost`, `time{created,completed}`) were read on 2026-09-24 from a live
`~/.local/share/opencode/opencode.db` with `sqlite3 -readonly` (`.schema` plus
one assistant row's keys and token object; no content, no identity). Only the
columns the reader queries are created; the real tables carry many more.
"""

from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from pathlib import Path

import pytest
from fr.run.telemetry import OpenCodeReader

START = "2026-09-24T10:00:00+00:00"
END = "2026-09-24T10:10:00+00:00"


def _ms(iso: str) -> int:
    return int(_dt.datetime.fromisoformat(iso).timestamp() * 1000)


def _data(role: str, i: int, o: int, r: int, cr: int, cw: int, cost: float, at: int) -> str:
    """One `message.data` JSON: input, output, reasoning, cache read, cache
    write, cost, and `time.created` in epoch ms."""
    return json.dumps(
        {
            "role": role,
            "tokens": {
                "total": i + o + r + cr + cw,
                "input": i,
                "output": o,
                "reasoning": r,
                "cache": {"read": cr, "write": cw},
            },
            "cost": cost,
            "time": {"created": at, "completed": at + 900},
        }
    )


def _db(path: Path, workspace: Path, base: Path) -> Path:
    """Two top-level sessions (`s-bound` in the workspace, `s-other` in the
    base clone), a child of `s-bound`, and one session elsewhere."""
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE session (id TEXT PRIMARY KEY, parent_id TEXT, directory TEXT NOT NULL)"
    )
    con.execute(
        "CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, "
        "time_created INTEGER NOT NULL, data TEXT NOT NULL)"
    )
    con.executemany(
        "INSERT INTO session VALUES (?, ?, ?)",
        [
            ("s-bound", None, str(workspace)),
            ("s-other", None, str(base)),
            ("s-child", "s-bound", str(workspace)),
            ("s-far", None, "/somewhere/else"),
        ],
    )
    rows = []
    inside = _ms("2026-09-24T10:05:00+00:00")
    edge = _ms(START) + 400  # truncates to the window's OPEN edge — excluded
    late = _ms(END) + 1000  # after the window closes
    for sid in ("s-bound", "s-other", "s-child", "s-far"):
        rows += [
            (f"{sid}-a1", sid, inside, _data("assistant", 10, 20, 5, 300, 40, 0.25, inside)),
            (f"{sid}-a2", sid, inside + 60_500, _data("assistant", 1, 2, 0, 30, 4, 0.5, inside)),
            (f"{sid}-u1", sid, inside, _data("user", 0, 0, 0, 0, 0, 0, inside)),
            (f"{sid}-edge", sid, edge, _data("assistant", 99, 99, 0, 0, 0, 9, edge)),
            (f"{sid}-late", sid, late, _data("assistant", 99, 99, 0, 0, 0, 9, late)),
        ]
    con.executemany("INSERT INTO message VALUES (?, ?, ?, ?)", rows)
    con.commit()
    con.close()
    return path


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return _db(tmp_path / "opencode.db", tmp_path / "ws", tmp_path / "base")


def _env(db: Path) -> dict[str, str]:
    return {"FR_HARNESS": "opencode", "FR_OPENCODE_DB": str(db)}


def test_the_database_path_honours_the_override(db: Path) -> None:
    assert OpenCodeReader().database(_env(db)) == db
    assert OpenCodeReader().database({}).name == "opencode.db"
