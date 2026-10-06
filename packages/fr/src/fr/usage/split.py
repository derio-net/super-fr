"""Who spent what: the main thread against its subagents, and per cursor unit.

Pure arithmetic over a `UsageRecord` and a `UnitIndex` read from a run cursor
(cost-evidence spec §B). Nothing here reads a transcript or writes a file, and
every dollar comes from `rollup.message_dollars`, the same per-message figure
`rollup` attributes, so the two splits cannot drift.

Attribution, one unit and one role per message at most:

- a **subagent** message (it has an `agent_id`) goes to the unit whose agents
  contain that id — role `executor` for an `implement-phase` unit, `reviewer`
  for a `review-phase` unit, `agent` for a flat `step/<id>` unit — else to
  `(unattributed)`, role `subagent`;
- a **main-thread** message goes to the `orchestrator` of the unit whose
  half-open `(dispatched, returned]` interval contains its timestamp; where
  intervals overlap (a retry opened after a later unit) the latest `dispatched`
  wins, so nothing is counted twice. Outside every interval it stays in its
  step figure only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from fr.run.telemetry import parse_timestamp
from fr.usage.model import WEIGHTS, Message, UsageRecord
from fr.usage.rollup import Window, message_dollars, step_of

UNATTRIBUTED_UNIT = "(unattributed)"
MAIN, SUBAGENT = "main", "subagent"
STEP_ROLES = (MAIN, SUBAGENT)
UNIT_ROLES = ("executor", "reviewer", "agent", "orchestrator", SUBAGENT)

_SUBAGENT_ROLE_BY_STEP = {"implement-phase": "executor", "review-phase": "reviewer"}


@dataclass(frozen=True)
class Interval:
    unit: str
    start: datetime
    end: datetime | None
    """`None`: open-ended — the unit's open attempt (`fr.run.units.open_attempt`)."""


@dataclass(frozen=True)
class UnitIndex:
    agents: dict[str, str] = field(default_factory=dict)
    """`{agent id: unit key}` — the unit's attempt agents and `evidence.reviewer`."""
    roles: dict[str, str] = field(default_factory=dict)
    """`{unit key: the role its subagent plays}`."""
    intervals: tuple[Interval, ...] = ()


@dataclass
class Acc:
    usd: float = 0.0
    turns: int = 0
    input: int = 0
    cache_write: int = 0
    cache_read: int = 0
    output: int = 0

    def add(self, message: Message, dollars: float) -> None:
        t = message.tokens
        self.usd += dollars
        self.turns += 1
        self.input += t.input
        self.cache_write += t.cache_write_5m + t.cache_write_1h
        self.cache_read += t.cache_read
        self.output += t.output


def _second(ts: str | None) -> datetime | None:
    parsed = parse_timestamp(ts)
    return None if parsed is None else parsed.replace(microsecond=0)


def _interval_unit(second: datetime, intervals: Sequence[Interval]) -> str | None:
    best: Interval | None = None
    for interval in intervals:
        if second > interval.start and (interval.end is None or second <= interval.end):
            if best is None or interval.start >= best.start:
                best = interval
    return None if best is None else best.unit


def is_subagent(message: Message) -> bool:
    return message.agent_id is not None or message.agent != "main"


def by_role_and_step(
    record: UsageRecord,
    windows: Sequence[Window],
    weights: Mapping[str, float] = WEIGHTS,
) -> dict[str, dict[str, Acc]]:
    """`{role: {step: figures}}` — each message counted once, in its step."""
    dollars, _remainder = message_dollars(record, weights)
    out: dict[str, dict[str, Acc]] = {MAIN: {}, SUBAGENT: {}}
    for message, usd in zip(record.messages, dollars, strict=True):
        step = step_of(message, windows)
        if step is None:
            continue
        role = SUBAGENT if is_subagent(message) else MAIN
        out[role].setdefault(step, Acc()).add(message, usd)
    return out


def by_unit_and_role(
    record: UsageRecord,
    index: UnitIndex,
    weights: Mapping[str, float] = WEIGHTS,
) -> dict[str, dict[str, Acc]]:
    """`{unit key: {role: figures}}`, including `(unattributed)`."""
    dollars, _remainder = message_dollars(record, weights)
    out: dict[str, dict[str, Acc]] = {}
    for message, usd in zip(record.messages, dollars, strict=True):
        if is_subagent(message):
            unit = index.agents.get(message.agent_id) if message.agent_id else None
            if unit is None:
                unit, role = UNATTRIBUTED_UNIT, SUBAGENT
            else:
                role = index.roles.get(unit, "agent")
        else:
            second = _second(message.ts)
            unit = None if second is None else _interval_unit(second, index.intervals)
            if unit is None:
                continue
            role = "orchestrator"
        out.setdefault(unit, {}).setdefault(role, Acc()).add(message, usd)
    return out


def step_role_of(step: str) -> str:
    """The subagent role of a unit under `step` (`agent` for a flat step)."""
    return _SUBAGENT_ROLE_BY_STEP.get(step, "agent")
