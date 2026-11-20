"""The wave merge queue's planner, as a pure function (spec 2026-11-19-wave-merge-queue §A,
§B, §C, §M).

`plan_queue(snapshot)` returns what one driver pass does with one repo's queue: open it
for a wave, build combinations into its slots, land the longest green prefix, rebuild on a
foreign move of `main`, eject a red or conflicting entry, drain a finished wave, and the
Needs the operator owns. The command layer builds the `QueueSnapshot` from the judgements,
the forge and the clone, and executes the actions; this module only decides.

Like `fr.triage.batch_drive`, it runs no git, reaches no forge and reads no clock: the time
is `QueueSnapshot.now`. `tests/unit/test_wave_queue_planner.py` pins that.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from fr.labels import pre_merge_held
from fr.triage.approval import ApprovalVerdict, is_approved
from fr.triage.batch import BatchStage
from fr.triage.batch_drive import LivePr
from fr.triage.model import (
    ApprovalEvent,
    Batch,
    DeferredEvent,
    QueueDrainEvent,
    QueueOpenEvent,
    QueueRecord,
    RequeuedEvent,
)

QueuePhase = Literal["open", "releasing", "idle"]
HoldState = Literal["open", "drained", "cleared"]
QueueActionKind = Literal[
    "queue-open",
    "queue-hold",
    "queue-build",
    "queue-land",
    "queue-eject",
    "queue-rebuild",
    "queue-post-merge",
    "queue-drain",
    "queue-cleared",
    "queue-held",
    "queue-need",
    "queue-warn",
]
REPORT_KINDS: frozenset[str] = frozenset({"queue-held", "queue-need", "queue-warn"})
"""The actions that only say something: the driver runs them before the executor exists
(phase 2 of the plan wires the planner in report-only mode)."""

TERMINAL_STAGES: frozenset[str] = frozenset({"merged", "partial", "cancelled", "abandoned"})
"""A batch at one of these, or deferred out of its wave, never holds its wave open (R2)."""


@dataclass(frozen=True)
class QueueConfig:
    """`.fr/triage.yaml`'s `queue:` block, with the spec's defaults (§ Config)."""

    ci: Literal["push", "none"] | None = "push"
    depth: int = 2
    land: Literal["push", "merge"] = "push"
    check_wait_minutes: int = 60
    release: Literal["workflow", "none"] = "workflow"
    release_workflow: str | None = None
    release_wait_hours: int = 6
    stall_hours: int = 4


@dataclass(frozen=True)
class Hold:
    """The repo's `refs/heads/fr-hold/queue` commit, as read (R17): its state, the scope and
    wave it names, its parent, and when it was opened and last refreshed."""

    state: HoldState
    scope: str
    wave: int | None
    parent: str
    opened: datetime | None = None
    refreshed: datetime | None = None


@dataclass(frozen=True)
class SlotCheck:
    """A combination's checks, read on its own sha under the required-checks rule (R7)."""

    verdict: Literal["green", "pending", "failing"]
    failing: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuildConflict:
    """A conflict the executor met building an entry at *head* (R6): the paths it could not
    resolve. The planner ejects the entry through `conflict_decision`."""

    head: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class QueueSnapshot:
    """Everything one repo's queue decides from. Built fresh each pass, never stored."""

    repo: str
    scope: str  # this driver's scope id
    config: QueueConfig
    now: datetime
    batches: tuple[Batch, ...]  # every batch of this repo: the wave choice reads them all
    stages: Mapping[str, BatchStage]
    live: Mapping[str, LivePr]  # batch id -> its PR as read now
    approvals: Mapping[str, ApprovalVerdict] = field(default_factory=dict)
    records: tuple[QueueRecord, ...] = ()  # this repo's queue records, oldest first
    hold: Hold | None = None
    base: str = ""  # the default branch's sha now; "" when unread
    slots: Mapping[str, SlotCheck] = field(default_factory=dict)  # combination sha -> checks
    conflicts: Mapping[str, BuildConflict] = field(default_factory=dict)  # entry key ->
    # The batches that may be entries (the drive's selection, minus those another scope's
    # claim holds); None: every batch.
    eligible: frozenset[str] | None = None
    sessions: Mapping[str, str] = field(default_factory=dict)  # batch id -> session status
    head_changed: Mapping[str, datetime] = field(default_factory=dict)  # batch id -> when
    # The open wave's close-out: None, it has none; False, not landed yet; True, landed.
    closeout_landed: bool | None = None
    warned: frozenset[str] = frozenset()  # report keys said already
    scope_args: tuple[str, ...] = ()  # the drive's own scope arguments, for pasted commands


@dataclass(frozen=True)
class QueueAction:
    """One thing the queue does. *entries* are entry keys (`entry_key`) in queue order."""

    kind: QueueActionKind
    repo: str
    detail: str
    wave: int | None = None
    entries: tuple[str, ...] = ()
    slots: tuple[int, ...] = ()
    # build: the commit the first entry is built on; rebuild: the new `main`
    base: str = ""
    sha: str = ""  # land: the tested tip `main` moves to; eject (red): the combination
    fresh: bool = False  # build: a rebuild of a red combination with the same tree (R13)
    reason: str = ""  # eject: conflict | red
    checks: tuple[str, ...] = ()  # eject (red): the failing check names
    paths: tuple[str, ...] = ()  # eject (conflict): the paths
    decision: str = ""  # eject: `red_decision`'s or `conflict_decision`'s kind
    batch: str = ""  # need, eject: the batch it is about
    key: str = ""  # warn: the report key, said once
    scope: str = ""  # held: the scope holding the hold


@dataclass(frozen=True)
class QueuePlan:
    repo: str
    phase: QueuePhase
    wave: int | None  # the open queue's wave, or the wave this pass opens
    actions: tuple[QueueAction, ...]
    entries: tuple[str, ...] = ()  # the queue's entries in order, after this plan
    waiting: tuple[str, ...] = ()  # ready entries that wait on a later queue


# ------------------------------------------------------------------ reading


def effective_wave(batch: Batch) -> int | None:
    """The wave *batch* queues in: the one its latest `requeued` event names (None: between
    waves), else its own (R29)."""
    for event in reversed(batch.events):
        if isinstance(event, RequeuedEvent):
            return event.wave
        if isinstance(event, DeferredEvent):
            break
    return batch.wave


def is_deferred(batch: Batch) -> bool:
    """*batch* was deferred out of its wave and not requeued since (R29)."""
    for event in reversed(batch.events):
        if isinstance(event, RequeuedEvent):
            return False
        if isinstance(event, DeferredEvent):
            return True
    return False


def is_terminal(batch: Batch, stage: str | None) -> bool:
    """Landed, cancelled, abandoned or deferred: it holds no wave open (R2, R30)."""
    return stage in TERMINAL_STAGES or is_deferred(batch)


def queue_phase(records: Sequence[QueueRecord], hold: Hold | None) -> QueuePhase:
    """§B: `open` from `queue_open` to `queue_drain`; `releasing` while the hold reads
    `drained`; `idle` once it is `cleared` or gone. *records* and *hold* are this scope's."""
    if hold is not None and hold.state == "drained":
        return "releasing"
    current = records[-1] if records else None
    if current is not None:
        opened = any(isinstance(e, QueueOpenEvent) for e in current.events)
        drained = any(isinstance(e, QueueDrainEvent) for e in current.events)
        if opened and not drained:
            return "open"
    return "idle"


def _ready_at(batch: Batch, pr: LivePr) -> datetime | None:
    """When *batch*'s PR became ready, as the records tell it: its latest approval."""
    for event in reversed(batch.events):
        if isinstance(event, ApprovalEvent) and event.pr == pr.number:
            return event.at
    return None


def _ready(batch: Batch, qs: QueueSnapshot) -> bool:
    """R3: open, a valid approval, its own head's checks green, and no pre-merge gate."""
    if qs.stages.get(batch.id) != "pr-open" or is_deferred(batch):
        return False
    if qs.eligible is not None and batch.id not in qs.eligible:
        return False
    pr = qs.live.get(batch.id)
    verdict = qs.approvals.get(batch.id)
    if pr is None or pr.state != "OPEN" or verdict is None or not is_approved(verdict):
        return False
    return pr.checks == "green" and not pre_merge_held(pr.labels)


def _by_readiness(batches: Sequence[Batch], qs: QueueSnapshot) -> list[Batch]:
    """*batches* in the order they became ready (R3); unknown last, then by wave order."""

    def key(b: Batch) -> tuple[bool, datetime | str, int, int, str]:
        at = _ready_at(b, qs.live[b.id])
        return (at is None, at or "", b.order is None, b.order or 0, b.id)

    return sorted(batches, key=key)  # type: ignore[arg-type]


# ------------------------------------------------------------------ planning


def _held(qs: QueueSnapshot) -> QueuePlan | None:
    """R31: another scope holds the repo's hold, `open` or `drained`."""
    hold = qs.hold
    if hold is None or hold.state == "cleared" or hold.scope == qs.scope:
        return None
    wave = "-" if hold.wave is None else str(hold.wave)
    why = (
        f"{qs.repo}'s merge queue is held by scope {hold.scope} (wave {wave}, hold "
        f"{hold.state}): this scope opens and lands nothing there until it is cleared"
    )
    action = QueueAction("queue-held", qs.repo, why, wave=hold.wave, scope=hold.scope)
    return QueuePlan(qs.repo, "idle", None, (action,))


def _plan_idle(qs: QueueSnapshot) -> QueuePlan:
    """§B: open the lowest wave with a non-terminal batch, ready entry or not; with no waved
    batch unfinished, a one-entry queue for the oldest ready between-waves entry."""
    unfinished = sorted(
        {w for b in qs.batches if not is_terminal(b, qs.stages.get(b.id))
         if (w := effective_wave(b)) is not None}
    )  # fmt: skip
    ready = _by_readiness([b for b in qs.batches if _ready(b, qs)], qs)
    if unfinished:
        wave: int | None = unfinished[0]
        entries: tuple[str, ...] = ()
        why = f"open {qs.repo}'s merge queue for wave {wave}"
    else:
        loose = [b for b in ready if effective_wave(b) is None]
        if not loose:
            return QueuePlan(qs.repo, "idle", None, (), waiting=tuple(b.id for b in ready))
        wave, entries = None, (loose[0].id,)
        why = f"open {qs.repo}'s merge queue between waves for {loose[0].id}"
    if qs.hold is not None and qs.hold.state != "cleared":
        # Our own `open` hold with no open record: the hold's writer settles it (R27).
        return QueuePlan(qs.repo, "idle", None, ())
    waiting = tuple(
        b.id for b in ready
        if b.id not in entries and (wave is None or effective_wave(b) != wave)
    )  # fmt: skip
    action = QueueAction("queue-open", qs.repo, why, wave=wave, entries=entries)
    return QueuePlan(qs.repo, "idle", wave, (action,), entries=entries, waiting=waiting)


def plan_queue(qs: QueueSnapshot) -> QueuePlan:
    """One pass of one repo's queue (§A)."""
    held = _held(qs)
    if held is not None:
        return held
    mine = tuple(r for r in qs.records if r.scope == qs.scope)
    phase = queue_phase(mine, qs.hold)
    if phase == "releasing":
        return QueuePlan(qs.repo, phase, mine[-1].wave if mine else None, ())
    if phase == "idle":
        return _plan_idle(qs)
    return QueuePlan(qs.repo, phase, mine[-1].wave, ())
