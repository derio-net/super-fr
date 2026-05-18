"""Concern K — agent prompt construction.

Ports `build_prompt:605-639` from the legacy bridge with one critical
change: the dependency preamble is derived from `phase.depends_on` (the
structured plan field), NOT from the GH Issue body. Body-text parsing
is gone in v2 — the plan is authoritative.

The bridge writes this prompt to the workspace's initial agent message.
The deps preamble fires whenever `depends_on` is non-empty so the agent
self-gates on blockers even if the dispatch-side `vk-blocked` projection
slipped through.
"""

from __future__ import annotations

from vk._urls import parse_issue_url
from vk.parser import Plan
from vk.types import PhaseDoc

__all__ = ["build_prompt"]


_DEPS_PREAMBLE_TEMPLATE = (
    "BEFORE YOU BEGIN: This Issue declares dependencies: {dep_refs}.\n"
    "Verify each is CLOSED via `gh issue view <n> --repo <owner/repo> --json state`.\n"
    "If any is OPEN:\n"
    "  - STOP. Do not start work.\n"
    "  - Do not duplicate the upstream work.\n"
    "  - Do not start 'parts that don't depend on it'.\n"
    "  - Exit with message: 'Blocked on <open_blocker>, not starting.'\n"
    "The bridge should have deferred this workspace if a blocker were "
    "open — if you see this and blockers are open, report it to the "
    "operator.\n\n"
    "---\n\n"
)


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

    preamble = ""
    if phase.phase.depends_on:
        dep_refs = ", ".join(_dep_ref(plan, dep) for dep in phase.phase.depends_on)
        preamble = _DEPS_PREAMBLE_TEMPLATE.format(dep_refs=dep_refs)

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
