"""An OpenCode 2 store whose run tree starts just before a lens review opened, with
the two `general` children's returns rewritten (review-lenses-reviewer-return-checked).

Usage: lens-review-session.py <out-dir> <opened ISO timestamp> [<child>=<return file> ...]
Prints the path of the store. The store is the committed capture
(tests/fixtures/usage/opencode/opencode.db) moved in time by
`tests.unit.opencode_fixture.shifted`; only the children's returns are edited, the
same edit `tests/unit/test_run_review_return_resolve.py` makes.
"""

from __future__ import annotations

import datetime as _dt
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tests.unit.opencode_fixture import shifted  # noqa: E402
from tests.unit.opencode_v2 import to_v2  # noqa: E402


def set_return(db: Path, child: str, text: str) -> None:
    with closing(sqlite3.connect(db)) as con:
        for pid, raw in con.execute("SELECT id, data FROM part").fetchall():
            data = json.loads(raw)
            if not isinstance(data, dict):
                continue
            mine = con.execute(
                "SELECT 1 FROM part WHERE id=? AND session_id=?", (pid, child)
            ).fetchone()
            if data.get("type") == "text" and mine:
                con.execute("DELETE FROM part WHERE id=?", (pid,))
                continue
            state = data.get("state") or {}
            if data.get("tool") == "task" and state.get("metadata", {}).get("sessionId") == child:
                state["output"] = (
                    f'<task id="{child}" state="completed"><task_result>{text}</task_result></task>'
                )
                con.execute("UPDATE part SET data=? WHERE id=?", (json.dumps(data), pid))
        con.commit()
    to_v2(db)


def main(argv: list[str]) -> None:
    out, opened, *returns = argv
    start = _dt.datetime.fromisoformat(opened)
    db = shifted(Path(out), start - _dt.timedelta(seconds=100))
    for pair in returns:
        child, _, path = pair.partition("=")
        set_return(db, child, Path(path).read_text())
    print(db)


if __name__ == "__main__":
    main(sys.argv[1:])
