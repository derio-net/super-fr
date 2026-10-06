"""THE one write path for a binding change (spec 2026-10-06-model-binding-churn
§B): persist it to the user `models.yaml`, then materialise the OpenCode agent
files that carry it.

`fr models set/check` (an operator's yes) and `fr run advance`'s pre-dispatch
guard (fr's own pick) both end here, so a binding takes effect the same way
whoever decided it. Reporting is the caller's: the guard wraps this in its
restore, `fr models` prints what changed.
"""

from __future__ import annotations

from pathlib import Path

from fr.models import ModelsConfig, load_models, resolved_config, set_binding
from fr.opencode_agents import MaterializeResult, default_config_home, materialize_agents


def materialize_from(models_path: Path, repo_cfg: ModelsConfig) -> MaterializeResult:
    """Rewrite the agent files from the repo-over-user map as it stands on disk."""
    cfg = resolved_config(repo_cfg=repo_cfg, user_cfg=load_models(models_path))
    return materialize_agents(default_config_home(), models_cfg=cfg)


def apply_binding(
    models_path: Path, harness: str, tier: str, model: str, *, repo_cfg: ModelsConfig
) -> MaterializeResult:
    """`set_binding`, then `materialize_agents` over the resulting map. Raises
    whatever either raises; a file the materialiser could not rewrite is in
    the result's `changes` with its `problem`, never an exception."""
    set_binding(models_path, harness, tier, model)
    return materialize_from(models_path, repo_cfg)
