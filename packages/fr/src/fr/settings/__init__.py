"""Per-repo feature settings (spec 2026-11-04-repo-feature-settings, R2-R5)."""

from __future__ import annotations

from pathlib import Path


class SettingsError(Exception):
    """The settings file (or the fr reading it) cannot be served; names file and key."""


def load_settings(repo_root: Path) -> object:
    return {}


def disabled(repo_root: Path, feature: str) -> bool:
    return False


def forge_allows(repo_root: Path, kind: str) -> bool:
    return True


__all__ = ["SettingsError", "disabled", "forge_allows", "load_settings"]
