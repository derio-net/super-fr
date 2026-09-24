"""`OpenCodeReader` — main-session usage from OpenCode's session database
(spec `2026-09-24-fr-goal-scope-proportion-cost-design.md` §D).

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
from fr.run.model import MainSessionUsage
from fr.run.telemetry import OpenCodeReader, SessionUsage, reader_for

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


EXPECTED_ONE = SessionUsage(
    input_tokens=11,
    cache_creation_input_tokens=44,
    cache_read_input_tokens=330,
    output_tokens=20 + 5 + 2,  # reasoning folded into output
    turns=2,
    cost_usd=0.75,
)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return _db(tmp_path / "opencode.db", tmp_path / "ws", tmp_path / "base")


def _env(db: Path) -> dict[str, str]:
    return {"FR_HARNESS": "opencode", "FR_OPENCODE_DB": str(db)}


def test_opencode_has_a_reader() -> None:
    assert isinstance(reader_for("opencode"), OpenCodeReader)


def test_one_session_is_summed_with_reasoning_folded_into_output(db: Path) -> None:
    assert OpenCodeReader().measure_main_session(db, "s-bound", START, END) == EXPECTED_ONE


def test_a_bound_session_is_measured(db: Path, tmp_path: Path) -> None:
    got = OpenCodeReader().measure_step(
        _env(db), ["s-bound"], START, END, directories=[tmp_path / "ws"]
    )
    assert got == MainSessionUsage(
        input_tokens=11,
        cache_creation_input_tokens=44,
        cache_read_input_tokens=330,
        output_tokens=27,
        turns=2,
        sessions=1,
        cost_usd=0.75,
    )


def test_an_unknown_bound_session_is_unreadable(db: Path, tmp_path: Path) -> None:
    assert (
        OpenCodeReader().measure_step(_env(db), ["nope"], START, END, directories=[tmp_path])
        is None
    )


def test_unbound_the_unique_top_level_session_in_the_workspace_is_measured(
    db: Path, tmp_path: Path
) -> None:
    got = OpenCodeReader().measure_step(_env(db), [], START, END, directories=[tmp_path / "ws"])
    assert got is not None and got.sessions == 1 and got.turns == 2


def test_unbound_two_qualifying_sessions_record_nothing(db: Path, tmp_path: Path) -> None:
    got = OpenCodeReader().measure_step(
        _env(db), [], START, END, directories=[tmp_path / "ws", tmp_path / "base"]
    )
    assert got is None, "two candidates is ambiguous — never a guess"


def test_a_child_session_is_never_a_candidate(db: Path, tmp_path: Path) -> None:
    """`s-child` sits in the workspace too; were it counted, the workspace
    alone would be ambiguous and this would be `None`."""
    assert OpenCodeReader().candidate_sessions(db, [tmp_path / "ws"], START, END) == ["s-bound"]


def test_a_session_with_nothing_in_the_window_does_not_qualify(db: Path, tmp_path: Path) -> None:
    later = ("2026-09-24T11:00:00+00:00", "2026-09-24T12:00:00+00:00")
    assert OpenCodeReader().candidate_sessions(db, [tmp_path / "ws"], *later) == []


def test_a_missing_database_is_no_measurement(tmp_path: Path) -> None:
    env = _env(tmp_path / "absent.db")
    assert OpenCodeReader().measure_step(env, ["s-bound"], START, END, directories=[]) is None
    assert not (tmp_path / "absent.db").exists(), "read-only: a missing DB is never created"


def test_the_database_path_honours_the_override(db: Path) -> None:
    assert OpenCodeReader().database(_env(db)) == db
    assert OpenCodeReader().database({}).name == "opencode.db"


def test_dispatch_measurement_stays_none(db: Path) -> None:
    reader = OpenCodeReader()
    assert reader.locate_session(_env(db)) is None
    assert reader.measure(db, agent=None, start=START, end=END, same_session=True) is None


def test_the_parity_matrix_declares_main_session_cost() -> None:
    """Spec §D: claude-code enforced, opencode partial (not live-proven),
    hermes absent (no reader)."""
    from fr.harness import load_matrix

    (row,) = [s for s in load_matrix().surfaces if s.id == "main-session-cost"]
    assert row.kind == "interaction"
    states = {name: cell.state for name, cell in row.harnesses.items()}
    assert states == {
        "claude-code": "enforced",
        "opencode": "partial",
        "hermes": "absent",
        "codex": "unsupported",
        "copilot-cli": "unsupported",
    }
