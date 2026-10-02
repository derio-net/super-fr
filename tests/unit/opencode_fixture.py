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
