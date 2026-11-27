"""The dwell ledger (spec 2026-11-27-board-session-state §D, R5-R7).

`observe` is driven with a fake clock over boards built from one template card; nothing
here reads the wall clock, a forge or a runner.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fr.triage import dwell
from fr.triage.dwell import (
    CAP,
    DWELL_FILE,
    Entry,
    Interval,
    Ledger,
    card_dwell,
    format_duration,
    load,
    observe,
    store,
    wave_time,
)
from fr.triage.kanban import COLUMN_TITLES, COLUMNS, Board, Card, ColumnView, build_board
from fr.triage.waits import Wait

from tests.unit.triage_board_fixtures import batch, facts, issue, j, judgements

T0 = datetime(2026, 11, 27, 9, 0, tzinfo=UTC)


def _template() -> Card:
    f = facts([issue(1)])
    return build_board(f, judgements({"widgets#1": j(1)}, [batch("a", [1])]), {}).card("a")


TEMPLATE = _template()


def _card(bid: str, column: str, wait: str | None, wave: int | None = None) -> Card:
    return replace(
        TEMPLATE,
        batch=TEMPLATE.batch.model_copy(update={"id": bid}),
        column=column,  # type: ignore[arg-type]
        wait=None if wait is None else Wait(wait),  # type: ignore[arg-type]
        wave=wave,
    )


def _board(*cards: Card) -> Board:
    return Board(
        scope="repo:example-org/widgets",
        collected_at="2026-11-27T09:00:00Z",
        columns=tuple(
            ColumnView(k, COLUMN_TITLES[k], tuple(c for c in cards if c.column == k))
            for k in COLUMNS
        ),
    )


def _at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


# ----------------------------------------------------------------- observe


def test_a_new_batch_starts_both_sinces_now_and_marks_both_first_seen() -> None:
    led = observe(Ledger(), _board(_card("a", "running", "agent")), T0)
    e = led.batches["a"]
    assert (e.column, e.column_since, e.column_first_seen) == ("running", T0, True)
    assert (e.wait, e.wait_since, e.wait_first_seen) == ("agent", T0, True)
    assert e.intervals == () and e.truncated is False


def test_an_unchanged_board_keeps_the_entry() -> None:
    board = _board(_card("a", "running", "agent"))
    first = observe(Ledger(), board, T0)
    assert observe(first, board, _at(30)) == first


def test_a_column_change_closes_an_interval_and_restarts_only_the_column() -> None:
    led = observe(Ledger(), _board(_card("a", "running", "agent")), T0)
    led = observe(led, _board(_card("a", "running", "ci")), _at(10))  # wait only
    led = observe(led, _board(_card("a", "pr-open", "ci")), _at(25))
    e = led.batches["a"]
    assert e.intervals == (
        Interval(column="running", wait="agent", start=T0, end=_at(10), first_seen=True),
        Interval(column="running", wait="ci", start=_at(10), end=_at(25), first_seen=False),
    )
    assert (e.column, e.column_since, e.column_first_seen) == ("pr-open", _at(25), False)
    assert (e.wait, e.wait_since, e.wait_first_seen) == ("ci", _at(10), False)


def test_a_wait_only_change_keeps_column_since_and_its_first_seen() -> None:
    led = observe(Ledger(), _board(_card("a", "running", "agent")), T0)
    led = observe(led, _board(_card("a", "running", None)), _at(5))
    e = led.batches["a"]
    assert (e.column_since, e.column_first_seen) == (T0, True)
    assert (e.wait, e.wait_since, e.wait_first_seen) == (None, _at(5), False)
    assert e.intervals[-1].first_seen is True  # it started at the first sighting


def test_the_interval_start_is_the_later_since_with_that_since_first_seen() -> None:
    led = observe(Ledger(), _board(_card("a", "running", "agent")), T0)
    led = observe(led, _board(_card("a", "pr-open", "agent")), _at(10))  # column restarted
    led = observe(led, _board(_card("a", "pr-open", "ci")), _at(30))
    last = led.batches["a"].intervals[-1]
    assert (last.start, last.first_seen) == (_at(10), False)  # column_since, not first-seen


def test_a_departed_batch_is_dropped() -> None:
    led = observe(Ledger(), _board(_card("a", "running", "agent"), _card("b", "done", None)), T0)
    led = observe(led, _board(_card("b", "done", None)), _at(1))
    assert set(led.batches) == {"b"}


def test_the_interval_past_the_cap_drops_the_oldest_and_marks_truncated() -> None:
    led = observe(Ledger(), _board(_card("a", "running", "agent")), T0)
    for n in range(1, CAP + 2):
        led = observe(led, _board(_card("a", "running", "ci" if n % 2 else "agent")), _at(n))
    e = led.batches["a"]
    assert len(e.intervals) == CAP and e.truncated is True
    assert e.intervals[0].start == _at(1)  # the first (T0 .. 1m) was dropped
    assert CAP == 200


def test_exactly_the_cap_is_not_truncated() -> None:
    led = observe(Ledger(), _board(_card("a", "running", "agent")), T0)
    for n in range(1, CAP + 1):
        led = observe(led, _board(_card("a", "running", "ci" if n % 2 else "agent")), _at(n))
    assert len(led.batches["a"].intervals) == CAP and led.batches["a"].truncated is False


def test_observe_does_not_mutate_its_input() -> None:
    led = observe(Ledger(), _board(_card("a", "running", "agent")), T0)
    before = led.model_dump()
    observe(led, _board(_card("a", "done", None)), _at(9))
    assert led.model_dump() == before


# ------------------------------------------------------------- load / store


def test_load_of_a_missing_file_is_empty_with_no_note(tmp_path: Path) -> None:
    assert load(tmp_path) == (Ledger(), None)


def test_load_of_garbage_is_empty_with_a_note(tmp_path: Path) -> None:
    (tmp_path / DWELL_FILE).write_text("{not json", encoding="utf-8")
    led, note = load(tmp_path)
    assert led == Ledger() and note is not None and DWELL_FILE in note


def test_load_of_a_wrong_schema_is_empty_with_a_note(tmp_path: Path) -> None:
    (tmp_path / DWELL_FILE).write_text('{"schema": 99, "batches": {}}', encoding="utf-8")
    led, note = load(tmp_path)
    assert led == Ledger() and note is not None


def test_load_of_non_utf8_is_empty_with_a_note(tmp_path: Path) -> None:
    (tmp_path / DWELL_FILE).write_bytes(b"\xff\xfe")
    led, note = load(tmp_path)
    assert led == Ledger() and note is not None


def test_store_round_trips_and_writes_the_schema_key(tmp_path: Path) -> None:
    led = observe(Ledger(), _board(_card("a", "running", "agent")), T0)
    led = observe(led, _board(_card("a", "pr-open", "ci")), _at(7))
    store(tmp_path, led)
    text = (tmp_path / DWELL_FILE).read_text(encoding="utf-8")
    assert '"schema": 1' in text
    assert load(tmp_path) == (led, None)
    assert [p.name for p in tmp_path.iterdir()] == [DWELL_FILE]  # atomic: no temp left


def test_dwell_reads_no_clock() -> None:
    src = Path(dwell.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in src and "time.time" not in src


# --------------------------------------------------------------- durations


def test_format_duration_boundaries() -> None:
    assert format_duration(0) == "0m"
    assert format_duration(59) == "0m"
    assert format_duration(60) == "1m"
    assert format_duration(45 * 60) == "45m"
    assert format_duration(3599) == "59m"
    assert format_duration(3600) == "1h 0m"
    assert format_duration(3 * 3600 + 12 * 60) == "3h 12m"
    assert format_duration(86399) == "23h 59m"
    assert format_duration(86400) == "1d 0h"
    assert format_duration(2 * 86400 + 4 * 3600 + 59 * 60) == "2d 4h"
    assert format_duration(-5) == "0m"


def _entry(**kw: object) -> Entry:
    base: dict[str, object] = {
        "column": "running", "column_since": T0, "column_first_seen": False,
        "wait": "agent", "wait_since": T0, "wait_first_seen": False,
    }  # fmt: skip
    base.update(kw)
    return Entry(**base)  # type: ignore[arg-type]


def test_card_dwell_names_column_and_party() -> None:
    card = _card("a", "running", "agent")
    line = card_dwell(_entry(wait_since=_at(30)), card, _at(75))
    assert line == "in Running 1h 15m · waits for agent 45m"


def test_card_dwell_marks_each_first_seen_part() -> None:
    card = _card("a", "pr-open", "ci")
    e = _entry(column="pr-open", column_first_seen=True, wait="ci", wait_since=_at(60))
    assert card_dwell(e, card, _at(60 * 50)) == "in PR open ≥2d 2h · waits for ci 2d 1h"
    e2 = _entry(column="pr-open", wait="ci", wait_first_seen=True)
    assert card_dwell(e2, card, _at(5)) == "in PR open 5m · waits for ci ≥5m"


def test_card_dwell_shows_only_the_column_when_the_card_has_no_wait() -> None:
    card = _card("a", "done", None)
    e = _entry(column="done", wait=None)
    assert card_dwell(e, card, _at(3 * 24 * 60)) == "in Done 3d 0h"


# --------------------------------------------------------------- wave time


def test_wave_time_sums_a_two_batch_wave_and_names_the_longest() -> None:
    a, b = _card("a", "running", "agent", 1), _card("b", "running", "agent", 1)
    led = observe(Ledger(), _board(a, b), T0)
    led = led.model_copy(
        update={
            "batches": {
                k: v.model_copy(update={"column_first_seen": False, "wait_first_seen": False})
                for k, v in led.batches.items()
            }
        }
    )
    led = observe(led, _board(replace(a, column="pr-open", wait=Wait("ci")), b), _at(60))
    a2 = replace(a, column="pr-open", wait=Wait("ci"))
    now = _at(90)
    waves = wave_time(led, _board(a2, b), now)
    assert [w.wave for w in waves] == [1]
    w = waves[0]
    rows = {r.key: r for r in w.columns}
    assert rows["running"].seconds == 60 * 60 + 90 * 60  # a's closed hour, b's open 90m
    assert rows["running"].longest == "b" and rows["running"].longest_seconds == 90 * 60
    assert rows["pr-open"].seconds == 30 * 60 and rows["pr-open"].longest == "a"
    assert not any(r.at_least for r in w.columns)
    parties = {r.key: r for r in w.parties}
    assert parties["agent"].seconds == 150 * 60 and parties["ci"].seconds == 30 * 60
    assert [r.key for r in w.columns] == ["running", "pr-open"]  # board order
    assert [r.key for r in w.parties] == ["agent", "ci"]  # PARTIES order


def test_wave_time_marks_at_least_for_first_seen_and_truncated() -> None:
    a, b = _card("a", "running", "agent", 2), _card("b", "pr-open", "ci", 2)
    led = observe(Ledger(), _board(a, b), T0)  # both first-seen
    w = wave_time(led, _board(a, b), _at(10))[0]
    assert all(r.at_least for r in (*w.columns, *w.parties))
    e = led.batches["b"].model_copy(
        update={"column_first_seen": False, "wait_first_seen": False, "truncated": True}
    )
    led2 = led.model_copy(update={"batches": {**led.batches, "b": e}})
    w2 = wave_time(led2, _board(b), _at(10))[0]
    assert {r.key: r.at_least for r in w2.columns} == {"pr-open": True}


def test_wave_time_puts_the_batches_with_no_wave_last() -> None:
    cards = (_card("a", "running", "agent", 3), _card("n", "running", "agent"),
             _card("c", "running", "agent", 1))  # fmt: skip
    led = observe(Ledger(), _board(*cards), T0)
    assert [w.wave for w in wave_time(led, _board(*cards), _at(1))] == [1, 3, None]


def test_wave_time_leaves_out_the_done_column() -> None:
    cards = (_card("a", "done", None, 1),)
    led = observe(Ledger(), _board(*cards), T0)
    w = wave_time(led, _board(*cards), _at(60))
    assert w and w[0].columns == () and w[0].parties == ()
