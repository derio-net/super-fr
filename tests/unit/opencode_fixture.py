"""The committed OpenCode run-tree fixture (`tests/fixtures/usage/opencode/`,
built by its `build.py`), and a copy of it moved in time.

A resolve-level gate reads only what happened since its unit opened — "now",
in a CLI test — while the fixture's clock is fixed. `shifted` copies the
database and moves EVERY timestamp by one offset (the `session`, `message` and
`part` rows' columns and the `state.time.{start,end}` inside `part.data`), so
the run tree starts at a chosen instant. Nothing else is edited: the shapes
stay the capture's.
"""

from __future__ import annotations

import datetime as _dt
import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

DB = Path(__file__).parents[1] / "fixtures" / "usage" / "opencode" / "opencode.db"
T0 = 1790328511802
TR = T0 + 3_600_000
"""When the run tree (`ses_run` and its children) starts, epoch ms."""


def shifted(tmp_path: Path, starts_at: _dt.datetime) -> Path:
    """A copy of the fixture whose run tree starts at `starts_at`."""
    delta = int(starts_at.timestamp() * 1000) - TR
    db = tmp_path / "opencode-shifted.db"
    shutil.copy(DB, db)
    with closing(sqlite3.connect(db)) as con:
        con.execute("UPDATE session SET time_created = time_created + ?", (delta,))
        con.execute(
            "UPDATE message SET time_created = time_created + ?, time_updated = time_updated + ?",
            (delta, delta),
        )
        rows = con.execute("SELECT id, data FROM part").fetchall()
        for part_id, raw in rows:
            data = json.loads(raw)
            times = data.get("state", {}).get("time") if isinstance(data, dict) else None
            if isinstance(times, dict):
                for key in ("start", "end"):
                    if isinstance(times.get(key), int):
                        times[key] += delta
            con.execute(
                "UPDATE part SET data = ?, time_created = time_created + ?, "
                "time_updated = time_updated + ? WHERE id = ?",
                (json.dumps(data), delta, delta, part_id),
            )
        con.commit()
    return db


def opencode_env(db: Path, session: str | None = "ses_run") -> dict[str, str | None]:
    """The environment of an OpenCode `bash` call the super-fr plugin exported
    `session` into (`None`: the plugin is absent)."""
    return {
        "FR_HARNESS": "opencode",
        "FR_OPENCODE_DB": str(db),
        "FR_OPENCODE_SESSION_ID": session,
        "CLAUDE_CODE_SESSION_ID": None,
    }


def with_copied_child(db: Path, source: str, new: str) -> Path:
    """`db` with a second child session `new`, dispatched exactly as `source`
    was (its `session` row and its dispatching `task` part, re-keyed). Edits
    the copy in place — pass a `shifted` copy, never `DB`."""
    assert db != DB
    with closing(sqlite3.connect(db)) as con:
        (parent, directory, title, created) = con.execute(
            "SELECT parent_id, directory, title, time_created FROM session WHERE id = ?",
            (source,),
        ).fetchone()
        con.execute(
            "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
            (new, parent, directory, f"{title} (copy)", created),
        )
        for part_id, message_id, session, t_created, t_updated, raw in con.execute(
            "SELECT id, message_id, session_id, time_created, time_updated, data FROM part"
        ).fetchall():
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("tool") != "task":
                continue
            meta = data.get("state", {}).get("metadata", {})
            if meta.get("sessionId") != source:
                continue
            meta["sessionId"] = new
            data["callID"] = f"{data.get('callID', 'call')}-copy"
            con.execute(
                "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
                (f"{part_id}_copy", message_id, session, t_created, t_updated, json.dumps(data)),
            )
        con.commit()
    return db


def with_resumed_child(db: Path, source: str) -> Path:
    """`db` with `source`'s dispatching `task` part repeated a second later — the
    orchestrator sending the same child back (OpenCode resumes a task by
    session). Edits the copy in place — pass a `shifted` copy, never `DB`."""
    assert db != DB
    with closing(sqlite3.connect(db)) as con:
        for part_id, message_id, session, t_created, t_updated, raw in con.execute(
            "SELECT id, message_id, session_id, time_created, time_updated, data FROM part"
        ).fetchall():
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("tool") != "task":
                continue
            state = data.get("state", {})
            if state.get("metadata", {}).get("sessionId") != source:
                continue
            data["callID"] = f"{data.get('callID', 'call')}-resume"
            for key in ("start", "end"):
                if isinstance(state.get("time", {}).get(key), int):
                    state["time"][key] += 1000
            con.execute(
                "INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)",
                (f"{part_id}_resume", message_id, session, t_created + 1000, t_updated + 1000,
                 json.dumps(data)),
            )  # fmt: skip
        con.commit()
    return db
