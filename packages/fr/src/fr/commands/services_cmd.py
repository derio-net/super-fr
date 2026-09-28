"""`fr services` — print the resolved forge / ci / tracking services (spec §3.F)."""

from __future__ import annotations

import json

import typer

from fr.commands.common import resolve_repo_root
from fr.services.resolve import resolve_services


def services_command(
    as_json: bool = typer.Option(False, "--json", help="Emit JSON keyed by service."),
) -> None:
    """Read-only: the resolved services with their type, host and source."""
    services = resolve_services(resolve_repo_root())
    f = services.forge
    typer.echo(json.dumps({"forge": {"type": f.type, "host": f.host, "source": f.source}}))
