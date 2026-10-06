"""`fr verification ...` CLI — resolve + validate verification strategies
(spec 2026-10-06-verification-strategies §A, R2).

`list` shows every strategy that resolves and where it came from. `check
[<name> | --all]` refuses a malformed manifest — whether a parse-time
`StrategyError` (unknown key, bad `when`/`driver`, unknown placeholder) or a
semantic `check_strategy` finding — through one report. Like `fr workflow
check --all`, `--all` FAILS when there is nothing to validate: a broken
installation is not a clean bill of health.

The group is deliberately NOT in `fr.artifacts.trigger.READ_ONLY_COMMANDS`: a
later subcommand (`walk`) reads the matrix with the live parser and must not
run over a stale one, and the gate exempts top-level names only.

Exit codes: 0 clean, 2 any failure or a usage error.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from fr.commands.common import resolve_repo_root
from fr.verification.check import check_strategy
from fr.verification.model import StrategyError
from fr.verification.resolve import (
    REPO_VERIFICATIONS_REL,
    list_strategies,
    resolve_strategy,
    shipped_verification_dirs,
)

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

verification_app = typer.Typer(
    help="Verification strategies: resolve (repo > shipped) and validate.",
    no_args_is_help=True,
)


def _check_one(name: str, repo_root: Path) -> list[str]:
    try:
        manifest = resolve_strategy(name, repo_root)
    except StrategyError as e:
        return [str(e)]
    return check_strategy(manifest)


@verification_app.command("list")
def list_cmd() -> None:
    """Every strategy that resolves, and where it came from."""
    for name, source in list_strategies(resolve_repo_root()):
        console.print(f"{name}  {source}")


@verification_app.command("check")
def check_cmd(
    name: str | None = typer.Argument(None, help="Strategy name (resolved repo > shipped)."),
    all_: bool = typer.Option(False, "--all", help="Validate every discoverable strategy."),
) -> None:
    """Validate one strategy by name, or every discoverable one with --all."""
    repo_root = resolve_repo_root()

    if all_:
        names = [n for n, _ in list_strategies(repo_root)]
        if not names:
            err_console.print("[red]no verification strategies found — nothing to validate.[/red]")
            err_console.print("Searched:")
            for d in [repo_root / REPO_VERIFICATIONS_REL, *shipped_verification_dirs()]:
                err_console.print(f"  {d}", soft_wrap=True)
            raise typer.Exit(2)
    elif name:
        names = [name]
    else:
        err_console.print("provide a strategy name or --all.")
        raise typer.Exit(2)

    had_errors = False
    for strategy in names:
        errors = _check_one(strategy, repo_root)
        if errors:
            had_errors = True
            for err in errors:
                err_console.print(f"[red]{strategy}:[/red] {err}", soft_wrap=True)
        else:
            console.print(f"{strategy}: ok")

    if had_errors:
        raise typer.Exit(2)
