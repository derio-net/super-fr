"""Read-only gh-API observer.

Walks every phase in a plan that has a `tracking_issue`, queries gh
for current Issue + linked-PR state, and returns a `GhState`. Never
mutates anything.

Phases without a `tracking_issue` are silently skipped — they haven't
been dispatched yet, so there's nothing to observe.
"""

from __future__ import annotations

from typing import Any

from fr._urls import parse_issue_url
from fr.ghclient import GhClient
from fr.parser import Plan
from fr.states import GhState, PhaseObservation, PrObservation

_VALID_ISSUE_STATES = ("OPEN", "CLOSED")
_VALID_PR_STATES = ("OPEN", "CLOSED")
_VALID_CI_STATES = ("PASS", "FAIL", "PENDING", "NONE")


def _to_pr_observation(pr: dict[str, Any]) -> PrObservation:
    """Coerce a gh PR dict into a PrObservation, validating enum fields."""
    state = pr["state"]
    if state not in _VALID_PR_STATES:
        raise ValueError(f"unexpected PR state from gh: {state!r}")
    ci = pr.get("ci", "NONE")
    if ci not in _VALID_CI_STATES:
        raise ValueError(f"unexpected PR ci from gh: {ci!r}")
    return PrObservation(
        url=str(pr["url"]),
        state=state,
        merged=bool(pr.get("merged", False)),
        draft=bool(pr.get("draft", False)),
        ci=ci,
    )


def observe(plan: Plan, gh: GhClient) -> GhState:
    phases: dict[int, PhaseObservation] = {}
    for phase in plan.phases:
        url = phase.phase.tracking_issue
        if not url:
            continue
        repo, number = parse_issue_url(url)
        info = gh.view_issue(repo, number)
        state = info["state"]
        if state not in _VALID_ISSUE_STATES:
            raise ValueError(f"unexpected Issue state from gh for {repo}#{number}: {state!r}")
        prs = gh.list_linked_prs(repo, number)
        phases[phase.phase.number] = PhaseObservation(
            issue_state=state,
            issue_labels=frozenset(info.get("labels", [])),
            issue_assignees=tuple(info.get("assignees", [])),
            linked_prs=tuple(_to_pr_observation(pr) for pr in prs),
            body=str(info.get("body", "")),
        )
    return GhState(phases=phases)
