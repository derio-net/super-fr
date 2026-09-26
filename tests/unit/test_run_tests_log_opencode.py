"""`deliver`'s `tests=<log>` gate on OpenCode, and where the log may live (gh#638).

Run `2026-09-26-fix-models-opencode-noop-505` resolved `deliver` on OpenCode
with an 8-line prose file the agent wrote itself — a file that reported a
failing test. `orchestrator_wrote_since` had a Claude Code reader only, so on
OpenCode the gate degraded to "a fresh, non-empty file exists". The same run
(and `2026-09-26-fix-659-isolation-gc-fetch`) committed its logs under
`<run>.records/`, a directory fr owns and empties, and they reached `main`.

The fixture database uses the REAL column names and `part.data` shape of a
`bash` tool part, read on 2026-09-26 from a live
`~/.local/share/opencode/opencode.db` with `sqlite3 -readonly` (`.schema
session`, `.schema part`, and one bash part's keys: `type`, `tool`,
`state.{status,input.command,metadata.exit,time.{start,end}}`, epoch ms). Only
the columns the reader queries are created.
"""

from __future__ import annotations

import datetime as _dt
import json
import sqlite3
import time
from pathlib import Path

import pytest
from fr.artifacts.validate import validate_repo
from fr.run.telemetry import orchestrator_wrote_since

from tests.unit.test_run_cli import _invoke_as_harness, _squash
from tests.unit.test_run_evidence_separate_context import _at_deliver

SINCE = "2026-09-26T10:00:00+00:00"


def _ms(iso: str) -> int:
    return int(_dt.datetime.fromisoformat(iso).timestamp() * 1000)


def _bash(command: str, start: int, *, status: str = "completed", exit_code: int = 0) -> str:
    return json.dumps(
        {
            "type": "tool",
            "tool": "bash",
            "callID": "call_x",
            "state": {
                "status": status,
                "input": {"command": command},
                "metadata": {"exit": exit_code},
                "time": {"start": start, "end": start + 5_000},
            },
        }
    )


def _db(path: Path, parts: list[tuple[str, str]], *, session_updated: int | None = None) -> Path:
    """`parts` is `(session id, part data)`; `s-top` is top-level, `s-child`
    a `task` subagent of it (`parent_id` set)."""
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE session (id TEXT PRIMARY KEY, parent_id TEXT, time_updated INTEGER NOT NULL)"
    )
    con.execute(
        "CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT NOT NULL, "
        "session_id TEXT NOT NULL, time_created INTEGER NOT NULL, "
        "time_updated INTEGER NOT NULL, data TEXT NOT NULL)"
    )
    now = session_updated if session_updated is not None else int(time.time() * 1000) + 3_600_000
    con.executemany(
        "INSERT INTO session VALUES (?, ?, ?)",
        [("s-top", None, now), ("s-child", "s-top", now)],
    )
    rows = []
    for i, (sid, data) in enumerate(parts):
        start = json.loads(data)["state"]["time"]["start"]
        rows.append((f"p{i}", f"m{i}", sid, start, start + 5_000, data))
    con.executemany("INSERT INTO part VALUES (?, ?, ?, ?, ?, ?)", rows)
    con.commit()
    con.close()
    return path


def _env(db: Path) -> dict[str, str]:
    return {"FR_HARNESS": "opencode", "FR_OPENCODE_DB": str(db)}


LOG = Path("/work/repo/suite.log")
AFTER = _ms(SINCE) + 60_000


def test_a_top_level_bash_command_that_wrote_the_log_is_a_window(tmp_path: Path) -> None:
    db = _db(tmp_path / "o.db", [("s-top", _bash(f"uv run pytest > {LOG} 2>&1", AFTER))])

    windows = orchestrator_wrote_since(_env(db), LOG, SINCE)

    assert windows is not None and len(windows) == 1
    start, end = windows[0]
    assert start == _dt.datetime.fromtimestamp(AFTER / 1000, tz=_dt.UTC)
    assert (end - start).total_seconds() == 5


@pytest.mark.parametrize(
    ("sid", "data"),
    [
        pytest.param("s-child", _bash(f"pytest > {LOG}", AFTER), id="a-subagent-ran-it"),
        pytest.param("s-top", _bash(f"pytest > {LOG}", AFTER, exit_code=1), id="it-failed"),
        pytest.param("s-top", _bash(f"pytest > {LOG}", AFTER, status="error"), id="errored"),
        pytest.param("s-top", _bash(f"pytest > {LOG}", _ms(SINCE) - 1), id="before-the-unit"),
        pytest.param("s-top", _bash(f"cat {LOG}", AFTER), id="only-read-it"),
    ],
)
def test_nothing_else_counts_as_the_orchestrator_writing_the_log(
    tmp_path: Path, sid: str, data: str
) -> None:
    """Readable, and no qualifying command: `[]` — a refusal, never `None`
    (which would degrade to "unverified" and pass)."""
    db = _db(tmp_path / "o.db", [(sid, data)])

    assert orchestrator_wrote_since(_env(db), LOG, SINCE) == []


def test_a_session_row_last_touched_before_the_unit_does_not_hide_its_parts(
    tmp_path: Path,
) -> None:
    """Review: nothing shows OpenCode bumps `session.time_updated` on every
    part, so the reader must not filter on it — a stale session row next to a
    fresh bash part is still the orchestrator writing the log."""
    db = _db(
        tmp_path / "o.db",
        [("s-top", _bash(f"pytest > {LOG}", AFTER))],
        session_updated=_ms(SINCE) - 3_600_000,
    )

    windows = orchestrator_wrote_since(_env(db), LOG, SINCE)

    assert windows is not None and len(windows) == 1


def test_an_unreadable_opencode_database_is_unobservable(tmp_path: Path) -> None:
    assert orchestrator_wrote_since(_env(tmp_path / "absent.db"), LOG, SINCE) is None


def _opencode_deliver(repo: Path, shipped: Path, db: Path, *evidence: str):
    extra = [x for e in evidence for x in ("--evidence", e)]
    argv = ["run", "resolve", "r1", "--step", "deliver", "--state", "done", *extra]
    return _invoke_as_harness(
        repo, shipped, argv, {"FR_HARNESS": "opencode", "FR_OPENCODE_DB": str(db)}
    )


def test_on_opencode_an_agent_written_log_is_refused(tmp_path: Path) -> None:
    """The #638 shape: the log exists and is fresh, but no bash command of the
    orchestrator's wrote it (the agent composed it with its edit tool)."""
    repo, shipped, _ = _at_deliver(tmp_path)
    time.sleep(0.01)
    (repo / "full-suite.log").write_text("Result: 5,458 passed, 1 failed\n")
    db = _db(tmp_path / "o.db", [("s-top", _bash("git status", AFTER))])

    result = _opencode_deliver(repo, shipped, db, "tests=full-suite.log")

    assert result.exit_code == 2, result.output
    assert "no command of YOURS wrote it" in _squash(result.output)


def test_on_opencode_a_log_the_orchestrator_wrote_is_accepted(tmp_path: Path) -> None:
    repo, shipped, opened = _at_deliver(tmp_path)
    log = repo / "full-suite.log"
    log.write_text("5458 passed\n")
    # The command starts as the unit opens and runs 5 s, which the log's mtime
    # (moments later) falls inside.
    start = _ms(opened)
    assert start <= log.stat().st_mtime * 1000 <= start + 5_000
    db = _db(tmp_path / "o.db", [("s-top", _bash(f"uv run pytest > {log}", start))])

    result = _opencode_deliver(repo, shipped, db, "tests=full-suite.log")

    assert result.exit_code == 0, result.output
    assert "could not verify" not in _squash(result.stderr)


def test_a_tests_log_inside_the_runs_records_dir_is_refused(tmp_path: Path) -> None:
    """`<run>.records/` holds step records and fr's own pr-body render, and fr
    empties it; a log written there was committed and reached `main` twice."""
    repo, shipped, _ = _at_deliver(tmp_path)
    records = repo / "docs" / "superpowers" / "runs" / "r1.records"
    records.mkdir(parents=True, exist_ok=True)
    time.sleep(0.01)
    (records / "full-suite.log").write_text("ok\n")

    result = _opencode_deliver(
        repo,
        shipped,
        tmp_path / "absent.db",
        "tests=docs/superpowers/runs/r1.records/full-suite.log",
    )

    assert result.exit_code == 2, result.output
    assert "records" in _squash(result.output)
    assert "outside the repo" in _squash(result.output)


@pytest.mark.parametrize(
    ("rel", "refused"),
    [
        pytest.param("docs/superpowers/runs/r1.records/out/full-suite.log", True, id="nested"),
        pytest.param("build/coverage.records/full-suite.log", False, id="unrelated-dir"),
    ],
)
def test_the_records_refusal_matches_exactly_the_runs_records_dirs(
    tmp_path: Path, rel: str, refused: bool
) -> None:
    """Review: the same scope `fr validate artifacts` checks — any depth under
    `docs/superpowers/runs/*.records/`, and nothing else named `.records`."""
    repo, shipped, _ = _at_deliver(tmp_path)
    log = repo / rel
    log.parent.mkdir(parents=True, exist_ok=True)
    time.sleep(0.01)
    log.write_text("ok\n")

    result = _opencode_deliver(repo, shipped, tmp_path / "absent.db", f"tests={rel}")

    assert ("records dir" in _squash(result.output)) is refused, result.output


def test_validate_flags_a_file_in_a_records_dir_that_is_not_a_record(tmp_path: Path) -> None:
    records = tmp_path / "docs" / "superpowers" / "runs" / "r1.records"
    records.mkdir(parents=True)
    (records / "full-suite.log").write_text("ok\n")
    (records / "pr-body.md").write_text("fr's own render\n")

    report = validate_repo(tmp_path)

    flagged = [i for i in report.issues if i.path.name == "full-suite.log"]
    assert len(flagged) == 1, report.issues
    assert "not a step record" in flagged[0].message
    assert not [i for i in report.issues if i.path.name == "pr-body.md"]
    assert validate_repo(tmp_path, kind_name="record").issues == report.issues


def test_this_repos_records_dirs_hold_only_records() -> None:
    """The two logs #638 found on `main` are gone, and stay gone."""
    root = Path(__file__).resolve().parents[2]
    stray = [
        p
        for d in (root / "docs" / "superpowers" / "runs").glob("*.records")
        for p in d.iterdir()
        if p.suffix != ".yaml" and p.name != "pr-body.md"
    ]
    assert stray == []
