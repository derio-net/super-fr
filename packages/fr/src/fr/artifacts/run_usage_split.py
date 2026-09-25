"""The `run` kind's 6 -> 7 migration: usage moves out of the cursor (spec
`2026-09-25-lean-cost-aware-process-design.md` §5.B.4).

`Attempt.estimate`, `Attempt.measured` and `StepRecord.main_session` are
REMOVED from the live model; the run's cost now lives in
`docs/superpowers/usage/<run-id>.yaml` (`fr.usage.file`). The rules of
`.claude/rules/artifact-versioning.md` for a removal, each kept here:

1. **Frozen reader.** The old file is read with `fr.run.legacy.RunStateV6` (a
   superset of v5 and v6), never the live model.
2. **Move, never drop.** A cursor's figures become one `at: migrated` capture
   in its usage file — host label `h(run + "(migrated)")`, so a later live
   capture from the migrating host does not replace it — with `usd_source:
   none` (the cursor never held dollars, except an OpenCode `cost_usd`, which
   is the harness's own figure and is kept as `exact`).
3. **Built in memory, written once per file**, via `write_text_atomic`: the
   usage file first, then the cursor. Every refusal fires before either write,
   so an unconvertible cursor stays byte-identical and is that one artifact's
   failure. A crash between the two writes leaves a v6 cursor that still
   carries its figures; re-running rebuilds the SAME migrated capture (it is a
   pure function of the cursor) and replaces it in place.
4. **The crash window between body and stamp.** A wholly-v7 body under a v6
   stamp is a subset of the v6 shape: it reads, carries no figures, converts to
   itself, and nothing is written — the runner just stamps it. Should a later
   version make v7 stop being a subset, the live-model fallback below still
   recognises it; that fallback is the ONE use of the live parser under
   `fr/artifacts/run_*.py`
   (`tests/unit/test_migration_run_unit_record.py::test_no_run_migration_names_the_live_parser`).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.run_cursor import UnreadableRunCursorError
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "run-usage-split"

_REMOVED_ATTEMPT_KEYS = ("estimate", "measured")
_REMOVED_STEP_KEYS = ("main_session",)
MAIN_SESSION_ID = "(main)"
"""The session id of the migrated main-session entry: v6 summed the main
session(s) per step without recording which, so there is no real id to use."""


class UnconvertibleRunCursorError(UnreadableRunCursorError):
    """A v6 cursor fr READ fine and still will not rewrite."""


def _carries_removed(data: dict[str, Any]) -> bool:
    for record in (data.get("steps") or {}).values():
        if not isinstance(record, dict):
            continue
        if any(k in record for k in _REMOVED_STEP_KEYS):
            return True
        for unit in (record.get("units") or {}).values():
            for attempt in (unit or {}).get("attempts") or ():
                if isinstance(attempt, dict) and any(k in attempt for k in _REMOVED_ATTEMPT_KEYS):
                    return True
    return False


def _already_v7(text: str, data: object) -> bool:
    from fr.run.model import RunStateError, parse_run_state

    if not isinstance(data, dict) or _carries_removed(data):
        return False
    try:
        parse_run_state(text)
    except RunStateError:
        return False
    return True


def split_usage(data: dict[str, Any]) -> tuple[dict[str, Any], list[Any]]:
    """`(v7 body, usage session entries)` — pure: no I/O, no clock.

    `data` is a v6 cursor already read by the frozen reader."""
    from fr.usage.file import Figure, ModelFigures, SessionEntry

    body = copy.deepcopy(data)
    entries: list[SessionEntry] = []
    main_steps: dict[str, Figure] = {}
    main_tokens = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
    main_usd: float | None = None
    for step_id, record in (body.get("steps") or {}).items():
        usage = record.pop("main_session", None)
        if usage is not None:
            cost = usage.get("cost_usd")
            main_steps[step_id] = Figure(usd=cost, turns=usage["turns"])
            main_tokens["input"] += usage["input_tokens"]
            main_tokens["cache_write"] += usage["cache_creation_input_tokens"]
            main_tokens["cache_read"] += usage["cache_read_input_tokens"]
            main_tokens["output"] += usage["output_tokens"]
            if cost is not None:
                main_usd = (main_usd or 0.0) + cost
        for key, unit in (record.get("units") or {}).items():
            for i, attempt in enumerate(unit.get("attempts") or ()):
                estimate = attempt.pop("estimate", None)
                measured = attempt.pop("measured", None)
                if estimate is None and measured is None:
                    continue
                if attempt.get("synthesized"):
                    role = None
                elif attempt.get("agent_type"):
                    role = f"subagent:{attempt['agent_type']}"
                elif attempt.get("agent"):
                    # dispatched (it names an agent) but v6 kept no type (p2-r23)
                    role = "subagent"
                else:
                    role = "main"
                models = {}
                if measured is not None:
                    models[attempt.get("model") or "unknown"] = ModelFigures(
                        input=measured["input_tokens"],
                        cache_write=measured["cache_creation_input_tokens"],
                        cache_read=measured["cache_read_input_tokens"],
                        output=measured["output_tokens"],
                    )
                entries.append(
                    SessionEntry(
                        session=attempt.get("agent") or f"{key}#{i + 1}",
                        role=role,
                        models=models,
                        steps={step_id: Figure()},
                        briefs={key: estimate.get("handoff_chars", 0)} if estimate else {},
                    )
                )
    if main_steps:
        entries.insert(
            0,
            SessionEntry(
                session=MAIN_SESSION_ID,
                role="main",
                models={
                    "unknown": ModelFigures(
                        **main_tokens,
                        usd=main_usd,
                        usd_source="exact" if main_usd is not None else "none",
                    )
                },
                steps=main_steps,
            ),
        )
    return body, entries


def _captured_at(data: dict[str, Any]) -> str:
    """Deterministic: the cursor's latest step `at`, else its `started` —
    so two machines migrating one cursor write one capture."""
    stamps = [
        str(r["at"])
        for r in (data.get("steps") or {}).values()
        if isinstance(r, dict) and r.get("at")
    ]
    return max(stamps) if stamps else str(data.get("started"))


def _harness(data: dict[str, Any]) -> str:
    for record in (data.get("steps") or {}).values():
        for unit in (record.get("units") or {}).values():
            for attempt in unit.get("attempts") or ():
                if attempt.get("harness"):
                    return str(attempt["harness"])
    return "unknown"


def split_run_usage(path: Path) -> list[Path] | None:
    """Rewrite the run cursor at `path` from v6 to v7, moving its figures into
    its usage file. Returns the usage path when one was written."""
    from fr.run.legacy import parse_run_state_v6
    from fr.run.model import RunStateError, dump_cursor_yaml, parse_run_state
    from fr.usage.file import (
        MIGRATED_HOST,
        Capture,
        UsageFile,
        UsageFileError,
        dump_usage,
        host_label,
        load_usage,
        upsert_capture,
        usage_path,
    )

    try:
        text = path.read_text()
        parse_run_state_v6(text)
    except (RunStateError, OSError) as e:
        try:
            data = yaml.safe_load(text) if isinstance(e, RunStateError) else None
        except yaml.YAMLError:
            data = None
        if data is not None and _already_v7(text, data):
            return None
        raise UnreadableRunCursorError(
            f"{path}: not a readable version-6 run cursor, so fr will not rewrite it to "
            f"version 7 ({e}). Fix the file by hand — it is left byte-identical on its "
            f"current version and will be retried."
        ) from e

    data = yaml.safe_load(text)
    body, entries = split_usage(data)
    if body == data:
        return None
    try:
        parse_run_state(dump_cursor_yaml(body))
    except RunStateError as e:
        raise UnconvertibleRunCursorError(
            f"{path}: the version-7 body fr would write does not validate ({e}); "
            "the cursor is left unchanged"
        ) from e

    written: list[Path] = []
    usage_text: str | None = None
    target = usage_path(path.parents[3], str(data["run"]))
    if entries:
        try:
            existing = load_usage(target) or UsageFile(run=str(data["run"]))
        except (OSError, UsageFileError) as e:
            raise UnconvertibleRunCursorError(
                f"{path}: its usage file {target.name} cannot be read ({e}), so fr will "
                "not move the cursor's figures into it; both are left unchanged"
            ) from e
        capture = Capture(
            host=host_label(str(data["run"]), MIGRATED_HOST),
            harness=_harness(data),
            mode="host-worktree",
            captured_at=_captured_at(data),
            at=("migrated",),
            sessions=tuple(entries),
        )
        usage_text = dump_usage(upsert_capture(existing, capture))
    # every refusal is above this line: now write, usage first
    if usage_text is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(target, usage_text)
        written.append(target)
    write_text_atomic(path, dump_cursor_yaml(body))
    return written


RUN_USAGE_SPLIT_MIGRATION = SchemaMigration(
    kind="run",
    from_version=6,
    to_version=7,
    fn=split_run_usage,
    description="run cursor: move `estimate`, `measured` and `main_session` into the "
    "run's usage file (`at: migrated`); a cursor it cannot convert is left untouched",
)

MIGRATIONS.register(RUN_USAGE_SPLIT_MIGRATION)

__all__ = [
    "MAIN_SESSION_ID",
    "MIGRATION_NAME",
    "RUN_USAGE_SPLIT_MIGRATION",
    "UnconvertibleRunCursorError",
    "split_run_usage",
    "split_usage",
]
