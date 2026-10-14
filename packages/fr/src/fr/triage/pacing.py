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

from fr.triage import pacing_state, probe, quota
from fr.triage.model import Facts, Judgements
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

    def limited(self, text: str = "") -> bool:
        """Did a pass meet a rate limit? Its text may say so; when it does not (a visibility
        read or a write whose error names no limit), the free `/rate_limit` still can: a
        budget at zero before its reset is the limit, whatever the failure said."""
        if quota.is_rate_limited(text):
            return True
        budget = self.read()
        return (
            budget is not None
            and budget.remaining <= 0
            and budget.reset + quota.RESET_MARGIN > self._now()
        )

    def clean(self) -> None:
        """A pass that met no rate limit ends the backoff and the recorded wait."""
        clean = quota.clean_pass(self.state)
        if clean != self.state:
            self._save(clean)

    def line(self, pace: Pace) -> str:
        return quota.quota_line(self.budget, self.floor, pace, self._now())

    # ------------------------------------------------ probes and pass kinds (§B, §C)

    def plan(
        self,
        forge: probe.Prober,
        *,
        repos: list[str],
        facts: Facts | None,
        judgements: Judgements | None,
        digest: str,
        essential: bool,
        board: bool = False,
    ) -> probe.PassPlan:
        """Probe every repo (before any collect, R8) and decide the pass (R7, R9-R11).
        No previous facts is always a full pass: there is nothing to carry.

        *board* (the kanban watch, R17) plans against the judgements digest alone: it has
        no drive summary to stand for a quiet pass, and records none, so a drive that
        follows still plans (`record_digest`)."""
        now = self._now()
        state = replace(self.state, summary=self.state.summary or {}) if board else self.state
        full = facts is None or probe.full_due(self.state, now)
        probes = probe.probe_set(repos, facts, judgements)
        changed, pending = probe.run_probes(forge, probes, state, full=full)
        plan = probe.plan_pass(
            state if facts is not None else replace(state, full_at=None),
            now,
            repos=repos,
            changed=changed,
            digest=digest,
            below_floor=essential,
            live=probe.live_repos(facts, judgements),
            pending=pending,
            probes=sum(len(p) for p in probes.values()),
            full=full,
            closing=probe.closing_repos(facts, judgements),
        )
        if facts is None:  # nothing to carry from: the collect reads every repo (p2-r5)
            plan = replace(plan, only=None, carried=frozenset())
        return plan

    def after_collect(self, plan: probe.PassPlan, facts: Facts, carried: frozenset[str]) -> None:
        """Once `facts.json` is written (R11): store the pending ETags of the repos read
        successfully, drop a failed repo's, and, when every repo was read, record the full
        pass. *carried* is the set the collect itself carried (p2-r5). A repo is failed
        when collect skipped it or left one of its keys unviewed on a rate limit (p2-r2).

        The last planned pass's summary and digest are dropped here (p2-r1): the facts
        moved on, and this pass may still fail before it plans, so nothing may be quiet on
        their strength; `record_summary` writes both once the pass has planned."""
        failed = {s.repo for s in facts.skipped} | _rate_limited_repos(facts)
        read = set(facts.repos) - set(carried) - failed
        state = probe.promote(self.state, plan.pending, read_ok=read, failed=failed)
        state = replace(state, summary=None, judgements_digest=None)
        if plan.only is None:
            state = replace(state, full_at=self._now())
        self._save(state)

    def record_summary(self, summary: dict[str, int], *, digest: str, held: bool) -> None:
        """The planned pass's summary, which a quiet pass reports as its own (R9), the
        judgements it planned on, and whether it held its dispatches for the quota: a pass
        back above the floor after a held one is never quiet (p2-r3)."""
        self._save(
            replace(
                self.state, summary=dict(summary), judgements_digest=digest, held_for_quota=held
            )
        )

    def record_digest(self, digest: str) -> None:
        """The board watch's collect (R17): the judgements it collected on, and no summary, so
        the next watch pass can be quiet and a drive's next pass cannot."""
        self._save(replace(self.state, judgements_digest=digest))

    def stretch(self, until: datetime | None) -> None:
        """R7: below the floor the next pass waits until *until* (four intervals)."""
        self._save(replace(self.state, next_pass_at=until))


def _rate_limited_repos(facts: Facts) -> set[str]:
    """The repos of the judged keys the collect left unviewed on a rate limit (p2-r2). A
    key is `<repo-name>#<n>`; a group never holds two repos of one name."""
    names = {
        u.key.split("#", 1)[0].lower() for u in facts.unviewed if quota.is_rate_limited(u.reason)
    }
    return {r for r in facts.repos if r.split("/", 1)[-1].lower() in names}
