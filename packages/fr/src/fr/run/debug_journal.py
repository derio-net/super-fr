"""The debug journal of a `fr-debugging` run (spec 2026-11-24-batch-merge-readiness R11).

The run names it: the `debug` step emits `debug: <debug-journal path>`, and every reader of
the journal (the record engine, the review evidence target, the derived `findings` gate and the
PR body) takes its slug from that path through `debug_slug`.
"""

from __future__ import annotations

from pathlib import Path

from fr.run.model import RunState

__all__ = ["debug_slug", "emitted_debug_path", "require_debug_slug"]


def emitted_debug_path(state: RunState) -> str | None:
    """The `debug` artifact the run's steps emitted, or `None` before it did."""
    return next(
        (r.emitted["debug"] for r in state.steps.values() if r.emitted and "debug" in r.emitted),
        None,
    )


def debug_slug(state: RunState) -> str | None:
    """The debug journal's slug (its file's stem), or `None` before the run emitted one."""
    rel = emitted_debug_path(state)
    return Path(rel).stem if rel else None


def require_debug_slug(state: RunState) -> str:
    """`debug_slug`, or a `RunStateError`: a gate that cannot read its journal refuses."""
    from fr.run.model import RunStateError

    slug = debug_slug(state)
    if slug is None:
        raise RunStateError(
            "cannot verify evidence — no debug journal recorded yet (resolve the step "
            "that emits `debug` first)"
        )
    return slug
