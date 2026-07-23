"""The repo ships `hermes:` tier defaults so fr-goal's phase dispatch can resolve
a model when running under Hermes (docs/superpowers/models.yaml is the repo
override `fr models` reads before user config)."""

from __future__ import annotations

from pathlib import Path

from fr.models import load_models
from fr.models import resolve as resolve_binding

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_YAML = REPO_ROOT / "docs" / "superpowers" / "models.yaml"


def test_models_yaml_ships_hermes_tiers() -> None:
    cfg = load_models(MODELS_YAML)
    assert set(cfg.get("hermes", {})) >= {"mechanical", "standard", "hard"}, (
        "docs/superpowers/models.yaml must bind all three tiers for the hermes harness"
    )


def test_resolve_hermes_tiers_from_repo_override() -> None:
    cfg = load_models(MODELS_YAML)
    for tier in ("mechanical", "standard", "hard"):
        model = resolve_binding("hermes", tier, repo_cfg=cfg, user_cfg={})
        assert model, f"hermes/{tier} should resolve to a non-empty model id"
