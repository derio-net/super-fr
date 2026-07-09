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

Backend-parameterized (GitHub/GitLab/Gitea) as of the multi-backend
design (see docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md §7): the noun
("GitHub Issue"/"GitLab Issue"/"Gitea Issue"), the tag (`gh#`/`gl#`/
`gt#`), and the dependency-check verify command are all resolved from
the phase's `tracking_issue` URL's own hostname via `fr._hosts`, not
hardcoded to GitHub. `fr._hosts.TAG_FOR_BACKEND` is shared with
`fr_vk._cardref` — not duplicated here — since `fr_dispatch` depends
only on `fr`, never on the fr_vk runner adapter.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fr._hosts import TAG_FOR_BACKEND, HostBackend, backend_for_hostname
from fr._urls import parse_issue_url
from fr.parser import Plan
from fr.types import PhaseDoc

__all__ = ["build_prompt"]


_SYNC_LINE = (
    "1. Fetch and rebase your worktree on origin/main: "
    "`git fetch origin && git rebase origin/main`. "
    "If rebase produces conflicts, STOP and report."
)

_ISSUE_NOUN: dict[HostBackend, str] = {
    "github": "GitHub Issue",
    "gitlab": "GitLab Issue",
    "gitea": "Gitea Issue",
}

# The dependency-check verify command an agent runs to confirm a blocker
# phase's tracking Issue is CLOSED. `<n>`/`<owner/repo>` are placeholders
# the agent substitutes; flag names verified directly against each CLI's
# own `--help` output during the multi-backend design's research (glab's
# `-R`/`--output json`, tea's no-`view`-subcommand shape).
_VERIFY_COMMAND: dict[HostBackend, str] = {
    "github": "`gh issue view <n> --repo <owner/repo> --json state`",
    "gitlab": "`glab issue view <n> -R <owner/repo> --output json`",
    "gitea": "`tea issues <n> --repo <owner/repo> --output json`",
}


def _backend_for_tracking_url(url: str) -> HostBackend:
    """Resolve backend from the tracking_issue URL's hostname alone —
    `build_prompt` has no `repo_root` to read explicit
    `.devcontainer/fr-profiles.yaml` config from (unlike
    `fr._hosts.detect_backend`'s full 3-tier resolution). This means a
    Gitea-hosted phase's prompt falls back to "GitHub Issue" wording:
    Gitea has no free hostname default (self-hosting is the norm), so
    hostname-alone resolution can never identify it, even for a literal
    `gitea.com` URL. A known, documented boundary (see
    test_prompt_backend_wording_gitea_hostname_alone_is_not_enough), not
    a bug — fixing it would mean threading a repo_root (or an explicit
    backend override) through `fr_dispatch.tick`/`dispatch_phase`'s
    signatures, out of scope for this pass.
    """
    return backend_for_hostname(urlparse(url).hostname)


def _deps_line(dep_refs: str, backend: HostBackend) -> str:
    return (
        f"2. This Issue declares dependencies: {dep_refs}. "
        f"Verify each is CLOSED via "
        f"{_VERIFY_COMMAND[backend]}. "
        "If any is OPEN, STOP and exit with: "
        "'Blocked on <open_blocker>, not starting.'"
    )


def _build_preamble(plan: Plan, phase: PhaseDoc, backend: HostBackend) -> str:
    items = [_SYNC_LINE]
    if phase.phase.depends_on:
        dep_refs = ", ".join(_dep_ref(plan, dep, backend) for dep in phase.phase.depends_on)
        items.append(_deps_line(dep_refs, backend))
    return "BEFORE YOU BEGIN:\n" + "\n".join(items) + "\n\n---\n\n"


def _dep_ref(plan: Plan, dep_number: int, backend: HostBackend) -> str:
    """Render one dep reference. Prefers the dep's tracking_issue (as
    `#N`); falls back to `Phase N` when the upstream phase hasn't been
    dispatched yet.

    `backend` is the DEPENDENT phase's own backend, used only for the
    `Phase N` fallback text — the `#N` form is backend-neutral (a plain
    issue-number reference), so a cross-backend dependency chain (rare,
    not a design goal in itself) doesn't need per-dep backend resolution.
    """
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


def build_prompt(
    plan: Plan,
    phase: PhaseDoc,
    *,
    agent_identity: str = "a runner-spawned agent",
    execute_skill: str = "fr-execute",
) -> str:
    """Render the agent prompt for one dispatched phase.

    Raises:
        ValueError: if `phase.tracking_issue` is unset OR malformed —
            building a prompt for a non-dispatchable phase is a
            programmer error, since the agent has no tracking Issue URL
            to anchor on.
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
    backend = _backend_for_tracking_url(tracking)
    tag = TAG_FOR_BACKEND[backend]
    noun = _ISSUE_NOUN[backend]

    preamble = _build_preamble(plan, phase, backend)

    repos = _format_repos(plan, repo)

    return (
        preamble
        + f"You are {agent_identity} working on {noun} {tag}#{issue_n}:\n"
        + f"{phase.phase.title}\n\n"
        + f"The Issue is at: {tracking}\n"
        + f"Repos: {repos}\n\n"
        + f"Use {execute_skill} to implement this task.\n\n"
        + f"The full task description is in the {noun} body — read it before "
        + "starting. When you finish, open a PR. The lifecycle board will reflect "
        + "your progress automatically."
    )
