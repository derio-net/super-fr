"""`fr settings` — the repo's feature settings (spec 2026-11-04-repo-feature-settings, R3)."""

from __future__ import annotations

import typer

settings_app = typer.Typer(
    help="Per-repo feature settings: init, show, check.",
    no_args_is_help=True,
)


@settings_app.command("init")
def init_cmd() -> None:
    """Write a fully commented defaults file."""


@settings_app.command("show")
def show_cmd() -> None:
    """Print the effective settings and each key's source."""


@settings_app.command("check")
def check_cmd() -> None:
    """Validate the settings."""
