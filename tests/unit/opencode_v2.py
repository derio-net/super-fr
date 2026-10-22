"""Carry a 1.x-shaped test database into OpenCode 2's tables, in place.

The older OpenCode tests build their stores in 1.x's `session`/`message`/`part`
shape. OpenCode 2 migrates those rows into `session_v2`/`session_message`
(measured 2026-10-20 on a live 2.1.0 store, spec 2026-10-20 §Context: every 1.x
session was present in `session_v2`, each message's parts folded into its
`data.content[]`, tool items keeping their 1.x names `bash`/`task`). This does
the same fold so those tests keep asserting what they always did, now through
the 2.x reader; the legacy tables are left in place, as OpenCode leaves them.

`tests/unit/test_opencode_store_fixture.py` pins that the tables written here
carry every column the readers query in the captured store's DDL.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

V2_DDL = [
    """CREATE TABLE session_v2 (id TEXT PRIMARY KEY, parent_id TEXT, directory TEXT,
       title TEXT, version TEXT NOT NULL, time_created INTEGER NOT NULL,
       time_updated INTEGER NOT NULL)""",
    """CREATE TABLE session_message (id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
       type TEXT NOT NULL, seq INTEGER NOT NULL, time_created INTEGER NOT NULL,
       time_updated INTEGER NOT NULL, data TEXT NOT NULL)""",
]


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}


def _item(part: dict[str, Any]) -> dict[str, Any] | None:
    kind = part.get("type", "tool")
    if kind == "text":
        return {"type": "text", "text": part.get("text")}
    if kind != "tool":
        return None
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    times = state.get("time") if isinstance(state.get("time"), dict) else {}
    out_state: dict[str, Any] = {
        k: v for k, v in state.items() if k in ("status", "input", "metadata", "error")
    }
    if isinstance(state.get("output"), str):
        out_state["content"] = [{"type": "text", "text": state["output"]}]
    item_time: dict[str, Any] = {}
    if "start" in times:
        item_time["created"] = times["start"]
        item_time["ran"] = times["start"]
    if "end" in times:
        item_time["completed"] = times["end"]
    return {
        "type": "tool",
        "id": part.get("callID"),
        "name": part.get("tool"),
        "time": item_time,
        "state": out_state,
    }


def to_v2(db: Path) -> Path:
    """Rebuild `db`'s `session_v2`/`session_message` from its 1.x tables."""
    with closing(sqlite3.connect(db)) as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        con.execute("DROP TABLE IF EXISTS session_v2")
        con.execute("DROP TABLE IF EXISTS session_message")
        for ddl in V2_DDL:
            con.execute(ddl)
        sessions: dict[str, tuple[Any, ...]] = {}
        if "session" in tables:
            cols = _columns(con, "session")
            for row in con.execute("SELECT * FROM session").fetchall():
                rec = dict(zip([c[1] for c in con.execute("PRAGMA table_info(session)")], row,
                               strict=True))  # fmt: skip
                created = rec.get("time_created") or rec.get("time_updated") or 0
                sessions[rec["id"]] = (
                    rec["id"],
                    rec.get("parent_id"),
                    rec.get("directory") if "directory" in cols else None,
                    rec.get("title") if "title" in cols else None,
                    "1.18.32",
                    created,
                    rec.get("time_updated") or created,
                )
        messages: dict[str, dict[str, Any]] = {}
        if "message" in tables:
            mcols = [c[1] for c in con.execute("PRAGMA table_info(message)")]
            for row in con.execute("SELECT * FROM message").fetchall():
                rec = dict(zip(mcols, row, strict=True))
                data = json.loads(rec["data"])
                messages[rec["id"]] = {
                    "session": rec["session_id"],
                    "created": rec["time_created"],
                    "updated": rec.get("time_updated", rec["time_created"]),
                    "data": data,
                    "content": [],
                }
        if "part" in tables:
            for mid, sid, created, updated, raw in con.execute(
                "SELECT message_id, session_id, time_created, time_updated, data FROM part "
                "ORDER BY time_created, id"
            ).fetchall():
                try:
                    part = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                msg = messages.setdefault(
                    mid,
                    {"session": sid, "created": created, "updated": updated,
                     "data": {"role": "assistant"}, "content": []},
                )  # fmt: skip
                msg["created"] = min(msg["created"], created)
                msg["updated"] = max(msg["updated"], updated)
                if not isinstance(part, dict):
                    msg["content"].append(part)  # kept: the reader must survive it
                    continue
                item = _item(part)
                if item is not None:
                    msg["content"].append(item)
        for sid in {m["session"] for m in messages.values()} - set(sessions):
            sessions[sid] = (sid, None, None, None, "1.18.32", 0, 0)
        con.executemany("INSERT INTO session_v2 VALUES (?, ?, ?, ?, ?, ?, ?)", sessions.values())
        seq: dict[str, int] = {}
        ordered = sorted(messages.items(), key=lambda kv: (kv[1]["created"], kv[0]))
        for mid, msg in ordered:
            data = dict(msg["data"])
            role = data.pop("role", "assistant")
            model = {"id": data.pop("modelID", None), "providerID": data.pop("providerID", None)}
            if model["id"] is not None or model["providerID"] is not None:
                data["model"] = model
            data["content"] = msg["content"]
            n = seq.get(msg["session"], 0)
            seq[msg["session"]] = n + 1
            con.execute(
                "INSERT INTO session_message VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mid, msg["session"], role, n, msg["created"], msg["updated"], json.dumps(data)),
            )
        con.commit()
    return db
