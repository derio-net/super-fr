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
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Literal

from fr.labels import pre_merge_held
from fr.triage.approval import ApprovalVerdict, is_approved
from fr.triage.batch import BatchStage
from fr.triage.batch_drive import (
    HANDBACKS_PER_DISPATCH,
    RED_HANDBACKS_PER_DISPATCH,
    LivePr,
    conflict_decision,
    handbacks_since,
    held_conflict,
    red_decision,
)
from fr.triage.model import (
    ApprovalEvent,
    Batch,
    ConflictEvent,
    DeferredEvent,
    QueueBuiltEvent,
    QueueDrainEvent,
    QueueEjectEvent,
    QueueEntryRef,
    QueueLandEvent,
    QueueOpenEvent,
    QueueRecord,
    RedHandbackEvent,
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
    # build: the one entry rebuilt as a fresh commit with the same tree as its red
    # combination (R13); the entries behind it are ordinary builds. "": none
    fresh_entry: str = ""
    head: str = ""  # eject: the head the entry leaves at, recorded on `queue_eject` (R6, R13)
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


def _by_readiness(
    batches: Sequence[Batch], qs: QueueSnapshot, since: Mapping[str, datetime] | None = None
) -> list[Batch]:
    """*batches* in the order they became ready (R3): the latest approval, or a later
    ejection (*since*) it re-entered after; unknown last, then by wave order."""

    def key(b: Batch) -> tuple[bool, datetime | str, int, int, str]:
        at = _ready_at(b, qs.live[b.id])
        floor = (since or {}).get(b.id)
        if floor is not None and (at is None or floor > at):
            at = floor
        return (at is None, at or "", b.order is None, b.order or 0, b.id)

    return sorted(batches, key=key)


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
    """§B: the lowest wave with a non-terminal batch opens once its first entry is ready;
    until then nothing opens and no hold is written, so a wave still being developed never
    holds the repo's releases (plan decision p2-queue-opens-on-first-ready). With no waved
    batch unfinished, a one-entry queue for the oldest ready between-waves entry."""
    unfinished = sorted(
        {w for b in qs.batches if not is_terminal(b, qs.stages.get(b.id))
         if (w := effective_wave(b)) is not None}
    )  # fmt: skip
    ready = _by_readiness([b for b in qs.batches if _ready(b, qs)], qs)
    if unfinished:
        wave: int | None = unfinished[0]
        if not any(effective_wave(b) == wave for b in ready):
            return QueuePlan(qs.repo, "idle", None, (), waiting=tuple(b.id for b in ready))
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


def entry_key(ref: QueueEntryRef) -> str:
    """The planner's name for an entry: its batch id, or `<kind>#<pr>` for any other PR."""
    return ref.batch if ref.batch is not None else f"{ref.kind}#{ref.pr}"


@dataclass(frozen=True)
class Combo:
    """One slot's combination as the records rebuild it: built on *parent* (the queue's
    base, or the combination ahead), holding *chain* (entry keys, front first) at *heads*
    over *base*."""

    slot: int
    sha: str
    parent: str
    chain: tuple[str, ...]
    heads: tuple[str, ...]
    base: str


@dataclass(frozen=True)
class Replay:
    """A queue record read in order: its base now, each slot's combination, the entries in
    the order they joined, what landed, what was ejected (at which head: "" for a conflict
    whose event names none, which `_ejected_head` reads from the batch) and how often each
    (parent, entry, head) was built (R13's one rebuild)."""

    base: str
    combos: Mapping[int, Combo]
    order: tuple[str, ...]
    landed: frozenset[str]
    ejected: Mapping[str, str]
    ejected_at: Mapping[str, datetime]
    builds: Mapping[tuple[str, str, str], int]


def replay(record: QueueRecord) -> Replay:
    """*record*'s events folded into the queue's state, from the events alone (R24)."""
    base = record.base
    combos: dict[int, Combo] = {}
    order: list[str] = []
    landed: set[str] = set()
    ejected: dict[str, str] = {}
    ejected_at: dict[str, datetime] = {}
    heads: dict[str, str] = {}
    builds: dict[tuple[str, str, str], int] = {}
    for event in record.events:
        if isinstance(event, QueueBuiltEvent):
            key = entry_key(event.entry)
            parent = event.parent or event.base
            ahead = next((c for c in combos.values() if c.sha == parent), None)
            chain, at = ((*ahead.chain, key), (*ahead.heads, event.head)) if ahead else (
                (key,), (event.head,))  # fmt: skip
            combos[event.slot] = Combo(event.slot, event.sha, parent, chain, at,
                                       ahead.base if ahead else event.base)  # fmt: skip
            base = event.base
            heads[key] = event.head
            builds[(parent, key, event.head)] = builds.get((parent, key, event.head), 0) + 1
            ejected.pop(key, None)
            if key not in order:
                order.append(key)
        elif isinstance(event, QueueLandEvent):
            done = tuple(entry_key(e) for e in event.entries)
            shifted: dict[int, Combo] = {}
            for slot, c in combos.items():
                if c.chain[: len(done)] == done and len(c.chain) > len(done):
                    n = len(done)
                    # Its parent stays: equal to the new `main` only when the landing pushed
                    # the tested commit itself (R9), else it is rebuilt on what landed.
                    shifted[slot] = Combo(slot, c.sha, c.parent, c.chain[n:], c.heads[n:],
                                          event.main)  # fmt: skip
            combos = shifted
            base = event.main
            landed.update(done)
            order = [k for k in order if k not in done]
        elif isinstance(event, QueueEjectEvent):
            key = entry_key(event.entry)
            # A conflict met at build has no `queue_built` at its head: the last build's head
            # is an older one, so only the event's own head is trusted for it.
            last = "" if event.reason == "conflict" else heads.get(key, "")
            ejected[key] = event.head or last
            ejected_at[key] = event.at
            order = [k for k in order if k != key]
    return Replay(base, combos, tuple(order), frozenset(landed), ejected, ejected_at, builds)


def _verdict(combo: Combo, qs: QueueSnapshot) -> SlotCheck:
    if qs.config.ci == "none":
        return SlotCheck("green")  # R20: built without a conflict is green
    return qs.slots.get(combo.sha, SlotCheck("pending"))


def _valid(
    entries: Sequence[str], base: str, combos: Mapping[int, Combo], qs: QueueSnapshot
) -> list[Combo]:
    """The combinations that still stand, front first: the one holding *entries*[:i+1] on
    *base*, at each entry's live head, built on the one before it. The first gap ends it."""
    out: list[Combo] = []
    for i in range(min(len(entries), qs.config.depth)):
        want = tuple(entries[: i + 1])
        parent = out[-1].sha if out else base
        found = next(
            (c for c in combos.values()
             if c.chain == want and c.base == base and c.parent == parent
             and c.heads[-1] == _head(want[-1], qs)),
            None,
        )  # fmt: skip
        if found is None:
            break
        out.append(found)
    return out


def _head(key: str, qs: QueueSnapshot) -> str:
    pr = qs.live.get(key)
    return pr.head if pr is not None else ""


def _ejected_head(key: str, rep: Replay, by_id: Mapping[str, Batch]) -> str | None:
    """The head *key* was ejected at (None: not ejected): the replay's, else its batch's
    latest `conflict` event for a conflict ejection that named none ("" when unknown)."""
    if key not in rep.ejected:
        return None
    if rep.ejected[key] or (batch := by_id.get(key)) is None:
        return rep.ejected[key]
    met = next((e for e in reversed(batch.events) if isinstance(e, ConflictEvent)), None)
    return met.head if met is not None else ""


def _entries(record: QueueRecord, rep: Replay, qs: QueueSnapshot) -> tuple[list[str], list[str]]:
    """The queue's entries in order (R3: the order they became ready), and the ready
    entries that wait on a later queue. An ejected entry re-enters once its head moves;
    until then it is ejected, neither an entry nor waiting (R25)."""
    by_id = {b.id: b for b in qs.batches}
    ready = [b for b in qs.batches if _ready(b, qs)]
    mine = [b for b in ready if effective_wave(b) == record.wave]
    if record.wave is None:  # one entry between waves: the one built, else the oldest
        if rep.landed:
            mine = []
        else:
            built = [by_id[k] for k in rep.order if k in by_id]
            mine = [b for b in built if b in mine][:1] or _by_readiness(mine, qs)[:1]
    keep = [b.id for b in mine]
    queued = [k for k in rep.order if k in keep]
    out = {b.id for b in ready if effective_wave(b) == record.wave
           and _ejected_head(b.id, rep, by_id) == _head(b.id, qs)}  # fmt: skip
    fresh = [
        b.id for b in _by_readiness([b for b in mine if b.id not in queued], qs, rep.ejected_at)
        if b.id not in rep.landed and b.id not in out
    ]  # fmt: skip
    entries = [*queued, *fresh]
    waiting = [b.id for b in _by_readiness(ready, qs) if b.id not in entries
               and b.id not in rep.landed and b.id not in out]  # fmt: skip
    return entries, waiting


def _free(combos: Sequence[Combo], depth: int, n: int) -> tuple[int, ...]:
    """*n* slots no standing combination holds, lowest first (R4: reused, never more)."""
    taken = {c.slot for c in combos}
    return tuple(s for s in range(1, depth + 1) if s not in taken)[:n]


def _plan_open(record: QueueRecord, qs: QueueSnapshot) -> QueuePlan:
    rep = replay(record)
    entries, waiting = _entries(record, rep, qs)
    depth = qs.config.depth
    actions: list[QueueAction] = []
    wave = record.wave
    if qs.base and qs.base != rep.base:  # R14: a move of `main` the queue did not make
        key = f"queue-base\0{qs.repo}\0{qs.base}"
        if key not in qs.warned:
            actions.append(QueueAction(
                "queue-warn", qs.repo, f"{qs.repo}'s default branch moved to {qs.base[:12]} "
                f"outside the queue (from {rep.base[:12]}): every combination is rebuilt on "
                "it; no PR branch moves", wave=wave, key=key))  # fmt: skip
        window = tuple(entries[:depth])
        if window:
            actions.append(QueueAction(
                "queue-rebuild", qs.repo, f"rebuild {', '.join(window)} on {qs.base[:12]}",
                wave=wave, entries=window, slots=tuple(range(1, len(window) + 1)),
                base=qs.base))  # fmt: skip
            return _tail(record, rep, qs, actions, entries, waiting)
        # Nothing to rebuild: the queue's base is the moved `main`, and it drains or stalls
        # there like any other pass (an empty window must not hold the hold open forever).
        rep = replace(rep, base=qs.base)
    by_id = {b.id: b for b in qs.batches}
    earlier: list[tuple[str, Sequence[str]]] = []
    for key in list(entries):  # R6: a conflict met at build, at the head it still has
        met = qs.conflicts.get(key)
        if met is None or met.head != _head(key, qs):
            continue
        batch = by_id.get(key)
        decided = (conflict_decision(batch.events, met.head, met.paths, earlier).kind
                   if batch is not None else "")  # fmt: skip
        earlier.append((key, met.paths))
        entries.remove(key)
        actions.append(QueueAction(
            "queue-eject", qs.repo, f"eject {key}: it conflicts in {', '.join(met.paths)}",
            wave=wave, entries=(key,), reason="conflict", paths=met.paths, decision=decided,
            batch=key if batch is not None else "", head=met.head))  # fmt: skip
    valid = _valid(entries, rep.base, rep.combos, qs)
    green = 0
    while green < len(valid) and _verdict(valid[green], qs).verdict == "green":
        green += 1
    base, standing = rep.base, valid
    if green:
        tip = valid[green - 1]
        done = tuple(entries[:green])
        actions.append(QueueAction("queue-land", qs.repo, f"land {', '.join(done)} at "
                                   f"{tip.sha[:12]}", wave=wave, entries=done,
                                   sha=tip.sha))  # fmt: skip
        entries, base, standing = entries[green:], tip.sha, valid[green:]
    fresh, first = "", None
    if standing and _verdict(standing[0], qs).verdict == "failing":  # R13: every one ahead green
        red = standing[0]
        key, check = red.chain[-1], _verdict(red, qs)
        if rep.builds.get((red.parent, key, red.heads[-1]), 0) < 2:
            fresh, first = key, red.slot  # once more, as a fresh commit with the same tree
        else:
            batch, pr = by_id.get(key), qs.live.get(key)
            told: str = (
                red_decision(batch.events, pr.number, pr.head, check.failing,
                             qs.sessions.get(key, "unknown"))
                if batch is not None and pr is not None else ""
            )  # fmt: skip
            entries.remove(key)
            actions.append(QueueAction(
                "queue-eject", qs.repo, f"eject {key}: combination {red.sha[:12]} failed "
                f"twice ({', '.join(check.failing) or 'checks failing'})", wave=wave,
                entries=(key,), reason="red", sha=red.sha, checks=check.failing,
                decision=told, batch=key if batch is not None else "",
                head=red.heads[-1]))  # fmt: skip
        standing = []
    todo = tuple(entries[len(standing) : depth])
    if todo:
        on = standing[-1].sha if standing else base
        slots = _free(standing, depth, depth)
        if first is not None:
            slots = (first, *(s for s in slots if s != first))
        actions.append(QueueAction(
            "queue-build", qs.repo, f"build {', '.join(todo)} on {on[:12]}"
            + (f" ({fresh} rebuilt fresh, same tree)" if fresh else ""), wave=wave,
            entries=todo, slots=slots[: len(todo)], base=on, fresh_entry=fresh))  # fmt: skip
    return _tail(record, rep, qs, actions, entries, waiting)


def _tail(
    record: QueueRecord,
    rep: Replay,
    qs: QueueSnapshot,
    actions: list[QueueAction],
    entries: Sequence[str],
    waiting: Sequence[str],
) -> QueuePlan:
    """Every open pass ends here, a foreign move's included: drain the finished wave, else
    propose the batch that stalls it (§B, R30)."""
    landing = any(a.kind == "queue-land" for a in actions)
    drained = None if entries or landing else _drained(record, rep, qs)
    if drained is not None:
        actions.append(drained)
    elif (need := _stall_need(record, qs, entries)) is not None:
        actions.append(need)
    return QueuePlan(qs.repo, "open", record.wave, tuple(actions), tuple(entries),
                     tuple(waiting))  # fmt: skip


def _drained(record: QueueRecord, rep: Replay, qs: QueueSnapshot) -> QueueAction | None:
    """§B: a wave drains once every batch of it is terminal (deferral included) and its
    close-out, if it has one, has landed; a between-waves queue once its one entry landed."""
    wave = record.wave
    if wave is None:
        done = bool(rep.landed)
    else:
        done = qs.closeout_landed is not False and all(
            is_terminal(b, qs.stages.get(b.id)) for b in qs.batches if effective_wave(b) == wave
        )
    if not done:
        return None
    which = "between waves" if wave is None else f"wave {wave}"
    return QueueAction("queue-drain", qs.repo, f"{qs.repo}'s queue for {which} is done: "
                       f"drain it at {rep.base[:12]}", wave=wave, sha=rep.base)  # fmt: skip


def _budget_spent(batch: Batch) -> bool:
    """Its conflict or red hand-backs since its dispatch are spent (R22, R10)."""
    red = handbacks_since(
        batch.events, lambda e: isinstance(e, RedHandbackEvent) and e.delivered == "session"
    )
    conflicts = handbacks_since(
        batch.events, lambda e: isinstance(e, ConflictEvent) and e.delivered != "held"
    )
    return (red >= RED_HANDBACKS_PER_DISPATCH or conflicts >= HANDBACKS_PER_DISPATCH
            or held_conflict(batch) is not None)  # fmt: skip


def _stall_need(
    record: QueueRecord, qs: QueueSnapshot, entries: Sequence[str]
) -> QueueAction | None:
    """R30: every other batch of the open wave is terminal, and the one left, which is not
    in the queue (*entries*: those move by building and landing), has spent its hand-back
    budget or made no progress (no new head, no event) for `stall_hours`. The driver
    proposes; the operator defers or requeues. Never a write."""
    wave = record.wave
    if wave is None:
        return None
    left = [b for b in qs.batches
            if effective_wave(b) == wave and not is_terminal(b, qs.stages.get(b.id))]  # fmt: skip
    if len(left) != 1 or left[0].id in entries:
        return None
    batch = left[0]
    stall = timedelta(hours=qs.config.stall_hours)
    mine = [e.at for e in record.events
            if (ref := getattr(e, "entry", None)) is not None and entry_key(ref) == batch.id
            or isinstance(e, QueueLandEvent) and batch.id in map(entry_key, e.entries)]  # fmt: skip
    last = max([e.at for e in batch.events] + mine, default=None)
    head = qs.head_changed.get(batch.id)
    if _budget_spent(batch):
        why = "its hand-back budget is spent"
    elif last is not None and qs.now - last >= stall and (head is None or qs.now - head >= stall):
        why = f"it has made no progress for {qs.config.stall_hours} h"
    else:
        return None
    args = "".join(f" {a}" for a in qs.scope_args)
    detail = (
        f"{batch.id} is the last batch holding wave {wave}'s drain and {why}: take it out of "
        f"the wave with `fr triage batch defer {batch.id}{args}`, or move it to a later "
        f"queue with `fr triage batch requeue {batch.id}{args}`"
    )
    return QueueAction("queue-need", qs.repo, detail, wave=wave, batch=batch.id)


def waits_on_queue(batch: Batch, stage: str | None, *, open_wave: int | None) -> bool:
    """R36: *batch*'s PR is delivered (`pr-open`) and waits on a later queue than the open
    one (wave *open_wave*): it takes no in-flight slot, so the open wave's undispatched
    batches are never starved by later waves' finished work."""
    return stage == "pr-open" and effective_wave(batch) != open_wave


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
    return _plan_open(mine[-1], qs)


# ------------------------------------------------------------------ lines


def queue_line(plan: QueuePlan) -> str:
    """One repo's queue in one line: `queue <repo>: open wave 3 · entries a, b · waiting c`.
    The full line of R25 (each entry's state, what landed, the hold) is the operator view's."""
    wave = "between waves" if plan.wave is None else f"wave {plan.wave}"
    parts = [plan.phase if plan.phase != "open" else f"open {wave}"]
    if plan.entries:
        parts.append("entries " + ", ".join(plan.entries))
    if plan.waiting:
        parts.append("waiting " + ", ".join(plan.waiting))
    return f"queue {plan.repo}: " + " · ".join(parts)


def queue_action_line(action: QueueAction) -> str:
    """The line a queue action prints."""
    return f"{action.kind} {action.repo}: {action.detail}"
