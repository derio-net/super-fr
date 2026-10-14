"""Sync a run's exit onto its PR's labels — spec 2026-10-14 exit-gates R7, §B.

`sync_exit_labels` makes the PR carry exactly one `verification:<kind>` label
per kind of the run's exit and one `gate:<gate>` label per post-merge gate. A
`gate:<g>-passed` label is the record of a passed gate and is never removed.
The caller chooses what a failure means: `deliver` refuses on it, the earlier
sync points only warn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr.gates import POST_MERGE_GATES
from fr.ghclient import GhClient, HostRefusedError, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS, client_for
from fr.labels import (
    GATE_PREFIX,
    PASSED_SUFFIX,
    VERIFICATION_PREFIX,
    LabelDef,
    gate_label,
    verification_label,
)

if TYPE_CHECKING:
    from fr.run.model import RunState

__all__ = ["LabelSyncError", "SyncOutcome", "desired_labels", "sync_exit_labels"]

_PR_URL = re.compile(r"^https?://[^/]+/(?P<repo>.+?)/(?:-/merge_requests|pulls?)/(?P<n>\d+)")


class LabelSyncError(Exception):
    """The PR's labels could not be synced (a forge refusal or an unreadable remap)."""


@dataclass(frozen=True)
class SyncOutcome:
    synced: bool
    warning: str | None = None
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()


def desired_labels(kinds: frozenset[str], gates: frozenset[str]) -> list[LabelDef]:
    """The labels a PR with this exit carries: every kind, every post-merge gate."""
    held = sorted(g for g in gates if g in POST_MERGE_GATES)
    return [verification_label(k) for k in sorted(kinds)] + [gate_label(g) for g in held]


def _is_managed(name: str) -> bool:
    """A label this sync owns: a `verification:*` or an unpassed `gate:*`."""
    if name.startswith(VERIFICATION_PREFIX):
        return True
    return name.startswith(GATE_PREFIX) and not name.endswith(PASSED_SUFFIX)


def _target(repo_root: Path, state: RunState, pr: str | None, client: GhClient) -> tuple[str, int]:
    from fr._hosts import origin_slug

    ref = (pr or "").strip()
    if (m := _PR_URL.match(ref)) is not None:
        return m["repo"], int(m["n"])
    slug = origin_slug(repo_root)
    if slug is None:
        raise LabelSyncError("cannot tell which repository the PR is in (no `origin` remote)")
    if ref.isdigit():
        return slug, int(ref)
    found = client.open_pr_for_head(slug, state.branch)
    if found is None:
        raise LabelSyncError(f"no open PR for branch {state.branch!r} in {slug}")
    return slug, int(found["number"])


def sync_exit_labels(
    repo_root: Path, state: RunState, pr: str | None, *, client: GhClient | None = None
) -> SyncOutcome:
    """Bring the PR's `verification:*` / `gate:*` labels to the run's exit.

    A no-op under `tracking: none`. A forge that cannot label a PR
    (`UnsupportedForgeOperation`) comes back as `SyncOutcome.warning`; any other
    forge failure, a PR it cannot find, or an unreadable remap raises
    `LabelSyncError`, so a caller that must not proceed on stale labels refuses.
    """
    from fr.services.model import ServicesError
    from fr.services.resolve import resolve_tracking
    from fr.verification.exit import run_exit

    try:
        if resolve_tracking(repo_root, lenient=True).type == "none":
            return SyncOutcome(synced=False)
    except ServicesError:
        pass
    exit_ = run_exit(repo_root, state)
    if exit_.remap_problem:
        raise LabelSyncError(
            f"the gate remap is unreadable, so the exit is not known: {exit_.remap_problem}"
        )
    want = desired_labels(exit_.kinds, exit_.gates)
    try:
        gh = client if client is not None else client_for(repo_root)
        repo, number = _target(repo_root, state, pr, gh)
        gh.ensure_labels(repo, want)
        have = {str(n) for n in gh.pr_view(repo, number).get("labels", [])}
        names = {d.name for d in want}
        add = frozenset(names - have)
        remove = frozenset(n for n in have if _is_managed(n) and n not in names)
        if add or remove:
            gh.edit_pr_labels(repo, number, add=add, remove=remove)
    except UnsupportedForgeOperation as e:
        return SyncOutcome(synced=False, warning=f"PR labels not synced: {e}")
    except (*FORGE_ERRORS, HostRefusedError) as e:
        raise LabelSyncError(str(e)) from e
    return SyncOutcome(synced=True, added=tuple(sorted(add)), removed=tuple(sorted(remove)))
