"""`fr usage backfill` — usage files for runs archived before usage existed
(spec `2026-09-25-lean-cost-aware-process-design.md` §5.B.5).

Run by the operator. It READS every archived run cursor
(`docs/superpowers/implemented/runs/*.yaml`, any version) and whatever
transcripts are still on this host, and writes a NEW
`implemented/usage/<run>.yaml` with one `at: backfill` capture. It never
writes a run cursor — archived artifacts are frozen history.

An archived run that already has a usage file is left alone, with one
exception (gh#756): a session this host captured with tokens but no dollars,
because it was still open when the capture ran (Claude Code writes a
session's cost only when it exits), is re-read, and replaced when the reading
now carries dollars. `backfill` is appended to that capture's `at`. A reading
that is unavailable or still unpriced changes nothing, so re-running is a
no-op once every session is priced.

Per run: when any session the cursor names is readable here, the capture is
those sessions, read (exact dollars where the harness keeps them). When none
is, the cursor's own figures — a v5/v6 attempt's `estimate`/`measured`, a
step's `main_session`, or a v1-v4 `accounting` map — are carried instead, with
`usd_source: none`, beside the sessions that could not be read.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from fr.usage.file import (
    NO_SESSION_FOUND,
    Capture,
    SessionEntry,
    UsageFile,
    archived_usage_path,
    current_usage_schema_version,
    dump_usage,
    load_usage,
    session_entry,
    units_by_agent,
    upsert_capture,
    usage_path,
)
from fr.usage.model import unavailable
from fr.usage.rollup import windows_from_cursor
from fr.usage.sources import read_session, sessions_of

ARCHIVED_RUNS_REL = Path("docs") / "superpowers" / "implemented" / "runs"


@dataclass
class BackfillReport:
    written: list[Path] = field(default_factory=list)
    refreshed: list[Path] = field(default_factory=list)
    """Archived usage files whose unpriced sessions now carry dollars."""
    skipped: list[str] = field(default_factory=list)
    """Runs that already had a usage file, left as they were."""
    failed: list[tuple[str, str]] = field(default_factory=list)


def _cursor_figures(raw: dict[str, Any]) -> list[SessionEntry]:
    """The figures a cursor itself kept, as usage entries — `[]` when none."""
    from fr.artifacts.run_usage_split import split_usage
    from fr.run.legacy import v4_to_v5

    data = raw
    if not any(isinstance(r, dict) and "units" in r for r in (raw.get("steps") or {}).values()):
        data = v4_to_v5(raw)
    _body, entries = split_usage(data)
    return entries


def _entries(raw: dict[str, Any], env: Mapping[str, str]) -> list[SessionEntry]:
    windows = windows_from_cursor(raw)
    units = units_by_agent(raw)
    read: list[SessionEntry] = []
    for harness, session in dict.fromkeys(sessions_of(raw)):
        try:
            record = read_session(harness, session, env)
        except Exception as e:  # noqa: BLE001 — one bad reader is one unavailable session
            record = unavailable(session, harness, f"reader failed: {type(e).__name__}")
        read.append(session_entry(record, windows, rekey=units))
    if any(e.unavailable is None for e in read):
        return read
    entries = _cursor_figures(raw) + read
    if not entries:
        # a cursor naming no session and keeping no figure: say so, never `[]` (#636)
        entries = [session_entry(unavailable("", _harness(raw), NO_SESSION_FOUND))]
    return entries


def _harness(raw: dict[str, Any]) -> str:
    return next((h for h, _ in sessions_of(raw)), "unknown")


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat()


def refreshed_file(
    usage: UsageFile, raw: dict[str, Any], env: Mapping[str, str]
) -> UsageFile | None:
    """`usage` with this host's unpriced sessions re-read, or `None` when no
    reading now carries dollars (gh#756). Only this host's capture: one host
    never rewrites another's entry. Never trades a reading for an absence."""
    from fr.usage.capture import this_host, unpriced_sessions

    mine = usage.host(this_host(usage.run, env))
    stale = set(unpriced_sessions(mine)) if mine is not None else set()
    if mine is None or not stale:
        return None
    harness_of = {session: harness for harness, session in sessions_of(raw)}
    windows, units = windows_from_cursor(raw), units_by_agent(raw)
    sessions: list[SessionEntry] = []
    for entry in mine.sessions:
        if entry.session in stale:
            harness = harness_of.get(entry.session, mine.harness)
            try:
                record = read_session(harness, entry.session, env)
            except Exception:  # noqa: BLE001 — an unreadable session stays as recorded
                record = None
            if record is not None and record.unavailable is None and record.cost.usd is not None:
                entry = session_entry(record, windows, rekey=units)
        sessions.append(entry)
    if tuple(sessions) == mine.sessions:
        return None
    at = mine.at if "backfill" in mine.at else (*mine.at, "backfill")
    return upsert_capture(
        usage,
        mine.model_copy(update={"sessions": tuple(sessions), "at": at, "captured_at": _now()}),
    )


def backfill(repo_root: Path, env: Mapping[str, str]) -> BackfillReport:
    from fr.artifacts.atomic import write_text_atomic
    from fr.usage.capture import this_host

    report = BackfillReport()
    runs = repo_root / ARCHIVED_RUNS_REL
    for cursor in sorted(runs.glob("*.yaml")) if runs.is_dir() else ():
        run_id = cursor.stem
        target = archived_usage_path(repo_root, run_id)
        if target.exists():
            try:
                raw = yaml.safe_load(cursor.read_text())
                usage = load_usage(target)
                fresh = (
                    refreshed_file(usage, raw, env)
                    if usage is not None and isinstance(raw, dict)
                    else None
                )
            except Exception as e:  # noqa: BLE001 — one unreadable run is that run's failure
                report.failed.append((run_id, f"{type(e).__name__}: {e}"))
                continue
            if fresh is None:
                report.skipped.append(run_id)
            else:
                write_text_atomic(target, dump_usage(fresh))
                report.refreshed.append(target)
            continue
        if usage_path(repo_root, run_id).exists():
            report.skipped.append(run_id)
            continue
        try:
            raw = yaml.safe_load(cursor.read_text())
            if not isinstance(raw, dict):
                raise ValueError("not a run cursor")
            capture = Capture(
                host=this_host(run_id, env),
                harness=_harness(raw),
                mode="host-worktree",
                captured_at=_now(),
                at=("backfill",),
                sessions=tuple(_entries(raw, env)),
            )
            text = dump_usage(
                UsageFile(
                    schema_version=current_usage_schema_version(), run=run_id, captures=(capture,)
                )
            )
        except Exception as e:  # noqa: BLE001 — one unreadable run is that run's failure
            report.failed.append((run_id, f"{type(e).__name__}: {e}"))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(target, text)
        report.written.append(target)
    return report


__all__ = ["ARCHIVED_RUNS_REL", "BackfillReport", "backfill", "refreshed_file"]
