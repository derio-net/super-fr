"""`check_reachable` — the §4.E gate over an item graph (Phase 8).

**A step's `needs` are inputs and must be reachable; its `emits` are
outputs and need not be.** By the time a `WorkItem` exists that rule has
already been applied: `item_graph.build_items` gives an item an
`ArtifactRef` for exactly the artifacts its shape requires, so this module
asks one question per ref — is it on `origin/HEAD`? — and never consults
the manifest again.

That is why the asymmetry falls out instead of being coded: a `unit: run`
item of a shape that emits its spec and plan carries **no** refs, so it
dispatches against a tree where neither exists; a `unit: phase` item
carries both, so it still refuses an unmerged plan.

The local half delegates to `fr.workflow.reachability.unreachable_paths`,
so `fr apply`'s gate and this one cannot drift about what "on origin/HEAD"
means.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fr.workflow.reachability import ORIGIN_HEAD, unreachable_paths

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from fr.ghclient import GhClient

    from fr_dispatch.work_item import WorkItem

__all__ = ["check_reachable"]


def check_reachable(
    items: Sequence[WorkItem],
    repo_root: Path,
    *,
    gh: GhClient | None = None,
) -> str | None:
    """`None` when every item's declared inputs are reachable, else a refusal.

    The returned string is a blocker in the same shape `runner.preflight`
    returns and the same wording the 2026-05-17 gate used — an operator who
    has seen `refuse to dispatch: N file(s) not at origin/HEAD` recognises
    it — with the item id added, because a tick carries many items and
    "which one" is the first question.

    `repo_root` is the checkout the *local* refs are resolved against. A ref
    naming a **different** repo cannot be answered by this repo's git at
    all: with `gh` it is resolved through the tracker's contents API (the
    same read path `compute_status` uses for a cross-repo plan row), and
    without one it is skipped — which is precisely what the old gate did
    with a cross-repo spec, trusting the operator to keep it correct.
    """
    for item in items:
        missing: list[str] = []
        for ref in item.inputs:
            if ref.repo != item.repo:
                if gh is not None and not gh.file_exists(ref.repo, ref.path):
                    missing.append(f"{ref.repo}:{ref.path}")
                continue
            missing.extend(str(p) for p in unreachable_paths(repo_root, [ref.path]))
        if missing:
            lines = [
                f"{item.id}: refuse to dispatch: {len(missing)} file(s) not at {ORIGIN_HEAD}:",
                *(f"  {p}" for p in missing),
                "",
                "Merge the plan + spec to the default branch first, then re-run.",
            ]
            return "\n".join(lines)
    return None
