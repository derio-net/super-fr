"""The board's pure model (spec 2026-10-05-triage-batch-board §C).

No `fr_dispatch` import: `BoardStatus` is fr's own copy of
`fr_dispatch.protocols.SessionStatus`, the way `batch_item_id` is a copy of
`run_item_id`, and `tests/unit/test_import_direction.py` pins the two equal.

`build_board` is a function of the facts, the judgements and the session
statuses it is handed: no clock, no I/O. The hint (R6) asks the driver itself
what it would do (`drive_pass` over `drive_snapshot`) and falls back per column.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from fr.triage.batch import (
    BatchStage,
    DependencyState,
    batch_item_id,
    batch_pr,
    batch_repo,
    closeout_state,
    dependency_state,
    derive_batch_stage,
    last_dispatch,
)
from fr.triage.batch_drive import (
    Action,
    closeout_event,
    closeout_item_id,
    default_selection,
    drive_pass,
)
from fr.triage.model import (
    Batch,
    CancelEvent,
    CloseoutEvent,
    DispatchEvent,
    Facts,
    Judgements,
    Launch,
)
from fr.triage.stage import Stage
from fr.triage.views import drive_snapshot

BoardStatus = Literal["working", "blocked", "idle", "done", "unknown", "absent"]
"""One session's live state as the board shows it; `absent` when the runner holds none."""

Column = Literal["proposed", "waiting", "running", "pr-open", "closing-out", "done"]

COLUMN_TITLES: Mapping[Column, str] = {
    "proposed": "Proposed",
    "waiting": "Waiting",
    "running": "Running",
    "pr-open": "PR open",
    "closing-out": "Closing out",
    "done": "Done",
}
"""The columns, left to right (R2): the one ordered table every other read derives from."""

COLUMNS: tuple[Column, ...] = tuple(COLUMN_TITLES)

_COLUMN_OF_STAGE: Mapping[BatchStage, Column] = {
    "dispatched": "running",
    "pr-open": "pr-open",
    "cancelled": "done",
    "abandoned": "done",
    "partial": "done",
}
PILL_STAGES: frozenset[BatchStage] = frozenset({"cancelled", "abandoned", "partial"})
_DEAD: frozenset[DependencyState] = frozenset({"unsatisfiable", "unknown"})

# R6: what the driver's action means for a card, by action kind.
_ACTION_PHRASES: Mapping[str, str] = {
    "dispatch": "dispatch next",
    "merge": "merge ready",
    "warn": "CI failing",
    "closeout": "close-out due",
    "archive": "archive PR ready to merge",
    "held": "held by the in-flight cap",
    "adopt": "close-out found; the drive records it",
    "foreign": "foreign PR on its branch",
    "close": "finished; session to close",
}
NEEDS_YOU = "needs you: session blocked"
# R6's per-column fallbacks.
HINT_QUEUED = "queued"
HINT_NOT_DRIVEN = "not driven"
HINT_RUNNING = "session running, no PR yet"
HINT_DRAFT = "PR draft"
HINT_CI_PENDING = "CI pending"
HINT_REVIEW = "awaiting review"
HINT_ARCHIVE_PENDING = "archive PR pending"
HINT_CLOSEOUT_NOT_RECORDED = "close-out not recorded"
HINT_FINISHED = "finished"


# ---------------------------------------------------------------- the model


@dataclass(frozen=True)
class Member:
    key: str
    title: str
    url: str | None
    stage: Stage | Literal["unknown"]


@dataclass(frozen=True)
class PrView:
    number: int
    url: str
    state: str
    draft: bool
    checks: dict[str, int] | None
    mergeable: str | None
    review: str | None


@dataclass(frozen=True)
class Dep:
    batch_id: str
    state: DependencyState


@dataclass(frozen=True)
class Setting:
    """A launch value and whether it came from the repo's default, not the batch."""

    value: str | None
    is_default: bool = False


@dataclass(frozen=True)
class EventRow:
    kind: str
    at: datetime
    detail: str


@dataclass(frozen=True)
class Card:
    batch: Batch
    column: Column
    stage: BatchStage
    pill: str | None
    blocked: bool
    hint: str
    needs_you: bool
    status: BoardStatus | None
    closeout_status: BoardStatus | None
    show_jump: bool
    show_closeout_jump: bool
    hand_closeout: bool
    members: tuple[Member, ...]
    pr: PrView | None
    wave: int | None
    after: tuple[Dep, ...]
    branch: str | None
    reserved_version: str | None
    runner: str | None
    skill: str
    rationale: str
    harness: Setting
    model: Setting
    events: tuple[EventRow, ...]


@dataclass(frozen=True)
class ColumnView:
    key: Column
    title: str
    cards: tuple[Card, ...]


@dataclass(frozen=True)
class Board:
    scope: str
    collected_at: str
    columns: tuple[ColumnView, ...]

    def column(self, key: Column) -> ColumnView:
        return next(c for c in self.columns if c.key == key)

    def card(self, batch_id: str) -> Card:
        return next(card for col in self.columns for card in col.cards if card.batch.id == batch_id)

    @property
    def batch_count(self) -> int:
        return sum(len(c.cards) for c in self.columns)


# ------------------------------------------------------------------ columns


def column_of(batch: Batch, facts: Facts, batches: Sequence[Batch]) -> Column:
    """R2's table, from `derive_batch_stage`, `dependency_state` and `closeout_state`."""
    if not batch.events:
        waiting = any(dependency_state(d, batches, facts) != "satisfied" for d in batch.after)
        return "waiting" if waiting else "proposed"
    stage = derive_batch_stage(batch, facts)
    if stage in _COLUMN_OF_STAGE:
        return _COLUMN_OF_STAGE[stage]
    archived = closeout_state(batch, facts) == "archived"
    return "done" if archived else "closing-out"


def pill_of(batch: Batch, facts: Facts) -> str | None:
    """`cancelled`, `abandoned` or `partial`: the word a Done card carries; else None."""
    stage = derive_batch_stage(batch, facts)
    return stage if stage in PILL_STAGES else None


# -------------------------------------------------------------------- hints


def first_actions(facts: Facts, judgements: Judgements) -> dict[str, Action]:
    """The first action the driver would take per batch on these facts, selecting what
    the drive selects by default, at its default in-flight cap (R6)."""
    snapshot = drive_snapshot(facts, judgements)
    chosen = replace(snapshot, selected=default_selection(judgements.batches))
    first: dict[str, Action] = {}
    for action in drive_pass(chosen).actions:
        first.setdefault(action.batch, action)
    return first


def action_phrase(action: Action) -> str:
    """One line for what the driver would do with the batch."""
    if action.kind == "blocked":
        return f"blocked: {action.detail}"
    return _ACTION_PHRASES[action.kind]


def fallback_hint(
    batch: Batch, column: Column, facts: Facts, batches: Sequence[Batch], *, selected: bool
) -> str:
    """R6's per-column fallback, for a card the driver has nothing to do for."""
    if column == "proposed":
        return HINT_QUEUED if selected else HINT_NOT_DRIVEN
    if column == "waiting":
        pending = [d for d in batch.after if dependency_state(d, batches, facts) != "satisfied"]
        return "waits on " + ", ".join(pending)
    if column == "running":
        return HINT_RUNNING
    if column == "pr-open":
        pr = batch_pr(batch, facts)
        if pr is not None and pr.is_draft:
            return HINT_DRAFT
        if pr is not None and (pr.checks or {}).get("pending", 0) > 0:
            return HINT_CI_PENDING
        return HINT_REVIEW
    if column == "closing-out":
        return HINT_ARCHIVE_PENDING if closeout_event(batch) else HINT_CLOSEOUT_NOT_RECORDED
    return pill_of(batch, facts) or HINT_FINISHED


# -------------------------------------------------------------------- cards


def _members(batch: Batch, facts: Facts) -> tuple[Member, ...]:
    found = {i.key: i for i in facts.issues}
    out = []
    for key in batch.ids:
        issue = found.get(key)
        if issue is not None:
            out.append(Member(key, issue.title, issue.url, issue.stage))
        else:
            out.append(Member(key, key, None, "unknown"))  # no forge URL is guessed
    return tuple(out)


def _setting(own: str | None, default: str | None) -> Setting:
    if own:
        return Setting(own)
    return Setting(default, True) if default else Setting(None)


def _event_row(event: object) -> EventRow:
    if isinstance(event, DispatchEvent):
        parts = [f"runner {event.runner}", f"branch {event.branch}"]
        if event.reserved_version:
            parts.append(f"version {event.reserved_version}")
        return EventRow("dispatch", event.at, " · ".join(parts))
    if isinstance(event, CancelEvent):
        return EventRow("cancel", event.at, event.reason)
    if isinstance(event, CloseoutEvent):
        detail = f"runner {event.runner}"
        if event.archived is not None:
            detail += " · archived"
        return EventRow("closeout", event.at, detail)
    return EventRow(getattr(event, "kind", "event"), event.at, "")  # type: ignore[attr-defined]


def _card(
    batch: Batch,
    facts: Facts,
    batches: Sequence[Batch],
    statuses: Mapping[str, BoardStatus],
    actions: Mapping[str, Action],
    selected: frozenset[str],
) -> Card:
    column = column_of(batch, facts, batches)
    deps = tuple(Dep(d, dependency_state(d, batches, facts)) for d in batch.after)
    repo = batch_repo(batch, facts)
    dispatch, closeout = last_dispatch(batch), closeout_event(batch)
    status: BoardStatus | None = None
    if dispatch is not None:
        status = statuses.get(batch_item_id(repo, batch.id), "unknown") if repo else "unknown"
    closeout_status: BoardStatus | None = None
    if closeout is not None and closeout.runner != "hand":
        key = closeout_item_id(repo, batch.id) if repo else ""
        closeout_status = statuses.get(key, "unknown")
    needs_you = "blocked" in (status, closeout_status)
    if needs_you:
        hint = NEEDS_YOU
    elif batch.id in actions:
        hint = action_phrase(actions[batch.id])
    else:
        hint = fallback_hint(batch, column, facts, batches, selected=batch.id in selected)
    pr = batch_pr(batch, facts)
    default = facts.config_for(repo or "").defaults.launch if repo else Launch()
    launch = batch.launch
    return Card(
        batch=batch,
        column=column,
        stage=derive_batch_stage(batch, facts),
        pill=pill_of(batch, facts),
        blocked=column == "waiting" and any(d.state in _DEAD for d in deps),
        hint=hint,
        needs_you=needs_you,
        status=status,
        closeout_status=closeout_status,
        show_jump=status is not None and status != "absent",
        show_closeout_jump=closeout_status is not None and closeout_status != "absent",
        hand_closeout=closeout is not None and closeout.runner == "hand",
        members=_members(batch, facts),
        pr=None
        if pr is None
        else PrView(pr.number, pr.url, pr.state, pr.is_draft, pr.checks, pr.mergeable, pr.review),
        wave=batch.wave,
        after=deps,
        branch=dispatch.branch if dispatch else None,
        reserved_version=dispatch.reserved_version if dispatch else None,
        runner=(dispatch.runner if dispatch else None) or launch.runner or default.runner,
        skill=batch.skill,
        rationale=batch.rationale,
        harness=_setting(launch.harness, default.harness),
        model=_setting(launch.model, default.model),
        events=tuple(sorted((_event_row(e) for e in batch.events), key=lambda e: e.at)),
    )


def build_board(facts: Facts, judgements: Judgements, statuses: Mapping[str, BoardStatus]) -> Board:
    """One card per batch in six columns, sorted by wave (none last) then id (R2)."""
    batches = judgements.batches
    actions = first_actions(facts, judgements)
    selected = default_selection(batches)
    cards = [_card(b, facts, batches, statuses, actions, selected) for b in batches]
    cards.sort(key=lambda c: (c.batch.wave is None, c.batch.wave or 0, c.batch.id))
    columns = tuple(
        ColumnView(key, COLUMN_TITLES[key], tuple(c for c in cards if c.column == key))
        for key in COLUMNS
    )
    return Board(scope=facts.scope, collected_at=facts.collected_at, columns=columns)
