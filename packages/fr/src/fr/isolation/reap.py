"""The reap and gc value types of the isolation lifecycle (#1517).

`MergeVerification`, `GcWorkspace`, `GcAction`, `ReapHazard` and `ReapRefused`
plus the helpers that build their messages. Split out of `local.py`; it never
imports `fr.isolation.local`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fr.artifacts.paths import KIND_DIRS
from fr.isolation.types import IsolationError, IsolationState


@dataclass
class MergeVerification:
    """Whether a branch's changes are present on a base ref (#320 close-out)."""

    changed: list[str]  # files the branch changed since its merge-base
    missing: list[str]  # changed files NOT yet present on the base ref
    changes_present: bool


@dataclass
class GcWorkspace:
    """A workspace discovered by the host-wide gc sweep (#354 Task B).

    `state` is None for a true orphan (worktree gone, container found only by
    docker label) or an ambiguous label-less directory with no fr state.
    """

    worktree: Path
    container_id: str | None
    state: IsolationState | None


def _forge_refused(exc: Exception) -> IsolationError:
    """The forge adapter's host refusal (spec 2026-10-06-forge-remainder §4.E:
    a declared GitHub host gh is not logged into) as this lifecycle's own
    error. Callers that guard work (`down`, `verify-merge`, the reap hazard)
    refuse on it like any other `IsolationError`; the read-only, many-workspace
    ones (`status`, the gc sweep) degrade per workspace instead (review p2-r1)."""
    return IsolationError(f"cannot ask the forge: {exc}")


@dataclass
class GcAction:
    """One workspace's gc verdict + what gc did about it (#354 Task B)."""

    worktree: str
    branch: str | None
    # merged | merged-by-content | open | no-pr | orphan | no-state | dangling-image
    # | empty-repo-dir | stale-session (cache/index hygiene, spec 2026-09-04 §5)
    # | unverifiable (a refused forge lookup, spec 2026-10-06-forge-remainder)
    # | agent-worktree (a subagent's `agent-*` worktree, gh#1270)
    verdict: str
    # reaped | skipped | warned | reap-failed | would-reap | would-skip | removed
    # | would-remove
    action: str
    detail: str = ""


@dataclass(frozen=True)
class ReapHazard:
    """Work that a reap would destroy, and how to keep it (spec 2026-09-20
    isolation-reap-data-loss-guards §3.1)."""

    kind: str  # "drifted-checkout" | "dirty-worktree" | "unlanded-content" | "unverifiable"
    detail: str  # names the branch and what would be lost — see _hazard_detail


class ReapRefused(IsolationError):  # noqa: N818 — a refusal is a decision, not
    # an "Error" (spec §3.5: gc classifies it as a skip, never a failure); the
    # name is the spec's own vocabulary (§3.1), kept verbatim.
    """Raised INSTEAD of tearing down, by `_down_worktree_tail`'s hazard check.
    Carries the hazard so gc can classify a refusal as a deliberate skip rather
    than a failure (spec §3.5, phase 3)."""

    def __init__(self, hazard: ReapHazard) -> None:
        self.hazard = hazard
        super().__init__(hazard.detail)


def _merged_before(pr: dict[str, Any], created_at: str) -> bool:
    """True when `pr` provably merged before the workspace was created (gh#844).

    `_pr_from` finds a PR by branch NAME, which a later workspace can re-use.
    Only a merge time we can read AND compare proves the PR is an earlier one:
    a missing or unparseable time keeps the old by-name verdict rather than
    inventing a new one."""
    try:
        merged = datetime.fromisoformat(str(pr.get("mergedAt") or "").replace("Z", "+00:00"))
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if merged.tzinfo is None or created.tzinfo is None:
        return False
    return merged < created


def _hazard_detail(branch: str, headline: str, paths: list[str], remedy: str) -> str:
    """One shared voice for every reap-hazard message (spec §3.8) — phases 2
    and 3 add two more callers (unlanded-content, unverifiable-fetch), and all
    three must read as the same product, not three ad hoc f-strings.

    `remedy` is per-hazard and NOT optional: the three hazards do not have the
    same way out, and a single hardcoded clause was wrong for two of them
    (phase-1 review f1). "Commit or stash them" has no referent when the
    hazard is that `git status` itself failed, and the way out of unlanded
    content is to push, not to stash.

    The `--force` sentence deliberately says what --force *does* rather than
    "destroys the work", because that is not uniformly true (phase-1 review
    f2, verified against real git): `git worktree remove --force` removes the
    working tree and fr's state record, and does NOT delete the branch or its
    commits. So a forced reap of a DIRTY tree is unrecoverable (uncommitted
    edits were never objects), while a forced reap of an unlanded COMMIT
    leaves the branch ref intact and recoverable. Overstating it is not a
    harmless exaggeration — an operator who believes --force deletes their
    commits will not use it, which is a false refusal by other means.

    Caps the listed paths so a hazard on a 200-file branch doesn't produce a
    wall of text: the first few, then `+N more`.
    """
    lines = [f"isolation: {branch} {headline} — refusing to reap (nothing was deleted)."]
    if paths:
        shown = paths[:5]
        rest = len(paths) - len(shown)
        listed = ", ".join(shown) + (f", +{rest} more" if rest > 0 else "")
        lines.append(f"  {listed}")
    lines.append(remedy)
    lines.append(
        f"Or reap it anyway with `fr isolation down --branch {branch} --force`, "
        "which removes the worktree and fr's record of it (the branch and any "
        "commits on it remain in the repo; uncommitted changes do not survive, except "
        f"fr's own records under `{KIND_DIRS['superpowers']}/`, which are preserved and restored "
        "by the next `up`)."
    )
    return "\n".join(lines)
