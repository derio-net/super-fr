"""Per-repo feature settings (spec 2026-11-04-repo-feature-settings, R2-R5)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path

    from fr.settings.load import EffectiveSettings

POLICY_FEATURES: Final = ("acceptance", "test_plan", "gates")
"""The `artifacts.*` keys: policy kinds only. spec, plan, journals and runs have no key."""
FORGE_KINDS: Final = ("labels", "comments", "issues")


class SettingsError(Exception):
    """The settings file (or the fr reading it) cannot be served; names file and key."""


def load_settings(repo_root: Path) -> EffectiveSettings:
    """The effective settings of *repo_root* (see `fr.settings.load`)."""
    from fr.settings.load import load_settings as _load

    return _load(repo_root)


def disabled(repo_root: Path, feature: str) -> bool:
    """Whether the repo turned *feature* (`acceptance`, `test_plan`, `gates`) off."""
    if feature not in POLICY_FEATURES:
        raise ValueError(f"{feature!r} has no setting; policy features are {POLICY_FEATURES}")
    return bool(getattr(load_settings(repo_root).settings.artifacts, feature) == "off")


def forge_allows(repo_root: Path, kind: str) -> bool:
    """Whether fr may write *kind* (`labels`, `comments`, `issues`) to the forge."""
    if kind not in FORGE_KINDS:
        raise ValueError(f"{kind!r} is not a forge write kind; kinds are {FORGE_KINDS}")
    return bool(getattr(load_settings(repo_root).settings.forge, kind) == "on")


__all__ = ["SettingsError", "disabled", "forge_allows", "load_settings"]
