"""Shared launch-model validation for dispatch and optional session operations."""

import re


def validate_model(harness: str, model: str) -> None:
    """Refuse malformed OpenCode selection before any launch/preparation side effect."""
    if harness == "opencode" and not re.fullmatch(r"[^/\s]+/[^\s]+", model):
        raise ValueError("OpenCode requires an explicit provider/model")
