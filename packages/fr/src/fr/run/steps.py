"""Run lookup: which step, unit and artifact a cursor names (spec 2026-11-27-run-verdict R4).

Slice 1 brings `emitted_plan` here, the one lookup the derived verifiers need; slice 2
moves the rest of `run_cmd.py`'s lookup cluster beside it.

Engine code: no `typer`, no `rich`, no `fr.commands` (`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

from fr.run.model import RunState


def emitted_plan(state: RunState) -> str | None:
    """The recorded repo-relative plan path, wherever the shape put it."""
    for record in state.steps.values():
        if record.emitted and "plan" in record.emitted:
            return record.emitted["plan"]
    return None
