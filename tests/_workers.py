"""How many xdist workers `-n auto` starts (gh#1225).

`tests/conftest.py` answers xdist's `pytest_xdist_auto_num_workers` hook with
`auto_workers`. Pure so `tests/unit/test_auto_workers.py` can pin it.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

import pytest

ENV = "FR_PYTEST_WORKERS"
FLOOR = 2


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() not in {"", "0", "false", "no"}


def auto_workers(*, cpus: int, load1: float | None, env: Mapping[str, str]) -> int:
    """`FR_PYTEST_WORKERS` when set; every CPU in CI; else the CPUs the host's
    one-minute load leaves free, never fewer than `FLOOR`.

    The load lags by a minute, so sessions that start together still each see an
    idle host; the override is the way to bound those exactly.
    """
    raw = (env.get(ENV) or "").strip()
    if raw:
        try:
            n = int(raw)
        except ValueError:
            n = 0
        if n < 1:
            raise pytest.UsageError(f"{ENV}={raw!r}: expected a whole number of workers, 1 or more")
        return n
    if _truthy(env.get("CI")):
        return cpus
    free = cpus - round(load1 or 0.0)
    return max(FLOOR, min(cpus, free))


def host_load1() -> float | None:
    try:
        return os.getloadavg()[0]
    except OSError:
        return None
