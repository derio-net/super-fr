"""`fr services` — print the resolved forge / ci / tracking services (spec
2026-09-28-fr-profiles-services §3.F, R7).

Read-only: it reads `.devcontainer/fr-profiles.yaml` and the repo's CI files
and writes nothing, so it is in `fr.artifacts.trigger.READ_ONLY_COMMANDS` and
keeps working on an unmigrated repo (a version-1 file shows `legacy`).
"""

from __future__ import annotations

import json

import typer

from fr.commands.common import resolve_repo_root
from fr.services.model import ResolvedService, Services, ServicesError
from fr.services.resolve import SERVICE_KEYS, resolve_services

NO_HOST = "—"


def services_json(services: Services) -> dict[str, dict[str, str | None]]:
    """The `--json` shape: an object keyed by service."""
    return {
        key: {"type": s.type, "host": s.host, "source": s.source}
        for key in SERVICE_KEYS
        for s in [getattr(services, key)]
    }


def _source_label(key: str, service: ResolvedService) -> str:
    # An undeclared ci / tracking that is not `none` is the forge's own system.
    if key != "forge" and service.source == "default" and service.type != "none":
        return "default (forge's own)"
    return service.source


def services_table(services: Services) -> str:
    """The plain output: one aligned line per service."""
    lines = []
    for key in SERVICE_KEYS:
        service: ResolvedService = getattr(services, key)
        host = service.host or NO_HOST
        lines.append(f"{key:<9} {service.type:<15} {host:<20} {_source_label(key, service)}")
    return "\n".join(lines)


def services_command(
    as_json: bool = typer.Option(False, "--json", help="Emit JSON keyed by service."),
) -> None:
    """Read-only: each resolved service with its type, host and source
    (`declared`, `default`, or `legacy` for an unmigrated file)."""
    try:
        services = resolve_services(resolve_repo_root())
    except ServicesError as exc:
        typer.echo(f"fr services: {exc}", err=True)
        raise typer.Exit(2) from exc
    if as_json:
        typer.echo(json.dumps(services_json(services), indent=2))
    else:
        typer.echo(services_table(services))
