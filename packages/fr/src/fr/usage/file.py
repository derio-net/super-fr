"""The `usage` artifact: `docs/superpowers/usage/<run-id>.yaml` (spec §5.B.1-2).

What a run cost, persisted — because the transcripts it was measured from may
not survive (a pod is torn down, a session is pruned). One CAPTURE per host;
a re-capture replaces its own host's entry and nothing else. No totals are
stored: readers sum on read. The per-step rollup IS stored, because computing
it needs the transcript.

**The file is an allowlist projection, never a dump** (finding p2-r12). A
`UsageRecord` holds raw tool-call targets — shell commands and file paths —
and a public repo commits this file. So `session_entry` copies numbers and ids
out of a record field by field, and `dump_usage` writes plain mappings built
field by field; nothing here calls `model_dump()` on a source record, so a
field added to `UsageRecord` later cannot leak by default. Stored: model ids,
token counts, dollars, session ids (already in cursors), step ids, brief
sizes, the isolation mode. Never stored: hostnames, provider base URLs, paths,
prompts or message content. The host label is `sha256(run_id + hostname)[:8]`
— stable within a run, carrying no name.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from fr.run.telemetry import parse_timestamp
from fr.usage.model import UsageRecord
from fr.usage.readers.hermes import ACP_ZERO_TOKENS
from fr.usage.rollup import Window, rollup
from fr.usage.split import (
    Acc,
    Interval,
    UnitIndex,
    by_role_and_step,
    by_unit_and_role,
    step_role_of,
    tokens_by_step,
)

USAGE_REL = Path("docs") / "superpowers" / "usage"
IMPLEMENTED_USAGE_REL = Path("docs") / "superpowers" / "implemented" / "usage"

Mode = Literal["host-worktree", "devcontainer", "external"]
UsdSource = Literal["exact", "estimated", "none"]

_HOST_RE = re.compile(r"^h-[0-9a-f]{8}$")
_AT_RE = re.compile(r"^(deliver|closeout|migrated|backfill|resolve:\S+)$")
_ROLE_RE = re.compile(r"^(main|subagent(:\S+)?)$")

MIGRATED_HOST = "(migrated)"
"""The pseudo-hostname a `migrated` capture is labelled with: those figures
were read from a cursor, not from any host's transcripts, so they must not
occupy — and be replaced by — the migrating host's own entry."""


class UsageFileError(Exception):
    """A usage file that does not parse or does not validate."""


class ModelFigures(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    input: int = 0
    cache_write: int = 0
    cache_read: int = 0
    output: int = 0
    usd: float | None = None
    usd_source: UsdSource = "none"


class Figure(BaseModel):
    """Dollars and turns of one activity or step. `usd: None` is "no figure"."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    usd: float | None = None
    turns: int | None = None
    input: int | None = None
    cache_write: int | None = None
    cache_read: int | None = None
    output: int | None = None
    """Token counts: set on the main/subagent and per-unit figures (R4), absent
    (`None`) on the older activity and step figures."""


class SessionEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session: str
    role: str | None = None
    models: dict[str, ModelFigures] = {}
    activity: dict[str, Figure] = {}
    steps: dict[str, Figure] = {}
    steps_by_role: dict[str, dict[str, Figure]] = {}
    """`{main|subagent: {step: figure}}` — a step's figures by thread (R2)."""
    units: dict[str, dict[str, Figure]] = {}
    """`{unit key | (unattributed): {role: figure}}` (R3)."""
    briefs: dict[str, int] = {}
    """Dispatch-brief sizes in characters, keyed by unit."""
    unavailable: str | None = None

    @field_validator("role")
    @classmethod
    def _role(cls, value: str | None) -> str | None:
        if value is not None and not _ROLE_RE.match(value):
            raise ValueError(f"role {value!r} must be `main` or `subagent:<agent_type>`")
        return value

    @model_validator(mode="after")
    def _unavailable_carries_no_figures(self) -> SessionEntry:
        if self.unavailable is not None and (
            self.models or self.activity or self.steps or self.steps_by_role or self.units
        ):
            raise ValueError("an `unavailable` session carries no figures")
        return self


class Capture(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str
    harness: str
    mode: Mode
    captured_at: str
    """When this host last captured."""
    at: tuple[str, ...]
    """Every capture event from this host, in order (spec §5.B.1, p2-r29): a
    later capture merges into the host's entry and appends, so a closeout
    never erases the deliver that preceded it."""
    sessions: tuple[SessionEntry, ...] = ()

    @field_validator("host")
    @classmethod
    def _host(cls, value: str) -> str:
        if not _HOST_RE.match(value):
            raise ValueError(f"host {value!r} must be a label `h-<8 hex>`, never a name")
        return value

    @field_validator("at")
    @classmethod
    def _at(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("at lists at least one capture event")
        for event in value:
            if not _AT_RE.match(event):
                raise ValueError(
                    f"at event {event!r} must be deliver | closeout | resolve:<step> | "
                    "migrated | backfill"
                )
        if len(set(value)) != len(value):
            raise ValueError(f"at lists an event twice: {list(value)}")
        return value


class UsageFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    run: str
    captures: tuple[Capture, ...] = ()

    @model_validator(mode="after")
    def _one_capture_per_host(self) -> UsageFile:
        hosts = [c.host for c in self.captures]
        doubled = sorted({h for h in hosts if hosts.count(h) > 1})
        if doubled:
            raise ValueError(f"one capture per host, but {', '.join(doubled)} appear twice")
        return self

    def host(self, label: str) -> Capture | None:
        return next((c for c in self.captures if c.host == label), None)


def current_usage_schema_version() -> int:
    """The `usage` artifact version this `fr` writes, read from the registry —
    the ONE place a kind's `current_version` is declared — so a file fr creates
    is born stamped with it, never stale (mirrors `current_run_schema_version`)."""
    from fr.artifacts.registry import artifact_kind

    return artifact_kind("usage").current_version


def host_label(run_id: str, hostname: str) -> str:
    """`h-` + sha256(run_id + hostname)[:8] — stable in a run, no name in it."""
    return "h-" + hashlib.sha256((run_id + hostname).encode()).hexdigest()[:8]


def upsert_capture(file: UsageFile, capture: Capture) -> UsageFile:
    """`file` with `capture` in place of its host's entry, or appended."""
    captures = list(file.captures)
    for i, existing in enumerate(captures):
        if existing.host == capture.host:
            captures[i] = capture
            break
    else:
        captures.append(capture)
    return file.model_copy(update={"captures": tuple(captures)})


def usage_path(repo_root: Path, run_id: str) -> Path:
    return repo_root / USAGE_REL / f"{run_id}.yaml"


def archived_usage_path(repo_root: Path, run_id: str) -> Path:
    return repo_root / IMPLEMENTED_USAGE_REL / f"{run_id}.yaml"


# --- the allowlist projection ---------------------------------------------


# The committed file's `unavailable` vocabulary (p2-r21). A reader's reason is
# free text — its own catch-all copies the exception's message, which carries
# absolute paths and usernames — so the projection keeps only these reasons
# verbatim and maps everything else to `reader failed[: <what>]`. The live
# `fr usage report` path reads the record, not this file, and keeps the detail.
NO_SESSION_FOUND = "no session found"
"""The reason on the placeholder entry a capture writes when it found no
session at all — the file then says so instead of carrying `sessions: []`."""

_KEPT_REASONS = frozenset(
    {
        NO_SESSION_FOUND,
        "no reader for this harness",
        "no transcript found for this session on this host",
        "no session id given",
        "session not in the Hermes database",
        "session not in the OpenCode database",
        ACP_ZERO_TOKENS,
    }
)
_READER_FAILED = re.compile(r"^reader failed(?:: [A-Za-z_][A-Za-z0-9_]*)?$")
_EXC_PREFIX = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning|Exit|Interrupt)): ")


def committed_reason(reason: str) -> str:
    """`reason`, mapped onto the closed vocabulary a committed file may carry."""
    if reason in _KEPT_REASONS or _READER_FAILED.match(reason):
        return reason
    if match := _EXC_PREFIX.match(reason):
        return f"reader failed: {match.group(1)}"
    if "database unreadable" in reason:
        return "reader failed: database unreadable"
    if reason.startswith(("unreadable transcript", "unreadable subagent transcript")):
        return "reader failed: unreadable transcript"
    return "reader failed"


def _role(record: UsageRecord) -> str:
    if record.role == "main":
        return "main"
    agent = next((m.agent for m in record.messages if m.agent != "main"), None)
    return f"subagent:{agent}" if agent else "subagent"


def unit_index(cursor: Mapping[str, Any]) -> UnitIndex:
    """What a run cursor says about who held each unit and when (spec §B).

    Read from the raw mapping, tolerantly, so any cursor version with `units`
    serves. A synthesized attempt contributes no agent and no interval; an
    attempt with no `returned` is open-ended only when it is the unit's last
    (`fr.run.units.open_attempt`'s rule: the held one)."""
    agents: dict[str, str] = {}
    roles: dict[str, str] = {}
    intervals: list[Interval] = []
    steps = cursor.get("steps")
    for step, record in steps.items() if isinstance(steps, Mapping) else ():
        units = record.get("units") if isinstance(record, Mapping) else None
        for key, unit in units.items() if isinstance(units, Mapping) else ():
            if not isinstance(unit, Mapping):
                continue
            unit_key = str(key)
            roles[unit_key] = step_role_of(str(step))
            attempts = unit.get("attempts")
            recorded = (
                [a for a in attempts if isinstance(a, Mapping)]
                if isinstance(attempts, list | tuple)
                else []
            )
            for position, attempt in enumerate(recorded):
                if attempt.get("synthesized"):
                    continue
                agent = attempt.get("agent")
                if isinstance(agent, str) and agent:
                    agents.setdefault(agent, unit_key)
                start = parse_timestamp(attempt.get("dispatched"))
                if start is None:
                    continue
                end = parse_timestamp(attempt.get("returned"))
                held = end is None and position == len(recorded) - 1
                if end is not None or held:
                    intervals.append(Interval(unit_key, start, end))
            evidence = unit.get("evidence")
            reviewer = evidence.get("reviewer") if isinstance(evidence, Mapping) else None
            if isinstance(reviewer, str) and reviewer:
                agents.setdefault(reviewer, unit_key)
    return UnitIndex(agents=agents, roles=roles, intervals=tuple(intervals))


def units_by_agent(cursor: Mapping[str, Any]) -> dict[str, str]:
    """`{agent id: unit key}` — how a brief the reader keyed by agent id finds
    its unit. A thin view of `unit_index`."""
    return unit_index(cursor).agents


def session_entry(
    record: UsageRecord,
    windows: Sequence[Window] = (),
    index: UnitIndex | None = None,
    *,
    rekey: Mapping[str, str] | None = None,
) -> SessionEntry:
    """One session's figures, copied out of `record` field by field.

    Only model ids, token counts, dollars, turns, step names and brief SIZES
    are read; tool calls are used to CLASSIFY (inside `rollup`) and never
    copied. `index` (`unit_index`) re-keys a brief from the agent id the reader
    found to the cursor unit that agent held (an unmatched brief keeps the
    reader's key, p2-r24) and, when given, adds the main/subagent split per
    step and the per-unit split (R2, R3). `None` writes neither: that is what
    `backfill` and `refreshed_file` pass, so archived files keep their shape.
    They still re-key briefs, through `rekey` (`units_by_agent`) alone."""
    if record.unavailable is not None:
        return SessionEntry(
            session=record.session, unavailable=committed_reason(record.unavailable)
        )
    result = rollup([record], windows=windows)
    source: UsdSource = record.cost.source if record.cost.usd is not None else "none"
    tokens: dict[str, dict[str, int]] = {}
    for message in record.messages:
        t = tokens.setdefault(
            message.model, {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
        )
        t["input"] += message.tokens.input
        t["cache_write"] += message.tokens.cache_write_5m + message.tokens.cache_write_1h
        t["cache_read"] += message.tokens.cache_read
        t["output"] += message.tokens.output
    for model in record.cost.by_model:
        tokens.setdefault(model, {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0})
    priced = record.cost.usd is not None
    models = {
        model: ModelFigures(
            **counts,
            usd=result.by_model.get(model, 0.0) if priced else None,
            usd_source=source,
        )
        for model, counts in tokens.items()
    }
    activities = set(result.by_activity) | set(result.turns_by_activity)
    activity = {
        name: Figure(
            usd=result.by_activity.get(name, 0.0) if priced else None,
            turns=result.turns_by_activity.get(name, 0),
        )
        for name in sorted(activities)
    }
    step_names = list(dict.fromkeys([*result.turns_by_step, *result.by_step]))
    step_tokens = tokens_by_step(record, windows)
    steps = {
        name: Figure(
            usd=sum(result.by_step.get(name, {}).values()) if priced else None,
            turns=result.turns_by_step.get(name, 0),
            input=step_tokens.get(name, Acc()).input,
            cache_write=step_tokens.get(name, Acc()).cache_write,
            cache_read=step_tokens.get(name, Acc()).cache_read,
            output=step_tokens.get(name, Acc()).output,
        )
        for name in step_names
    }
    briefs: dict[str, int] = {}
    for key, size in record.briefs.items():
        unit = (rekey if rekey is not None else index.agents if index else {}).get(key, key)
        briefs[unit] = briefs.get(unit, 0) + size
    return SessionEntry(
        session=record.session,
        role=_role(record),
        models=models,
        activity=activity,
        steps=steps,
        steps_by_role=_figures_by_role(record, windows) if index is not None else {},
        units=_figures_by_unit(record, index) if index is not None else {},
        briefs=briefs,
    )


def _figure_of(acc: Acc, priced: bool) -> Figure:
    return Figure(
        usd=acc.usd if priced else None,
        turns=acc.turns,
        input=acc.input,
        cache_write=acc.cache_write,
        cache_read=acc.cache_read,
        output=acc.output,
    )


def _figures_by_role(
    record: UsageRecord, windows: Sequence[Window]
) -> dict[str, dict[str, Figure]]:
    priced = record.cost.usd is not None
    split = by_role_and_step(record, windows)
    return {
        role: {step: _figure_of(acc, priced) for step, acc in steps.items()}
        for role, steps in split.items()
        if steps
    }


def _figures_by_unit(record: UsageRecord, index: UnitIndex) -> dict[str, dict[str, Figure]]:
    priced = record.cost.usd is not None
    return {
        unit: {role: _figure_of(acc, priced) for role, acc in roles.items()}
        for unit, roles in by_unit_and_role(record, index).items()
    }


# --- read / write -------------------------------------------------------------


def _figure(f: Figure) -> dict[str, Any]:
    out: dict[str, Any] = {"usd": f.usd, "turns": f.turns}
    for name in ("input", "cache_write", "cache_read", "output"):
        if getattr(f, name) is not None:
            out[name] = getattr(f, name)
    return out


def _session(entry: SessionEntry) -> dict[str, Any]:
    out: dict[str, Any] = {"session": entry.session}
    if entry.unavailable is not None:
        out["unavailable"] = entry.unavailable
        return out
    if entry.role is not None:
        out["role"] = entry.role
    out["models"] = {
        model: {
            "input": m.input,
            "cache_write": m.cache_write,
            "cache_read": m.cache_read,
            "output": m.output,
            "usd": m.usd,
            "usd_source": m.usd_source,
        }
        for model, m in entry.models.items()
    }
    out["activity"] = {name: _figure(f) for name, f in entry.activity.items()}
    out["steps"] = {name: _figure(f) for name, f in entry.steps.items()}
    if entry.steps_by_role:
        out["steps_by_role"] = {
            role: {step: _figure(f) for step, f in steps.items()}
            for role, steps in entry.steps_by_role.items()
        }
    if entry.units:
        out["units"] = {
            unit: {role: _figure(f) for role, f in roles.items()}
            for unit, roles in entry.units.items()
        }
    if entry.briefs:
        out["briefs"] = dict(entry.briefs)
    return out


def dump_usage(file: UsageFile) -> str:
    """The file as YAML — plain mappings built field by field (the allowlist)."""
    data = {
        "schema_version": file.schema_version,
        "run": file.run,
        "captures": [
            {
                "host": c.host,
                "harness": c.harness,
                "mode": c.mode,
                "captured_at": c.captured_at,
                "at": list(c.at),
                "sessions": [_session(s) for s in c.sessions],
            }
            for c in file.captures
        ],
    }
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def parse_usage(text: str) -> UsageFile:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise UsageFileError(f"not valid YAML: {e}") from e
    if not isinstance(data, Mapping):
        raise UsageFileError("a usage file is a mapping")
    try:
        return UsageFile.model_validate(data)
    except ValidationError as e:
        raise UsageFileError(str(e)) from e


def load_usage(path: Path) -> UsageFile | None:
    """The file at `path`, or `None` when there is none. Raises on a bad one."""
    if not path.is_file():
        return None
    return parse_usage(path.read_text())


__all__ = [
    "NO_SESSION_FOUND",
    "committed_reason",
    "current_usage_schema_version",
    "unit_index",
    "units_by_agent",
    "IMPLEMENTED_USAGE_REL",
    "MIGRATED_HOST",
    "USAGE_REL",
    "Capture",
    "Figure",
    "ModelFigures",
    "SessionEntry",
    "UsageFile",
    "UnitIndex",
    "UsageFileError",
    "archived_usage_path",
    "dump_usage",
    "host_label",
    "load_usage",
    "parse_usage",
    "session_entry",
    "upsert_capture",
    "usage_path",
]
