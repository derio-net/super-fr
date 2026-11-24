"""Conflict hand-backs onto the stack target (spec 2026-11-24-wave-queue-gaps R1-R6).

A queue entry ejected for a real conflict is handed back naming the commit it will be
stacked on when it re-enters (the last standing combination, else the base), re-issued
free while its head is unchanged and that commit stops leading to `main`, and held with a
carry brief when its head reaches a combination the queue built that no longer leads.
Pure: git answers ancestry in the command layer.
"""

from __future__ import annotations

import shlex
from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from fr.settle.managed import MANAGED_SENTENCE
from fr.triage.model import Batch, ConflictEvent

if TYPE_CHECKING:  # `fr.triage.wave_queue` imports `batch_drive`, which imports this lazily
    from fr.triage.wave_queue import QueueConfig, Replay

BriefMode = Literal["slot", "main"]


def brief_mode(config: QueueConfig, method: str) -> BriefMode:
    """R1: `slot` when the queue lands by push and squashes or merges, so the slot commit a
    hand-back merges becomes `main` as it stands; else `main` (`land: merge` never makes the
    slot commit `main`, and `rebase` would not replay the merge the session made)."""
    return "slot" if config.land == "push" and method in ("merge", "squash") else "main"


def stack_target(rep: Replay) -> tuple[str, int | None]:
    """R1: the commit an ejected entry will be stacked on when it re-enters: the last
    combination of *rep* that stands (on its base, holding no ejected entry), as its sha and
    slot; else the base and None."""
    standing = [c for c in rep.combos.values()
                if c.base == rep.base and not set(c.chain) & set(rep.ejected)]  # fmt: skip
    if not standing:
        return rep.base, None
    last = max(standing, key=lambda c: (len(c.chain), c.slot))
    return last.sha, last.slot


def latest_conflict(events: Sequence[object], head: str) -> ConflictEvent | None:
    """The latest `conflict` event at *head*, or None."""
    return next((e for e in reversed(events)
                 if isinstance(e, ConflictEvent) and e.head == head), None)  # fmt: skip


def reissue_due(events: Sequence[object], head: str, leads: bool | None) -> bool:
    """R2, R3: the latest `conflict` event at *head* named a commit (`onto`) and git reads
    that commit as no longer leading to `main` (*leads* False). One that still leads, one
    that names none, and one git could not read (*leads* None, R5) are not briefed again."""
    met = latest_conflict(events, head)
    return met is not None and met.onto is not None and leads is False


def conflict_brief(
    batch: Batch,
    *,
    pr: int | None,
    head: str,
    paths: Sequence[str],
    branch: str,
    base: str,
    mirrors: Sequence[Sequence[str]],
    onto: str = "",
    onto_ref: str = "",
) -> str:
    """The conflict hand-back brief (spec 2026-10-06-verification-strategies §G, R20):
    the batch, its PR, the head and the paths merge refused, then the six steps. The
    repo's `.fr/triage.yaml` `mirrors:` commands, when declared, are step 4's.

    With *onto* and an *onto_ref* under `fr-queue/` (spec 2026-11-24-wave-queue-gaps R1),
    step 2 fetches that slot and merges that sha, the commit `main` becomes when the
    entries ahead land, and says to wait for a re-issued brief when the slot moved on.
    Otherwise (*onto_ref* `origin/<default>`, or none) it merges *base*, as before."""
    from fr.triage.batch_dispatch import NO_APPROVAL_LINE, title_block

    where = f"PR #{pr}" if pr is not None else "its PR"
    regenerate = "4. Regenerate generated mirrors instead of hand-resolving them"
    if mirrors:
        commands = "; ".join(f"`{shlex.join(argv)}`" for argv in mirrors)
        regenerate += f": run {commands}, then stage what they wrote."
    else:
        regenerate += " (rerun whatever generates them), then stage what they wrote."
    slot = bool(onto) and onto_ref.startswith("fr-queue/")
    against = f"the merge queue's commit ahead of it, {onto_ref} at {onto}" if slot else base
    merge = (
        f"2. `git fetch origin {onto_ref}`, check that it still contains {onto} (`git "
        f"merge-base --is-ancestor {onto} FETCH_HEAD`), then `git merge {onto}` into {branch}. "
        f"That commit is what `main` becomes when the entries ahead of {where} in the merge "
        "queue land, so merging it, not `origin/main`, keeps the PR from conflicting again "
        "once they do. If the fetched ref no longer contains it, stop and wait for a "
        "re-issued brief. Do not rebase and do not force-push: the PR's history stays as "
        "it is."
        if slot
        else f"2. `git fetch origin && git merge {base}` into {branch}. Do not rebase and "
        "do not force-push: the PR's history stays as it is."
    )
    return "\n".join(
        [
            f"Merge conflict on batch {batch.id}: {where} on {branch}, at "
            f"head {head}, conflicts with {against} in a change the wave driver will not "
            f"resolve: {', '.join(paths)}.",
            *title_block(batch),
            f"Resolve it on {branch} itself, in these six steps:",
            f"1. Enter the batch's workspace first: `fr isolation up --branch {branch}`. "
            f"{branch} is checked out there, not in the clone you may have started in; "
            "on an existing workspace the command resumes it, and a session already in "
            "that workspace has nothing to do. Every later step runs in the workspace.",
            merge,
            f"3. Resolve the conflicted paths: {', '.join(paths)}.",
            regenerate,
            "5. Run the test suite, and fix what the merge broke.",
            f"6. Commit the merge and `git push origin {branch}`. The driver merges the PR "
            "once its checks are green.",
            MANAGED_SENTENCE,
            NO_APPROVAL_LINE,
        ]
    )
