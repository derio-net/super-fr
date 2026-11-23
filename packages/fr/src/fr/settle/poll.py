"""The bounded settle poll (spec 2026-11-23-pr-readiness-wait R3, R11).

`settle` reads the PR, evaluates it, and reads again every `POLL_INTERVAL` seconds while
a concern under `report` or `fix` is `unknown` or `pending`, until the wait ends. A
concern under `off` is not read. It only ever reads: no push, no PR edit, no ready, no
merge. The clock, the sleeper and the head's commit time are injected.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Final

from fr.ghclient import UnsupportedForgeOperation
from fr.settle.evaluate import evaluate, unsupported_verdict
from fr.settle.model import Modes, SettleRefused, Verdict

DEFAULT_WAIT: Final = 300
WAIT_CEILING: Final = 540
"""Both below 600 seconds, so one call fits in an agent's shell tool (R3)."""
POLL_INTERVAL: Final = 15.0


__all__ = ["DEFAULT_WAIT", "POLL_INTERVAL", "WAIT_CEILING", "SettleRefused", "check_wait", "settle"]


def check_wait(wait: float) -> None:
    if wait < 0 or wait > WAIT_CEILING:
        raise SettleRefused(
            f"--wait {wait:g} is outside 0..{WAIT_CEILING} seconds: one call must fit in an "
            "agent's shell tool; call `fr pr settle` again to wait longer"
        )


def settle(
    client: Any,
    repo: str,
    pr: int,
    *,
    gate_names: Sequence[str] | None,
    modes: Modes,
    ci_none: bool,
    wait: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    committed_at: Callable[[str], float],
    first_view: dict[str, Any] | None = None,
) -> Verdict:
    """Poll PR *pr* of *repo* until it settles or *wait* seconds pass. *committed_at*
    gives a head sha's commit time (the no-CI wait reads it); *first_view* is a
    `pr_view` the caller already read, used for the first round instead of a read."""
    check_wait(wait)
    read_checks = modes.ci.mode != "off" and not ci_none
    deadline = clock() + wait
    pending_view = first_view
    while True:
        view: dict[str, Any] = {}
        try:
            if pending_view is not None:
                view, pending_view = pending_view, None
            elif not modes.both_off:
                view = client.pr_view(repo, pr)
            checks = client.pr_checks(repo, pr) if read_checks else []
        except UnsupportedForgeOperation as e:
            head = str(view.get("head_oid") or "")
            return unsupported_verdict(modes, backend=e.backend, op=e.op, head=head)
        state = str(view.get("state") or "OPEN")
        if state != "OPEN":
            raise SettleRefused(f"PR #{pr} is {state}, not open: there is nothing to settle")
        head = str(view.get("head_oid") or "")
        now = clock()
        verdict = evaluate(
            view,
            checks,
            gate_names,
            modes,
            ci_none=ci_none,
            head_committed_at=committed_at(head) if head else now,
            now=now,
        )
        left = deadline - now
        if verdict.settled or left <= 0:
            return verdict
        sleep(min(POLL_INTERVAL, left))
