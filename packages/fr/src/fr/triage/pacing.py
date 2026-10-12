"""The drive's pacing, with its IO: `pacing.json` and `/rate_limit` (spec 2026-10-12-quota-pacing).

`quota` holds the pure decisions; this holds the one helper both adapters use — the
host loop and the cloud `drive pass` — so a rate limit is read, recorded and reported
the same way on both. Pacing is an optimisation: whatever fails here fails open.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from fr.triage import pacing_state, quota
from fr.triage.pacing_state import PacingState
from fr.triage.quota import Budget, Pace, RateLimitSource


class Pacer:
    def __init__(
        self,
        target: Path,
        *,
        floor: float,
        interval_s: float,
        api: str,
        forge: Callable[[], RateLimitSource],
        now: Callable[[], datetime],
        warn: Callable[[str], None],
    ) -> None:
        self.target, self.floor, self.interval_s, self.api = target, floor, interval_s, api
        self._forge, self._now, self._warn = forge, now, warn
        self._warned: set[str] = set()
        self.state, problem = pacing_state.load(target)
        if problem:
            self._once(problem)
        self.budget: Budget | None = None

    def _once(self, why: str) -> None:
        """R5: a cause is reported once, however many passes meet it."""
        if why not in self._warned:
            self._warned.add(why)
            self._warn(why)

    def _save(self, state: PacingState) -> None:
        self.state = state
        try:
            pacing_state.save(self.target, state)
        except OSError as exc:  # a pass is never lost to its bookkeeping
            self._once(f"pacing.json not written ({exc})")

    def read(self) -> Budget | None:
        """The paced budget now (`/rate_limit` is free); None, with the cause reported
        once, when it cannot be read: the pass then runs as it does without pacing (R5)."""
        budget, why = quota.budget_or_why(self._forge, self.api)
        if why is not None:
            self._once(f"quota: /rate_limit could not be read ({why}); not pacing this pass")
        self.budget = budget
        if budget is not None:
            self.state = replace(self.state, budget=budget.to_json())
        return budget

    def before_pass(self) -> Pace:
        """R3: read the budget and decide, before any collect."""
        pace = quota.decide(
            self.read(), self.floor, self._now(), self.state, interval=self.interval_s
        )
        if pace.kind == "run":
            self._save(self.state)  # the budget read is the footer's (R14)
        return pace

    def rate_limited(self) -> Pace:
        """R2/R4: a pass met a rate limit. Read `/rate_limit` once to learn the reset,
        and record the wait so any other loop on this state honours it."""
        pace, state = quota.after_rate_limit(self.read(), self._now(), self.state, self.interval_s)
        self._save(state)
        return pace

    def clean(self) -> None:
        """A pass that met no rate limit ends the backoff and the recorded wait."""
        clean = quota.clean_pass(self.state)
        if clean != self.state:
            self._save(clean)

    def line(self, pace: Pace) -> str:
        return quota.quota_line(self.budget, self.floor, pace, self._now())
