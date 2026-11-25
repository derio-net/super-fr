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
from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING, Literal

from fr.settle.managed import MANAGED_SENTENCE
from fr.triage.model import Batch, ConflictEvent

if TYPE_CHECKING:  # `fr.triage.wave_queue` imports this module: read at run time lazily
    from fr.triage.wave_queue import Combo, QueueAction, QueueConfig, QueueSnapshot, Replay

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
    that names none, one git could not read (*leads* None, R5) and one the budget held
    (`delivered: held`, the operator's) are not briefed again."""
    met = latest_conflict(events, head)
    return (met is not None and met.onto is not None and met.delivered != "held"
            and leads is False)  # fmt: skip


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


# ------------------------------------------------------------ the planner's part (§A)


def slot_name(scope: str, slot: int) -> str:
    """The slot branch a brief names, `fr-queue/<scope>/slot-<j>`: `queue_exec.slot_ref`
    without `refs/heads/`, derived so the two never drift (l-tests-r5)."""
    from fr.triage.queue_exec import slot_ref  # queue_exec imports this module's importer

    return slot_ref(scope, slot).removeprefix("refs/heads/")


def target_ref(qs: QueueSnapshot, slots: Sequence[int]) -> str:
    """The ref a brief fetches for a target in *slots* (one slot, or none: the default
    branch by its bare name, which `git fetch origin <name>` takes)."""
    return slot_name(qs.scope, slots[0]) if slots else qs.default or "main"


def fetch_name(ref: str) -> str:
    """*ref* as `git fetch origin` names it: `origin/<branch>` without its remote."""
    return ref.removeprefix("origin/")


def _lineage_key(qs: QueueSnapshot, key: str) -> str:
    pr = qs.live.get(key)
    return f"queue-lineage\0{qs.repo}\0{key}\0{pr.head if pr is not None else ''}"


def _unread(
    qs: QueueSnapshot, key: str, met: ConflictEvent | None, what: str, wave: int | None
) -> QueueAction | None:
    """R5, as amended by l-errors-r4: an entry git could not read *what* about is held with
    a warning, said once; held for `stall_hours` since the later of its hand-back (*met*) and
    its head's last change (or, for a non-batch entry, its approval), it is a Need naming
    the commit and the entry, never held silently. None: warned already, not yet due."""
    from fr.triage.wave_queue import QueueAction

    other = next((o.at for o in qs.others if o.key == key), None)
    times = [t for t in (met.at if met else None, qs.head_changed.get(key), other) if t]
    batch = key if any(b.id == key for b in qs.batches) else ""
    if times and qs.now - max(times) >= timedelta(hours=qs.config.stall_hours):
        return QueueAction(
            "queue-need", qs.repo, f"{key} has been held for {qs.config.stall_hours} h: git "
            f"could not read {what} in the driver's clone of {qs.repo} (a missing object, or "
            "a failed command): fetch it there, or hand the entry back by hand", wave=wave,
            entries=(key,), batch=batch)  # fmt: skip
    if (k := _lineage_key(qs, key)) in qs.warned:
        return None
    return QueueAction("queue-warn", qs.repo, f"{key} is held this pass: git could not read "
                       f"{what}", wave=wave, key=k)  # fmt: skip


def hold_lineage(qs: QueueSnapshot, entries: list[str]) -> list[tuple[str, tuple[str, ...] | None]]:
    """R4, R5: take out of *entries* each one whose head carries a combination the queue
    built that no longer leads to `main` (its carried shas), and each one git could not
    read (None). Only under R1's land and method; else nothing."""
    if brief_mode(qs.config, qs.method) != "slot":
        return []
    out: list[tuple[str, tuple[str, ...] | None]] = []
    for key in list(entries):
        carried = qs.carries.get(key, ())
        if carried is None or qs.leads.get(key, True) is None:
            out.append((key, None))
        elif carried:
            out.append((key, tuple(carried)))
        else:
            continue
        entries.remove(key)
    return out


def aimed(qs: QueueSnapshot, rep: Replay, standing: Sequence[Combo]) -> tuple[str, tuple[int, ...]]:
    """The target a hand-back names this pass, as (sha, slots): the last combination of
    *standing* (R1), or the base with no slot; always the base outside R1's mode."""
    if brief_mode(qs.config, qs.method) != "slot":
        return rep.base, ()
    sha, slot = stack_target(replace(rep, combos={c.slot: c for c in standing}))
    return sha, (slot,) if slot is not None else ()


def lineage_actions(
    qs: QueueSnapshot,
    rep: Replay,
    held: Sequence[tuple[str, tuple[str, ...] | None]],
    target: tuple[str, tuple[int, ...]],
    wave: int | None,
) -> list[QueueAction]:
    """The actions *held* entries give (R4-R6): a warning, said once, for one git could not
    read (a Need once held for `stall_hours`, l-errors-r4); a `queue-carry` for a batch whose
    head was never briefed (a `conflict` event at the head is the brief, so one per head),
    and a Need for any other entry."""
    from fr.triage.wave_queue import QueueAction

    by_id = {b.id: b for b in qs.batches}
    sha, slots = target
    out: list[QueueAction] = []
    for key, carried in held:
        pr = qs.live.get(key)
        head = pr.head if pr is not None else ""
        if carried is None:
            owner = by_id.get(key)
            met = latest_conflict(owner.events, head) if owner is not None else None
            told = _unread(qs, key, met, f"whether its head {head[:12]} leads to {qs.repo}'s "
                           "`main`", wave)  # fmt: skip
            out.extend([told] if told is not None else [])
            continue
        said = (f"{key} at {head[:12]} carries {', '.join(s[:12] for s in carried)}, a "
                "combination the queue built that no longer leads to `main`")  # fmt: skip
        batch = by_id.get(key)
        if batch is None:
            out.append(QueueAction(
                "queue-need", qs.repo, f"PR #{pr.number if pr else '?'} ({said}): reset its "
                "branch to a head before that merge, re-apply its own commits, then "
                + merge_clause(qs, target), wave=wave))  # fmt: skip
        elif latest_conflict(batch.events, head) is None:
            out.append(QueueAction(
                "queue-carry", qs.repo, f"hold {said}", wave=wave, entries=(key,), batch=key,
                head=head, base=sha, slots=slots, carried=carried, reason="conflict"))  # fmt: skip
    return out


def reissue_actions(
    qs: QueueSnapshot, rep: Replay, target: tuple[str, tuple[int, ...]], wave: int | None
) -> list[QueueAction]:
    """R2, R5: each batch ejected at the head it still has whose hand-back named a commit
    that no longer leads to `main` gets one `queue-reissue` on *target*; one git could not
    read is warned once and stays out."""
    from fr.triage.wave_queue import QueueAction, _ejected_head

    if brief_mode(qs.config, qs.method) != "slot":
        return []
    out: list[QueueAction] = []
    by_id = {b.id: b for b in qs.batches}
    sha, slots = target
    for key in rep.ejected:
        batch, pr = by_id.get(key), qs.live.get(key)
        if batch is None or pr is None or _ejected_head(key, rep, by_id) != pr.head:
            continue
        met = latest_conflict(batch.events, pr.head)
        if met is None or met.onto is None or met.delivered == "held" or key not in qs.leads:
            continue  # a held hand-back is the operator's: never re-issued (p1-r2)
        if qs.leads[key] is None:
            said = _unread(qs, key, met, f"whether {met.onto[:12]}, the commit its hand-back "
                           f"named, still leads to {qs.repo}'s `main`", wave)  # fmt: skip
            out.extend([said] if said is not None else [])
        elif reissue_due(batch.events, pr.head, qs.leads[key]):
            out.append(QueueAction(
                "queue-reissue", qs.repo, f"re-issue {key}'s hand-back: {met.onto[:12]} no "
                f"longer leads to `main`; merge {sha[:12]} instead", wave=wave, entries=(key,),
                batch=key, head=pr.head, base=sha, slots=slots, paths=tuple(met.paths),
                reason="conflict", decision="reissue"))  # fmt: skip
    return out


def merge_clause(qs: QueueSnapshot, target: tuple[str, tuple[int, ...]]) -> str:
    """R6's words for a non-batch entry: the commit to merge, and where to fetch it."""
    sha, slots = target
    return f"merge `{sha}` (`git fetch origin {target_ref(qs, slots)}`) into its branch"


# ------------------------------------------------------------ the driver's part (R1-R4)


def handback_onto(action: QueueAction, scope: str, default: str) -> tuple[str, str]:
    """The commit a hand-back of *action* names and the ref to fetch it from: its slot, or
    the default branch (R1). ("", "") for an action that names no target."""
    if not action.base:
        return "", ""
    ref = slot_name(scope, action.slots[0]) if action.slots else f"origin/{default}"
    return action.base, ref


def carry_brief(
    batch: Batch,
    *,
    pr: int | None,
    head: str,
    reset: str,
    carried: Sequence[str],
    onto: str,
    onto_ref: str,
    branch: str,
) -> str:
    """R4's brief: *head* carries *carried*, combinations the queue built that no longer
    lead to `main`. Reset to *reset* (the newest hand-back head free of them), cherry-pick
    the branch's own commits since it, merge the stack target, push with a lease pinned to
    *head* (l-security-r1: a bare lease would pin the ref step 2 just fetched). The one
    brief that allows a force-push."""
    from fr.triage.batch_dispatch import NO_APPROVAL_LINE, title_block

    where = f"PR #{pr}" if pr is not None else "its PR"
    dead = ", ".join(carried)
    return "\n".join(
        [
            f"Merge queue carry on batch {batch.id}: {where} on {branch}, at head {head}, "
            f"carries {dead}, a combination the merge queue built that no longer leads to "
            "`main` (an entry it was stacked on left the queue). The queue will not build "
            f"{where} while its branch holds that commit.",
            *title_block(batch),
            f"Rebuild {branch} without it, in these six steps:",
            f"1. Enter the batch's workspace first: `fr isolation up --branch {branch}`. "
            "Every later step runs in the workspace.",
            f"2. `git fetch origin {branch} {fetch_name(onto_ref)}`, then list the branch's own "
            f"commits since {reset}: `git rev-list --first-parent --no-merges --reverse "
            f"{reset}..origin/{branch}` (first parent only: a commit a merge brought in is not "
            "the branch's own).",
            f"3. `git reset --hard {reset}`: the newest head the queue handed back that holds "
            "no such commit.",
            "4. Re-apply each commit step 2 listed, oldest first, with `git cherry-pick`.",
            f"5. `git merge {onto}` ({onto_ref}, the commit `main` becomes when the entries "
            "ahead land), resolve what conflicts, and run the test suite.",
            f"6. `git push --force-with-lease={branch}:{head} origin {branch}`: the lease is "
            f"the head this brief names, so the push replaces only that head. If the push is "
            "refused, the branch moved since the driver checked it: stop and wait for a "
            "re-issued brief. This is the one hand-back that allows a force-push: the commit "
            "it drops must not reach `main`.",
            MANAGED_SENTENCE,
            NO_APPROVAL_LINE,
        ]
    )
