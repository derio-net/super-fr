"""Capture a run's usage into `docs/superpowers/usage/<run-id>.yaml` (spec §5.B.3).

Three capture points, all riding calls that already happen and costing no
inference: `fr run resolve --step deliver`, the first `fr run resolve` on a
host that has no capture yet, and `fr archive` (the closeout session, before
the file moves with the plan). The caller commits the file with the cursor.

**Capture never fails its step.** A reader that raises is recorded as that
session's `unavailable`; a usage file that cannot be read is left untouched
and reported on stderr; anything else is swallowed the same way. A step's
outcome is never hostage to observability.

A re-capture on the same host merges into that host's entry: its event is
appended to the entry's `at` list (spec §5.B.1/3, p2-r29) — and a session the
earlier capture READ and this one cannot (a pruned transcript) keeps its
earlier figures: replacing a measurement with an absence would lose the one
thing the file exists to keep.
"""

from __future__ import annotations

import datetime as _dt
import socket
import sys
from collections.abc import Mapping
from pathlib import Path

from fr.run.model import RunState
from fr.usage.file import (
    Capture,
    Mode,
    SessionEntry,
    UsageFile,
    UsageFileError,
    dump_usage,
    host_label,
    load_usage,
    session_entry,
    units_by_agent,
    upsert_capture,
    usage_path,
)
from fr.usage.model import unavailable
from fr.usage.rollup import windows_from_cursor
from fr.usage.sources import read_session, sessions_of

HOSTNAME_ENV = "FR_HOSTNAME"
"""Overrides the hostname the host label hashes — tests, and a pod whose
hostname changes per restart but is one host for this purpose."""

_BINDING_TO_HARNESS: Mapping[str, str] = {
    "claude": "claude-code",
    "claude-code": "claude-code",
    "unknown": "claude-code",
    "opencode": "opencode",
    "hermes": "hermes",
}
"""A workspace binding's harness word -> the reader key. `unknown` is Claude
Code's, as in `fr.run.telemetry._BINDING_HARNESSES`."""


def hostname(env: Mapping[str, str]) -> str:
    return env.get(HOSTNAME_ENV) or socket.gethostname()


def this_host(run_id: str, env: Mapping[str, str]) -> str:
    return host_label(run_id, hostname(env))


def isolation_mode(repo_root: Path, state: RunState) -> Mode:
    """The run's isolation mode, from its workspace record — `host-worktree`
    when there is none (fr then runs where the harness runs)."""
    try:
        from fr.isolation.types import load_state, recorded_mode

        workspace = load_state(repo_root, state.branch)
    except Exception:  # noqa: BLE001 — observability degrades, never raises
        workspace = None
    if workspace is None:
        return "external" if _external_marker(repo_root) else "host-worktree"
    mode = recorded_mode(workspace)
    return "host-worktree" if mode == "worktree" else mode


def _external_marker(repo_root: Path) -> bool:
    import json

    try:
        data = json.loads((repo_root / ".fr-isolation").read_text())
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("mode") == "external"


def candidates(state: RunState, env: Mapping[str, str], repo_root: Path) -> list[tuple[str, str]]:
    """`(harness, session)` pairs, first-seen order: every session the cursor
    records, every session bound to the run's workspace, and this process's."""
    from fr.harness.detect import detect_harness
    from fr.run.telemetry import current_session

    found: list[tuple[str, str]] = list(sessions_of(state.model_dump(mode="json")))
    try:
        from fr.isolation.types import load_state

        workspace = load_state(repo_root, state.branch)
    except Exception:  # noqa: BLE001
        workspace = None
    for binding in workspace.sessions if workspace is not None else ():
        found.append(
            (_BINDING_TO_HARNESS.get(binding.harness, binding.harness), binding.session_id)
        )
    current = current_session(env)
    if current:
        try:
            harness = detect_harness(env) or "claude-code"
        except Exception:  # noqa: BLE001 — a mistyped FR_HARNESS must not fail a step
            harness = "claude-code"
        found.append((harness, current))
    return list(dict.fromkeys(found))


def _merge(previous: Capture | None, entries: list[SessionEntry]) -> list[SessionEntry]:
    if previous is None:
        return entries
    fresh = {e.session: e for e in entries}
    for old in previous.sessions:
        new = fresh.get(old.session)
        if new is None:
            entries.append(old)
        elif new.unavailable is not None and old.unavailable is None:
            entries[entries.index(new)] = old
    return entries


def needs_capture(repo_root: Path, state: RunState, env: Mapping[str, str]) -> bool:
    """True when this host has no capture of the run yet (spec §5.B.3 row 3)."""
    try:
        existing = load_usage(usage_path(repo_root, state.run))
    except (OSError, UsageFileError):
        return False
    return existing is None or existing.host(this_host(state.run, env)) is None


def capture(
    repo_root: Path,
    state: RunState,
    at: str,
    env: Mapping[str, str],
    *,
    path: Path | None = None,
    require_sessions: bool = False,
) -> Path | None:
    """Write this host's capture of `state`'s run; the path written, or `None`.

    `require_sessions` skips the write when there is no session at all to
    record (a new host's first resolve with nothing to read is not a capture).
    Never raises."""
    target = path or usage_path(repo_root, state.run)
    try:
        existing = load_usage(target) or UsageFile(run=state.run)
        pairs = candidates(state, env, repo_root)
        if require_sessions and not pairs:
            return None
        windows = windows_from_cursor(
            {"started": state.started, "steps": {k: {"at": v.at} for k, v in state.steps.items()}}
        )
        units = units_by_agent(state.model_dump(mode="json"))
        entries: list[SessionEntry] = []
        for harness, session in pairs:
            try:
                record = read_session(harness, session, env)
            except Exception as e:  # noqa: BLE001 — a reader must not fail a step
                record = unavailable(session, harness, f"reader failed: {type(e).__name__}")
            entries.append(session_entry(record, windows, units))
        label = this_host(state.run, env)
        previous = existing.host(label)
        events = previous.at if previous is not None else ()
        if at not in events:
            events = (*events, at)
        try:
            from fr.harness.detect import detect_harness

            harness_now = detect_harness(env) or (pairs[-1][0] if pairs else "unknown")
        except Exception:  # noqa: BLE001
            harness_now = "unknown"
        new = Capture(
            host=label,
            harness=harness_now,
            mode=isolation_mode(repo_root, state),
            captured_at=_dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat(),
            at=events,
            sessions=tuple(_merge(previous, entries)),
        )
        from fr.artifacts.atomic import write_text_atomic

        target.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(target, dump_usage(upsert_capture(existing, new)))
        return target
    except Exception as e:  # noqa: BLE001 — capture never fails its step
        print(f"fr: usage not captured ({target.name}): {e}", file=sys.stderr)
        return None


__all__ = ["HOSTNAME_ENV", "candidates", "capture", "hostname", "isolation_mode", "needs_capture"]
