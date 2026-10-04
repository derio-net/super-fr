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

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from fr.triage.batch import (
    UNSATISFIABLE,
    BatchStage,
    ForeignPr,
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
JOURNAL_DIRS = ("docs/superpowers/journals/", "docs/superpowers/implemented/journals/")
RUN_ARTIFACT_DIRS = tuple(
    f"docs/superpowers/{d}/" for d in ("plans", "specs", "journals", "runs", "usage")
)
"""Where a run's live artifacts sit until its close-out archives them under
`docs/superpowers/implemented/` (`fr archive --branch`)."""

ChecksVerdict = Literal["green", "pending", "failing"]
ActionKind = Literal[
    "merge", "closeout", "archive", "dispatch", "blocked", "held", "warn", "foreign"
]

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
    # From the repo itself, by an allowed author (`fr.triage.batch.distrust`). False
    # unless the command checked it: an archive PR is attributed only when True (gh#936).
    trusted: bool = False


@dataclass(frozen=True)
class Snapshot:
    """Everything one pass decides from. Built fresh each pass, never stored."""

    batches: tuple[Batch, ...]  # every batch of the state file
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
    # What was reported already: a head sha whose CI failed, or a `ForeignPr.key`.
    warned: frozenset[str] = frozenset()
    # The batches this drive acts on (None: all). The in-flight cap and dependency
    # resolution always read every batch: a batch outside the selection still holds
    # a slot, and a dependency outside it is still merged or not (review rg-3).
    selected: frozenset[str] | None = None
    # Landed batches whose merge added run artifacts that are all archived now: closed
    # out already, by hand or by an earlier driver (`is_archived`). A batch merged
    # before the driver existed carries no close-out event, so without this every one
    # of them read as owed (debug 2026-10-03: 50 on this repo).
    archived: frozenset[str] = frozenset()
    # batch id -> the open PRs on its branch that are not its own (gh#936).
    foreign: Mapping[str, tuple[ForeignPr, ...]] = field(default_factory=dict)


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
    def idle(self) -> bool:
        """Nothing pending, in flight or closing: nothing the driver can still move."""
        return self.in_flight == 0 and self.pending == 0 and self.closing == 0

    @property
    def done(self) -> bool:
        """Idle and nothing blocked: every driven batch is finished."""
        return self.idle and self.blocked == 0

    @property
    def waiting_on_operator(self) -> bool:
        """Idle, but a blocked batch remains: only the operator can move it (R7)."""
        return self.idle and self.blocked > 0


def settle(summary: Summary, *, unlanded: int = 0, held: int = 0) -> Summary:
    """The pass's summary once its actions ran: *unlanded* planned merges did not
    land (held, updated, refused), so they are still in flight and not closing, and
    *held* planned dispatches did not start, so they are still pending (review rg-1)."""
    return replace(
        summary,
        in_flight=summary.in_flight + unlanded - held,
        merged=summary.merged - unlanded,
        closing=summary.closing - unlanded,
        pending=summary.pending + held,
    )


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
    `NEUTRAL` read as passed. No check reported at all is `pending`, never green: a
    head the driver just pushed, or a PR just readied, has no check registered yet
    (review rg-4); only a `ci none` repo merges without one.
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
    if not all_checks.get("pass", 0):
        return "pending", ("no check reported yet",)
    return "green", ()


def closeout_due(*, released: bool, merged_at: datetime | None, now: datetime) -> bool:
    """§B step 2: the release commit that follows the merge is on the base branch,
    or ten minutes passed since the merge with none. An unknown merge time is not
    yet due (review rg-9): the caller supplies when it first saw the merge."""
    if released:
        return True
    return merged_at is not None and now - merged_at >= CLOSEOUT_FALLBACK


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
    """Whether archive PR *pr* belongs to *batch*'s close-out (§B step 3).

    Its head alone attributes it only when the head is `chore/closeout-<batch branch
    with / as ->`, a name no other batch can produce. Any other `chore/archive-*` or
    `chore/closeout-*` head (`chore/archive-<plan>`, `chore/closeout-<run-id>`) must
    also change the batch's run file or its plan journal (review rg-12). Neither
    attributes a PR that is not `trusted`: a fork or a foreign author can choose
    both the head name and the files (gh#936)."""
    if not pr.trusted:
        return False
    branch = batch_branch(batch)
    if pr.head_ref == f"chore/closeout-{branch.replace('/', '-')}":
        return True
    if not pr.head_ref.startswith(ARCHIVE_PREFIXES):
        return False
    archive = event.archive or ""
    plan = archive.removeprefix("chore/archive-") if archive.startswith("chore/archive-") else ""
    for f in pr.files:
        if event.run and (f == f"{RUNS_DIR}/{event.run}.yaml" or f.endswith(f"/{event.run}.yaml")):
            return True
        if plan and f.startswith(JOURNAL_DIRS) and PurePosixPath(f).stem == plan:
            return True
    return False


def is_archived(added: Iterable[str], live: Callable[[str], bool]) -> bool:
    """Whether a merged batch's close-out has already happened: its merge commit
    *added* at least one run artifact (`RUN_ARTIFACT_DIRS`), and none of those is
    *live* on the default branch any more. No added artifact is no evidence, so
    the close-out stays owed."""
    mine = [p for p in added if p.startswith(RUN_ARTIFACT_DIRS)]
    return bool(mine) and not any(live(p) for p in mine)


def closeout_event(batch: Batch) -> CloseoutEvent | None:
    """The batch's close-out event, if it has one."""
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
    """One pass: report foreign PRs, merge, close out, archive, dispatch — in that
    order, so a slot a merge frees is used in the same pass."""
    actions: list[Action] = []
    stages = dict(snap.stages)
    merging: set[str] = set()
    chosen = tuple(b for b in snap.batches if snap.selected is None or b.id in snap.selected)

    # 0. Report a PR on a batch branch that is not the batch's, once (gh#936). It
    # never reaches the queue, so it is never merged.
    for batch in chosen:
        for found in snap.foreign.get(batch.id, ()):
            if found.key not in snap.warned:
                actions.append(
                    Action("foreign", batch.id,
                           f"PR #{found.pr.number} on {found.pr.head_ref} is not this batch's: "
                           f"{found.reason}; it is never merged", pr=found.pr.number,
                           head=found.key)
                )  # fmt: skip

    # 1. Merge.
    for entry in merge_order(list(snap.queue)):
        bid = entry.batch.id
        if snap.selected is not None and bid not in snap.selected:
            continue
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
    for batch in chosen:
        if stages.get(batch.id) not in LANDED or batch.id in merging:
            continue
        if batch.id in snap.archived:
            continue  # closed out already: its run's artifacts are archived
        event = closeout_event(batch)
        if event is not None:
            continue
        closing += 1
        due = closeout_due(
            released=batch.id in snap.released,
            merged_at=snap.merged_at.get(batch.id),
            now=snap.now,
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
    for batch in chosen:
        event = closeout_event(batch)
        if event is None or stages.get(batch.id) not in LANDED:
            continue
        if event.archived is not None:
            continue  # the driver merged its archive PR: the batch is finished
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
    # The cap counts every batch in flight, selected or not (review rg-3); the
    # summary's own figure is the selection's, which is what this drive waits on.
    occupants = {
        b.id for b in snap.batches if stages.get(b.id) in IN_FLIGHT and b.id not in merging
    }
    driven = {b.id for b in chosen}
    in_flight = sum(1 for b in driven if stages.get(b) in IN_FLIGHT) - len(merging)
    for bid in merging:
        stages[bid] = "merged"
    by_id = {b.id: b for b in snap.batches}
    pending = blocked = 0
    for batch in sorted(chosen, key=_dispatch_key):
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
        if len(occupants) >= snap.max_inflight:
            # The summary counts only the selection, so a cap held by batches
            # outside it would otherwise read as idle (gh#913).
            pending += 1
            actions.append(Action("held", batch.id, f"the in-flight cap ({snap.max_inflight}) "
                                  f"is full: {', '.join(sorted(occupants))}"))  # fmt: skip
            continue
        occupants.add(batch.id)
        in_flight += 1
        actions.append(
            Action("dispatch", batch.id, f"wave {batch.wave if batch.wave is not None else '-'}")
        )

    merged = sum(1 for b in driven if stages.get(b) in LANDED)
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
