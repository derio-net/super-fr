"""The dwell ledger: how long each batch has sat where it is (spec
2026-11-27-board-session-state §D, R5-R7).

`dwell.json` in the scope's state directory records, per batch, the column and the wait
party (`Card.wait`, None for none) it was last seen in and since when, plus the closed
intervals before that. Everything here is pure but `load` and `store`: the clock is passed
in (`now`), and only `write_board` reads and writes the file, as the ledger's one writer
(R5). Precision is the observation cadence: a transition is dated at the observation that
saw it, never earlier.

`card_dwell` is the card's dwell line (R6) and `wave_time` the Batches page's "Time per
wave" section (R7).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fr.artifacts.atomic import write_text_atomic
from fr.triage.kanban import COLUMN_TITLES, COLUMNS, Board, Card, Column
from fr.triage.waits import PARTIES, Party

DWELL_FILE = "dwell.json"
SCHEMA: Literal[1] = 1
CAP = 200
"""The intervals each batch keeps; the oldest goes first, and the batch is `truncated`."""

UNMEASURED: frozenset[Column] = frozenset({"done"})
"""Columns `wave_time` leaves out: a Done batch's open time is time since it finished,
not time spent in the pipeline, and it grows without bound."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Interval(_Strict):
    column: Column
    wait: Party | None
    start: datetime
    end: datetime
    first_seen: bool = False  # its start was the ledger's first sighting of the state


class Entry(_Strict):
    column: Column
    column_since: datetime
    column_first_seen: bool
    wait: Party | None
    wait_since: datetime
    wait_first_seen: bool
    intervals: tuple[Interval, ...] = ()
    truncated: bool = False

    def open_interval(self, now: datetime) -> Interval:
        """The state the batch is in now, as an interval ending at *now*."""
        start, first = _start(self)
        return Interval(column=self.column, wait=self.wait, start=start, end=now, first_seen=first)


class Ledger(_Strict):
    schema_: Literal[1] = Field(default=SCHEMA, alias="schema")
    batches: dict[str, Entry] = Field(default_factory=dict)


def _start(e: Entry) -> tuple[datetime, bool]:
    """The later of the two `since` times, and the first-seen mark of that one."""
    if e.column_since >= e.wait_since:
        return e.column_since, e.column_first_seen
    return e.wait_since, e.wait_first_seen


def _cards(board: Board) -> Iterator[Card]:
    for col in board.columns:
        yield from col.cards


def observe(ledger: Ledger, board: Board, now: datetime) -> Ledger:
    """The ledger after seeing *board* at *now* (§D): a new batch starts first-seen, an
    unchanged one is kept, a changed one closes its open interval and restarts each
    changed `since`; a batch absent from the board is dropped."""
    out: dict[str, Entry] = {}
    for card in _cards(board):
        bid = card.batch.id
        wait = card.wait.party if card.wait is not None else None
        old = ledger.batches.get(bid)
        if old is None:
            out[bid] = Entry(
                column=card.column, column_since=now, column_first_seen=True,
                wait=wait, wait_since=now, wait_first_seen=True,
            )  # fmt: skip
            continue
        if old.column == card.column and old.wait == wait:
            out[bid] = old
            continue
        intervals = (*old.intervals, old.open_interval(now))
        truncated = old.truncated or len(intervals) > CAP
        moved_column = old.column != card.column
        moved_wait = old.wait != wait
        out[bid] = Entry(
            column=card.column,
            column_since=now if moved_column else old.column_since,
            column_first_seen=False if moved_column else old.column_first_seen,
            wait=wait,
            wait_since=now if moved_wait else old.wait_since,
            wait_first_seen=False if moved_wait else old.wait_first_seen,
            intervals=intervals[-CAP:],
            truncated=truncated,
        )
    return Ledger(batches=out)


def load(state_dir: Path) -> tuple[Ledger, str | None]:
    """The ledger in *state_dir*, and a page note when the file was there but unusable
    (an unreadable ledger is an empty one, never a crash)."""
    path = state_dir / DWELL_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Ledger(), None
    except (OSError, ValueError) as exc:  # ValueError: not UTF-8
        return Ledger(), f"{DWELL_FILE}: unreadable, dwell times start over ({exc})"
    try:
        return Ledger.model_validate_json(text), None
    except ValidationError as exc:
        why = exc.errors()[0].get("msg", "invalid") if exc.errors() else "invalid"
        return Ledger(), f"{DWELL_FILE}: not usable, dwell times start over ({why})"


def store(state_dir: Path, ledger: Ledger) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    text = ledger.model_dump_json(by_alias=True, indent=2)
    write_text_atomic(state_dir / DWELL_FILE, text + "\n")


# ------------------------------------------------------------------ rendering


def format_duration(seconds: float) -> str:
    """`45m`, `3h 12m`, `2d 4h`; `0m` under a minute."""
    minutes = max(0, int(seconds)) // 60
    if minutes < 60:
        return f"{minutes}m"
    hours, mins = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {mins}m"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h"


def _span(seconds: float, at_least: bool) -> str:
    return ("≥" if at_least else "") + format_duration(seconds)


def card_dwell(entry: Entry, card: Card, now: datetime) -> str:
    """The card's dwell line (R6): `in <column> <d> · waits for <party> <d>`, each part
    `≥` when its state is first-seen; the column alone when the card has no wait."""
    column = (now - entry.column_since).total_seconds()
    line = f"in {COLUMN_TITLES[card.column]} {_span(column, entry.column_first_seen)}"
    if card.wait is None:
        return line
    waited = (now - entry.wait_since).total_seconds()
    return f"{line} · waits for {card.wait.party} {_span(waited, entry.wait_first_seen)}"


@dataclass(frozen=True)
class TimeRow:
    key: str  # a column key, or a wait party
    seconds: float
    at_least: bool
    longest: str | None = None  # the batch that spent longest here (columns only)
    longest_seconds: float = 0.0
    longest_at_least: bool = False


@dataclass(frozen=True)
class WaveTime:
    wave: int | None  # None: the batches with no wave
    batches: tuple[str, ...]
    columns: tuple[TimeRow, ...]
    parties: tuple[TimeRow, ...]


_Tally = dict[str, tuple[float, bool]]
"""key -> (seconds, at least): one batch's time per column or per party."""


def _per_batch(entry: Entry, now: datetime) -> tuple[_Tally, _Tally]:
    """Seconds and the at-least mark per column and per party for one batch: closed
    intervals plus the open one, every part `≥` when the batch is truncated."""
    cols: _Tally = {}
    parties: _Tally = {}
    for iv in (*entry.intervals, entry.open_interval(now)):
        if iv.column in UNMEASURED:
            continue
        secs = max(0.0, (iv.end - iv.start).total_seconds())
        mark = iv.first_seen or entry.truncated
        for bucket, key in ((cols, iv.column), (parties, iv.wait)):
            if key is not None:
                was, was_mark = bucket.get(key, (0.0, False))
                bucket[key] = (was + secs, was_mark or mark)
    return cols, parties


def wave_time(ledger: Ledger, board: Board, now: datetime) -> list[WaveTime]:
    """Per wave, ascending, then one block for the batches with no wave (R7): the time the
    wave's batches spent per column (board order) and per wait party (`PARTIES` order),
    closed plus open intervals up to *now*, and per column the batch that spent longest."""
    groups: dict[int | None, list[Card]] = {}
    for card in _cards(board):
        if card.batch.id in ledger.batches:
            groups.setdefault(card.wave, []).append(card)
    order = sorted(w for w in groups if w is not None) + ([None] if None in groups else [])
    out: list[WaveTime] = []
    for wave in order:
        cards = sorted(groups[wave], key=lambda c: c.batch.id)
        per = {c.batch.id: _per_batch(ledger.batches[c.batch.id], now) for c in cards}
        out.append(
            WaveTime(
                wave=wave,
                batches=tuple(per),
                columns=_rows(per, 0, COLUMNS, longest=True),
                parties=_rows(per, 1, PARTIES, longest=False),
            )
        )
    return out


def _rows(
    per: dict[str, tuple[_Tally, _Tally]], which: int, keys: Sequence[str], *, longest: bool
) -> tuple[TimeRow, ...]:
    """One row per key some batch spent time in; *per* is in batch-id order, so the
    longest batch on a tie is the first id."""
    rows: list[TimeRow] = []
    for key in keys:
        hits = [(bid, parts[which][key]) for bid, parts in per.items() if key in parts[which]]
        if not hits:
            continue
        total = sum(secs for _, (secs, _m) in hits)
        mark = any(m for _, (_s, m) in hits)
        if longest:
            bid, (secs, top_mark) = max(hits, key=lambda h: h[1][0])
            rows.append(TimeRow(key, total, mark, bid, secs, top_mark))
        else:
            rows.append(TimeRow(key, total, mark))
    return tuple(rows)
