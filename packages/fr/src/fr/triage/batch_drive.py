"""The wave driver's pass, as a pure function (wave-driver spec §B, §C).

`drive_pass(snapshot)` returns the ordered actions one pass of `fr triage batch
drive` takes: merge what is ready, close out what merged, merge an attributed
archive PR, dispatch what may start, and report what is blocked or failing.
The command layer (`fr.commands.triage_batch_cmd`) builds the `Snapshot` from
the facts, the forge client, the checkout and the runner, and executes the
actions; this module only decides.

It imports nothing from `fr_dispatch`, runs no git, starts no process and
reads no clock: the time is `Snapshot.now`, so the ten-minute fallback is
testable. `tests/unit/test_triage_batch_drive.py` pins that.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from fr.triage.batch import (
    UNSATISFIABLE,
    BatchStage,
    QueueEntry,
    batch_branch,
    merge_order,
)
from fr.triage.model import Batch, CloseoutEvent

CLOSEOUT_FALLBACK = timedelta(minutes=10)
"""How long after a merge the close-out starts when no release commit followed it
(a PR with no change fragment releases nothing)."""

DEFAULT_MAX_INFLIGHT = 4

IN_FLIGHT: frozenset[BatchStage] = frozenset({"dispatched", "pr-open"})
LANDED: frozenset[BatchStage] = frozenset({"merged", "partial"})
ARCHIVE_PREFIXES = ("chore/archive-", "chore/closeout-")
RUNS_DIR = "docs/superpowers/runs"

ChecksVerdict = Literal["green", "pending", "failing"]
ActionKind = Literal["merge", "closeout", "archive", "dispatch", "blocked", "warn"]

_FAILING_BUCKETS = frozenset({"fail", "cancel"})


@dataclass(frozen=True)
class LivePr:
    """A PR as the forge shows it now: a batch PR, or an archive PR candidate."""

    number: int
    state: str  # OPEN | MERGED | CLOSED
    draft: bool
    head: str
    checks: ChecksVerdict = "green"
    failing: tuple[str, ...] = ()
    head_ref: str = ""
    files: tuple[str, ...] = ()


@dataclass(frozen=True)
class Snapshot:
    """Everything one pass decides from. Built fresh each pass, never stored."""

    batches: tuple[Batch, ...]
    stages: Mapping[str, BatchStage]
    queue: tuple[QueueEntry, ...]  # pr-open batches with their collected PR
    live: Mapping[str, LivePr]  # batch id -> its PR as read now
    repos: Mapping[str, str]  # batch id -> OWNER/REPO
    now: datetime
    max_inflight: int = DEFAULT_MAX_INFLIGHT
    merged_at: Mapping[str, datetime] = field(default_factory=dict)
    released: frozenset[str] = frozenset()  # merged batches whose release commit landed
    archives: Mapping[str, tuple[LivePr, ...]] = field(default_factory=dict)  # repo -> PRs
    existing: frozenset[str] = frozenset()  # runner item ids live now
    warned: frozenset[str] = frozenset()  # head shas whose failing CI was reported


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    batch: str
    detail: str
    pr: int | None = None
    head: str = ""
    recorded: bool = False  # closeout: the runner holds the tab; record the event only
    post_merge: bool = False  # closeout: run the repo's post_merge first


@dataclass(frozen=True)
class Summary:
    """The pass's closing line, projected past its own actions."""

    in_flight: int
    merged: int
    pending: int
    closing: int
    blocked: int = 0

    @property
    def done(self) -> bool:
        """Nothing pending, in flight or closing (a blocked batch waits on the operator)."""
        return self.in_flight == 0 and self.pending == 0 and self.closing == 0


@dataclass(frozen=True)
class Pass:
    actions: tuple[Action, ...]
    summary: Summary


# ------------------------------------------------------------------ checks (R4)


def checks_verdict(
    required: Sequence[Mapping[str, Any]], all_checks: Mapping[str, int], *, ci_none: bool
) -> tuple[ChecksVerdict, tuple[str, ...]]:
    """R4: the required checks when the branch has any, else all checks; a repo
    whose services say `ci none` is green on non-draft alone.

    *required* is `GhClient.pr_required_checks`; *all_checks* is the collected
    `PullRequest.checks` counts (`pass`, `fail`, `pending`). `SKIPPED` and
    `NEUTRAL` read as passed.
    """
    if ci_none:
        return "green", ()
    if required:
        failing = tuple(
            sorted(str(c.get("name")) for c in required if c.get("bucket") in _FAILING_BUCKETS)
        )
        if failing:
            return "failing", failing
        pending = tuple(
            sorted(str(c.get("name")) for c in required if c.get("bucket") == "pending")
        )
        return ("pending", pending) if pending else ("green", ())
    if all_checks.get("fail", 0):
        return "failing", (f"{all_checks['fail']} failing check(s)",)
    if all_checks.get("pending", 0):
        return "pending", (f"{all_checks['pending']} pending check(s)",)
    return "green", ()


# ---------------------------------------------------------- close-out (§C)


def closeout_item_id(repo: str, batch_id: str) -> str:
    """`<OWNER>/<REPO>/run/closeout-<batch-id>`: unit `run`, one per batch.

    Spelled here like `batch_item_id`: `fr.triage` never imports `fr_dispatch`.
    """
    return f"{repo}/run/closeout-{batch_id}"


def find_run(cursors: Iterable[object], branch: str) -> tuple[str, str | None] | None:
    """The run id (and plan slug, if one was emitted) of the cursor whose `branch` is
    *branch*, from the parsed `docs/superpowers/runs/*.yaml` documents; None when no
    cursor names it (a debug batch, or a run that left none)."""
    for doc in cursors:
        if not isinstance(doc, Mapping) or doc.get("branch") != branch:
            continue
        run = doc.get("run")
        if not isinstance(run, str) or not run:
            continue
        plan: str | None = None
        steps = doc.get("steps")
        for record in steps.values() if isinstance(steps, Mapping) else ():
            emitted = record.get("emitted") if isinstance(record, Mapping) else None
            if isinstance(emitted, Mapping) and isinstance(emitted.get("plan"), str):
                plan = PurePosixPath(emitted["plan"]).name
        return run, plan
    return None


def housekeeping_branch(branch: str, run: str | None, plan: str | None) -> str:
    """The branch the close-out pushes its archive PR from — the naming of
    `fr.run.closeout` (`chore/archive-<plan>`, `chore/closeout-<run>`,
    `chore/closeout-<branch with / as ->`)."""
    if run is not None:
        return f"chore/archive-{plan}" if plan else f"chore/closeout-{run}"
    return f"chore/closeout-{branch.replace('/', '-')}"


def closeout_brief(batch: Batch, *, run: str | None, checkout: Path) -> str:
    """The close-out work item's brief: the `fr pickup` instruction for the batch."""
    branch = batch_branch(batch)
    pickup = f"fr pickup --run {run}" if run else f"fr pickup --branch {branch}"
    return (
        f"Close out batch {batch.id} ({batch.title}): its PR on {branch} has merged.\n"
        f"In {checkout}, run `{pickup}` and follow the brief it prints, in order."
    )


def attributed(pr: LivePr, batch: Batch, event: CloseoutEvent) -> bool:
    """Whether archive PR *pr* belongs to *batch*'s close-out (§B step 3): its head is
    the close-out's own housekeeping branch, or `chore/closeout-<batch branch>`, or
    any `chore/archive-*` / `chore/closeout-*` head that changes the batch's run file."""
    branch = batch_branch(batch)
    own = {f"chore/closeout-{branch.replace('/', '-')}"}
    if event.archive:
        own.add(event.archive)
    if pr.head_ref in own:
        return True
    if not pr.head_ref.startswith(ARCHIVE_PREFIXES) or not event.run:
        return False
    run_file = f"{RUNS_DIR}/{event.run}.yaml"
    return any(f == run_file or f.endswith(f"/{event.run}.yaml") for f in pr.files)


def _closeout(batch: Batch) -> CloseoutEvent | None:
    for e in reversed(batch.events):
        if isinstance(e, CloseoutEvent):
            return e
    return None


# ------------------------------------------------------------------ the pass


def _dispatch_key(batch: Batch) -> tuple[int, int, int, int, str]:
    """Wave, then merge order (an explicit `order`), then id; unset sorts last."""
    wave, order = batch.wave, batch.order
    return (wave is None, wave or 0, order is None, order or 0, batch.id)


def drive_pass(snap: Snapshot) -> Pass:
    """One pass: merge, close out, archive, dispatch — in that order, so a slot a
    merge frees is used in the same pass."""
    actions: list[Action] = []
    stages = dict(snap.stages)
    merging: set[str] = set()

    # 1. Merge.
    for entry in merge_order(list(snap.queue)):
        bid = entry.batch.id
        pr = snap.live.get(bid)
        if pr is None or pr.state != "OPEN" or pr.draft or pr.head != entry.pr.head_oid:
            continue
        if pr.checks == "failing":
            if pr.head not in snap.warned:
                actions.append(
                    Action("warn", bid, f"PR #{pr.number} CI failing at {pr.head[:12]}: "
                           f"{', '.join(pr.failing)}", pr=pr.number, head=pr.head)
                )  # fmt: skip
            continue
        if pr.checks == "pending":
            continue
        actions.append(
            Action("merge", bid, f"PR #{pr.number} at {pr.head[:12]}", pr=pr.number, head=pr.head)
        )
        merging.add(bid)

    # 2. Close out.
    closing = 0
    for batch in snap.batches:
        if stages.get(batch.id) not in LANDED or batch.id in merging:
            continue
        event = _closeout(batch)
        if event is not None:
            continue
        closing += 1
        merged_at = snap.merged_at.get(batch.id)
        due = (
            batch.id in snap.released
            or merged_at is None
            or snap.now - merged_at >= CLOSEOUT_FALLBACK
        )
        if not due:
            continue
        item = closeout_item_id(snap.repos.get(batch.id, ""), batch.id)
        owed = not any(e.kind == "post_merge" for e in batch.events)
        if item in snap.existing:
            actions.append(Action("closeout", batch.id, f"record the live {item}", recorded=True))
        else:
            actions.append(Action("closeout", batch.id, f"start {item}", post_merge=owed))

    # 3. Archive.
    for batch in snap.batches:
        event = _closeout(batch)
        if event is None or stages.get(batch.id) not in LANDED:
            continue
        mine = [
            p
            for p in snap.archives.get(snap.repos.get(batch.id, ""), ())
            if attributed(p, batch, event)
        ]
        if any(p.state == "MERGED" for p in mine):
            continue  # archived: the batch is finished
        closing += 1
        ready = next(
            (p for p in mine if p.state == "OPEN" and not p.draft and p.checks == "green"), None
        )
        if ready is not None:
            actions.append(
                Action("archive", batch.id, f"PR #{ready.number} ({ready.head_ref})",
                       pr=ready.number, head=ready.head)
            )  # fmt: skip

    # 4. Dispatch.
    in_flight = sum(1 for s in stages.values() if s in IN_FLIGHT) - len(merging)
    for bid in merging:
        stages[bid] = "merged"
    by_id = {b.id: b for b in snap.batches}
    pending = blocked = 0
    for batch in sorted(snap.batches, key=_dispatch_key):
        if stages.get(batch.id) != "proposed":
            continue
        dead = [
            f"{d} is {stages.get(d, 'unknown')}"
            for d in batch.after
            if d not in by_id or stages.get(d) in UNSATISFIABLE
        ]
        if dead:
            blocked += 1
            actions.append(Action("blocked", batch.id, f"waits on {'; '.join(dead)}"))
            continue
        if any(stages.get(d) != "merged" for d in batch.after):
            pending += 1
            continue
        if in_flight >= snap.max_inflight:
            pending += 1
            continue
        in_flight += 1
        actions.append(
            Action("dispatch", batch.id, f"wave {batch.wave if batch.wave is not None else '-'}")
        )

    merged = sum(1 for s in stages.values() if s in LANDED)
    closing += len(merging)
    return Pass(
        actions=tuple(actions),
        summary=Summary(
            in_flight=in_flight, merged=merged, pending=pending, closing=closing, blocked=blocked
        ),
    )


# --------------------------------------------------------------- lines (R13)


def action_line(action: Action, outcome: str | None = None) -> str:
    """The one line an action prints, in plan mode (*outcome* None) and when acted:
    the same words in `--once` and loop mode."""
    return f"{action.kind} {action.batch}: {outcome or action.detail}"


def summary_line(summary: Summary) -> str:
    line = (
        f"in flight {summary.in_flight}, merged {summary.merged}, "
        f"pending {summary.pending}, closing {summary.closing}"
    )
    return line + (f", blocked {summary.blocked}" if summary.blocked else "")
