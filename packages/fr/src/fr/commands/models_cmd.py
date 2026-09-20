"""`fr models ...` CLI — tier→model bindings for subagent dispatch (spec §B.2).

- ``set``     persist a harness/tier → model binding to the user config, then
              materialize it into any on-disk OpenCode agent files it affects
              (spec 2026-09-20-opencode-tier-binding-reaches-dispatch §3.A) —
              a binding a caller answers must take effect in the run that
              made it, not wait for the next install.
- ``get``     print the raw config (or one harness's tiers).
- ``resolve`` print the model for a harness+tier (repo override > user);
              prints nothing + exits 0 when unbound, so fr-goal can detect
              "ask the operator" without parsing an error.
- ``apply``   re-run the materialiser for one harness over the CURRENT
              resolved config. install.sh's OpenCode delivery step calls
              this instead of resolving per tier and rewriting frontmatter
              in bash (§3.A's second trigger).
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from fr.commands.common import resolve_repo_root
from fr.models import (
    ModelsConfig,
    default_models_path,
    load_models,
    resolved_config,
    set_binding,
)
from fr.opencode_agents import Change, default_config_home, materialize_agents

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

models_app = typer.Typer(
    help="Tier→model bindings for fr-goal subagent dispatch (harness-keyed).",
    no_args_is_help=True,
)

REPO_MODELS_REL = Path("docs/superpowers/models.yaml")

# Harnesses `fr models apply` knows how to materialize. Checked up front so a
# typo'd --harness is refused rather than silently doing nothing — the exact
# failure class (a step that reports success while doing nothing) this whole
# spec exists to close one layer up.
_APPLY_HARNESSES = {"opencode"}


def _repo_cfg() -> ModelsConfig:
    try:
        root = resolve_repo_root()
    except Exception:
        return {}
    return load_models(root / REPO_MODELS_REL)


def _resolved_config() -> ModelsConfig:
    """This machine's repo-over-user model map.

    The layering rule itself lives in `fr.models.resolved_config`, which
    `fr.models.resolve` is also defined on — this function only supplies the
    two config files. Reimplementing the merge here left the rule written
    twice and the two disagreeing on a falsy repo binding (review r-p2-f2)."""
    return resolved_config(repo_cfg=_repo_cfg(), user_cfg=load_models(default_models_path()))


def _report_changes(changes: list[Change]) -> None:
    """Print exactly what the materialiser did, or that there was nothing to
    do. A silent side effect on a path outside the repo, or a report that
    claims a write that never happened, are both the defect this spec fixes
    one layer in (review r-p1-f3) — this is the one place both `set` and
    `apply` print through, so neither can reintroduce it."""
    if not changes:
        console.print("nothing to update (no OpenCode agent files found)")
        return
    for change in changes:
        if change.problem is not None:
            err_console.print(f"  WARNING: {change.path} not updated — {change.problem}")
        elif change.new_model is None:
            console.print(f"  {change.path}: unbound, model: key removed")
        else:
            console.print(f"  {change.path}: model: {change.new_model}")


@models_app.command("set")
def set_cmd(
    harness: str = typer.Option(..., "--harness", help="e.g. claude-code | opencode | hermes."),
    tier: str = typer.Option(..., "--tier", help="mechanical | standard | hard."),
    model: str = typer.Option(..., "--model", help="Concrete model id for this harness+tier."),
) -> None:
    """Persist a binding to ~/.config/fr/models.yaml, then materialize it
    into any on-disk OpenCode agent files it affects."""
    path = default_models_path()
    set_binding(path, harness, tier, model)
    console.print(f"set {harness}/{tier} → {model} ({path})")
    changes = materialize_agents(default_config_home(), models_cfg=_resolved_config())
    _report_changes(changes)


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
    model = _resolved_config().get(harness, {}).get(tier)
    if model:
        console.print(model)


@models_app.command("apply")
def apply_cmd(
    harness: str = typer.Option(..., "--harness", help="Harness to materialize bindings for."),
) -> None:
    """Re-run the materialiser for one harness over the current resolved
    config. This is what install.sh's OpenCode delivery step calls instead
    of resolving per tier and rewriting frontmatter in bash."""
    if harness not in _APPLY_HARNESSES:
        err_console.print(
            f"error: unknown harness {harness!r} for `fr models apply` "
            f"(known: {', '.join(sorted(_APPLY_HARNESSES))})"
        )
        raise typer.Exit(code=2)
    changes = materialize_agents(default_config_home(), models_cfg=_resolved_config())
    _report_changes(changes)
