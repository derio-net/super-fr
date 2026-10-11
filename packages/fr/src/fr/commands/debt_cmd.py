"""`fr debt` — what a repo owes, as one report (spec 2026-10-11-debt-engine, R1, R25).

Read-only: it writes nothing, which is why `debt` is in
`fr.artifacts.trigger.READ_ONLY_COMMANDS`. Exit 0 on a report, 2 on a usage
error (a bad `.fr/debt.yaml` or `--stale-days`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from fr.commands.common import resolve_repo_root

if TYPE_CHECKING:
    from fr.debt.engine import DebtForge

debt_app = typer.Typer(
    help="What this repo owes: acceptance, plans and owed actions (read-only).",
    invoke_without_command=True,
    no_args_is_help=False,
)


def _now() -> datetime:
    """The clock, one seam for tests."""
    return datetime.now(UTC)


def _forge(root: Path) -> tuple[DebtForge | None, str]:
    """The repo's forge adapter and, when there is none, the reason why."""
    try:
        from fr import _hosts
        from fr.commands.archive_cmd import _make_gh_client
        from fr.debt.forge import ClientDebtForge
        from fr.services.resolve import resolve_tracking

        if resolve_tracking(root, lenient=True).type == "none":
            return None, "tracking: none"
        slug = _hosts.origin_slug(root)
        if not slug:
            return None, "no origin remote to name the repository"
        return ClientDebtForge(_make_gh_client(), cwd=root, repo=slug), ""
    except Exception as e:
        return None, f"forge adapter unavailable ({type(e).__name__}: {e})"


@debt_app.callback()
def debt(
    ctx: typer.Context,
    json_out: Annotated[bool, typer.Option("--json", help="Print the report as JSON.")] = False,
    stale_days: Annotated[
        int | None,
        typer.Option("--stale-days", help="Days without activity before a plan is stale."),
    ] = None,
    offline: Annotated[
        bool, typer.Option("--offline", help="Do not touch the forge or the network.")
    ] = False,
) -> None:
    """Print the debt report (text, or JSON with --json)."""
    if ctx.invoked_subcommand is not None:
        return
    from fr.debt import render
    from fr.debt.engine import DebtConfigError, compute

    root = resolve_repo_root()
    try:
        forge, why = (None, "offline") if offline else _forge(root)
        report = compute(
            root, forge=forge, now=_now(), stale_days=stale_days, fetch=not offline, forge_why=why
        )
    except DebtConfigError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from e
    typer.echo(report.model_dump_json(indent=2) if json_out else render.text(report))
