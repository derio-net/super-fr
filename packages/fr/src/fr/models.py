"""Tier→model binding config, backing `fr models` (spec §B.2).

`tier` on a phase is harness-neutral; the concrete model is resolved at dispatch
from config, mirroring the `~/.config/fr/repos.yaml` user-config pattern
(`fr.repos`). Resolution order is repo override > user config; a missing binding
returns ``None`` so the caller (fr-goal) can fall back to a runtime prompt and
persist the answer.

Config shape (``harness → tier → model``)::

    claude-code:
      mechanical: claude-haiku-4-5
      standard: claude-sonnet-5
      hard: claude-opus-4-8
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

ModelsConfig = dict[str, dict[str, str]]


class ModelsError(Exception):
    """Raised when a models config file is structurally invalid."""


def default_models_path() -> Path:
    """User-level models config, honoring ``$XDG_CONFIG_HOME`` then ``$HOME``."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "fr" / "models.yaml"


def load_models(path: Path) -> ModelsConfig:
    """Parse a ``harness → tier → model`` mapping. A missing file yields ``{}``."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    if not isinstance(raw, dict):
        raise ModelsError(f"{path}: top level must be a harness→tier→model mapping")
    out: ModelsConfig = {}
    for harness, tiers in raw.items():
        if not isinstance(tiers, dict):
            raise ModelsError(f"{path}: harness '{harness}' must map tiers to models")
        out[harness] = {str(t): str(m) for t, m in tiers.items()}
    return out


def resolve(
    harness: str,
    tier: str,
    *,
    repo_cfg: ModelsConfig,
    user_cfg: ModelsConfig,
) -> str | None:
    """Resolve ``(harness, tier) → model`` with repo overriding user; else None."""
    for cfg in (repo_cfg, user_cfg):
        model = cfg.get(harness, {}).get(tier)
        if model:
            return model
    return None


def set_binding(path: Path, harness: str, tier: str, model: str) -> None:
    """Persist one ``harness/tier → model`` binding, preserving other entries."""
    cfg = load_models(path)
    cfg.setdefault(harness, {})[tier] = model
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cfg, sort_keys=True))
