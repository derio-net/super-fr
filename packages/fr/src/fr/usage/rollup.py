"""Split each session's harness dollars across activities, sub-activities and steps.

**Dollars come from the harness** (spec §5.A.2). For every model, the harness's
own figure for that model is divided over that model's messages in proportion
to price-weighted tokens — `WEIGHTS`, the fixed ratios, and nothing else. The
split therefore always sums back to the harness total: a model the harness
billed but no transcript message carries (a side query, a compaction) lands in
`other / unattributed`, never dropped and never invented.

A message's share is split evenly across its tool calls (1/k each, classified
by `fr.usage.classify`); a message with none is narration. A session without a
dollar figure contributes no dollars, and an `unavailable` one contributes
nothing at all — both render `—`, never `0`.

Step windows come from a run cursor: step `s` owns the messages with a
timestamp in `(previous step's at, s.at]`, the first window opening at the
run's `started`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from fr.run.telemetry import parse_timestamp
from fr.usage.classify import NARRATION, Classification, classify
from fr.usage.model import WEIGHTS, Message, UsageRecord

UNATTRIBUTED = Classification("other", "unattributed")
OUTSIDE = "(outside run)"
"""The step name for a message no step window contains."""


@dataclass(frozen=True)
class Window:
    step: str
    start: datetime | None
    end: datetime


@dataclass(frozen=True)
class SessionRow:
    session: str
    harness: str
    usd: float | None
    source: str
    unavailable: str | None
    attribution: str
    messages: int
    by_activity: dict[str, float]


@dataclass
class Rollup:
    sessions: list[SessionRow] = field(default_factory=list)
    by_model: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    by_activity: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    by_sub: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    by_step: dict[str, dict[str, float]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(float))
    )
    calls: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def total(self) -> float | None:
        """Summed harness dollars, or `None` when no session had a figure."""
        priced = [s.usd for s in self.sessions if s.usd is not None]
        return sum(priced) if priced else None

    def share(self, activity: str) -> float | None:
        total = self.total
        if not total:
            return None
        return self.by_activity.get(activity, 0.0) / total


def windows_from_cursor(cursor: Mapping[str, object]) -> list[Window]:
    """Step windows from a run cursor's raw mapping (read tolerantly: only the
    run's `started` and each top-level step's `at` are needed, so any cursor
    version serves)."""
    steps = cursor.get("steps")
    stamped: list[tuple[datetime, str]] = []
    for name, record in steps.items() if isinstance(steps, Mapping) else ():
        at = parse_timestamp(record.get("at")) if isinstance(record, Mapping) else None
        if at is not None:
            stamped.append((at, str(name)))
    stamped.sort()
    out: list[Window] = []
    previous = parse_timestamp(cursor.get("started"))
    for at, name in stamped:
        out.append(Window(step=name, start=previous, end=at))
        previous = at
    return out


def _step_of(message: Message, windows: Sequence[Window]) -> str | None:
    if not windows:
        return None
    ts = parse_timestamp(message.ts)
    if ts is None:
        return OUTSIDE
    ts = ts.replace(microsecond=0)
    for window in windows:
        if (window.start is None or ts > window.start) and ts <= window.end:
            return window.step
    return OUTSIDE


def _prices(record: UsageRecord, weights: Mapping[str, float]) -> tuple[dict[str, float], float]:
    """Dollars per weighted unit for each model, and the unattributed remainder."""
    units: dict[str, float] = defaultdict(float)
    for message in record.messages:
        units[message.model] += message.tokens.weighted(weights)
    usd = record.cost.usd
    if usd is None:
        return {}, 0.0
    if not record.cost.by_model:
        pool = sum(units.values())
        if pool <= 0:
            return {}, usd
        return {model: usd / pool for model in units}, 0.0
    prices: dict[str, float] = {}
    remainder = 0.0
    for model, dollars in record.cost.by_model.items():
        if units.get(model, 0.0) > 0:
            prices[model] = dollars / units[model]
        else:
            remainder += dollars
    # a model with messages but no harness figure carries no dollars (price 0);
    # a per-model breakdown that does not add up to the total is made whole
    remainder += usd - sum(record.cost.by_model.values())
    return prices, remainder


def rollup(
    records: Iterable[UsageRecord],
    weights: Mapping[str, float] = WEIGHTS,
    windows: Sequence[Window] = (),
) -> Rollup:
    result = Rollup()
    for record in records:
        activity: dict[str, float] = defaultdict(float)
        if record.unavailable is None:
            prices, remainder = _prices(record, weights)
            for message in record.messages:
                dollars = message.tokens.weighted(weights) * prices.get(message.model, 0.0)
                labels = [classify(c.name, c.target) for c in message.tool_calls] or [NARRATION]
                step = _step_of(message, windows)
                for label in labels:
                    result.calls[label.sub] += 1
                if not dollars:
                    # an unpriced message adds no dollar row: a `$0.00` would
                    # read as a measurement of nothing, not an absence of one
                    continue
                share = dollars / len(labels)
                for label in labels:
                    activity[label.activity] += share
                    result.by_sub[label.sub] += share
                    if step is not None:
                        result.by_step[step][label.activity] += share
                if dollars:
                    result.by_model[message.model] += dollars
            if remainder:
                activity[UNATTRIBUTED.activity] += remainder
                result.by_sub[UNATTRIBUTED.sub] += remainder
                if windows:
                    result.by_step[OUTSIDE][UNATTRIBUTED.activity] += remainder
                for model, dollars in record.cost.by_model.items():
                    if model not in prices:
                        result.by_model[model] += dollars
        for name, dollars in activity.items():
            result.by_activity[name] += dollars
        result.sessions.append(
            SessionRow(
                session=record.session,
                harness=record.harness,
                usd=record.cost.usd if record.unavailable is None else None,
                source=record.cost.source,
                unavailable=record.unavailable,
                attribution=record.attribution,
                messages=len(record.messages),
                by_activity=dict(activity),
            )
        )
    return result
