"""Pacing the drive against the host's shared rate budget (spec 2026-10-12-quota-pacing §A, R1-R6).

Every function here is pure: the clock is passed in, the budget is read by the
caller (`read_budget`, over the `Forge` seam), and the state is a loaded
`pacing.json`. The host loop and the cloud pass both ask the same `decide`.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

from fr.triage.pacing_state import PacingState

# GitHub's reset is announced to the second; a margin keeps the first call after it
# from landing on the old window (R2).
RESET_MARGIN = timedelta(seconds=30)
# R4's ceiling on the secondary-limit backoff.
BACKOFF_CAP_SECONDS = 900
_MAX_BACKOFF = 32
_MAX_EXPONENT = 10  # 2**10 already exceeds the cap for any sane interval
# R7: an essential-only pass stretches the next one to this many intervals.
ESSENTIAL_STRETCH = 4

_RESOURCES = {"graphql": ("graphql", "core"), "rest": ("core",)}


@dataclass(frozen=True)
class Budget:
    resource: str
    remaining: int
    limit: int
    reset: datetime

    @property
    def fraction(self) -> float:
        return self.remaining / self.limit

    def to_json(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "remaining": self.remaining,
            "limit": self.limit,
            "reset": self.reset.astimezone(UTC).isoformat(),
        }


def budget_from_json(data: dict[str, Any] | None) -> Budget | None:
    """The inverse of `Budget.to_json`, None for a missing or unusable record."""
    try:
        assert data is not None
        return Budget(
            str(data["resource"]),
            int(data["remaining"]),
            int(data["limit"]),
            datetime.fromisoformat(str(data["reset"])),
        )
    except (AssertionError, KeyError, TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Pace:
    """What the drive does next: `run`, `essential` (below the floor) or `wait`."""

    kind: Literal["run", "essential", "wait"]
    until: datetime | None = None  # `wait`: resume time; `essential`: the next pass
    why: str = ""

    @property
    def essential(self) -> bool:
        return self.kind == "essential"


class RateLimitSource(Protocol):
    def rate_limit(self) -> dict[str, Any]: ...


def budget_from_rate_limit(raw: dict[str, Any], api: str) -> Budget:
    """The lowest remaining fraction among the resources *api* spends (R1)."""
    resources = raw.get("resources") if isinstance(raw, dict) else None
    found: list[Budget] = []
    for name in _RESOURCES.get(api, _RESOURCES["graphql"]):
        entry: Any = resources.get(name) if isinstance(resources, dict) else None
        try:
            limit = int(entry["limit"])
            if limit > 0:
                reset = datetime.fromtimestamp(int(entry["reset"]), UTC)
                found.append(Budget(name, int(entry["remaining"]), limit, reset))
        except (KeyError, TypeError, ValueError):
            continue
    if not found:
        raise ValueError(f"rate_limit: no usable {'/'.join(_RESOURCES.get(api, ()))} resource")
    return min(found, key=lambda b: b.fraction)


def budget_or_why(
    forge: Callable[[], RateLimitSource], api: str
) -> tuple[Budget | None, str | None]:
    """The paced budget, else why it could not be read (R5: the caller fails open and
    reports the cause once). *forge* is a factory, so a forge that cannot even be built
    fails open too."""
    try:
        return budget_from_rate_limit(forge().rate_limit(), api), None
    except Exception as exc:  # noqa: BLE001 — any failure to read a free route fails open
        return None, str(exc) or type(exc).__name__


def read_budget(forge: RateLimitSource, api: str) -> Budget | None:
    """The paced budget, or None when `/rate_limit` cannot be read (R5: fail open)."""
    return budget_or_why(lambda: forge, api)[0]


def is_rate_limited(text: str) -> bool:
    """R2: a rate limit by its text. `gh.classify` needs a `403` and so misses
    GraphQL's `API rate limit exceeded for user ID …`, which carries no status."""
    return "rate limit" in text.lower() or "RATE_LIMITED" in text


def _wait(budget: Budget, why: str) -> Pace:
    return Pace("wait", budget.reset + RESET_MARGIN, why)


def decide(
    budget: Budget | None,
    floor: float,
    now: datetime,
    state: PacingState,
    *,
    interval: float = 120,
) -> Pace:
    """R3/R5/R7: a recorded wait still ahead, else the budget against the floor (and,
    below it, the stretched next pass)."""
    if state.wait_until is not None and state.wait_until > now:
        return Pace("wait", state.wait_until, "recorded wait")
    if budget is None:
        return Pace("run")
    if budget.remaining <= 0:
        if budget.reset + RESET_MARGIN > now:
            return _wait(budget, "exhausted")
        return Pace("run")  # a reading from before its own reset: stale, not a reason to wait
    if budget.fraction < floor:
        if state.next_pass_at is not None and state.next_pass_at > now:  # R7's stretch
            return Pace("wait", state.next_pass_at, "below floor")
        return Pace("essential", now + timedelta(seconds=ESSENTIAL_STRETCH * interval), "floor")
    return Pace("run")


def after_rate_limit(
    budget: Budget | None, now: datetime, state: PacingState, interval: float
) -> tuple[Pace, PacingState]:
    """R2/R4: the wait after a rate-limit response, and the state recording it. An
    exhausted reading whose reset is already past is stale: it backs off as a secondary limit."""
    if budget is not None and budget.remaining <= 0 and budget.reset + RESET_MARGIN > now:
        pace = _wait(budget, "exhausted")
        return pace, replace(state, wait_until=pace.until)
    delay = min(interval * 2 ** min(max(state.backoff, 0), _MAX_EXPONENT), BACKOFF_CAP_SECONDS)
    pace = Pace("wait", now + timedelta(seconds=delay), "secondary limit")
    backoff = min(max(state.backoff, 0) + 1, _MAX_BACKOFF)  # the count stops growing too
    return pace, replace(state, backoff=backoff, wait_until=pace.until)


def clean_pass(state: PacingState) -> PacingState:
    """A pass that met no rate limit: the backoff and the recorded wait are over."""
    return replace(state, backoff=0, wait_until=None)


def _minutes(delta: timedelta) -> str:
    return f"{max(1, math.ceil(delta.total_seconds() / 60))}m"


def quota_line(budget: Budget | None, floor: float, verdict: Pace, now: datetime) -> str:
    """R13: the one line logged whenever the drive throttles itself."""
    until = verdict.until
    if budget is None:
        head = "quota: unreadable"
    else:
        head = (
            f"quota: {budget.resource} {budget.remaining}/{budget.limit} "
            f"({round(budget.fraction * 100)}%), resets {budget.reset:%H:%M}Z"
        )
    if verdict.kind == "essential" and until is not None:
        return (
            f"{head}; below floor {round(floor * 100)}%: essential-only pass, "
            f"dispatch held, next pass in {_minutes(until - now)}"
        )
    if verdict.kind == "wait" and until is not None:
        return f"{head}; {verdict.why}: waiting {_minutes(until - now)} (until {until:%H:%M}Z)"
    return head
