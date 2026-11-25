"""The operator's queue requests, folded (spec 2026-11-24-wave-queue-gaps R11, §C).

`fr triage queue add|remove` append `queue_add` / `queue_remove` events to the
judgements' `queue_requests:`; this pure module reads them. Nothing here touches the
forge, git or a file.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from fr.triage.model import QueueAddEvent, QueueRemoveEvent


@dataclass(frozen=True)
class Added:
    """A PR whose latest request is an add: by *by* at *at*, *preapproved* or not."""

    pr: int
    preapproved: bool
    at: datetime
    by: str


def added(
    requests: Iterable[QueueAddEvent | QueueRemoveEvent], repo: str, scope: str
) -> dict[int, Added]:
    """Each of *repo*'s PRs in *scope* whose latest request is an add, by PR number."""
    out: dict[int, Added] = {}
    for event in requests:
        if event.repo != repo or event.scope != scope:
            continue
        if isinstance(event, QueueAddEvent):
            out[event.pr] = Added(event.pr, event.preapproved, event.at, event.by)
        else:
            out.pop(event.pr, None)
    return out
