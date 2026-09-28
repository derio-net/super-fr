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
`state.{status,input.command,output,metadata.exit,time.{start,end}}`, epoch ms;
`state.output` confirmed on 2026-09-27 for gh#719). Only
the columns the reader queries are created.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sqlite3
import time
from pathlib import Path

import pytest
from fr.artifacts.validate import validate_repo
from fr.harness.long_commands import LONG_COMMAND_RULES
from fr.run.telemetry import _detaches, orchestrator_wrote_since

from tests.unit.test_run_cli import _invoke_as_harness, _squash
from tests.unit.test_run_evidence_separate_context import _at_deliver

SINCE = "2026-09-26T10:00:00+00:00"


def _ms(iso: str) -> int:
    return int(_dt.datetime.fromisoformat(iso).timestamp() * 1000)


def _bash(
    command: str,
    start: int,
    *,
    status: str = "completed",
    exit_code: int = 0,
    output: str = "",
    duration: int = 5_000,
) -> str:
    return json.dumps(
        {
            "type": "tool",
            "tool": "bash",
            "callID": "call_x",
            "state": {
                "status": status,
                "input": {"command": command},
                "output": output,
                "metadata": {"exit": exit_code, "output": output, "truncated": False},
                "time": {"start": start, "end": start + duration},
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


@pytest.mark.parametrize(
    "parts",
    [
        pytest.param([], id="empty"),
        pytest.param(
            [("s-top", _bash(f"pytest > {LOG}", _ms(SINCE) - 3_600_000))], id="all-before-the-unit"
        ),
    ],
)
def test_a_database_that_saw_nothing_since_the_unit_opened_is_unobservable(
    tmp_path: Path, parts: list[tuple[str, str]]
) -> None:
    """gh#740: a READABLE database can still be the wrong one — the operator's
    global db when OpenCode wrote the run to `$XDG_DATA_HOME`. The calling
    orchestrator cannot be in a db that recorded no part since the unit opened
    (its own `fr run resolve` is one), so that is `None` — unobserved — never
    `[]`, which refuses a valid suite log as "no command of YOURS wrote it"."""
    db = _db(tmp_path / "o.db", parts)

    assert orchestrator_wrote_since(_env(db), LOG, SINCE) is None


def _detached(log: Path, cmd: str = "uv run pytest -n auto") -> str:
    """OpenCode's long-command rule, VERBATIM from the brief it rides
    (`fr.harness.long_commands`), with its `cmd` and `log` filled in — so a
    rewording of the rule that the gate cannot window turns this red."""
    shape = re.search(r"\(cmd;.*?log\.pid", LONG_COMMAND_RULES["opencode"])
    assert shape is not None, "the OpenCode rule no longer carries its detach form"
    return shape.group(0).replace("cmd", cmd).replace("log", str(log))


MINUTE = 60_000


def _dt_ms(ms: int) -> _dt.datetime:
    return _dt.datetime.fromtimestamp(ms / 1000, tz=_dt.UTC)


def _covers(windows: list[tuple[_dt.datetime, _dt.datetime]] | None, ms: int) -> bool:
    return windows is not None and any(s <= _dt_ms(ms) <= e for s, e in windows)


def test_a_detached_suite_is_windowed_until_the_orchestrator_sees_its_exit_line(
    tmp_path: Path,
) -> None:
    """gh#719: the rule's `&` returns at once, so the launch part alone is a
    zero-length window and the suite's real write (minutes later) fell outside
    it. OpenCode has no completion event; its record of a LATER bash part of
    the orchestrator's that names the log and printed `exit=0` is one."""
    db = _db(
        tmp_path / "o.db",
        [
            ("s-top", _bash(_detached(LOG), AFTER, duration=40)),
            ("s-top", _bash(f"tail -3 {LOG}", AFTER + 5 * MINUTE, output="12 passed\n")),
            ("s-top", _bash(f"tail -3 {LOG}", AFTER + 12 * MINUTE, output="5458 passed\nexit=0\n")),
        ],
    )

    windows = orchestrator_wrote_since(_env(db), LOG, SINCE)

    assert _covers(windows, AFTER + 11 * MINUTE), windows
    assert not _covers(windows, AFTER + 13 * MINUTE), "the window outlived what it saw"


@pytest.mark.parametrize(
    "observation",
    [
        pytest.param(None, id="never-observed"),
        pytest.param(("s-top", f"tail -3 {LOG}", "1 failed\nexit=1\n"), id="the-suite-failed"),
        pytest.param(("s-child", f"tail -3 {LOG}", "exit=0\n"), id="a-subagent-saw-it"),
        pytest.param(("s-top", "tail -3 other.log", "exit=0\n"), id="another-log"),
        pytest.param(("s-top", f"tail -3 {LOG}", "still running\n"), id="no-exit-line"),
    ],
)
def test_a_detached_suite_without_a_seen_exit_0_is_not_windowed_past_its_launch(
    tmp_path: Path, observation: tuple[str, str, str] | None
) -> None:
    parts = [("s-top", _bash(_detached(LOG), AFTER, duration=40))]
    if observation is not None:
        sid, command, output = observation
        parts.append((sid, _bash(command, AFTER + 12 * MINUTE, output=output)))
    db = _db(tmp_path / "o.db", parts)

    windows = orchestrator_wrote_since(_env(db), LOG, SINCE)

    assert windows is not None
    assert not _covers(windows, AFTER + 11 * MINUTE), windows


def test_the_first_exit_line_the_orchestrator_saw_is_final(tmp_path: Path) -> None:
    """A later `exit=0` (a rerun's, or forged into the log) can neither revive
    a suite the orchestrator saw fail nor stretch a window it already closed —
    the same rule the Claude Code reader applies to task notices."""
    db = _db(
        tmp_path / "o.db",
        [
            ("s-top", _bash(_detached(LOG), AFTER, duration=40)),
            ("s-top", _bash(f"tail -1 {LOG}", AFTER + 12 * MINUTE, output="exit=1\n")),
            ("s-top", _bash(f"tail -1 {LOG}", AFTER + 20 * MINUTE, output="exit=0\n")),
        ],
    )

    windows = orchestrator_wrote_since(_env(db), LOG, SINCE)

    assert not _covers(windows, AFTER + 11 * MINUTE), windows
    assert not _covers(windows, AFTER + 19 * MINUTE), windows


def test_a_foreground_write_is_not_stretched_by_a_later_exit_line(tmp_path: Path) -> None:
    """Only a DETACHED writer waits for an exit line; a foreground one's own
    end is its end, so a later `cat` cannot reopen its window."""
    db = _db(
        tmp_path / "o.db",
        [
            ("s-top", _bash(f"pytest > {LOG} 2>&1", AFTER)),
            ("s-top", _bash(f"cat {LOG}", AFTER + 12 * MINUTE, output="exit=0\n")),
        ],
    )

    windows = orchestrator_wrote_since(_env(db), LOG, SINCE)

    assert not _covers(windows, AFTER + 11 * MINUTE), windows


def test_on_opencode_a_detached_suite_the_orchestrator_saw_finish_is_accepted(
    tmp_path: Path,
) -> None:
    """End to end, the #719 shape: launched as the unit opens, finished a
    minute later, its `exit=0` read back a minute after that."""
    repo, shipped, opened = _at_deliver(tmp_path)
    log = repo / "full-suite.log"
    log.write_text("5458 passed\nexit=0\n")
    start = _ms(opened)
    os.utime(log, (start / 1000 + 60, start / 1000 + 60))
    db = _db(
        tmp_path / "o.db",
        [
            ("s-top", _bash(_detached(log), start, duration=40)),
            ("s-top", _bash(f"tail -2 {log}", start + 2 * MINUTE, output="5458 passed\nexit=0\n")),
        ],
    )

    result = _opencode_deliver(repo, shipped, db, "tests=full-suite.log")

    assert result.exit_code == 0, result.output
    assert "could not verify" not in _squash(result.stderr)


def test_on_opencode_an_unobserved_detached_suite_says_how_to_close_it(tmp_path: Path) -> None:
    repo, shipped, opened = _at_deliver(tmp_path)
    log = repo / "full-suite.log"
    log.write_text("5458 passed\nexit=0\n")
    start = _ms(opened)
    os.utime(log, (start / 1000 + 60, start / 1000 + 60))
    db = _db(tmp_path / "o.db", [("s-top", _bash(_detached(log), start, duration=40))])

    result = _opencode_deliver(repo, shipped, db, "tests=full-suite.log")

    assert result.exit_code == 2, result.output
    assert "exit=0" in _squash(result.output)


def _opencode_deliver(repo: Path, shipped: Path, db: Path, *evidence: str):
    extra = [x for e in evidence for x in ("--evidence", e)]
    argv = ["run", "resolve", "r1", "--step", "deliver", "--state", "done", *extra]
    return _invoke_as_harness(
        repo, shipped, argv, {"FR_HARNESS": "opencode", "FR_OPENCODE_DB": str(db)}
    )


def test_on_opencode_an_agent_written_log_is_refused(tmp_path: Path) -> None:
    """The #638 shape: the log exists and is fresh, but no bash command of the
    orchestrator's wrote it (the agent composed it with its edit tool)."""
    repo, shipped, opened = _at_deliver(tmp_path)
    time.sleep(0.01)
    (repo / "full-suite.log").write_text("Result: 5,458 passed, 1 failed\n")
    db = _db(tmp_path / "o.db", [("s-top", _bash("git status", _ms(opened)))])

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


def test_on_opencode_the_suite_log_is_found_under_xdg_data_home(tmp_path: Path) -> None:
    """gh#740's run, end to end: OpenCode started with `XDG_DATA_HOME` set and
    no `FR_OPENCODE_DB`, so its sessions are in `$XDG_DATA_HOME/opencode/`. The
    orchestrator's own redirect is found there and `deliver` resolves."""
    repo, shipped, opened = _at_deliver(tmp_path)
    log = repo / "full-suite.log"
    log.write_text("5458 passed\n")
    start = _ms(opened)
    data = tmp_path / "xdg-data"
    (data / "opencode").mkdir(parents=True)
    _db(data / "opencode" / "opencode.db", [("s-top", _bash(f"uv run pytest > {log}", start))])
    argv = ["run", "resolve", "r1", "--step", "deliver", "--state", "done"]
    env = {
        "FR_HARNESS": "opencode",
        "FR_OPENCODE_DB": None,
        "XDG_DATA_HOME": str(data),
        "HOME": str(tmp_path / "home"),
    }

    result = _invoke_as_harness(repo, shipped, [*argv, "--evidence", "tests=full-suite.log"], env)

    assert result.exit_code == 0, result.output
    assert "could not verify" not in _squash(result.stderr)


def test_on_opencode_a_database_without_the_run_does_not_refuse_the_log(tmp_path: Path) -> None:
    """The wrong database (here: one whose last part is an hour before the unit
    opened) degrades to the fresh-file check with a warning — it is not proof
    that nobody wrote the log."""
    repo, shipped, opened = _at_deliver(tmp_path)
    time.sleep(0.01)
    (repo / "full-suite.log").write_text("5458 passed\n")
    db = _db(tmp_path / "o.db", [("s-top", _bash("git status", _ms(opened) - 3_600_000))])

    result = _opencode_deliver(repo, shipped, db, "tests=full-suite.log")

    assert result.exit_code == 0, result.output
    assert "unverified" in _squash(result.stderr)


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


@pytest.mark.parametrize(
    ("harness", "said"),
    [
        pytest.param(
            "hermes", "unsupported on hermes (parity row deliver-tests-provenance)", id="hermes"
        ),
        pytest.param("opencode", "OpenCode session database could not be read", id="opencode"),
    ],
)
def test_an_unverifiable_log_says_why_by_harness(tmp_path: Path, harness: str, said: str) -> None:
    """Hermes is declared `unsupported` for this check (operator decision
    2026-09-26): the log is recorded unverified and the warning names the
    parity row, not a missing reader."""
    repo, shipped, _ = _at_deliver(tmp_path)
    time.sleep(0.01)
    (repo / "full-suite.log").write_text("ok\n")
    argv = ["run", "resolve", "r1", "--step", "deliver", "--state", "done"]
    env = {"FR_HARNESS": harness, "FR_OPENCODE_DB": str(tmp_path / "absent.db")}

    result = _invoke_as_harness(repo, shipped, [*argv, "--evidence", "tests=full-suite.log"], env)

    assert result.exit_code == 0, result.output
    assert said in _squash(result.stderr)
    assert "unverified" in _squash(result.stderr)


@pytest.mark.parametrize(
    ("command", "detached"),
    [
        pytest.param(_detached(LOG), True, id="the-rule"),
        pytest.param(f"pytest > {LOG} 2>&1", False, id="stderr-dup"),
        pytest.param(f"pytest &> {LOG}", False, id="amp-redirect"),
        pytest.param(f"cd x && pytest > {LOG}", False, id="and-chain"),
        pytest.param(f"pytest |& tee {LOG}", False, id="pipe-both"),
        pytest.param(f"echo 'a & b' > {LOG}", False, id="quoted"),
    ],
)
def test_only_a_lone_ampersand_detaches(command: str, detached: bool) -> None:
    assert _detaches(command) is detached
