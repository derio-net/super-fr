"""Model bindings that survive provider churn (spec 2026-10-06-model-binding-churn).

`fr.models` stays the config layer (tier -> model strings). This package asks a
provider whether a bound model still answers (`probe`), reads the catalogue for
lineage and price (`catalogue`), picks a replacement by fixed rules (`choose`)
and reports a harness's bindings as a whole (`health`).
"""

from __future__ import annotations

from fr.bindings.ids import valid_model_id, valid_model_name, valid_provider
from fr.bindings.probe import OpenCodeProber, Prober

__all__ = [
    "default_prober_for",
    "prober_for",
    "valid_model_id",
    "valid_model_name",
    "valid_provider",
]


def default_prober_for(harness: str) -> Prober | None:
    """Only OpenCode can be probed: Claude Code's `claude -p` is forbidden by
    `no-claude-p-batch`, and Hermes has no probe surface (spec §1 non-goals), so
    those harnesses get ``None`` and report ``unprobed``."""
    return OpenCodeProber() if harness == "opencode" else None


def prober_for(harness: str) -> Prober | None:
    """THE factory every caller reaches a prober through — `fr models`, `fr run`.
    Tests monkeypatch THIS name (callers use ``fr.bindings.prober_for(...)``,
    never a ``from`` import, so the patch lands); `default_prober_for` is what it
    does until they do."""
    return default_prober_for(harness)
