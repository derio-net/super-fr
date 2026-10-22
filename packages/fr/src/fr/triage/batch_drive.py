"""The wave driver's pass, as a pure function (wave-driver spec §B, §C).

`drive_pass(snapshot)` returns the ordered actions one pass of `fr triage batch
drive` takes: merge what is ready, close out what merged, merge an attributed
archive PR, dispatch what may start, report what is blocked or failing, and say
when a finished wave leaves duplicate candidates (`dedupe`).
The command layer (`fr.commands.triage_batch_cmd`) builds the `Snapshot` from
the facts, the forge client, the checkout and the runner, and executes the
actions; this module only decides.

It imports nothing from `fr_dispatch`, runs no git, starts no process and
reads no clock: the time is `Snapshot.now`, so the ten-minute fallback is
testable. `tests/unit/test_triage_batch_drive.py` pins that.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from fr.ghclient import QueueState
from fr.labels import held_gates
from fr.triage.approval import ApprovalVerdict, is_approved
from fr.triage.batch import (
    UNSATISFIABLE,
    BatchStage,
    ForeignPr,
    QueueEntry,
    batch_item_id,
    batch_pr,
    last_dispatch,
    recorded_branch,
)
from fr.triage.claims import Claim, held_line, held_members
from fr.triage.mergeability import conflicting
from fr.triage.model import (
    ArchiveConflictEvent,
    Batch,
    CloseoutEvent,
    CloseoutHandbackEvent,
    CloseoutHoldEvent,
    CollectedCloseout,
    ConflictEvent,
    DispatchEvent,
    EnqueueEvent,
    Export,
    Facts,
    RedHandbackEvent,
    UpdateEvent,
)

DEFAULT_WORKSPACE_PREFIX = "drive"
CLOSEOUT_FALLBACK = timedelta(minutes=10)
"""How long after a merge the close-out starts when no release commit followed it
(a PR with no change fragment releases nothing)."""
STALE_CLOSEOUT = timedelta(minutes=15)
"""How long a recorded close-out may go with no live tab and no archive PR before the
driver says so (gh#1025): long enough to cover the record-then-start window of gh#883
and a runner's own lag in reporting a tab it just opened."""

DEFAULT_MAX_INFLIGHT = 4

AWAITING_LIVE_HOLD = "its members await a live walk: no work to dispatch"
"""The `held` detail of a planned batch whose open members all carry `fr:awaiting-live`
(spec 2026-10-06-verification-strategies §F, R18): the one rule the board reads too."""

IN_FLIGHT: frozenset[BatchStage] = frozenset({"dispatched", "pr-open"})
LANDED: frozenset[BatchStage] = frozenset({"merged", "partial"})
ARCHIVE_PREFIXES = ("chore/archive-", "chore/closeout-")
EXPORT_PREFIX = "chore/triage-state-"  # + `<scope id>-wave-<N>` (gh#1101)
"""The head of a wave's state-export PR (pages-goal R13). Not in `ARCHIVE_PREFIXES`, so
archive attribution can never claim an export PR."""
RUNS_DIR = "docs/superpowers/runs"
JOURNAL_DIRS = ("docs/superpowers/journals/", "docs/superpowers/implemented/journals/")
RUN_ARTIFACT_DIRS = tuple(
    f"docs/superpowers/{d}/" for d in ("plans", "specs", "journals", "runs", "usage")
)
"""Where a run's live artifacts sit until its close-out archives them under
`docs/superpowers/implemented/` (`fr archive --branch`)."""

ChecksVerdict = Literal["green", "pending", "failing"]
ActionKind = Literal[
    "merge",
    "closeout",
    "adopt",
    "archive",
    "dispatch",
    "blocked",
    "held",
    "warn",
    "foreign",
    "close",
    "dedupe",
    "claim",
    "refresh",
    "release",
    "settle",
    "export",
    "export-merge",
    "export-reconcile",
    "export-closed",
    "enqueue",
    "archive-conflict",
    "export-conflict",
    "awaiting-live",
    "gate-pass",
    "ledger-unread",
    "post-merge",
    "closeout-held",
    "closeout-handback",
    "closeout-stuck",
    "closeout-unrecorded",
    "closeout-reopened",
    "closeout-merged",
    "closeout-pr-closed",
    "closeout-needs-review",
    "closeout-abandoned",
]
EXPORT_KINDS: frozenset[str] = frozenset(
    {"export", "export-merge", "export-reconcile", "export-closed"}
)

ARCHIVE_WAIT = "archive PR"
"""How an archive PR's waiting line starts (merge-truth R9): `views.needs_you` reads a warn
that starts so as a status line, never a `failing-ci` Need."""

CONFLICTING = "CONFLICTING"
"""The forge's `mergeable` for a PR that cannot merge cleanly (merge-truth R12)."""

ARCHIVED_BY_UNKNOWN_PR = 0
"""`CloseoutEvent.archived` for a close-out found archived on the default branch with
no PR to name: every reader only asks whether `archived` is set (gh#900)."""

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
    # The branch the PR merges into, as the forge says now; "" when not read. An export
    # PR is reused or merged only into the default branch (p4-r15).
    base: str = ""
    # GitHub's `mergeable` (MERGEABLE | CONFLICTING | UNKNOWN) and `mergeStateStatus`, ""
    # when not read. A CONFLICTING archive or export PR is never merged (merge-truth R12);
    # a collected close-out's PR merges only once `MERGEABLE` (exit-gates R15).
    mergeable: str = ""
    merge_state: str = ""


@dataclass(frozen=True)
class GatedRow:
    """A matrix row a post-merge gate gates, as the default branch reads it (exit-gates
    R13, R14): whether it reads `walked` there, and the issues (`owner/repo#n`) it cites."""

    id: str
    gate: str
    walked: bool
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateLedger:
    """A landed batch's merged PR as the gate ledger (R14): its number and labels, and the
    rows its post-merge gates gate. `rows` is None when they were not read (the board,
    which reads no clone; an unreadable default branch): no label and no pass is planned
    from an unknown."""

    pr: int
    labels: frozenset[str]
    rows: tuple[GatedRow, ...] | None = None
    # The run-level gate, and whether any row inherits it (p4-r3): a run gate no row
    # inherits is never passed by walked rows, only by `fr gate pass`.
    run_gate: str = "none"
    run_gate_inherited: bool = False
    # fr-ops R13: `devops` holds because the run's plan has ops, so walked rows never pass it.
    ops_promoted: bool = False


def is_gated(batch: Batch, snap: Snapshot) -> bool:
    """R13: *batch* landed and its merged PR holds an unpassed post-merge gate. The one
    predicate the driver's step 2 and the board's views read; labels never read are no
    evidence, so such a batch is not gated."""
    ledger = snap.ledgers.get(batch.id)
    return (
        snap.stages.get(batch.id) in LANDED
        and ledger is not None
        and bool(held_gates(ledger.labels))
    )


def fact_ledgers(
    batches: Iterable[Batch], facts: Facts, stages: Mapping[str, str]
) -> dict[str, GateLedger]:
    """Each landed batch's merged PR as the facts read it (labels only: rows need the
    default branch). A PR whose labels were never read (facts before 12) has no ledger."""
    out: dict[str, GateLedger] = {}
    for b in batches:
        if stages.get(b.id) not in LANDED:
            continue
        pr = batch_pr(b, facts)
        if pr is not None and pr.state == "MERGED" and pr.labels is not None:
            out[b.id] = GateLedger(pr=pr.number, labels=frozenset(pr.labels))
    return out


def fact_ledger_unknown(
    batches: Iterable[Batch], facts: Facts, stages: Mapping[str, str]
) -> frozenset[str]:
    """The landed batches with no close-out event whose merged PR's labels collect could
    not read (p4-r1): from facts 12 on, every such PR is read, so None is a failed read.
    Unknown is not ungated: step 2 holds their close-out. A file below 12 never read them,
    and is upgraded by the next collect."""
    if facts.schema_ < 12:
        return frozenset()
    out: set[str] = set()
    for b in batches:
        if stages.get(b.id) not in LANDED or closeout_event(b) is not None:
            continue
        pr = batch_pr(b, facts)
        if pr is not None and pr.state == "MERGED" and pr.labels is None:
            out.add(b.id)
    return frozenset(out)


def awaiting_unlabelled(facts: Facts) -> frozenset[str]:
    """The open issues (`owner/repo#n`) in *facts* not labelled `fr:awaiting-live`: the
    only ones a gated batch's first pass labels (R13). An issue outside the facts is not
    known open, so it is never labelled."""
    from fr.labels import FR_AWAITING_LIVE

    return frozenset(
        f"{i.repo}#{i.number}"
        for i in facts.issues
        if i.state == "open" and FR_AWAITING_LIVE.name not in i.labels
    )


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
    # Landed batches with no close-out event whose close-out PR, on the head no other
    # batch can produce (`housekeeping_branch` with no run), is open or merged: a
    # close-out started by hand (gh#912).
    adopted: Mapping[str, LivePr] = field(default_factory=dict)
    # batch id -> the open PRs on its branch that are not its own (gh#936).
    foreign: Mapping[str, tuple[ForeignPr, ...]] = field(default_factory=dict)
    # Close finished batches' sessions (off under `--keep-sessions` and without `--yes`),
    # and the batch and close-out item ids of batches that a closing runner holds live.
    close_sessions: bool = False
    sessions: frozenset[str] = frozenset()
    # Triage-dedupe R10. The waves that were unfinished on this process's previous pass
    # (None on its first), the candidate-group count, and the scope-qualified check
    # command: the count and the command arrive here so this module imports no dedupe.
    unfinished_waves: frozenset[str] | None = None  # wave keys, as `finished`
    duplicate_groups: int = 0
    dedupe_command: str = ""
    # Per-wave state export (pages-goal R13, §I). `export_path`: repo -> the export
    # directory `<path>/<scope>` in the repo, for a single-repo scope only; `exports`:
    # what the state file records; `export_prs`: (repo, wave) -> the live PR of a recorded, unmerged
    # export, or the open PR on the wave's export head when none is recorded;
    # `finished`: `finished_waves(batches, stages)`, computed once; `export_refused`:
    # the repos of a group or org scope that opt in, which never export.
    export_path: Mapping[str, str] = field(default_factory=dict)
    exports: tuple[Export, ...] = ()
    export_prs: Mapping[tuple[str, str], LivePr] = field(default_factory=dict)
    finished: frozenset[str] = frozenset()
    export_refused: frozenset[str] = frozenset()
    # repo -> the open PRs from the repo itself on any `chore/triage-state-wave-<N>`
    # head that no live export entry records: a pass that died between opening and
    # recording (p4-r3), or a reopened PR recorded closed. Cross-repo PRs never appear
    # here (p4-r7). The export reuses one; it never adopts its content (p4-r12).
    export_orphans: Mapping[str, tuple[LivePr, ...]] = field(default_factory=dict)
    # This scope's id: the export heads it pushes and reuses name it, so another host's
    # scope of the same repo never takes this one's export PR for an orphan (gh#1101).
    scope_id: str = ""
    # repo -> its default branch: the only base an export PR (p4-r15) or an archive PR
    # (gh#1004) may have; "" or absent when the clone could not say, which matches none
    default_branch: Mapping[str, str] = field(default_factory=dict)
    # Landed batches with no close-out event whose evidence (archived? released?) the
    # clone could not give: plan mode only, where a failed read is reported rather
    # than fatal. Unknown is not "not archived", so no close-out is planned (gh#991).
    unverified: frozenset[str] = frozenset()
    # The batches whose open members all await their live walk (`batch_awaits_live`):
    # a planned one is held, never dispatched (spec §F, R18).
    awaiting: frozenset[str] = frozenset()
    # batch id -> why the driver adapter does not dispatch it (another runner named
    # explicitly, cloud-triage §E, p4-r1): a hold, so it takes no in-flight slot. Still
    # pending: the driver whose runner it names may yet dispatch it.
    refused: Mapping[str, str] = field(default_factory=dict)
    # The batches with a recorded close-out whose item `existing` was read for (gh#1025):
    # only for these is "not in `existing`" evidence that no tab holds it. Plan mode
    # reads no runner, so it probes none and never calls a close-out stale.
    closeout_probed: frozenset[str] = frozenset()
    # Triage-claims §3.F. `me`: this scope's id; `held`: issue key -> the other scope's
    # winning claim (R4, R6), from facts; the three `*_owed` lists are (key, batch id)
    # pairs, from `claim_sync.plan_sync`: this module decides order, never what is owed.
    me: str = ""
    held: Mapping[str, Claim] = field(default_factory=dict)
    claims_owed: tuple[tuple[str, str], ...] = ()
    refresh_owed: tuple[tuple[str, str], ...] = ()
    releases_owed: tuple[tuple[str, str], ...] = ()
    # Closed issues to settle (post-merge truth R1, R2): (key, batch id), the batch "" when
    # no batch of this scope holds the key. Written after the releases.
    settles_owed: tuple[tuple[str, str], ...] = ()
    # Sessions the runner reports idle with no PR, past `idle_session_minutes` (driver-sessions
    # §D, R7): built by the command from live statuses, never by `views.drive_snapshot`
    # (whose warns all read as a failing CI). `scope_args` are the drive's own, for the
    # paste-ready focus command.
    idle: tuple[IdleSession, ...] = ()
    scope_args: tuple[str, ...] = ()
    # batch id -> its PR's approval verdict (merge-train-safety §A "The walk"): from the
    # live labels in the driver, from facts on the board and `drive --plan`. A batch
    # with no verdict here is never approved.
    approvals: Mapping[str, ApprovalVerdict] = field(default_factory=dict)
    # Merge queues (merge-train-safety §D "Queue mode", R13), from the driver's reads: the
    # repos whose base requires one (their train picks no head), those of them with a
    # `version:` block, whether `forge.api` is `rest` (which cannot enqueue), each queued
    # batch's `QueueState`, and each such repo's base sha now. The board and `drive --plan`
    # read no forge, so they leave all of these empty and show the ordinary train.
    queue_repos: frozenset[str] = frozenset()
    queue_versioned: frozenset[str] = frozenset()
    queue_rest: bool = False
    # Repos whose default branch could not be told: queue mode is unknown, so they are held.
    queue_unknown: frozenset[str] = frozenset()
    # Facts-only views (the board, `drive --plan`) read no queue state: a PR whose last
    # event is an `enqueued` one at its current head is then shown in the merge queue.
    queue_inferred: bool = False
    queue_states: Mapping[str, QueueState] = field(default_factory=dict)
    bases: Mapping[str, str] = field(default_factory=dict)
    # Why this pass dispatches nothing at all (spec 2026-10-12-quota-pacing R7: "quota below
    # floor"); None dispatches as usual. Each dispatch it stops is a `held` action counted
    # pending, never `Summary.held`: the budget recovers, so the drive is not stalled.
    dispatch_held: str | None = None
    # The gate ledger (exit-gates R13, R14): batch id -> its merged PR's labels and gated
    # rows, from facts (the labels) and the default branch (the rows, driver only); and
    # the issues (`owner/repo#n`) that are open in facts without `fr:awaiting-live`.
    ledgers: Mapping[str, GateLedger] = field(default_factory=dict)
    awaiting_unlabelled: frozenset[str] = frozenset()
    # Landed batches whose merged PR's labels could not be read (p4-r1): never closed out
    # until the ledger is known.
    ledger_unknown: frozenset[str] = frozenset()
    # The repos whose `post_merge` this driver runs (p4-r2): a landed batch of one gets a
    # `post-merge` action at merge, gated or not, before any close-out of it.
    post_merge_repos: frozenset[str] = frozenset()
    # Collected close-outs (exit-gates R15, §D): the start markers from the judgements,
    # and, driver only, what the driver itself reads for each unfinished one, by item:
    # its PR on its branch; its own git diff (`<status>\t<path>`) and commits from the
    # default branch to the RECORDED head (None: unreadable); the issues its PR body
    # closes; the issues the members' narrowing decisions name now (None: unreadable);
    # whether its branch is pushed; and the PR now open again on a closed marker's branch.
    closeouts: tuple[CollectedCloseout, ...] = ()
    collected_prs: Mapping[str, LivePr] = field(default_factory=dict)
    collected_diff: Mapping[str, frozenset[str] | None] = field(default_factory=dict)
    collected_commits: Mapping[str, tuple[str, ...] | None] = field(default_factory=dict)
    collected_body_closes: Mapping[str, frozenset[str]] = field(default_factory=dict)
    collected_narrowed: Mapping[str, frozenset[str] | None] = field(default_factory=dict)
    collected_pushed: frozenset[str] = frozenset()
    collected_reopened: Mapping[str, LivePr] = field(default_factory=dict)


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    batch: str
    detail: str
    pr: int | None = None
    head: str = ""
    recorded: bool = False  # closeout: the runner holds the tab; record the event only
    train: str = ""  # merge: the repo whose train this candidate belongs to
    archived: int | None = None  # adopt: the close-out event's `archived`
    # close: the item ids whose sessions to close; closeout, archive, closeout-handback,
    # closeout-stuck of a collected close-out: its member batch ids
    items: tuple[str, ...] = ()
    # export*, and a warn about one: the wave key (`batch` is then the repo); the
    # highest wave the export PR covers, which names its branch
    wave: str | None = None
    covers: tuple[str, ...] = ()  # export: every wave the PR records
    # claim, refresh, release, settle: the issue key; a collected close-out's actions: its
    # name, `closeout-<date>-<n>`
    key: str = ""
    red: bool = False  # warn: a failing batch PR, which the driver tries to recover (§C)
    checks: tuple[str, ...] = ()  # warn (red): the failing check names
    ejected: bool = False  # warn: a queued PR that left the merge queue unmerged (§D)
    gate: str = ""  # gate-pass: the post-merge gate whose rows all read walked
    # archive: the PR is a draft, marked ready first (merge-truth R11; a collected
    # close-out's PR the same way)
    draft: bool = False
    branch: str = ""  # archive-conflict: the archive PR's head branch (merge-truth R12)


@dataclass(frozen=True)
class Summary:
    """The pass's closing line, projected past its own actions."""

    in_flight: int
    merged: int
    pending: int
    closing: int
    blocked: int = 0
    queued: int = 0  # merge-train members not attempted this pass (the head excluded)
    held: int = 0  # batches another scope's claim holds: waiting on that scope, not the operator
    # Landed batches a post-merge gate holds (R13): waiting on a person's walk or pass, so,
    # like a batch awaiting its live walk, never work that keeps a drive alive.
    gated: int = 0

    @property
    def idle(self) -> bool:
        """Nothing pending, in flight or closing: nothing the driver can still move."""
        return self.in_flight == 0 and self.pending == 0 and self.closing == 0

    @property
    def done(self) -> bool:
        """Idle and nothing blocked or held: every driven batch is finished."""
        return self.idle and self.blocked == 0 and self.held == 0

    @property
    def waiting_on_operator(self) -> bool:
        """Idle, but a blocked batch remains: only the operator can move it (R7)."""
        return self.idle and self.blocked > 0

    @property
    def stalled(self) -> bool:
        """Idle, with only blocked batches (the operator's) and held ones (another
        scope's, R6) left: nothing this driver can move."""
        return self.idle and (self.blocked > 0 or self.held > 0)


def settle(summary: Summary, *, unlanded: int = 0, held: int = 0, queued: int = 0) -> Summary:
    """The pass's summary once its actions ran: *unlanded* planned merges did not
    land (held, updated, refused), so they are still in flight and not closing, and
    *held* planned dispatches did not start, so they are still pending (review rg-1)."""
    return replace(
        summary,
        in_flight=summary.in_flight + unlanded - held,
        merged=summary.merged - unlanded,
        closing=summary.closing - unlanded,
        pending=summary.pending + held,
        queued=summary.queued + queued,
    )


@dataclass(frozen=True)
class Train:
    """One repo's merge train for a pass (drive-merge-train spec §A)."""

    repo: str
    head: str | None  # the first candidate, or the waiting head; None: all stepped over
    candidates: tuple[str, ...]  # batches with a merge action, in order
    queued: tuple[str, ...]  # the member that stopped the walk (not the head), then the rest
    stepped: tuple[str, ...]  # batches stepped over (failing)
    numbers: Mapping[str, int]  # batch id -> PR number, for train_line
    # Members with no valid `approved-fr` approval: held, never the head, never a stop
    # (merge-train-safety §A "The walk").
    awaiting: tuple[str, ...] = ()
    # Queue mode (§D): the members enqueued this pass and those already in the queue. A
    # queue-mode train has no head and no candidates.
    enqueue: tuple[str, ...] = ()
    in_merge_queue: tuple[str, ...] = ()
    queue_mode: bool = False


@dataclass(frozen=True)
class Pass:
    actions: tuple[Action, ...]
    summary: Summary
    trains: tuple[Train, ...] = ()
    # (batch id, the scope ids holding its members): the batches waiting on another scope
    held_by: tuple[tuple[str, tuple[str, ...]], ...] = ()


# ------------------------------------------------------- idle sessions (R7, R8)


@dataclass(frozen=True)
class IdleSession:
    """A session that sat idle (or done) past the threshold with nothing to show for it."""

    item: str
    batch: str
    closeout: bool
    since: datetime  # the dispatch, or the close-out event, it was started at
    minutes_since: int  # whole minutes from `since` to now: NOT how long it has been idle
    status: str = "idle"


def idle_session(
    batch: Batch,
    *,
    repo: str,
    closeout: bool,
    status: str | None,
    stage: BatchStage,
    archives: Sequence[LivePr],
    now: datetime,
    threshold: int,
) -> IdleSession | None:
    """The one definition of an idle session (driver-sessions R7): the runner reports the
    item `idle` or `done`, it is owed work, and its last dispatch (the close-out: its
    event) is at least *threshold* minutes old.

    Owed work is a function of *stage* (`derive_batch_stage`): a batch session is owed a PR
    only while the batch is `dispatched` (no PR yet; a cancelled, proposed or PR-carrying
    batch owes it nothing), and a close-out session only once the batch has landed and the
    close-out is not finished (`is_finished`: its archive PR merged, or recorded). An
    archive PR in *archives*, open or merged, attributed to the close-out is its product.
    Pure and stateless, so the driver and the board read the same rule."""
    if status not in ("idle", "done"):
        return None
    if closeout:
        event = closeout_event(batch)
        if event is None or stage not in LANDED or is_finished(batch, stage, archives):
            return None
        if event.archived is not None or any(attributed(p, batch, event) for p in archives):
            return None
        since = event.at
        item = event_item_id(repo, batch.id, event)
    else:
        dispatch = last_dispatch(batch)
        if dispatch is None or stage != "dispatched":
            return None
        since = dispatch.at
        item = batch_item_id(repo, batch.id)
    age = now - since
    if age < timedelta(minutes=threshold):  # "at least the threshold" is idle
        return None
    return IdleSession(item, batch.id, closeout, since, int(age.total_seconds() // 60), status)


def _idle_actions(snap: Snapshot, chosen: Sequence[Batch]) -> list[Action]:
    """One warn per idle session, once per driver process (its head is in `warned`)."""
    out: list[Action] = []
    ids = {b.id for b in chosen}
    for idle in snap.idle:
        key = f"idle-session\0{idle.item}\0{idle.since.isoformat()}"
        if idle.batch not in ids or key in snap.warned:
            continue
        what = "archive PR" if idle.closeout else "PR"
        cmd = shlex.join(
            ["fr", "triage", "batch", "focus", idle.batch,
             *(["--closeout"] if idle.closeout else []), *snap.scope_args]
        )  # fmt: skip
        out.append(
            Action("warn", idle.batch,
                   f"{idle.item} is {idle.status}, "
                   f"{'close-out started' if idle.closeout else 'dispatched'} "
                   f"{idle.minutes_since} min ago, with no {what}; focus it: {cmd}", head=key)
        )  # fmt: skip
    return out


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


def _stale_closeout(batch: Batch, event: CloseoutEvent, snap: Snapshot) -> Action | None:
    """A close-out recorded but, it seems, never started (gh#1025): the event is older
    than `STALE_CLOSEOUT`, the runner holds no tab for it and no archive PR names it.
    A driver killed between the record (gh#883) and the tab leaves exactly this, and
    the batch would read `closing` forever. Said once; the operator decides."""
    if snap.now - event.at < STALE_CLOSEOUT:
        return None
    item = event_item_id(snap.repos.get(batch.id, ""), batch.id, event)
    if item in snap.existing:
        return None
    key = f"stale-closeout\0{batch.id}\0{event.at.isoformat()}"
    if key in snap.warned:
        return None
    since = event.at.strftime("%Y-%m-%dT%H:%M")
    pickup = f"--run {event.run}" if event.run else f"--branch {recorded_branch(batch)}"
    return Action(
        "warn", batch.id,
        f"close-out {item} was recorded at {since}Z but no runner holds it and no archive "
        f"PR names it; run it by hand: `fr pickup {pickup}`",
        head=key,
    )  # fmt: skip


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


COLLECTED_PREFIX = "chore/closeout-"
_COLLECTED = re.compile(r"^chore/closeout-(\d{4}-\d{2}-\d{2})-(\d+)$")


def collected_branch(day: date, n: int) -> str:
    """`chore/closeout-<YYYY-MM-DD>-<n>`: the head of one collected close-out."""
    return f"{COLLECTED_PREFIX}{day.isoformat()}-{n}"


def collected_name(branch: str) -> str | None:
    """`closeout-<YYYY-MM-DD>-<n>` for a collected close-out's branch, the name of its
    work item; None for any other head (a per-batch close-out's)."""
    return branch.removeprefix("chore/") if _COLLECTED.match(branch) else None


def next_collected(branches: Iterable[str], day: date) -> int:
    """The first number after every collected close-out of *day* in *branches*."""
    used = [
        int(m.group(2))
        for b in branches
        if (m := _COLLECTED.match(b)) is not None and m.group(1) == day.isoformat()
    ]
    return max(used, default=0) + 1


def collected_item_id(repo: str, name: str) -> str:
    """`<OWNER>/<REPO>/run/closeout-<date>-<n>`: unit `run`, one per collected close-out."""
    return f"{repo}/run/{name}"


def event_item_id(repo: str, batch_id: str, event: CloseoutEvent) -> str:
    """The work item a batch's close-out event started: the collected close-out's when its
    `archive` is a collected branch (R15), else the batch's own."""
    name = collected_name(event.archive or "")
    return collected_item_id(repo, name) if name else closeout_item_id(repo, batch_id)


def marker_of(branch: str, closeouts: Iterable[CollectedCloseout]) -> CollectedCloseout | None:
    """The start marker of the collected close-out on *branch*, if one was recorded."""
    return next((c for c in closeouts if c.branch == branch), None)


def closeout_of(batch: Batch, closeouts: Iterable[CollectedCloseout]) -> CloseoutEvent | None:
    """The batch's close-out, as owed-ness reads it: its latest `closeout` event, unless
    that event names a collected close-out whose PR was closed unmerged (R15, p6-r5):
    then the batch is owed a close-out again."""
    event = closeout_event(batch)
    if event is None or collected_name(event.archive or "") is None:
        return event
    marker = marker_of(event.archive or "", closeouts)
    return None if marker is not None and marker.closed and not marker.merged else event


def closeout_hold(batch: Batch) -> CloseoutHoldEvent | None:
    """The batch's `closeout_hold` since its last dispatch with no close-out after it (R15):
    the driver never collects it again; only `fr triage batch closeout <id>` retries it."""
    for event in reversed(batch.events):
        if isinstance(event, (DispatchEvent, CloseoutEvent)):
            return None
        if isinstance(event, CloseoutHoldEvent):
            return event
    return None


def collected_used(repo: str, batches: Iterable[Batch],
                   closeouts: Iterable[CollectedCloseout]) -> list[str]:  # fmt: skip
    """Every collected branch *repo* has used: its markers' and its events' archives."""
    out = [c.branch for c in closeouts if c.repo == repo]
    out += [e.archive for b in batches for e in b.events
            if isinstance(e, CloseoutEvent) and e.archive]  # fmt: skip
    return out


def collected_candidate(
    repo: str,
    batches: Iterable[Batch],
    repos: Mapping[str, str],
    closeouts: Iterable[CollectedCloseout],
    day: date,
) -> tuple[str, str]:
    """`(name, item id)` of *repo*'s next collected close-out on *day*."""
    used = collected_used(repo, (b for b in batches if repos.get(b.id) == repo), closeouts)
    name = str(collected_name(collected_branch(day, next_collected(used, day))))
    return name, collected_item_id(repo, name)


def next_collected_item(repo: str, snap: Snapshot) -> tuple[str, str]:
    """`collected_candidate` on the pass's day."""
    return collected_candidate(repo, snap.batches, snap.repos, snap.closeouts, snap.now.date())


def _collected_under_way(repo: str, snap: Snapshot) -> bool:
    """R15: a collected close-out of *repo* was started (its marker) and has not ended
    (merged, or closed with no archive): the next one waits for it."""
    return any(c.repo == repo and not c.merged and not c.closed for c in snap.closeouts)


def wave_group(prefix: str, wave: int | None) -> str:
    """The runner group (a herdr workspace) a wave's sessions open in."""
    if not prefix.strip():
        raise ValueError("the workspace prefix must not be blank")
    return f"{prefix}-wave-{wave}" if wave is not None else f"{prefix}-no-wave"


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
    branch = recorded_branch(batch)
    pickup = f"fr pickup --run {run}" if run else f"fr pickup --branch {branch}"
    return (
        f"Close out batch {batch.id} ({batch.title}): its PR on {branch} has merged.\n"
        f"In {checkout}, run `{pickup}` and follow the brief it prints, in order."
    )


# ------------------------------------------------- conflict hand-back (§G)

HANDBACKS_PER_DISPATCH = 2
"""R22: hand-backs a batch gets per dispatch; the next conflict is held."""


def handbacks_since(
    events: Sequence[object], counted: Callable[[object], bool], *, reset: bool = True
) -> int:
    """The hand-back budget's one count: the events *counted* accepts, newest first, back
    to the batch's latest `dispatch` (*reset*), or all of them. Conflict (R22) and red
    (R10) hand-backs count per dispatch here; a collected close-out's (R27) counts per
    close-out item across its members, which no single batch's dispatch resets, so it
    counts distinct heads instead (`closeout_handback_decision`)."""
    n = 0
    for event in reversed(events):
        if reset and isinstance(event, DispatchEvent):
            break
        n += counted(event)
    return n


ConflictKind = Literal["skip", "wait-behind", "held", "handback"]


@dataclass(frozen=True)
class ConflictDecision:
    """What drive does with a real merge conflict (spec 2026-10-06-verification-
    strategies §G): `behind` names the batch a `wait-behind` waits on."""

    kind: ConflictKind
    behind: str | None = None


def conflict_decision(
    events: Sequence[object],
    head: str,
    paths: Sequence[str],
    earlier_in_pass: Sequence[tuple[str, Sequence[str]]],
) -> ConflictDecision:
    """The pure decision on a conflict at *head* refusing *paths* (R21, R22).

    `skip`: a `conflict` event already exists for this head, so a restarted driver
    never hands the same head back twice. `wait-behind`: a refused path is shared
    with a conflict met earlier in this pass (*earlier_in_pass*, `(batch, paths)` in
    train order), which is fixed first. `held`: two `session|fresh` hand-backs were
    made since the batch's latest `dispatch` event (held ones never count). Else
    `handback`.
    """
    if any(isinstance(e, ConflictEvent) and e.head == head for e in events):
        return ConflictDecision("skip")
    mine = set(paths)
    for batch_id, theirs in earlier_in_pass:
        if mine.intersection(theirs):
            return ConflictDecision("wait-behind", behind=batch_id)
    handed = handbacks_since(
        events, lambda e: isinstance(e, ConflictEvent) and e.delivered != "held"
    )
    if handed >= HANDBACKS_PER_DISPATCH:
        return ConflictDecision("held")
    return ConflictDecision("handback")


# ------------------------------------------------- red recovery (merge-train-safety §C)

RED_HANDBACKS_PER_DISPATCH = 2
"""R10: red hand-backs a batch gets per dispatch, counted apart from conflict ones."""

RedDecisionKind = Literal["reupdate", "handback", "wait", "needs_you", "skip"]


def red_decision(
    events: Sequence[object],
    pr: int,
    head: str,
    failing: Sequence[str],
    base_now: str,
    status: str,
    *,
    queue: bool = False,
) -> RedDecisionKind:
    """What the driver does with PR *pr* red at *head* (*failing* names the checks), by the
    first rule that applies (R9-R11):

    1. a `red_handback` event exists for (pr, head): `skip`;
    2. *head* is an `update` event's `head_after`, the base moved past that event's base,
       and no later `update` starts from *head*: `reupdate`;
    3. `RED_HANDBACKS_PER_DISPATCH` delivered hand-backs have gone out since the latest
       dispatch: `needs_you`;
    4. the session's *status*: `idle` is a `handback`, `absent` or `done` a `needs_you`,
       anything else `wait`.
    """
    red = [e for e in events if isinstance(e, RedHandbackEvent)]
    if any(e.pr == pr and e.head == head for e in red):
        return "skip"
    updates = [e for e in events if isinstance(e, UpdateEvent) and e.pr == pr]
    made = [e for e in updates if e.head_after == head]
    # In a merge-queue repo fr never pushes an update (R13): rule 2 does not apply.
    if (
        not queue
        and made
        and made[-1].base != base_now
        and not any(e.head_before == head for e in updates)
    ):
        return "reupdate"
    handed = handbacks_since(
        events, lambda e: isinstance(e, RedHandbackEvent) and e.delivered == "session"
    )
    if handed >= RED_HANDBACKS_PER_DISPATCH:
        return "needs_you"
    if status == "idle":
        return "handback"
    return "needs_you" if status in ("absent", "done") else "wait"


def held_conflict(batch: Batch) -> ConflictEvent | None:
    """The batch's latest `conflict` event when it is `held` and no `dispatch` came after
    it (R22): the operator owns that conflict. A new dispatch resets the count."""
    for event in reversed(batch.events):
        if isinstance(event, DispatchEvent):
            return None
        if isinstance(event, ConflictEvent):
            return event if event.delivered == "held" else None
    return None


def fresh_conflicts(batch: Batch, *, since_dispatch: bool) -> int:
    """How many fresh conflict sessions the batch started: all of them (the next one's
    number), or only since its latest dispatch (whether one is the message target)."""
    return handbacks_since(
        batch.events,
        lambda e: isinstance(e, ConflictEvent) and e.delivered == "fresh",
        reset=since_dispatch,
    )


def conflict_item_id(repo: str, batch_id: str, n: int) -> str:
    """`<OWNER>/<REPO>/run/conflict-<batch-id>-<n>`: the *n*th fresh conflict session."""
    return f"{repo}/run/conflict-{batch_id}-{n}"


# ------------------------------------------ archive conflicts (merge-truth R12, §E)

ARCHIVE_HANDBACKS_PER_CLOSEOUT = 2
"""R12: hand-backs a conflicting archive PR gets per close-out before it is the operator's."""

ArchiveConflictKind = Literal["skip", "held", "handback"]


def archive_conflict_decision(events: Sequence[object], head: str) -> ArchiveConflictKind:
    """The pure decision on an archive PR conflicting at *head* (R12).

    `skip`: an `archive_conflict` event exists for this head, so a restarted driver
    never hands the same head back twice. `held`: two `session|fresh` hand-backs were
    made since the batch's latest close-out event (held ones never count; a batch PR's
    `conflict` events are another counter). Else `handback`."""
    if any(isinstance(e, ArchiveConflictEvent) and e.head == head for e in events):
        return "skip"
    handed = 0
    for event in reversed(events):
        if isinstance(event, CloseoutEvent):
            break
        if isinstance(event, ArchiveConflictEvent) and event.delivered != "held":
            handed += 1
    return "held" if handed >= ARCHIVE_HANDBACKS_PER_CLOSEOUT else "handback"


def held_archive_conflict(batch: Batch) -> ArchiveConflictEvent | None:
    """The batch's latest `archive_conflict` event when it is `held` and no close-out
    event came after it (R12): the operator owns that conflict."""
    for event in reversed(batch.events):
        if isinstance(event, CloseoutEvent):
            return None
        if isinstance(event, ArchiveConflictEvent):
            return event if event.delivered == "held" else None
    return None


def _held_archive_conflict(batch: Batch, head: str) -> bool:
    held = held_archive_conflict(batch)
    return held is not None and held.head == head


def archive_conflict_item_id(repo: str, batch_id: str, n: int) -> str:
    """`<OWNER>/<REPO>/run/archive-conflict-<batch-id>-<n>`: the *n*th fresh session
    started for the batch's conflicting archive PR."""
    return f"{repo}/run/archive-conflict-{batch_id}-{n}"


# ------------------------------------------- collected close-out hand-back (R27)

CLOSEOUT_HANDBACKS = 1
"""R27: hand-backs a collected close-out gets, counted per close-out item across its
members; apart from conflict and red hand-backs, which count per batch dispatch."""

CloseoutDecisionKind = Literal["skip", "handback", "stuck"]


def closeout_handback_decision(
    events: Iterable[object], item: str, head: str, handed: Iterable[str] = ()
) -> CloseoutDecisionKind:
    """What the driver does with collected close-out *item*'s PR failing at *head*, from
    every member's events (R27): `skip`, its session was handed it at this head already;
    `stuck`, no session could take the hand-back at this head, or the one hand-back went
    out at an earlier head (a second failure); else `handback`."""
    mine = [e for e in events if isinstance(e, CloseoutHandbackEvent) and e.item == item]
    here = [e for e in mine if e.head == head]
    if here:
        return "stuck" if all(e.delivered == "none" for e in here) else "skip"
    heads = {e.head for e in mine} | set(handed)  # the marker's own count (p6b-r10)
    if head in heads:
        return "skip"
    return "stuck" if len(heads) >= CLOSEOUT_HANDBACKS else "handback"


ARCHIVE_DIRS = ("plans", "specs", "journals", "runs", "usage")
MATRIX_FILES = frozenset({
    "docs/acceptance/matrix.yaml", "docs/acceptance/report_local.html",
    "docs/acceptance/report_linked.html", "docs/acceptance/report_linked.md",
})  # fmt: skip


def archive_allowed(entry: str) -> bool:
    """Whether one `<status>\t<path>` change is what an archive makes (R15's auto-merge
    allowlist): anything under `docs/superpowers/implemented/`, a deletion out of a live
    artifact directory, or the acceptance matrix and its three reports. Never a workflow
    or verification manifest, nor anything else."""
    status, _, path = entry.partition("\t")
    if not path or ".." in PurePosixPath(path).parts:
        return False
    if path.startswith("docs/superpowers/implemented/") or path in MATRIX_FILES:
        return True
    return status == "D" and path.startswith(tuple(f"docs/superpowers/{d}/" for d in ARCHIVE_DIRS))


def review_reasons(marker: CollectedCloseout, pr: LivePr, snap: Snapshot) -> list[str]:
    """Why the driver may NOT merge *marker*'s PR without `approved-fr` (R15's trust
    anchor); [] only when every condition holds: the PR head is the head the verb
    recorded; the driver's own diff to it is exactly the recorded file set and every
    path is an archive's; the only commit past the base is that head; the PR is the
    repo's own by an allowed author; and its body closes exactly the recorded issues,
    less any a narrowing decision names now. Each unknown is a reason."""
    why: list[str] = []
    if not marker.head:
        return ["the verb recorded no head for it"]
    if pr.head != marker.head:
        why.append(f"its head {pr.head[:12] or 'unknown'} is not the recorded {marker.head[:12]}")
    if not pr.trusted:
        why.append("it is not the repo's own PR by an allowed author")
    diff = snap.collected_diff.get(marker.item)
    if diff is None:
        why.append("its diff could not be read")
    else:
        if diff != frozenset(marker.files):
            why.append("its diff is not the recorded file set")
        if outside := sorted(e.partition("\t")[2] for e in diff if not archive_allowed(e)):
            why.append(f"it changes {', '.join(outside[:5])}, which no archive changes")
    commits = snap.collected_commits.get(marker.item)
    if commits is None or tuple(commits) != (marker.head,):
        why.append("its commits past the base are not the one the verb pushed")
    narrowed = snap.collected_narrowed.get(marker.item)
    if narrowed is None:
        why.append("its members' narrowing decisions could not be read")
    else:
        owner = marker.repo.lower()
        want = {c for c in marker.closes if c.lower().startswith(owner + "#")}
        want = {c for c in want if c.lower() not in narrowed}
        if snap.collected_body_closes.get(marker.item, frozenset()) != want:
            why.append("its body's Closes lines are not the recorded issues")
    return why


def _collected_step(marker: CollectedCloseout, snap: Snapshot) -> tuple[Action | None, str]:
    """§D step 3 for one unfinished collected close-out, keyed on its start marker, and how
    the summary counts it (`closing` | `blocked` | ""). Membership is what the verb
    recorded on the marker, never a PR body. Its PR is merged with no approval only when
    `review_reasons` is empty, at the recorded head; a conflict or failing checks go back
    ONCE to its session (R27); a PR closed unmerged ends the close-out (p6-r5)."""
    repo = marker.repo
    known = {b.id for b in snap.batches}
    members = tuple(b for b in marker.members if b in known)
    first = (members or tuple(b for b in marker.planned if b in known) or ("",))[0]
    pr = snap.collected_prs.get(marker.item)
    if not first:
        return None, ""
    if pr is None:
        pushed = marker.item in snap.collected_pushed
        live = marker.item in snap.existing
        stale = snap.now - marker.at >= STALE_CLOSEOUT
        if pushed and not live and stale:
            return Action("closeout-unrecorded", first, f"{marker.branch} is pushed with no PR "
                          f"the verb recorded: re-run `fr triage batch closeout --branch "
                          f"{marker.branch} --yes`", key=marker.item), "blocked"  # fmt: skip
        if not live and not pushed and marker.item in snap.closeout_probed and stale:
            return Action("closeout-abandoned", first, f"{marker.item} ended with no PR on "
                          f"{marker.branch}; its batches are owed a close-out again",
                          key=marker.item), "closing"  # fmt: skip
        return None, "closing"
    if pr.state == "CLOSED":
        return Action("closeout-pr-closed", first, f"close-out PR #{pr.number} on "
                      f"{marker.branch} was closed unmerged; its batches are owed a close-out "
                      "again", pr=pr.number, items=members, key=marker.item), "closing"  # fmt: skip
    if not marker.head:
        return Action("closeout-unrecorded", first, f"PR #{pr.number} on {marker.branch} has no "
                      "head, members or files the verb recorded; re-run `fr triage batch "
                      f"closeout --branch {marker.branch} --yes` to record them", pr=pr.number,
                      key=marker.item), "blocked"  # fmt: skip
    if pr.state == "MERGED":
        return Action("closeout-merged", first, f"close-out PR #{pr.number} merged",
                      pr=pr.number, items=members, key=marker.item), "closing"  # fmt: skip
    default = snap.default_branch.get(repo, "")
    if not default:
        return None, "closing"  # the default branch unknown: wait
    if wrong := _wrong_base(pr, default):
        return Action("blocked", first, f"close-out PR #{pr.number} ({pr.head_ref}) {wrong}; it "
                      "is never merged", pr=pr.number, items=members), "blocked"  # fmt: skip
    conflict = conflicting(pr.mergeable, pr.merge_state)
    if pr.checks == "failing" or conflict:
        what = (
            "conflicts with its base"
            if conflict
            else f"has failing checks: {', '.join(pr.failing) or 'unknown'}"
        )
        events = [e for b in snap.batches if b.id in members for e in b.events]
        decision = closeout_handback_decision(events, marker.item, pr.head, marker.handed)
        if decision == "skip":
            return None, "closing"  # its session has it at this head
        checks = ("merge conflict",) if conflict else pr.failing
        if decision == "stuck":
            return Action("closeout-stuck", first, f"close-out PR #{pr.number} {what} at "
                          f"{pr.head[:12]}, and its one hand-back is spent: fix it on "
                          f"{pr.head_ref}", pr=pr.number, head=pr.head, items=members,
                          key=marker.item, checks=checks), "blocked"  # fmt: skip
        return Action("closeout-handback", first, f"close-out PR #{pr.number} {what}; hand "
                      f"it back to {marker.item}", pr=pr.number, head=pr.head, items=members,
                      key=marker.item, checks=checks), "closing"  # fmt: skip
    if why := review_reasons(marker, pr, snap):
        return Action("closeout-needs-review", first, f"close-out PR #{pr.number} is never "
                      f"merged without approved-fr: {'; '.join(why)}", pr=pr.number,
                      items=members, key=marker.item), "blocked"  # fmt: skip
    if pr.checks == "green" and pr.mergeable == "MERGEABLE":
        return Action("archive", first, f"PR #{pr.number} ({pr.head_ref}) for "
                      f"{', '.join(members)} at {marker.head[:12]}", pr=pr.number,
                      head=marker.head, items=members, draft=pr.draft,
                      key=marker.item), "closing"  # fmt: skip
    return None, "closing"


def attributed(pr: LivePr, batch: Batch, event: CloseoutEvent) -> bool:
    """Whether archive PR *pr* belongs to *batch*'s close-out (§B step 3).

    Its head alone attributes it only when the head is `chore/closeout-<batch branch
    with / as ->`, a name no other batch can produce. Any other `chore/archive-*` or
    `chore/closeout-*` head (`chore/archive-<plan>`, `chore/closeout-<run-id>`) must
    also change the batch's run file or its plan journal (review rg-12). Neither
    attributes a PR that is not `trusted`: a fork or a foreign author can choose
    both the head name and the files (gh#936). A trusted PR on the event's own collected
    `archive` head (`chore/closeout-<date>-<n>`, a name only that close-out produces) is
    the batch's: its one PR names every member, a batch with no run included (§D)."""
    if not pr.trusted:
        return False
    if collected_name(event.archive or "") is not None and pr.head_ref == event.archive:
        return True  # a collected close-out's shared head names every member (§D)
    branch = recorded_branch(batch)
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


def default_selection(batches: Iterable[Batch]) -> frozenset[str]:
    """The batch ids a drive acts on when none is named: every batch with a wave, else
    all. The one rule `fr triage batch drive` and the board's hints both read."""
    every = list(batches)
    waved = [b for b in every if b.wave is not None]
    return frozenset(b.id for b in (waved or every))


def closeout_event(batch: Batch) -> CloseoutEvent | None:
    """The batch's close-out event, if it has one."""
    for e in reversed(batch.events):
        if isinstance(e, CloseoutEvent):
            return e
    return None


def finished_waves(batches: Iterable[Batch], stages: Mapping[str, str]) -> frozenset[str]:
    """The wave keys (`str(batch.wave)`) whose every batch is terminal: derived stage
    `cancelled` or `abandoned`, or a close-out event whose `archived` is set. *stages* maps
    batch id to its derived stage. A batch with no wave never makes one, and a wave with a
    batch that is not terminal (a merged one still owed its archive, say) is not finished.
    The board, the history page and the driver all read this one predicate."""
    wave_ok: dict[str, bool] = {}
    for b in batches:
        if b.wave is None:
            continue
        event = closeout_event(b)
        terminal = stages.get(b.id) in {"cancelled", "abandoned"} or (
            event is not None and event.archived is not None
        )
        key = str(b.wave)
        wave_ok[key] = wave_ok.get(key, True) and terminal
    return frozenset(k for k, ok in wave_ok.items() if ok)


def export_branch(wave: str, scope: str) -> str:
    """The head a wave's state-export PR is pushed to; the driver of scope id *scope*
    owns it. The scope id keeps two scopes of one repo (another host's driver) off each
    other's export PRs (gh#1101)."""
    return f"{EXPORT_PREFIX}{scope}-wave-{wave}"


def _wave_order(wave: str) -> tuple[int, int | str]:
    return (0, int(wave)) if wave.lstrip("-").isdigit() else (1, wave)


ExportCount = Literal["closing", "blocked"] | None


def _outside(root: str, files: Sequence[str]) -> str:
    """Why *files* do not all lie under the export directory *root*, or "". An unknown
    file list is never "all inside": an export PR always changes something."""
    if not files:
        return "its changed files are unknown"
    prefix = root.rstrip("/") + "/"
    stray = [f for f in files if not f.startswith(prefix)]
    return f"it changes {', '.join(stray[:3])}, outside {prefix}" if stray else ""


@dataclass(frozen=True)
class ExportTarget:
    """What step 3b decides about for one repo (§I, R13): the repo's newest unmerged
    export PR and the waves recorded with it, or, with none, every finished wave of the
    repo that has no export entry at all. `wave`, the highest, names the branch."""

    repo: str
    wave: str
    covers: tuple[str, ...]
    recorded: Export | None  # the newest unmerged entry with a PR; None: not exported
    orphan: LivePr | None = None  # unrecorded: the open PR to reuse, on wave `wave`'s head


def export_wave_of(head_ref: str, scope: str) -> str | None:
    """The wave key a `chore/triage-state-<scope>-wave-<N>` head of scope id *scope*
    names, or None: another scope's export head is never this scope's."""
    prefix = f"{EXPORT_PREFIX}{scope}-wave-"
    wave = head_ref.removeprefix(prefix) if head_ref.startswith(prefix) else ""
    return wave if wave.isdigit() else None


def export_target(
    repo: str,
    batches: Iterable[Batch],
    repos: Mapping[str, str],
    finished: frozenset[str],
    exports: Iterable[Export],
    orphans: Sequence[LivePr] = (),
    *,
    scope: str,
) -> ExportTarget | None:
    """One export PR per repo covers every unexported finished wave. While one is
    unmerged, it is the target and a wave that finished since waits for a later pass,
    so no second PR is opened. With none recorded, an unrecorded open PR on any wave's
    export head (*orphans*, highest wave first) is reused: the export pushes onto its
    branch and covers every owed wave (p4-r3, p4-r13). None: nothing is owed."""
    mine = [e for e in exports if e.repo == repo and not e.closed]  # closed: owed again
    unmerged = [e for e in mine if e.pr is not None and not e.merged]
    if unmerged:
        newest = unmerged[-1]
        covers = sorted({e.wave for e in unmerged if e.pr == newest.pr}, key=_wave_order)
        return ExportTarget(repo, covers[-1], tuple(covers), newest)
    entered = {e.wave for e in mine}
    waves = {str(b.wave) for b in batches if b.wave is not None and repos.get(b.id) == repo}
    owed = sorted((waves & finished) - entered, key=_wave_order)
    if not owed:
        return None
    named = [(w, o) for o in orphans if (w := export_wave_of(o.head_ref, scope)) is not None]
    if named:
        wave, orphan = max(named, key=lambda pair: _wave_order(pair[0]))
        return ExportTarget(repo, wave, tuple(owed), None, orphan)
    return ExportTarget(repo, owed[-1], tuple(owed), None)


def _wrong_base(live: LivePr, default: str) -> str:
    """Why *live* is not based on the default branch, or "" (p4-r15). An unknown base
    is never the default."""
    if default and live.base == default:
        return ""
    return f"is based on {live.base or 'an unknown branch'}, not {default or 'the default branch'}"


def _export_row(
    repo: str,
    wave: str,
    done: Export | None,
    live: LivePr | None,
    root: str,
    default: str = "",
    *,
    scope: str,
) -> tuple[Action | None, ExportCount]:
    """One row of §I's table: the action for *repo*'s finished *wave*, given its
    recorded export (*done*), the live PR and the export directory *root*
    (`<path>/<scope>`), and how the summary counts it. The driver auto-merges this
    PR unreviewed, so it adopts or merges one only when every file it changes is under
    *root*, and merges only at the head it recorded (p4-sec-unpinned-merge)."""
    head = export_branch(wave, scope)
    if done is not None and (done.merged or done.pr is None):
        return None, None  # merged, or the export changed nothing
    if done is None:
        if live is None or live.state != "OPEN":
            return Action("export", repo, f"to {root} on {head}", wave=wave), "closing"
        why = "" if live.trusted else "is not trusted (not from this repo by an allowed author)"
        why = why or _wrong_base(live, default)
        if why:
            return Action("warn", repo, f"PR #{live.number} on {head} {why}; it is never "
                          "reused or merged", pr=live.number, wave=wave), "blocked"  # fmt: skip
        # Reused, never adopted (p4-r12): the export pushes the driver's own commit onto
        # this PR's branch, and the merge pins to that commit. Nothing of the PR's is kept.
        reuse = f"to {root} on {head}, reusing open PR #{live.number}"
        return Action("export", repo, reuse, pr=live.number, wave=wave), "closing"
    if live is None:
        return None, "closing"  # not read this pass: still owed
    if live.state == "MERGED":  # merged by hand, or a pass died before recording (p4-r1)
        merged = f"export PR #{live.number} was merged outside the driver; recording it"
        return Action("export-reconcile", repo, merged, pr=live.number, wave=wave), "closing"
    if live.state != "OPEN":  # closed unmerged: recorded once, its waves owed again (p4-r6)
        return Action("export-closed", repo, f"export PR #{live.number} was closed without "
                      "a merge; its waves are owed again and re-exported next pass",
                      pr=live.number, wave=wave), "closing"  # fmt: skip
    why = ""
    if not live.trusted:
        why = "is not trusted (not from this repo by an allowed author)"
    elif live.head != done.head or not done.head:
        why = (f"head is {live.head[:12] or 'unknown'}, not the recorded "
               f"{(done.head or 'none')[:12]}: a commit the driver did not push")  # fmt: skip
    elif outside := _outside(root, live.files):
        why = outside
    elif wrong := _wrong_base(live, default):
        why = wrong
    elif live.mergeable == CONFLICTING:
        # No session owns it: straight to the operator, with a recorded stop (R12).
        return Action("export-conflict", repo, f"export PR #{live.number} conflicts with "
                      "the default branch; the operator must act", pr=live.number,
                      head=live.head, wave=wave), "blocked"  # fmt: skip
    elif live.draft:
        why = "is a draft"
    elif live.checks == "failing":
        why = f"has failing checks: {', '.join(live.failing) or 'unknown'}"
    if why:
        return Action("warn", repo, f"export PR #{live.number} {why}; the operator must act",
                      pr=live.number, wave=wave), "blocked"  # fmt: skip
    if live.checks != "green":
        return None, "closing"  # checks pending: wait
    pinned = done.head or ""  # set: a head that differs was refused above
    # Pinned to the RECORDED head, never the live one (they are equal here).
    return Action("export-merge", repo, f"PR #{live.number} at {pinned[:12]}",
                  pr=live.number, head=pinned, wave=wave), "closing"  # fmt: skip


def _export_actions(snap: Snapshot) -> tuple[list[Action], int, int]:
    """§I step 3b: a group or org scope that opts in is warned once; then, for each
    opted-in repo, `_export_row` on its `export_target`: one PR per repo, never one per
    wave. Returns the actions and how many owed export PRs are closing (acting or
    waiting) and blocked (warned)."""
    actions = [
        Action("warn", repo, f"export is per repo scope; run drive with --repo {repo}")
        for repo in sorted(snap.export_refused)
    ]
    counts = {"closing": 0, "blocked": 0}
    for repo in sorted(snap.export_path):
        target = export_target(
            repo, snap.batches, snap.repos, snap.finished, snap.exports,
            snap.export_orphans.get(repo, ()), scope=snap.scope_id,
        )  # fmt: skip
        if target is None:
            continue
        live = (
            target.orphan if target.recorded is None else snap.export_prs.get((repo, target.wave))
        )
        action, count = _export_row(
            repo, target.wave, target.recorded, live, snap.export_path[repo],
            snap.default_branch.get(repo, ""), scope=snap.scope_id,
        )  # fmt: skip
        if action is not None:
            if action.kind == "export":
                action = replace(action, covers=target.covers)
                if len(target.covers) > 1:
                    action = replace(action, detail=f"{action.detail} (covers waves "
                                     f"{', '.join(target.covers)})")  # fmt: skip
            actions.append(action)
        if count is not None:
            counts[count] += 1
        if action is not None and action.kind == "export" and target.orphan is not None:
            actions.extend(_stale_orphans(repo, snap, target.orphan))
    return actions, counts["closing"], counts["blocked"]


def _stale_orphans(repo: str, snap: Snapshot, reused: LivePr) -> list[Action]:
    """p4-r16: every other unrecorded export PR, named once per drive as stale. They
    block nothing: the reused PR carries the state."""
    out = []
    for o in sorted(snap.export_orphans.get(repo, ()), key=lambda o: o.number):
        key = f"stale-export\0{repo}\0{o.number}"
        if o.number == reused.number or key in snap.warned:
            continue
        out.append(Action("warn", repo, f"export PR #{o.number} on {o.head_ref} is stale: "
                          f"PR #{reused.number} carries the export; it is safe to close",
                          pr=o.number, head=key))  # fmt: skip
    return out


def is_finished(batch: Batch, stage: BatchStage, archives: Sequence[LivePr]) -> bool:
    """Whether *batch* is finished: landed, with a close-out event whose `archived`
    is set (the driver merged its archive PR), or an attributed archive PR in
    `archives` that is MERGED. One reading for the archive step and the close step."""
    event = closeout_event(batch)
    if event is None or stage not in LANDED:
        return False
    if event.archived is not None:
        return True
    return any(p.state == "MERGED" and attributed(p, batch, event) for p in archives)


def unfinished_waves(snap: Snapshot) -> frozenset[str]:
    """The wave keys (`str(batch.wave)`) of the state file that `snap.finished` does not
    hold: what the next pass compares against (triage-dedupe R10). `finished` is
    `finished_waves`, the one predicate the board, the history page and the driver read."""
    return frozenset(str(b.wave) for b in snap.batches if b.wave is not None) - snap.finished


# ------------------------------------------------------------------ the pass


def _dispatch_key(batch: Batch) -> tuple[int, int, int, int, str]:
    """Wave, then merge order (an explicit `order`), then id; unset sorts last."""
    wave, order = batch.wave, batch.order
    return (wave is None, wave or 0, order is None, order or 0, batch.id)


def _queue_hold(repo: str, snap: Snapshot) -> str | None:
    """Why a merge-queue repo is held, or None (§D "Holds")."""
    if repo in snap.queue_unknown:
        return f"cannot tell {repo}'s default branch: queue mode unknown"
    if repo in snap.queue_versioned:
        return f"{repo} requires a merge queue, and fr does not reserve versions through one"
    if snap.queue_rest:
        return f"{repo} requires a merge queue, and forge.api rest cannot enqueue"
    return None


def last_enqueue(batch: Batch, pr: int) -> EnqueueEvent | None:
    """The batch's latest `enqueue` event for PR *pr*, whatever it records."""
    for event in reversed(batch.events):
        if isinstance(event, EnqueueEvent) and event.pr == pr:
            return event
    return None


REFUSALS_BEFORE_NEED = 2
"""Enqueue refusals at one head before the driver stops retrying and asks the operator."""


def enqueue_refusals(batch: Batch, pr: int, head: str) -> list[EnqueueEvent]:
    return [
        e for e in batch.events
        if isinstance(e, EnqueueEvent) and e.pr == pr and e.head == head and e.outcome == "refused"
    ]  # fmt: skip


def _walk_queue(
    repo: str, entries: Sequence[QueueEntry], snap: Snapshot
) -> tuple[Train | None, list[Action]]:
    """§D "Queue mode": the walk of a repo whose base requires a merge queue. It picks no
    head: every approved, green member not already queued is enqueued, a queued one is in
    the merge queue, an ejected one (its last event an `enqueued` one at the current head,
    open, out of the queue with auto-merge cleared) is enqueued again when the base moved,
    a recorded need when it did not, and red when its checks failed. A held repo (*hold*)
    enqueues nothing but still reports its red members. `--max-inflight` is untouched: a
    queued batch is still `pr-open`. `_walk_train` branches here at its entry, so the merge
    train's loop is untouched."""
    actions: list[Action] = []
    enqueue: list[str] = []
    queued: list[str] = []
    in_queue: list[str] = []
    stepped: list[str] = []
    awaiting: list[str] = []
    numbers: dict[str, int] = {}
    hold = _queue_hold(repo, snap)
    members: list[QueueEntry] = []
    for entry in entries:
        pr = snap.live.get(entry.batch.id)
        verdict = snap.approvals.get(entry.batch.id)
        approved = verdict is not None and is_approved(verdict)
        if pr is None or pr.state != "OPEN" or (pr.draft and not approved):
            continue  # not a member
        members.append(entry)
        numbers[entry.batch.id] = pr.number
    if not members:
        return None, actions
    if hold is not None:
        actions.append(Action("held", members[0].batch.id, hold))
    for entry in members:
        bid = entry.batch.id
        pr = snap.live[bid]
        verdict = snap.approvals.get(bid)
        approved = verdict is not None and is_approved(verdict)
        state = snap.queue_states.get(bid)
        event = last_enqueue(entry.batch, pr.number)
        at_head = event is not None and event.head == pr.head
        mine = at_head and event is not None and event.outcome == "enqueued"
        if mine and state is not None and (state.in_queue or state.auto_merge):
            in_queue.append(bid)  # in the queue, or waiting to enter it: never ejected
            continue
        if state is not None and not state.open:
            continue  # merged or closed since it was read: it never left a queue unmerged
        if pr.checks == "failing":
            stepped.append(bid)
            actions.append(
                Action("warn", bid, f"PR #{pr.number} CI failing at {pr.head[:12]}: "
                       f"{', '.join(pr.failing)}", pr=pr.number, head=pr.head, red=True,
                       checks=pr.failing)
            )  # fmt: skip
            continue
        if not approved:
            awaiting.append(bid)
            continue
        if hold is not None:
            queued.append(bid)
            continue
        if mine and state is None:
            in_queue.append(bid)  # the state was not read: nothing to decide from
            continue
        if pr.head != entry.pr.head_oid or pr.checks == "pending":
            queued.append(bid)
            continue
        base_moved = event is not None and snap.bases.get(repo, event.base) != event.base
        why = f"at {pr.head[:12]}"
        if mine or (at_head and event is not None and event.outcome == "ejected"):
            if not base_moved:
                if mine:  # the driver records it once; the recorded event is the need
                    actions.append(
                        Action("warn", bid, f"PR #{pr.number} left the merge queue unmerged",
                               pr=pr.number, head=pr.head, ejected=True)
                    )  # fmt: skip
                continue
            why = "the base moved since it was enqueued"
        elif len(enqueue_refusals(entry.batch, pr.number, pr.head)) >= REFUSALS_BEFORE_NEED:
            continue  # refused twice at this head: a recorded need, no third try
        enqueue.append(bid)
        actions.append(
            Action("enqueue", bid, f"PR #{pr.number} {why}", pr=pr.number, head=pr.head,
                   train=repo)
        )  # fmt: skip
    train = Train(repo, None, (), tuple(queued), tuple(stepped), numbers, tuple(awaiting),
                  tuple(enqueue), tuple(in_queue), True)  # fmt: skip
    return train, actions


def _walk_train(
    repo: str, entries: Sequence[QueueEntry], snap: Snapshot
) -> tuple[Train | None, list[Action]]:
    if repo in snap.queue_repos:
        return _walk_queue(repo, entries, snap)
    return _walk_merge_train(repo, entries, snap)


def _walk_merge_train(
    repo: str, entries: Sequence[QueueEntry], snap: Snapshot
) -> tuple[Train | None, list[Action]]:
    """§A: walk one repo's *entries* (already in train order). A green member becomes
    a merge candidate and the walk goes on; a failing one is stepped over, wherever it
    sits; one without a valid approval awaits it, wherever it sits; a moved head or a
    pending one stops it, and every other member after the stop is queued. A draft is
    a member only with a valid approval (merge-train-safety §A)."""
    merges: list[Action] = []
    candidates: list[str] = []
    stepped: list[str] = []
    awaiting: list[str] = []
    numbers: dict[str, int] = {}
    waiting: str | None = None
    queued: list[str] = []
    in_queue: list[str] = []
    members = 0
    for entry in entries:
        bid = entry.batch.id
        pr = snap.live.get(bid)
        verdict = snap.approvals.get(bid)
        approved = verdict is not None and is_approved(verdict)
        if pr is None or pr.state != "OPEN" or (pr.draft and not approved):
            continue  # not a member
        members += 1
        numbers[bid] = pr.number
        if snap.queue_inferred:  # facts only: what the events say fr did (§D, R13)
            seen = last_enqueue(entry.batch, pr.number)
            if seen is not None and seen.head == pr.head and seen.outcome == "enqueued":
                in_queue.append(bid)
                continue
        if pr.checks == "failing":  # wherever it sits: reported now, not when it leads
            stepped.append(bid)
            # Said on every pass: the command's recovery (§C) decides whether this pass
            # has anything new to report, from the recorded events, not from memory.
            merges.append(
                Action("warn", bid, f"PR #{pr.number} CI failing at {pr.head[:12]}: "
                       f"{', '.join(pr.failing)}", pr=pr.number, head=pr.head, red=True,
                       checks=pr.failing)
            )  # fmt: skip
            continue
        if not approved:  # never the head, never a stop
            awaiting.append(bid)
            continue
        if waiting is not None or queued:
            queued.append(bid)
            continue
        if pr.head != entry.pr.head_oid or pr.checks == "pending":
            if candidates:
                queued.append(bid)
            else:
                waiting = bid
            continue
        candidates.append(bid)
        merges.append(
            Action("merge", bid, f"PR #{pr.number} at {pr.head[:12]}", pr=pr.number,
                   head=pr.head, train=repo)
        )  # fmt: skip
    if not members:
        return None, merges
    head = candidates[0] if candidates else waiting
    train = Train(
        repo, head, tuple(candidates), tuple(queued), tuple(stepped), numbers, tuple(awaiting),
        in_merge_queue=tuple(in_queue),
    )  # fmt: skip
    return train, merges


def _claim_actions(snap: Snapshot) -> list[Action]:
    """The claim writes of a pass, ahead of every other action (§3.F): claims, then
    refreshes, then releases, then the settles of closed issues. A batch outside the
    selection is left alone; one the snapshot does not know (a dropped member's old
    batch) is still released."""
    known = {b.id for b in snap.batches}

    def mine(bid: str) -> bool:
        return snap.selected is None or bid in snap.selected or bid not in known

    out: list[Action] = []
    for kind, owed, why in (
        ("claim", snap.claims_owed, "owed"),
        ("refresh", snap.refresh_owed, "heartbeat due"),
        ("release", snap.releases_owed, "no longer owed"),
        ("settle", snap.settles_owed, "closed"),
    ):
        out.extend(
            Action(kind, bid, why, key=key)  # type: ignore[arg-type]
            for key, bid in owed
            if mine(bid)
        )
    return out


def _gate_actions(batch: Batch, snap: Snapshot, labelled: set[str]) -> list[Action]:
    """R13, R14 for one gated batch: `fr:awaiting-live` on each open issue its held gates'
    rows cite that lacks it (once per issue per pass), then a `gate-pass` for each held
    gate whose rows ALL read walked. A gate with no row (a run-level gate) passes only
    explicitly, through `fr gate pass`; rows never read plan nothing."""
    ledger = snap.ledgers[batch.id]
    if ledger.rows is None:
        return []
    out: list[Action] = []
    held = held_gates(ledger.labels)
    rows = [r for r in ledger.rows if r.gate in held]
    for ref in sorted({i for r in rows for i in r.issues}):
        if ref in snap.awaiting_unlabelled and ref not in labelled:
            labelled.add(ref)
            out.append(Action("awaiting-live", batch.id, f"label {ref} fr:awaiting-live",
                              pr=ledger.pr, key=ref))  # fmt: skip
    for gate in sorted(held):
        if gate == ledger.run_gate and not ledger.run_gate_inherited:
            continue  # p4-r3: no row stands for the run gate, so no walk passes it
        if gate == "devops" and ledger.ops_promoted:
            continue  # fr-ops R13: the ops' evidence passes it, through `fr gate pass`
        mine = [r for r in rows if r.gate == gate]
        if mine and all(r.walked for r in mine):
            ids = ", ".join(r.id for r in mine)
            why = f"every row the {gate} gate gates reads walked ({ids})"
            out.append(
                Action("gate-pass", batch.id, f"PR #{ledger.pr}: {why}", pr=ledger.pr, gate=gate)
            )
    return out


def drive_pass(snap: Snapshot) -> Pass:
    """One pass: report foreign PRs, merge, close out, archive, dispatch, close sessions,
    then report duplicate candidates of newly finished waves — in that order, so a slot a
    merge frees is used in the same pass."""
    actions: list[Action] = _claim_actions(snap)
    stages = dict(snap.stages)
    merging: set[str] = set()
    chosen = tuple(b for b in snap.batches if snap.selected is None or b.id in snap.selected)

    # -1. A batch with a member another scope holds is left alone this pass (R6): one
    # `held` action, and no merge, update, close-out, archive or dispatch below.
    held_ids: set[str] = set()
    held_by: list[tuple[str, tuple[str, ...]]] = []
    for batch in snap.batches:
        members = held_members(batch.ids, snap.held)
        if not members:
            continue
        held_ids.add(batch.id)
        if batch in chosen and stages.get(batch.id) not in ("cancelled", "abandoned"):
            held_by.append((batch.id, tuple(sorted({c.signer for _, c in members}))))
            detail = "; ".join(held_line(k, c, snap.now) for k, c in members)
            actions.append(Action("held", batch.id, detail))

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

    # 1. Merge: one train per repo, walked in the stable dispatch order.
    by_repo: dict[str, list[QueueEntry]] = {}
    for entry in sorted(snap.queue, key=lambda e: _dispatch_key(e.batch)):
        bid = entry.batch.id
        if (snap.selected is not None and bid not in snap.selected) or bid in held_ids:
            continue
        by_repo.setdefault(snap.repos.get(bid, ""), []).append(entry)
    trains: list[Train] = []
    for repo in sorted(by_repo):
        train, merges = _walk_train(repo, by_repo[repo], snap)
        actions.extend(merges)
        merging.update(a.batch for a in merges if a.kind == "merge")
        if train is not None:
            trains.append(train)

    # 2. Close out. Recording a close-out that has already finished starts nothing and
    # writes nothing to the forge, so it reads every landed batch, selected or not
    # (gh#990); starting one, or recording one under way, follows the selection.
    closing = gated = closeouts_held = 0
    collecting: dict[str, list[str]] = {}  # repo -> the batches its collected close-out takes
    labelled: set[str] = set()  # issues an awaiting-live action already names this pass
    for batch in snap.batches:
        if stages.get(batch.id) not in LANDED or batch.id in merging or batch.id in held_ids:
            continue
        if closeout_of(batch, snap.closeouts) is not None:
            continue
        driven_now = snap.selected is None or batch.id in snap.selected
        if batch.id in snap.unverified:
            closing += driven_now
            continue
        # A close-out the driver did not start is recorded once, as an event: every
        # later pass, the board and `batch list` read it (gh#899, gh#900, gh#912).
        if batch.id in snap.archived:
            actions.append(Action("adopt", batch.id, "archived on the default branch already",
                                  archived=ARCHIVED_BY_UNKNOWN_PR))  # fmt: skip
            continue
        hand = snap.adopted.get(batch.id)
        if hand is not None and hand.state == "MERGED":
            actions.append(Action("adopt", batch.id, f"close-out PR #{hand.number} merged",
                                  pr=hand.number, archived=hand.number))  # fmt: skip
            continue
        if not driven_now:
            continue
        due = closeout_due(
            released=batch.id in snap.released,
            merged_at=snap.merged_at.get(batch.id),
            now=snap.now,
        )
        owed = not any(e.kind == "post_merge" for e in batch.events)
        item = closeout_item_id(snap.repos.get(batch.id, ""), batch.id)
        if (
            due
            and hand is None
            and owed
            and item not in snap.existing  # a live close-out tab ran it before it started
            and snap.repos.get(batch.id) in snap.post_merge_repos
        ):
            # p4-r2: at merge (once its release commit landed, or the fallback), gated or
            # not, and always ahead of the batch's close-out, which never runs it itself.
            actions.append(Action("post-merge", batch.id, "run the repo's post_merge"))
        if batch.id in snap.ledger_unknown:  # p4-r1: unknown is not ungated
            closing += 1
            actions.append(Action("ledger-unread", batch.id, "its merged PR's labels were not "
                                  "read, so whether a gate holds it is unknown; no close-out "
                                  "until they are"))  # fmt: skip
            continue
        if is_gated(batch, snap):  # R13: held by a post-merge gate, never closed out
            gated += 1
            actions.extend(_gate_actions(batch, snap, labelled))
            continue
        closing += 1
        if hand is not None:
            actions.append(Action("adopt", batch.id,
                                  f"close-out PR #{hand.number} ({hand.head_ref}) is open",
                                  pr=hand.number))  # fmt: skip
            continue
        if not due:
            continue
        if item in snap.existing:  # a per-batch close-out started before R15: recorded
            actions.append(Action("closeout", batch.id, f"record the live {item}", recorded=True))
            continue
        if (hold := closeout_hold(batch)) is not None:  # R15: held by the verb; the operator's
            closing -= 1
            closeouts_held += 1
            actions.append(Action("closeout-held", batch.id, f"{hold.reason}; fix it, then "
                                  f"retry: fr triage batch closeout {batch.id} --yes",
                                  key=hold.item))  # fmt: skip
            continue
        collecting.setdefault(snap.repos.get(batch.id, ""), []).append(batch.id)
    # R15: at most one collected close-out per repo, and none while one is under way.
    for repo in sorted(collecting):
        name, item_id = next_collected_item(repo, snap)
        if _collected_under_way(repo, snap) or item_id in snap.existing:
            continue  # one at a time; a live session of this item is not started twice
        taking = tuple(collecting[repo])
        actions.append(
            Action("closeout", taking[0], f"start {collected_item_id(repo, name)} for "
                   f"{', '.join(taking)}", items=taking, key=name)
        )  # fmt: skip

    # 3. Archive.
    archives_blocked = 0
    for marker in snap.closeouts:  # R15: one step per collected close-out, never per member
        reopened = snap.collected_reopened.get(marker.item)
        if marker.closed and reopened is not None:  # p6b-r10: never merged by the driver
            key = f"reopened\0{marker.item}\0{reopened.number}"
            if key not in snap.warned:
                said = (f"close-out PR #{reopened.number} was closed and reopened: the driver "
                        "never merges it; it needs approved-fr like any PR")  # fmt: skip
                actions.append(Action("closeout-reopened", (marker.planned or [""])[0], said,
                                      pr=reopened.number, key=marker.item, head=key))  # fmt: skip
            continue
        if marker.merged or marker.closed:
            continue
        step, count = _collected_step(marker, snap)
        if step is not None:
            actions.append(step)
        if count == "blocked":
            archives_blocked += 1
        elif count == "closing":
            closing += 1
    for batch in chosen:
        event = closeout_event(batch)
        if event is None or stages.get(batch.id) not in LANDED or batch.id in held_ids:
            continue
        if collected_name(event.archive or "") is not None:
            continue  # its collected close-out's marker plans for it, above
        archives = snap.archives.get(snap.repos.get(batch.id, ""), ())
        mine = [p for p in archives if attributed(p, batch, event)]
        if is_finished(batch, stages[batch.id], archives):
            landed = next((p for p in mine if p.state == "MERGED"), None)
            if event.archived is None and landed is not None:
                # Merged, but not by this driver: recorded once, so `batch list` and
                # every later pass read it from the event (gh#882).
                actions.append(Action("adopt", batch.id, f"archive PR #{landed.number} merged",
                                      pr=landed.number, archived=landed.number))  # fmt: skip
            continue
        if not mine and batch.id in snap.closeout_probed:
            stale = _stale_closeout(batch, event, snap)
            if stale is not None:
                actions.append(stale)
        # A draft is ready too (merge-truth R11): the archive marks it ready, then merges.
        # One the forge reports conflicting is never merged: it is handed back (R12).
        open_ = [p for p in mine if p.state == "OPEN"]
        conflicting = [p for p in open_ if p.mergeable == CONFLICTING]
        ready = [p for p in open_ if p.checks == "green" and p not in conflicting]
        default = snap.default_branch.get(snap.repos.get(batch.id, ""), "")
        good = next((p for p in ready if default and not _wrong_base(p, default)), None)
        if good is None and ready and default:
            # Merged only into the default branch, as the export (gh#1004, p4-r15): only
            # the operator can retarget it, so the batch is blocked, and named every pass
            # as a blocked dispatch is. An unknown default proves nothing: it waits.
            archives_blocked += 1
            wrong = ready[0]
            actions.append(
                Action("blocked", batch.id, f"archive PR #{wrong.number} ({wrong.head_ref}) "
                       f"{_wrong_base(wrong, default)}; it is never merged", pr=wrong.number)
            )  # fmt: skip
            continue
        spent = [p for p in conflicting if _held_archive_conflict(batch, p.head)]
        if good is None and spent:
            # Its hand-backs are spent (R12): only the operator can resolve it, so the
            # batch is blocked, and named every pass as a blocked dispatch is.
            archives_blocked += 1
            p = spent[0]
            actions.append(
                Action("blocked", batch.id, f"{ARCHIVE_WAIT} #{p.number} ({p.head_ref}) "
                       "conflicts and its hand-backs are spent; resolve it", pr=p.number)
            )  # fmt: skip
            continue
        closing += 1
        if good is not None:
            actions.append(
                Action("archive", batch.id, f"PR #{good.number} ({good.head_ref})",
                       pr=good.number, head=good.head, draft=good.draft)
            )  # fmt: skip
        for p in conflicting:
            actions.append(
                Action("archive-conflict", batch.id, f"{ARCHIVE_WAIT} #{p.number} "
                       f"({p.head_ref}) conflicts with the default branch", pr=p.number,
                       head=p.head, branch=p.head_ref)
            )  # fmt: skip
        # merge-truth R9: every other attributed open one is named with what it waits on,
        # every pass (no head, so never deduplicated). A status line, never a Need.
        for p in open_:
            if p not in conflicting and p.checks != "green":
                actions.append(
                    Action("warn", batch.id, f"{ARCHIVE_WAIT} #{p.number}: checks {p.checks}",
                           pr=p.number)
                )  # fmt: skip

    # 3a. Report idle sessions (driver-sessions R7). A warn never moves the summary.
    actions.extend(_idle_actions(snap, chosen))

    # 3b. Export each finished wave's state (pages-goal R13).
    exporting, exports_closing, exports_blocked = _export_actions(snap)
    actions.extend(exporting)
    closing += exports_closing

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
    pending, blocked = 0, exports_blocked + archives_blocked + closeouts_held
    for batch in sorted(chosen, key=_dispatch_key):
        if stages.get(batch.id) != "proposed" or batch.id in held_ids:
            continue
        if batch.id in snap.awaiting:
            # No work, so not pending either: it never keeps a drive alive.
            actions.append(Action("held", batch.id, AWAITING_LIVE_HOLD))
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
        if batch.id in snap.refused:
            pending += 1
            actions.append(Action("held", batch.id, snap.refused[batch.id]))
            continue
        if len(occupants) >= snap.max_inflight:
            # The summary counts only the selection, so a cap held by batches
            # outside it would otherwise read as idle (gh#913).
            pending += 1
            actions.append(Action("held", batch.id, f"the in-flight cap ({snap.max_inflight}) "
                                  f"is full: {', '.join(sorted(occupants))}"))  # fmt: skip
            continue
        if snap.dispatch_held is not None:
            pending += 1
            actions.append(Action("held", batch.id, snap.dispatch_held))
            continue
        occupants.add(batch.id)
        in_flight += 1
        actions.append(
            Action("dispatch", batch.id, f"wave {batch.wave if batch.wave is not None else '-'}")
        )

    # 5. Close the sessions of finished batches. Never work remaining (R10): the
    # summary does not see it.
    if snap.close_sessions:
        for batch in chosen:
            repo = snap.repos.get(batch.id, "")
            if not is_finished(
                batch, stages.get(batch.id, "proposed"), snap.archives.get(repo, ())
            ):
                continue
            live = tuple(
                i for i in (batch_item_id(repo, batch.id), closeout_item_id(repo, batch.id))
                if i in snap.sessions
            )  # fmt: skip
            if live:
                actions.append(Action("close", batch.id, f"sessions {', '.join(live)}", items=live))

    # 6. Report duplicate candidates once per wave observed going unfinished -> finished
    # (R10). Never inferred from a planned action: an archive merge may still fail.
    if snap.duplicate_groups > 0:
        n = snap.duplicate_groups
        groups = f"{n} duplicate candidate {'group' if n == 1 else 'groups'}"
        for wave in sorted(snap.finished & (snap.unfinished_waves or frozenset()), key=int):
            actions.append(
                Action("dedupe", "", f"{groups} after wave {wave} finished; run "
                       f"`{snap.dedupe_command}` to judge them")
            )  # fmt: skip

    merged = sum(1 for b in driven if stages.get(b) in LANDED)
    closing += len(merging)
    return Pass(
        actions=tuple(actions),
        summary=Summary(
            in_flight=in_flight,
            merged=merged,
            pending=pending,
            closing=closing,
            blocked=blocked,
            queued=sum(len(t.queued) for t in trains),
            held=len(held_by),
            gated=gated,
        ),
        trains=tuple(trains),
        held_by=tuple(held_by),
    )


# --------------------------------------------------------------- lines (R13)


def action_line(action: Action, outcome: str | None = None) -> str:
    """The one line an action prints, in plan mode (*outcome* None) and when acted:
    the same words in `--once` and loop mode."""
    if action.kind == "dedupe":  # names no batch
        return f"dedupe: {outcome or action.detail}"
    if action.kind in ("claim", "refresh", "release", "settle"):
        where = f" ({action.batch})" if action.batch else ""
        return f"{action.kind} {action.key}{where}: {outcome or action.detail}"
    if action.wave is not None:
        return f"{action.kind} wave {action.wave} {action.batch}: {outcome or action.detail}"
    return f"{action.kind} {action.batch}: {outcome or action.detail}"


def summary_line(summary: Summary) -> str:
    line = (
        f"in flight {summary.in_flight}, merged {summary.merged}, "
        f"pending {summary.pending}, closing {summary.closing}"
    )
    if summary.queued:
        line += f", queued {summary.queued}"
    if summary.blocked:
        line += f", blocked {summary.blocked}"
    line += f", held {summary.held}" if summary.held else ""
    return line + (f", gated {summary.gated}" if summary.gated else "")


def train_line(train: Train) -> str:
    """R6: `train <repo>: head a (PR #12) · then b (#13) · queued c (#14) · stepped over d`."""

    def ref(bid: str) -> str:
        return f"{bid} (#{train.numbers[bid]})" if bid in train.numbers else bid

    if train.queue_mode:
        parts = ["merge queue"]
        if train.enqueue:
            parts.append("enqueue " + ", ".join(ref(b) for b in train.enqueue))
        if train.in_merge_queue:
            parts.append("in merge queue " + ", ".join(ref(b) for b in train.in_merge_queue))
        if train.queued:
            parts.append("queued " + ", ".join(ref(b) for b in train.queued))
        if train.stepped:
            parts.append("stepped over " + ", ".join(ref(b) for b in train.stepped))
        if train.awaiting:
            parts.append("awaiting approval " + ", ".join(ref(b) for b in train.awaiting))
        return f"train {train.repo}: " + " · ".join(parts)
    head = train.head
    parts = []
    if head is None:
        parts.append("no head")
    else:
        parts.append(f"head {head} (PR #{train.numbers[head]})" if head in train.numbers
                     else f"head {head}")  # fmt: skip
    then = train.candidates[1:]
    if then:
        parts.append("then " + ", ".join(ref(b) for b in then))
    if train.queued:
        parts.append("queued " + ", ".join(ref(b) for b in train.queued))
    if train.stepped:
        parts.append("stepped over " + ", ".join(ref(b) for b in train.stepped))
    if train.awaiting:
        parts.append("awaiting approval " + ", ".join(ref(b) for b in train.awaiting))
    if train.in_merge_queue:
        parts.append("in merge queue " + ", ".join(ref(b) for b in train.in_merge_queue))
    return f"train {train.repo}: " + " · ".join(parts)
