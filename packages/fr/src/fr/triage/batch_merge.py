"""`batch merge`: reconcile, refusals and execution (spec 2026-09-25-triage-batches §3.D, §3.F).

The order is `fr.triage.batch.merge_order`; this module turns it into a queue
of `Slot`s (reconcile) and merges them one at a time (execution). Every forge
operation is a `GhClient` adapter call (§3.J) and every git operation goes
through the checkout / worktree seam (`fr.triage.gitseam`), both passed in, so
this module runs no process itself and tests drive it with fakes.

Queue progress is never stored: the plan re-reads each PR, so a PR that merged
on an earlier run drops out and a re-run resumes at the first unmerged batch.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from fr.ghclient import GhClient
from fr.hostclient import FORGE_ERRORS
from fr.triage.batch import MergeStep, QueueEntry, merge_order, with_forecast
from fr.triage.batch_version import all_version_files, is_above, read_source, slot_versions
from fr.triage.errors import TriageError
from fr.triage.model import VersionBlock

FAILING_BUCKETS = frozenset({"fail", "cancel"})
# Update-push-wait rounds per PR before merge gives up on a moving main.
MAX_UPDATES = 3


class MergeStopError(TriageError):
    """The queue stops here (exit 1): the message says why and what to do."""


class WorktreeSeam(Protocol):
    path: Path

    def merge(self, ref: str) -> list[str]: ...
    def take_theirs(self, paths: list[str]) -> None: ...
    def abort_merge(self) -> None: ...
    def read(self, file: str) -> str | None: ...
    def run(self, command: str, **fields: str) -> None: ...
    def commit_all(self, message: str) -> str | None: ...
    def push(self, branch: str) -> None: ...


class CheckoutSeam(Protocol):
    path: Path

    def fetch(self) -> None: ...
    def default_branch(self) -> str: ...
    def show(self, ref: str, file: str) -> str | None: ...
    def is_ancestor(self, ancestor: str, descendant: str) -> bool: ...
    def add_worktree(self, where: Path, ref: str) -> Any: ...
    def remove_worktree(self, where: Path) -> None: ...


@dataclass(frozen=True)
class Slot:
    """One queued PR as the plan printed it: the head it will merge and the
    version it must carry there."""

    step: MergeStep
    head: str
    slot: str | None  # None when the repo declares no version block


@dataclass
class MergeContext:
    client: GhClient
    checkout: CheckoutSeam
    repo: str
    version: VersionBlock | None
    scratch_root: Path
    method: str
    say: Callable[[str], None]
    # `wait_required_checks` bounds, in seconds: poll interval, give-up, and the
    # grace period in which "no checks yet" is not "none required".
    interval: float = 30.0
    timeout: float = 3600.0
    grace: float = 120.0
    scratch: set[Path] = field(default_factory=set)  # worktrees this run created

    @property
    def main(self) -> str:
        return f"origin/{self.checkout.default_branch()}"

    def version_at(self, ref: str) -> str | None:
        if self.version is None:
            return None
        text = self.checkout.show(ref, self.version.source.file)
        if text is None:
            raise MergeStopError(f"{self.version.source.file} does not exist at {ref}")
        return read_source(text, self.version.source)


# ------------------------------------------------------------------ planning


def plan_queue(
    ctx: MergeContext, entries: Sequence[QueueEntry]
) -> tuple[list[Slot], list[MergeStep]]:
    """Re-read every PR, drop the merged ones, order the rest and reconcile slots.

    Returns the queue and the steps already merged (reported, never re-run).
    """
    ctx.checkout.fetch()
    live: list[QueueEntry] = []
    heads: dict[str, str] = {}
    merged: list[MergeStep] = []
    for e in entries:
        view = ctx.client.pr_view(ctx.repo, e.pr.number)
        if view.get("state") == "MERGED":
            merged.extend(with_forecast([e]))
            continue
        live.append(e)
        heads[e.batch.id] = str(view.get("head_oid") or e.pr.head_oid)
    steps = with_forecast(merge_order(live))
    main_version = ctx.version_at(ctx.main)
    slots: list[str | None] = (
        list(slot_versions(main_version, [s.batch.bump for s in steps]))
        if main_version is not None
        else [None] * len(steps)
    )
    return [Slot(s, heads[s.batch.id], v) for s, v in zip(steps, slots, strict=True)], merged


def describe(index: int, slot: Slot) -> str:
    """One line of the printed plan: PR, versions, and the shared-file forecast."""
    step = slot.step
    parts = [f"{index}. batch {step.batch.id}", f"PR #{step.pr.number}", f"head {slot.head[:12]}"]
    if slot.slot is not None:
        parts.append(f"version {step.reserved_version or '?'} -> slot {slot.slot}")
    parts.append(f"shares: {', '.join(step.shared)}" if step.shared else "shares: nothing later")
    return "  ".join(parts)


# ----------------------------------------------------------------- execution


def run_queue(ctx: MergeContext, queue: Sequence[Slot]) -> None:
    """Merge each slot in order; the first `MergeStopError` stops the queue."""
    previous: str | None = None
    for slot in queue:
        merge_one(ctx, slot, previous)
        previous = slot.step.batch.id


def _checks(ctx: MergeContext, number: int, *, after_push: bool) -> None:
    """Stop unless every required check passes, waiting in the foreground (d5).

    Right after a push the wait always runs: the answer read before it would
    describe the old head (review r2p-f10).
    """
    checks = [] if after_push else ctx.client.pr_required_checks(ctx.repo, number)
    if after_push or any(c.get("bucket") == "pending" for c in checks):
        checks = ctx.client.wait_required_checks(
            ctx.repo, number, interval=ctx.interval, timeout=ctx.timeout, grace=ctx.grace
        )
    failing = sorted(str(c.get("name")) for c in checks if c.get("bucket") in FAILING_BUCKETS)
    if failing:
        raise MergeStopError(f"PR #{number}: required checks failing: {', '.join(failing)}")
    pending = sorted(str(c.get("name")) for c in checks if c.get("bucket") == "pending")
    if pending:
        raise MergeStopError(f"PR #{number}: required checks still pending: {', '.join(pending)}")


def merge_one(ctx: MergeContext, slot: Slot, previous: str | None) -> None:
    """Steps 1-4 of spec §3.F for one PR."""
    pr, batch = slot.step.pr, slot.step.batch
    expected = slot.head
    for _ in range(MAX_UPDATES + 1):
        view = ctx.client.pr_view(ctx.repo, pr.number)  # step 1: re-read
        if view.get("state") == "MERGED":
            ctx.say(f"{batch.id}: already merged (PR #{pr.number})")
            return
        if view.get("state") != "OPEN":
            raise MergeStopError(f"PR #{pr.number} (batch {batch.id}) is {view.get('state')}")
        if view.get("draft"):
            raise MergeStopError(f"PR #{pr.number} (batch {batch.id}) is a draft; mark it ready")
        head = str(view.get("head_oid"))
        if head != expected:
            raise MergeStopError(
                f"PR #{pr.number} (batch {batch.id}): head moved since the plan was printed "
                f"({expected[:12]} -> {head[:12]}); re-run to re-plan"
            )
        _checks(ctx, pr.number, after_push=False)
        ctx.checkout.fetch()
        behind = not ctx.checkout.is_ancestor(ctx.main, head)
        head_version = ctx.version_at(head)
        wrong_slot = slot.slot is not None and head_version != slot.slot
        if not behind and not wrong_slot:
            _merge(ctx, slot, head, head_version)  # step 2
            return
        expected = _update(ctx, slot, head, behind, previous)  # step 3
        _checks(ctx, pr.number, after_push=True)
    raise MergeStopError(
        f"PR #{pr.number} (batch {batch.id}): still behind or off its slot after "
        f"{MAX_UPDATES} updates; main keeps moving — re-run later"
    )


def _merge(ctx: MergeContext, slot: Slot, head: str, head_version: str | None) -> None:
    pr = slot.step.pr
    main_version = ctx.version_at(ctx.main)
    if head_version is not None and main_version is not None:
        if not is_above(head_version, main_version):
            raise MergeStopError(
                f"PR #{pr.number} (batch {slot.step.batch.id}) carries {head_version}, "
                f"not above main's {main_version}; re-run to re-plan"
            )
    try:
        ctx.client.pr_merge(ctx.repo, pr.number, head_sha=head, method=ctx.method)
    except FORGE_ERRORS as exc:  # a protection refusal, in the forge's own words
        raise MergeStopError(f"PR #{pr.number}: the forge refused the merge: {exc}") from exc
    ctx.say(f"merged PR #{pr.number} (batch {slot.step.batch.id}) at {head[:12]}")
    where = scratch_path(ctx, slot)
    if where in ctx.scratch or where.exists():
        ctx.checkout.remove_worktree(where)  # step 4: only after a successful merge
        ctx.scratch.discard(where)


def scratch_path(ctx: MergeContext, slot: Slot) -> Path:
    """`<state dir>/merge/<branch>/`: outside every repo on purpose (§3.F)."""
    return ctx.scratch_root / slot.step.pr.head_ref


def _update_message(
    ctx: MergeContext, slot: str | None, *, behind: bool, previous: str | None
) -> str:
    """Spec §3.F step 3's commit message."""
    default = ctx.main.removeprefix("origin/")
    if behind and slot is not None:
        after = f"batch {previous}" if previous else default
        return f"chore: take reserved version {slot} after {after}"
    if behind:
        return f"chore: update from {default}"
    return f"chore: re-slot version to {slot}"


def _update(ctx: MergeContext, slot: Slot, head: str, behind: bool, previous: str | None) -> str:
    """Step 3: bring the PR branch up to date and onto its slot; the new head."""
    pr = slot.step.pr
    where = scratch_path(ctx, slot)
    wt: WorktreeSeam = ctx.checkout.add_worktree(where, head)
    ctx.scratch.add(where)
    if behind:
        conflicted = wt.merge(ctx.main)
        if conflicted:
            globs = ctx.version.files if ctx.version else []
            if globs and all_version_files(conflicted, globs):
                wt.take_theirs(conflicted)
            else:
                wt.abort_merge()
                outside = [p for p in conflicted if not all_version_files([p], globs)]
                raise MergeStopError(
                    f"PR #{pr.number} (batch {slot.step.batch.id}) conflicts with {ctx.main} "
                    f"outside the version files: {', '.join(outside)}. The scratch worktree "
                    f"is kept for inspection at {where}"
                )
    if ctx.version is not None and slot.slot is not None:
        text = wt.read(ctx.version.source.file)
        current = read_source(text, ctx.version.source) if text is not None else None
        if current != slot.slot:
            wt.run(ctx.version.set_, version=slot.slot)
            if ctx.version.relock:
                wt.run(ctx.version.relock)
    message = _update_message(ctx, slot.slot, behind=behind, previous=previous)
    new = wt.commit_all(message)
    if new is None:
        raise MergeStopError(f"PR #{pr.number}: the update produced no change to push")
    wt.push(pr.head_ref)
    ctx.say(f"PR #{pr.number}: pushed {new[:12]} ({message}); waiting for required checks")
    return new
