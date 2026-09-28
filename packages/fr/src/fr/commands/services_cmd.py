"""`fr services` — print the resolved forge / ci / tracking services (spec §3.F)."""

from __future__ import annotations

import dataclasses
import json

import typer

from fr.commands.common import resolve_repo_root
from fr.services.resolve import resolve_services


def services_command(
    as_json: bool = typer.Option(False, "--json", help="Emit JSON keyed by service."),
) -> None:
    """Read-only: the resolved services with their type, host and source."""
    services = resolve_services(resolve_repo_root())
    typer.echo(json.dumps({"forge": dataclasses.asdict(services.forge)}))
