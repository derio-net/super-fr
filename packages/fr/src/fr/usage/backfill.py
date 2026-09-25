"""`fr usage backfill` — usage files for runs archived before usage existed
(spec `2026-09-25-lean-cost-aware-process-design.md` §5.B.5).

Run once by the operator. It READS every archived run cursor
(`docs/superpowers/implemented/runs/*.yaml`, any version) and whatever
transcripts are still on this host, and writes a NEW
`implemented/usage/<run>.yaml` with one `at: backfill` capture. It never
writes a run cursor — archived artifacts are frozen history — and it never
touches a run that already has a usage file, so re-running is a no-op.

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
    Capture,
    SessionEntry,
    UsageFile,
    archived_usage_path,
    dump_usage,
    session_entry,
    units_by_agent,
    usage_path,
)
from fr.usage.model import unavailable
from fr.usage.rollup import windows_from_cursor
from fr.usage.sources import read_session, sessions_of

ARCHIVED_RUNS_REL = Path("docs") / "superpowers" / "implemented" / "runs"


@dataclass
class BackfillReport:
    written: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    """Runs that already had a usage file."""
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
        read.append(session_entry(record, windows, units))
    if any(e.unavailable is None for e in read):
        return read
    return _cursor_figures(raw) + read


def _harness(raw: dict[str, Any]) -> str:
    return next((h for h, _ in sessions_of(raw)), "unknown")


def backfill(repo_root: Path, env: Mapping[str, str]) -> BackfillReport:
    from fr.artifacts.atomic import write_text_atomic
    from fr.usage.capture import this_host

    report = BackfillReport()
    runs = repo_root / ARCHIVED_RUNS_REL
    for cursor in sorted(runs.glob("*.yaml")) if runs.is_dir() else ():
        run_id = cursor.stem
        target = archived_usage_path(repo_root, run_id)
        if target.exists() or usage_path(repo_root, run_id).exists():
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
                captured_at=_dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat(),
                at=("backfill",),
                sessions=tuple(_entries(raw, env)),
            )
            text = dump_usage(UsageFile(run=run_id, captures=(capture,)))
        except Exception as e:  # noqa: BLE001 — one unreadable run is that run's failure
            report.failed.append((run_id, f"{type(e).__name__}: {e}"))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(target, text)
        report.written.append(target)
    return report


__all__ = ["ARCHIVED_RUNS_REL", "BackfillReport", "backfill"]
