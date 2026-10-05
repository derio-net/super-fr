"""Reshape a drifted run cursor onto the current step list (spec
2026-10-05-run-upgrade-midflight §A)."""

from __future__ import annotations

from fr.run.model import RunState
from fr.workflow.model import WorkflowManifest


class ReshapeError(Exception):
    """A reshape the rules refuse; nothing is written."""


def reshape(state: RunState, manifest: WorkflowManifest) -> RunState:
    """`state` rewritten onto `manifest`'s step list, or `ReshapeError`."""
    return state
