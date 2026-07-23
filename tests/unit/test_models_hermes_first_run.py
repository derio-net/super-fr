"""super-fr must NOT ship guessed `hermes:` model bindings.

fr-goal's contract (SKILL.md step 1 / step 6) is: when `fr models resolve` is
unbound for the harness, ASK the operator for a model per tier and persist it
with `fr models set`. Shipping repo-level defaults defeats that — an invented
model id resolves successfully, the first-run question never fires, and the
operator silently inherits a wrong (possibly non-existent) model.

An earlier revision of this feature shipped fabricated `NousResearch/Hermes-4-*`
ids. This guard exists so they cannot come back: the repo override must carry no
`hermes` bindings, leaving resolution unbound so the question is reachable.
"""

from __future__ import annotations

from pathlib import Path

from fr.models import load_models
from fr.models import resolve as resolve_binding

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_MODELS = REPO_ROOT / "docs" / "superpowers" / "models.yaml"


def test_repo_override_ships_no_hermes_bindings() -> None:
    cfg = load_models(REPO_MODELS) if REPO_MODELS.exists() else {}
    assert not cfg.get("hermes"), (
        "super-fr must not ship guessed hermes model ids — fr-goal asks the "
        f"operator on first run when unbound. Found: {cfg.get('hermes')!r}"
    )


def test_hermes_tiers_resolve_unbound_so_fr_goal_asks() -> None:
    cfg = load_models(REPO_MODELS) if REPO_MODELS.exists() else {}
    for tier in ("mechanical", "standard", "hard"):
        assert resolve_binding("hermes", tier, repo_cfg=cfg, user_cfg={}) is None, (
            f"hermes/{tier} must be unbound in-repo so fr-goal's model-per-tier "
            "question fires on the first Hermes run"
        )
