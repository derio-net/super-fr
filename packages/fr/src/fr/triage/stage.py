"""Stages are derived, never set (spec §3.E, decision d3).

Pure functions over the facts models: the page is read-only, and "moving" an
issue means doing the work and re-running `collect`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable

    from fr.triage.model import Issue, PullRequest

Stage = Literal["closed", "merged", "pr-ready", "pr-draft", "blocked", "backlog"]

# Most advanced first. The ONE ordering: `derive_stage`, the collector's
# most-advanced-PR rule and the page's display order all read it.
STAGES: tuple[Stage, ...] = ("closed", "merged", "pr-ready", "pr-draft", "blocked", "backlog")


def pr_stage(pr: PullRequest) -> Stage | None:
    """The stage one PR would give an open issue; a closed, unmerged PR gives none."""
    if pr.state == "MERGED":
        return "merged"
    if pr.state == "OPEN":
        return "pr-draft" if pr.is_draft else "pr-ready"
    return None


def pr_rank(pr: PullRequest) -> int:
    """Sort key, lower is more advanced — the position of `pr_stage` in `STAGES`."""
    stage = pr_stage(pr)
    return STAGES.index(stage) if stage is not None else len(STAGES)


def derive_stage(issue: Issue, prs: Iterable[PullRequest]) -> Stage:
    """The stage of *issue* given the PRs that name it; the most advanced PR wins."""
    if issue.state == "closed":
        return "closed"
    from_prs = [s for s in map(pr_stage, prs) if s is not None]
    if from_prs:
        return min(from_prs, key=STAGES.index)
    if any(label.lower() == "blocked" for label in issue.labels):
        return "blocked"
    return "backlog"
