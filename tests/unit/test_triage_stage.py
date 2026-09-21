"""Stages are derived, never set — one case per row of spec §3.E (plan P2.T3)."""

from __future__ import annotations

from typing import Any

import pytest
from fr.triage.model import Issue, PullRequest
from fr.triage.stage import STAGES, derive_stage


def _pr(number: int, *, state: str, draft: bool = False) -> PullRequest:
    return PullRequest(
        repo="derio-net/super-fr",
        number=number,
        title=f"pr {number}",
        state=state,  # type: ignore[arg-type]
        is_draft=draft,
        merged_at="2026-09-20T00:00:00Z" if state == "MERGED" else None,
        url=f"https://github.com/derio-net/super-fr/pull/{number}",
    )


def _issue(*, state: str = "open", labels: list[str] | None = None, **kw: Any) -> Issue:
    return Issue(
        repo="derio-net/super-fr",
        number=1,
        title="t",
        state=state,  # type: ignore[arg-type]
        labels=labels or [],
        url="https://github.com/derio-net/super-fr/issues/1",
        **kw,
    )


MERGED = _pr(10, state="MERGED")
READY = _pr(11, state="OPEN")
DRAFT = _pr(12, state="OPEN", draft=True)
CLOSED_PR = _pr(13, state="CLOSED")


@pytest.mark.parametrize(
    ("issue", "prs", "stage"),
    [
        (_issue(state="closed"), [], "closed"),
        (_issue(), [MERGED], "merged"),
        (_issue(), [READY], "pr-ready"),
        (_issue(), [DRAFT], "pr-draft"),
        (_issue(labels=["Blocked"]), [], "blocked"),
        (_issue(labels=["blocked"]), [], "blocked"),
        (_issue(labels=["BLOCKED", "bug"]), [], "blocked"),
        (_issue(labels=["bug"]), [], "backlog"),
        (_issue(), [], "backlog"),
        # A closed issue with an open PR is still closed.
        (_issue(state="closed"), [READY], "closed"),
        # The most advanced linked PR wins, whatever order they arrive in.
        (_issue(), [DRAFT, READY, MERGED], "merged"),
        (_issue(), [DRAFT, READY], "pr-ready"),
        # A closed, unmerged PR advances nothing.
        (_issue(), [CLOSED_PR], "backlog"),
        # A PR outranks the blocked label: blocked means "no PR".
        (_issue(labels=["blocked"]), [DRAFT], "pr-draft"),
    ],
)
def test_derive_stage(issue: Issue, prs: list[PullRequest], stage: str) -> None:
    assert derive_stage(issue, prs) == stage


def test_the_six_stages_in_one_order_most_advanced_first() -> None:
    assert STAGES == ("closed", "merged", "pr-ready", "pr-draft", "blocked", "backlog")


def test_an_issue_exposes_its_derived_stage() -> None:
    assert _issue(prs=[DRAFT]).stage == "pr-draft"
