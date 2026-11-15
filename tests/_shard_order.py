"""Longest-first scheduling for a sharded xdist run (gh#1428).

`tests/conftest.py` wires these in. Pure so `tests/unit/test_shard_order.py` can
pin them without starting a pytest session.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def longest_first(nodeids: Sequence[str], durations: Mapping[str, float]) -> list[str]:
    """`nodeids` ordered by recorded duration, longest first.

    A test with no recorded duration counts as the average, as pytest-split counts
    it when it splits. The sort is stable, so equal durations keep collection order
    (every xdist worker must compute the identical order).
    """
    if not durations:
        return list(nodeids)
    avg = sum(durations.values()) / len(durations)
    return sorted(nodeids, key=lambda n: -durations.get(n, avg))


def scheduling_options(option: Any) -> dict[str, int]:
    """The xdist options a sharded run needs for longest-first order to work.

    xdist's `load` scheduler sends each worker a contiguous chunk of the queue (a
    quarter of its share) up front, so a longest-first queue would give one worker
    every long test. One-test chunks make it greedy: whichever worker frees up takes
    the next-longest test. Only a sharded (`--splits`), parallel run is changed, and
    never over an explicit `--maxschedchunk`.
    """
    if not getattr(option, "splits", None) or not getattr(option, "numprocesses", None):
        return {}
    if getattr(option, "maxschedchunk", None) is not None:
        return {}
    return {"maxschedchunk": 1}
