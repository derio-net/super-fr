"""A subprocess's timeout grows with the xdist worker count (gh#629, gh#640).

A child that finishes in about 2 s alone overran a fixed 120 s budget during a
loaded `pytest -n auto` run on a macOS host: every worker competes for the same
cores, so a budget sized for a serial run is too small for a parallel one.
"""

from __future__ import annotations

from tests.conftest import subprocess_timeout


def test_a_serial_run_keeps_the_budget_as_written() -> None:
    assert subprocess_timeout(120, env={}) == 120


def test_the_budget_scales_with_the_worker_count() -> None:
    assert subprocess_timeout(120, env={"PYTEST_XDIST_WORKER_COUNT": "12"}) == 1440


def test_an_unreadable_worker_count_falls_back_to_the_written_budget() -> None:
    assert subprocess_timeout(120, env={"PYTEST_XDIST_WORKER_COUNT": "auto"}) == 120
    assert subprocess_timeout(120, env={"PYTEST_XDIST_WORKER_COUNT": "0"}) == 120
