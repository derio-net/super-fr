"""Read-only gh-API observer.

Walks every phase in a plan that has a `tracking_issue`, queries gh
for current Issue + linked-PR state, and returns a `GhState`. Never
mutates anything.

Phases without a `tracking_issue` are silently skipped — they haven't
been dispatched yet, so there's nothing to observe.
"""

from __future__ import annotations

import re
from typing import Any

from vk.v2.ghclient import GhClient
from vk.v2.parser import Plan
from vk.v2.states import GhState, PhaseObservation, PrObservation

_ISSUE_URL_RE = re.compile(r"^https://github\.com/([^/]+/[^/]+)/issues/(\d+)$")


def _parse_issue_url(url: str) -> tuple[str, int]:
    """('https://github.com/owner/repo/issues/N') -> ('owner/repo', N)."""
    m = _ISSUE_URL_RE.match(url)
    if not m:
        raise ValueError(f"not a github issue url: {url}")
    return m.group(1), int(m.group(2))


def _to_pr_observation(pr: dict[str, Any]) -> PrObservation:
    """Coerce a gh PR dict into a PrObservation."""
    return PrObservation(
        url=str(pr["url"]),
        state=pr["state"],
        merged=bool(pr.get("merged", False)),
        draft=bool(pr.get("draft", False)),
        ci=pr.get("ci", "NONE"),
    )


def observe(plan: Plan, gh: GhClient) -> GhState:
    phases: dict[int, PhaseObservation] = {}
    for phase in plan.phases:
        url = phase.phase.tracking_issue
        if not url:
            continue
        repo, number = _parse_issue_url(url)
        info = gh.view_issue(repo, number)
        prs = gh.list_linked_prs(repo, number)
        phases[phase.phase.number] = PhaseObservation(
            issue_state=info["state"],
            issue_labels=frozenset(info.get("labels", [])),
            issue_assignees=tuple(info.get("assignees", [])),
            linked_prs=tuple(_to_pr_observation(pr) for pr in prs),
        )
    return GhState(phases=phases)
