"""`fr acceptance ...` CLI — the acceptance-matrix registry and gate.

Spec: docs/superpowers/specs/2026-07-04-acceptance-matrix-design.md §4.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from fr.acceptance.model import AcceptanceError, Matrix, load_matrix
from fr.commands.common import resolve_repo_root

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

MATRIX_REL = Path("docs/acceptance/matrix.yaml")

acceptance_app = typer.Typer(
    help="Acceptance matrix: business-level acceptance tests × verification levels.",
    no_args_is_help=True,
)


def _load(root: Path) -> Matrix:
    matrix_path = root / MATRIX_REL
    if not matrix_path.exists():
        err_console.print(f"no {MATRIX_REL} (run `fr acceptance init` to scaffold one)")
        raise typer.Exit(1)
    try:
        return load_matrix(matrix_path)
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1) from e


@acceptance_app.command("check")
def check_cmd(
    sibling_root: str = typer.Option(
        "..",
        "--sibling-root",
        help="Where sister repos live, relative to the repo root ('..' = repos as siblings).",
    ),
) -> None:
    """The gate: refs resolve, staleness, exit 2 on failing rows."""
    from fr.acceptance.check import check

    root = resolve_repo_root()
    matrix = _load(root)
    try:
        result = check(matrix, root, sibling_root)
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(1) from e

    # Plain echo, never rich: `::warning::` annotations are parsed by GitHub
    # line-by-line — rich's soft-wrap would split them and they'd vanish.
    for r in result.warning_rows:
        typer.echo(
            f"::warning title=acceptance-matrix::{r.id} is {r.status}: "
            f"{r.acceptance} — backfill owed ({r.notes[:120]})"
        )
    for w in result.warnings:
        typer.echo(f"::warning title=acceptance-matrix::{w}")
    for e_line in result.errors:
        typer.echo(f"ERROR: {e_line}", err=True)
    if result.failing_ids:
        typer.echo(f"ERROR: failing acceptance rows: {result.failing_ids}", err=True)
    if result.exit_code == 0:
        typer.echo(result.summary)
    raise typer.Exit(result.exit_code)
