"""Concern K — agent prompt construction.

Ports `build_prompt:605-639` from the legacy bridge with one critical
change: the dependency preamble is derived from `phase.depends_on` (the
structured plan field), NOT from the GH Issue body. Body-text parsing
is gone in v2 — the plan is authoritative.

The bridge writes this prompt to the workspace's initial agent message.
Every prompt opens with a combined numbered "BEFORE YOU BEGIN" block —
the shape is "numbered list of pre-flight checks; the bridge prepends;
agents self-gate on each item":

- **Item 1 (sync)** fires unconditionally on every dispatch. The bridge
  pod's `~/repos/<repo>` checkouts are shared with the operator and
  can't be auto-pulled by the bridge (would clobber operator's
  in-progress work), so agent-side `git fetch && git rebase
  origin/main` compensates without violating shared-pod ownership.
  Added in Phase 8 of #147 after the 2026-05-18 stale-checkout
  incident (the bridge projected Phase 5 of #147 as `vk-blocked` for
  9 hours because its plan checkout was out of date).
- **Item 2 (deps)** is conditional on `phase.depends_on`. The agent
  self-gates on open blockers even if the dispatch-side `vk-blocked`
  projection slipped through.
"""

from __future__ import annotations

from vk._urls import parse_issue_url
from vk.parser import Plan
from vk.types import PhaseDoc

__all__ = ["build_prompt"]


_SYNC_LINE = (
    "1. Fetch and rebase your worktree on origin/main: "
    "`git fetch origin && git rebase origin/main`. "
    "If rebase produces conflicts, STOP and report."
)


def _deps_line(dep_refs: str) -> str:
    return (
        f"2. This Issue declares dependencies: {dep_refs}. "
        "Verify each is CLOSED via "
        "`gh issue view <n> --repo <owner/repo> --json state`. "
        "If any is OPEN, STOP and exit with: "
        "'Blocked on <open_blocker>, not starting.'"
    )


def _build_preamble(plan: Plan, phase: PhaseDoc) -> str:
    items = [_SYNC_LINE]
    if phase.phase.depends_on:
        dep_refs = ", ".join(_dep_ref(plan, dep) for dep in phase.phase.depends_on)
        items.append(_deps_line(dep_refs))
    return "BEFORE YOU BEGIN:\n" + "\n".join(items) + "\n\n---\n\n"


def _dep_ref(plan: Plan, dep_number: int) -> str:
    """Render one dep reference. Prefers the dep's tracking_issue (as
    `#N`); falls back to `Phase N` when the upstream phase hasn't been
    dispatched yet."""
    for p in plan.phases:
        if p.phase.number == dep_number:
            url = p.phase.tracking_issue
            if url:
                try:
                    _, issue_n = parse_issue_url(url)
                except ValueError:
                    return f"Phase {dep_number}"
                return f"#{issue_n}"
            return f"Phase {dep_number}"
    return f"Phase {dep_number}"


def _format_repos(plan: Plan, tracking_repo: str) -> str:
    """Render the `Repos:` line for the prompt.

    For a same-repo phase we list the one repo. For a cross-repo phase
    (`plan.meta.target_repo` ≠ the phase's `tracking_issue` repo) we
    list both so the agent reading the prompt isn't misled about where
    the work lands.

    Fallback chain: meta.target_repo + tracking_repo (deduped, ordered),
    then tracking_repo alone if meta is unset, then "" only if both are
    missing (shouldn't happen at dispatch time — `build_prompt` already
    requires `tracking_issue`).
    """
    meta_repo = getattr(plan.meta, "target_repo", None)
    if meta_repo and meta_repo != tracking_repo:
        return f"{meta_repo}, {tracking_repo}"
    return meta_repo or tracking_repo


def build_prompt(plan: Plan, phase: PhaseDoc) -> str:
    """Render the agent prompt for one dispatched phase.

    Raises:
        ValueError: if `phase.tracking_issue` is unset OR malformed —
            building a prompt for a non-dispatchable phase is a
            programmer error, since the agent has no GH Issue URL to
            anchor on.
    """
    tracking = phase.phase.tracking_issue
    if not tracking:
        raise ValueError(
            f"phase {phase.phase.number} has no tracking_issue — "
            "cannot build a prompt without an anchoring GH Issue"
        )
    # Canonical URL parser; raises ValueError on malformed inputs. The
    # live bridge never sees malformed URLs because the writeback path
    # stamps them via `apply()` → `_urls.build_issue_url`, but
    # propagating the error here surfaces test-fixture mistakes
    # immediately rather than rendering `gh#?:` and pretending it's OK.
    repo, issue_n = parse_issue_url(tracking)

    preamble = _build_preamble(plan, phase)

    repos = _format_repos(plan, repo)

    return (
        preamble
        + f"You are a VK-spawned agent working on GitHub Issue gh#{issue_n}:\n"
        + f"{phase.phase.title}\n\n"
        + f"The Issue is at: {tracking}\n"
        + f"Repos: {repos}\n\n"
        + "Use superpowers-for-vk:vk-execute to implement this task.\n\n"
        + "The full task description is in the GitHub Issue body — read it before "
        + "starting. When you finish, open a PR. The lifecycle board will reflect "
        + "your progress automatically."
    )
