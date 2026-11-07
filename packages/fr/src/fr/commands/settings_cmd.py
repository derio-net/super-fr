"""`fr settings` — the repo's feature settings (spec 2026-11-04-repo-feature-settings, R3).

Read-only for the artifact-migration gate (`fr.artifacts.trigger.READ_ONLY_COMMANDS`):
`init` writes `.fr/settings.yaml`, which is not a registered artifact, and never commits it.
"""

from __future__ import annotations

import json
from typing import Any

import typer
from pydantic import BaseModel

from fr.commands.common import resolve_repo_root
from fr.settings import SettingsError, load_settings
from fr.settings.check import check_settings
from fr.settings.load import SETTINGS_PATH

settings_app = typer.Typer(
    help="Per-repo feature settings: init, show, check.",
    no_args_is_help=True,
)


def _flatten(model: BaseModel, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, field in type(model).model_fields.items():
        value = getattr(model, name)
        key = f"{prefix}{field.alias or name}"
        if isinstance(value, BaseModel):
            out.update(_flatten(value, f"{key}."))
        else:
            out[key] = value
    return out


def _refuse(error: Exception) -> typer.Exit:
    typer.echo(str(error), err=True)
    return typer.Exit(2)


@settings_app.command("init")
def init_cmd(
    force: bool = typer.Option(False, "--force", help="Overwrite an existing file."),
) -> None:
    """Write `.fr/settings.yaml` with every key commented out at its default.

    Writes only; commit it (and land it on the default branch) yourself.
    """
    from fr.settings.render import render_init

    path = resolve_repo_root() / SETTINGS_PATH
    if path.exists() and not force:
        typer.echo(f"{SETTINGS_PATH} already exists; pass --force to overwrite it", err=True)
        raise typer.Exit(2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_init())
    typer.echo(f"wrote {path}")


@settings_app.command("show")
def show_cmd(
    as_json: bool = typer.Option(False, "--json", help="Print {key: {value, source}}."),
) -> None:
    """Print the effective settings and each key's source."""
    try:
        eff = load_settings(resolve_repo_root())
    except SettingsError as e:
        raise _refuse(e) from e
    values = _flatten(eff.settings)
    if as_json:
        typer.echo(
            json.dumps({k: {"value": v, "source": eff.sources[k]} for k, v in values.items()})
        )
        return
    width = max(len(k) for k in values)
    typer.echo(f"{'key'.ljust(width)}  {'value'.ljust(8)}  source")
    for key, value in values.items():
        typer.echo(f"{key.ljust(width)}  {str(value)[:40].ljust(8)}  {eff.sources[key]}")
    typer.echo(f"({eff.ref_note})")
    if eff.pending_edit:
        typer.echo(f"note: {eff.pending_edit}")


@settings_app.command("check")
def check_cmd() -> None:
    """Validate the settings: schema, servable placement, coherence."""
    try:
        problems = check_settings(resolve_repo_root())
    except SettingsError as e:
        raise _refuse(e) from e
    if problems:
        for problem in problems:
            typer.echo(f"{problem.id}: {problem.message}", err=True)
        raise typer.Exit(2)
    typer.echo("settings ok")
