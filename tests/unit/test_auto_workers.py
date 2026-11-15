"""`-n auto` leaves room for the other sessions on the host (gh#1225).

Four sessions each running `pytest -n auto` on a 16-thread host started 64
workers: load average ~800, suites 40-80 min instead of minutes, and the
wall-clock-bounded tests of gh#1280 failing. `-n auto` now asks
`tests/conftest.py`: `FR_PYTEST_WORKERS` when set, every CPU in CI (a runner
belongs to one job), else the CPUs the host's load leaves free, never fewer than 2.
"""

from __future__ import annotations

import pytest

from tests.conftest import auto_workers


def test_an_idle_host_gets_every_cpu() -> None:
    assert auto_workers(cpus=12, load1=0.4, env={}) == 12


def test_a_busy_host_gets_what_its_load_leaves() -> None:
    # Another session's suite holds ~8 CPUs busy.
    assert auto_workers(cpus=12, load1=8.2, env={}) == 4


def test_an_overloaded_host_still_gets_two() -> None:
    assert auto_workers(cpus=16, load1=300.0, env={}) == 2


def test_ci_ignores_the_load() -> None:
    assert auto_workers(cpus=4, load1=9.0, env={"CI": "true"}) == 4


def test_the_env_override_wins_everywhere() -> None:
    assert auto_workers(cpus=12, load1=0.0, env={"FR_PYTEST_WORKERS": "3"}) == 3
    assert auto_workers(cpus=4, load1=0.0, env={"CI": "true", "FR_PYTEST_WORKERS": "8"}) == 8


@pytest.mark.parametrize("bad", ["0", "-1", "four"])
def test_a_bad_override_is_refused_not_ignored(bad: str) -> None:
    with pytest.raises(pytest.UsageError, match="FR_PYTEST_WORKERS"):
        auto_workers(cpus=12, load1=0.0, env={"FR_PYTEST_WORKERS": bad})


def test_an_empty_override_is_unset_and_ci_false_is_not_ci() -> None:
    assert auto_workers(cpus=12, load1=8.0, env={"FR_PYTEST_WORKERS": ""}) == 4
    assert auto_workers(cpus=12, load1=8.0, env={"CI": "false"}) == 4


def test_an_unreadable_load_counts_as_idle() -> None:
    assert auto_workers(cpus=6, load1=None, env={}) == 6
