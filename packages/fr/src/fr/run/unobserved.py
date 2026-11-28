"""The unobserved-gate channel (spec 2026-09-25 §5.B.7; moved by spec 2026-11-27-run-verdict R3).

A gate that cannot observe (no harness detected, no readable transcript) notes itself
here and prints a warning; the resolve then records the names under the unit's
`unobserved` evidence, so the gap is in the cursor, not only in a stderr nobody keeps.
The context variable holds no console, so run-engine code notes a gate here directly.

Engine code: no `typer`, no `rich`, no `fr.commands` (`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

import os
from contextvars import ContextVar

from fr.harness.detect import detect_harness
from fr.harness.model import HarnessError

UNOBSERVED: ContextVar[list[str] | None] = ContextVar("fr_unobserved", default=None)


def note_unobserved(gate: str) -> None:
    found = UNOBSERVED.get()
    if found is None:
        found = []
        UNOBSERVED.set(found)
    if gate not in found:
        found.append(gate)


def why_unobservable(what: str) -> str:
    """Why a gate could not observe `what` — the thing it reads from the
    transcript (`questions`, `subagent dispatches`, `commands`), so a gate
    never borrows another gate's noun (#815)."""
    from fr.run.observed import why_unobservable as _observed_why

    try:
        harness = detect_harness(os.environ)
    except HarnessError:
        harness = None
    return _observed_why(harness, os.environ, what)


TESTS_PROVENANCE_SURFACE = "deliver-tests-provenance"
"""The parity row declaring where `tests=<log>` provenance is verified."""


def why_tests_unobservable() -> str:
    """Why `tests=<log>` could not be tied to a command. Hermes is declared
    `unsupported` for this check (operator decision 2026-09-26, gh#638): say
    so by name rather than implying a reader is merely missing."""
    try:
        harness = detect_harness(os.environ)
    except HarnessError:
        harness = None
    if harness == "hermes":
        return f"tests= provenance is unsupported on hermes (parity row {TESTS_PROVENANCE_SURFACE})"
    if harness == "opencode":
        return "the OpenCode session database could not be read"
    return why_unobservable("commands")


def take_unobserved() -> dict[str, str]:
    """`{"unobserved": "<gate>,…"}` for every gate noted so far, and forget them."""
    from fr.run.telemetry import UNOBSERVED as UNOBSERVED_KEY

    found = UNOBSERVED.get() or []
    UNOBSERVED.set(None)
    return {UNOBSERVED_KEY: ",".join(found)} if found else {}
