"""A sharded run schedules its longest tests first (gh#1428).

A CI shard's wall clock is its workers' serial work divided by the worker count,
plus the TAIL: a 135 s scenario test that xdist hands out near the end of the shard
runs alone while the other workers idle (run 43639946152, shard py3.14/2: the last
8% of the progress bar took 77 s). Longest-first order with one-test scheduling
chunks is greedy LPT scheduling, which bounds that tail by the shortest tests
instead of the longest.
"""

from __future__ import annotations

from types import SimpleNamespace

from tests._shard_order import longest_first, scheduling_options


def test_known_tests_run_longest_first() -> None:
    durations = {"a": 1.0, "b": 9.0, "c": 3.0}
    assert longest_first(["a", "b", "c"], durations) == ["b", "c", "a"]


def test_an_unmeasured_test_counts_as_the_average_like_pytest_split() -> None:
    # The known durations average 4.0, so the new test sits between 7.0 and 1.0.
    durations = {"a": 1.0, "b": 7.0}
    assert longest_first(["new", "a", "b"], durations) == ["b", "new", "a"]


def test_equal_durations_keep_collection_order() -> None:
    durations = {"a": 2.0, "b": 2.0, "c": 2.0}
    assert longest_first(["c", "a", "b"], durations) == ["c", "a", "b"]


def test_no_durations_leaves_the_order_alone() -> None:
    assert longest_first(["b", "a"], {}) == ["b", "a"]


def _opt(**kw: object) -> SimpleNamespace:
    base: dict[str, object] = {"splits": None, "numprocesses": None, "maxschedchunk": None}
    base.update(kw)
    return SimpleNamespace(**base)


def test_a_sharded_xdist_run_schedules_one_test_at_a_time() -> None:
    # Without it xdist's `load` scheduler hands each worker a contiguous quarter
    # of its share up front, so longest-first would give ONE worker every long test.
    assert scheduling_options(_opt(splits=6, numprocesses=4)) == {"maxschedchunk": 1}


def test_an_explicit_maxschedchunk_wins() -> None:
    assert scheduling_options(_opt(splits=6, numprocesses=4, maxschedchunk=8)) == {}


def test_an_unsharded_or_serial_run_is_untouched() -> None:
    assert scheduling_options(_opt(numprocesses=4)) == {}
    assert scheduling_options(_opt(splits=6)) == {}
    assert scheduling_options(_opt(splits=6, numprocesses=0)) == {}
