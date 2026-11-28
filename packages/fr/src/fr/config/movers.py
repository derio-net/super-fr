"""The scope of a MOVER of S1's old configuration forms (spec 2026-11-28-s1-followups R3).

`fr migrate artifacts` (and the CLI-entry migration), `fr settings init` creating the
configuration space from the old switch, `fr repos sync` and `fr repair` read and move the
old forms on both sides of the transition gate (`fr.config.transition`), so the refusal
never strands a repo. Inside `moving()` the readers read the old forms as before the gate.

This module imports nothing of fr's: the migration runner imports it at module load, and
`fr.config.transition` (which needs `fr.settings`) would close an import cycle there.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_MOVING: ContextVar[bool] = ContextVar("fr_transition_moving", default=False)


@contextmanager
def moving() -> Iterator[None]:
    """Read the old forms as a mover, on both sides of the gate."""
    token = _MOVING.set(True)
    try:
        yield
    finally:
        _MOVING.reset(token)


def mover[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Run *fn* inside `moving()`: the migration's own entry points."""

    @functools.wraps(fn)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        with moving():
            return fn(*args, **kwargs)

    return wrapped


def is_moving() -> bool:
    return _MOVING.get()
