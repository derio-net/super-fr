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

__all__ = [
    "ForgeUndeterminable",
    "LabelSyncError",
    "PrNotFound",
    "SyncOutcome",
    "desired_labels",
    "sync_exit_labels",
]

_PR_URL = re.compile(r"^https?://[^/]+/(?P<repo>.+?)/(?:-/merge_requests|pulls?)/(?P<n>\d+)")


_FORGE_FAILURES: tuple[type[Exception], ...] = (*FORGE_ERRORS, HostRefusedError)


class LabelSyncError(Exception):
    """The PR's labels could not be synced (a forge refusal or an unreadable remap)."""


class PrNotFound(LabelSyncError):  # noqa: N818 — a kind of sync failure, not a fault
    """The run has no open PR to label (yet): not a failure for a caller that syncs early."""


class ForgeUndeterminable(PrNotFound):  # noqa: N818 — same family
    """Which forge the PR is on cannot be told (no `origin` remote): nothing to label."""


@dataclass(frozen=True)
class SyncOutcome:
    synced: bool
    warning: str | None = None
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    unknown: bool = False
    """The run's exit could not be read, so its labels are not known (`warning` says why)."""


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

    slug = origin_slug(repo_root)
    if slug is None:  # a checkout with no `origin` has no forge to ask, whatever the PR ref
        raise ForgeUndeterminable("no `origin` remote, so the forge is unknown and no PR to label")
    ref = (pr or "").strip()
    if (m := _PR_URL.match(ref)) is not None:
        return m["repo"], int(m["n"])
    if ref.isdigit():
        return slug, int(ref)
    found = client.open_pr_for_head(slug, state.branch)
    if found is None:
        raise PrNotFound(f"no open PR for branch {state.branch!r} in {slug}")
    return slug, int(found["number"])


def sync_exit_labels(
    repo_root: Path, state: RunState, pr: str | None, *, client: GhClient | None = None
) -> SyncOutcome:
    """Bring the PR's `verification:*` / `gate:*` labels to the run's exit.

    A no-op under `tracking: none`. `SyncOutcome.warning` carries a forge that cannot
    label a PR (`UnsupportedForgeOperation`); `SyncOutcome.unknown` an exit that cannot
    be read (the section or matrix is `fr plan self-review`'s to report), which a caller
    that needs the labels treats as a failure. `ForgeUndeterminable` / `PrNotFound` say
    there is no forge or no open PR to label; any other forge failure, or an unreadable
    remap, raises `LabelSyncError`.
    """
    from fr.acceptance.model import AcceptanceError
    from fr.services.model import ServicesError
    from fr.services.resolve import resolve_tracking
    from fr.verification.exit import run_exit
    from fr.verification.spec_section import SectionError

    try:
        if resolve_tracking(repo_root, lenient=True).type == "none":
            return SyncOutcome(synced=False)
    except ServicesError:
        pass
    try:
        gh = client if client is not None else client_for(repo_root)
        repo, number = _target(repo_root, state, pr, gh)
    except UnsupportedForgeOperation as e:
        return SyncOutcome(synced=False, warning=f"PR labels not synced: {e}")
    except _FORGE_FAILURES as e:
        raise LabelSyncError(str(e)) from e
    try:
        exit_ = run_exit(repo_root, state)
    except (SectionError, AcceptanceError, OSError, ValueError) as e:
        return SyncOutcome(
            synced=False,
            unknown=True,
            warning=f"PR labels not synced: the exit cannot be read: {e}",
        )
    if exit_.remap_problem:
        raise LabelSyncError(
            f"the gate remap is unreadable, so the exit is not known: {exit_.remap_problem}"
        )
    want = desired_labels(exit_.kinds, exit_.gates)
    try:
        # Probe the PR first: a forge that cannot label one creates no labels.
        have = {str(n) for n in gh.pr_view(repo, number).get("labels", [])}
        names = {d.name for d in want}
        add = frozenset(names - have)
        remove = frozenset(n for n in have if _is_managed(n) and n not in names)
        gh.ensure_labels(repo, want)
        if add or remove:
            gh.edit_pr_labels(repo, number, add=add, remove=remove)
    except UnsupportedForgeOperation as e:
        return SyncOutcome(synced=False, warning=f"PR labels not synced: {e}")
    except _FORGE_FAILURES as e:
        raise LabelSyncError(str(e)) from e
    return SyncOutcome(synced=True, added=tuple(sorted(add)), removed=tuple(sorted(remove)))
