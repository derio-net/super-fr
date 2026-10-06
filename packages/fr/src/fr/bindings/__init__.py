"""Model bindings that survive provider churn (spec 2026-10-06-model-binding-churn).

`fr.models` stays the config layer (tier -> model strings). This package asks a
provider whether a bound model still answers (`probe`), reads the catalogue for
lineage and price (`catalogue`), picks a replacement by fixed rules (`choose`)
and reports a harness's bindings as a whole (`health`).
"""

from __future__ import annotations

import re

from fr.bindings.probe import OpenCodeProber, Prober

__all__ = [
    "default_prober_for",
    "prober_for",
    "valid_model_id",
    "valid_model_name",
    "valid_provider",
]

_PROVIDER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")


def valid_provider(provider: str) -> bool:
    return _PROVIDER.fullmatch(provider) is not None


def valid_model_name(model: str) -> bool:
    """A model id that cannot be read as a command-line option: ``provider/model``
    or a bare name, each part starting alphanumeric, with no whitespace and no
    ``=``. A binding can arrive from the tracked repo-layer models.yaml, so every
    value that reaches an argv passes this first."""
    head, sep, tail = model.partition("/")
    if not sep:
        return _MODEL.fullmatch(model) is not None
    return valid_provider(head) and _MODEL.fullmatch(tail) is not None


def valid_model_id(model: str) -> bool:
    """`valid_model_name`, and a provider is required: the shape OpenCode takes."""
    return "/" in model and valid_model_name(model)


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
