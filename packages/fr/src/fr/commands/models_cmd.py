"""`fr models ...` CLI — tier→model bindings for subagent dispatch (spec §B.2).

- ``set``     persist a harness/tier → model binding to the user config.
- ``get``     print the raw config (or one harness's tiers).
- ``resolve`` print the model for a harness+tier (repo override > user);
              prints nothing + exits 0 when unbound, so fr-goal can detect
              "ask the operator" without parsing an error.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from fr.commands.common import resolve_repo_root
from fr.models import (
    default_models_path,
    load_models,
    set_binding,
)
from fr.models import (
    resolve as resolve_binding,
)

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

models_app = typer.Typer(
    help="Tier→model bindings for fr-goal subagent dispatch (harness-keyed).",
    no_args_is_help=True,
)

REPO_MODELS_REL = Path("docs/superpowers/models.yaml")


def _repo_cfg() -> dict[str, dict[str, str]]:
    try:
        root = resolve_repo_root()
    except Exception:
        return {}
    return load_models(root / REPO_MODELS_REL)


@models_app.command("set")
def set_cmd(
    harness: str = typer.Option(..., "--harness", help="e.g. claude-code | opencode | hermes."),
    tier: str = typer.Option(..., "--tier", help="mechanical | standard | hard."),
    model: str = typer.Option(..., "--model", help="Concrete model id for this harness+tier."),
) -> None:
    """Persist a binding to ~/.config/fr/models.yaml."""
    path = default_models_path()
    set_binding(path, harness, tier, model)
    console.print(f"set {harness}/{tier} → {model} ({path})")


@models_app.command("get")
def get_cmd(
    harness: str | None = typer.Option(None, "--harness", help="Limit to one harness."),
) -> None:
    """Print the user model config (optionally one harness)."""
    import yaml

    cfg = load_models(default_models_path())
    if harness is not None:
        cfg = {harness: cfg.get(harness, {})}
    console.print(yaml.safe_dump(cfg, sort_keys=True).rstrip() or "{}")


@models_app.command("resolve")
def resolve_cmd(
    harness: str = typer.Option(..., "--harness"),
    tier: str = typer.Option(..., "--tier"),
) -> None:
    """Print the bound model, or nothing (exit 0) when unbound."""
    model = resolve_binding(
        harness, tier, repo_cfg=_repo_cfg(), user_cfg=load_models(default_models_path())
    )
    if model:
        console.print(model)
