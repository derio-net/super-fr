"""The operator's queue requests, folded (spec 2026-11-24-wave-queue-gaps R11, §C).

`fr triage queue add|remove` append `queue_add` / `queue_remove` events to the
judgements' `queue_requests:`; this pure module reads them. Nothing here touches the
forge, git or a file.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
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


REQUEST_REPO_KEY = "\0queue-request:"
"""The key prefix `reader_repos` gives a repo only queue requests name: no batch id can be it."""


def reader_repos(
    repos: Mapping[str, str],
    requests: Iterable[QueueAddEvent | QueueRemoveEvent],
    scope: str,
    collected: Iterable[str],
) -> dict[str, str]:
    """The driver's batch-to-repo map *repos* plus every collected repo (*collected*, the
    facts' repos) a queue request of *scope* names, each under a key no batch has (review
    p2-r3): `fr triage queue add` takes any collected repo, so the queue readers read a repo
    with no batch too, and R14's between-waves queue works there. The readers use only the
    map's values; the Snapshot's own `repos` stays the batches'."""
    have, known = set(repos.values()), set(collected)
    extra = sorted({e.repo for e in requests if e.scope == scope and e.repo in known} - have)
    return {**repos, **{f"{REQUEST_REPO_KEY}{r}": r for r in extra}}
