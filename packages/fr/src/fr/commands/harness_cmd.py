"""`fr harness parity` — render the declared harness-parity matrix.

2026-09-18 harness-parity-matrix spec §3.F, Phase 1 (walking skeleton).
Render reads ONLY the shipped `parity.yaml` (via `fr.harness.load_matrix`,
`importlib.resources` under the hood) — no repo, no registration files, so
it works on a pod with no plugin installed and no super-fr checkout.
`--check` (declared vs. observed, needing the registration files) is
Phase 2 and deliberately absent here.

Exit codes: 0 always (a render has nothing to fail on); 2 usage
(`--format`/`--harness` given a bad value).
"""

from __future__ import annotations

import json as _json

import typer
from rich.console import Console
from rich.table import Table

from fr.harness import HARNESSES, load_matrix
from fr.harness.model import Matrix

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

harness_app = typer.Typer(
    help="Declared harness-parity matrix: which surfaces are wired on which harness.",
    no_args_is_help=True,
)


def _matrix_json(matrix: Matrix) -> dict[str, object]:
    """`Matrix.model_dump(mode='json', by_alias=True)` round-trips through
    `parse_matrix` unchanged — `by_alias` so the `schema` wire key survives,
    not the Python-side `schema_version` rename."""
    return matrix.model_dump(mode="json", by_alias=True)


def _table(matrix: Matrix, harness_filter: str | None) -> Table:
    columns = [harness_filter] if harness_filter else list(HARNESSES)
    table = Table(title="Harness parity")
    table.add_column("surface")
    table.add_column("kind")
    for col in columns:
        table.add_column(col)
    for surface in matrix.surfaces:
        row = [surface.id, surface.kind]
        for col in columns:
            hstate = surface.harnesses[col]
            cell: str = hstate.state
            if hstate.scope_note:
                cell = f"{cell} — {hstate.scope_note}"
            row.append(cell)
        table.add_row(*row)
    return table


def _validate_harness(harness: str | None) -> None:
    if harness is not None and harness not in HARNESSES:
        err_console.print(
            f"--harness must be one of {list(HARNESSES)}, got {harness!r}",
        )
        raise typer.Exit(2)


@harness_app.command("parity")
def parity_cmd(
    output_format: str = typer.Option(
        "table",
        "--format",
        help="Output format: table (default, human-readable) or json.",
    ),
    harness: str | None = typer.Option(
        None,
        "--harness",
        help="Restrict the table to one harness column (with its scope_notes).",
    ),
) -> None:
    """Render the declared harness-parity matrix (`fr.harness.parity.yaml`)."""
    if output_format not in ("table", "json"):
        err_console.print(f"--format must be 'table' or 'json', got {output_format!r}")
        raise typer.Exit(2)
    _validate_harness(harness)

    matrix = load_matrix()

    if output_format == "json":
        console.print_json(_json.dumps(_matrix_json(matrix)))
        return

    console.print(_table(matrix, harness))


__all__ = ["harness_app"]
