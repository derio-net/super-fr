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


def _render(matrix: Matrix, harness_filter: str | None) -> tuple[list[Table], list[str]]:
    """The tables, plus the footnotes that did not fit inside them.

    Three things make this readable at the default 80 columns, and all three
    were review findings (r1-i2):

    1. `overflow="fold"` on every column. rich's default is `ellipsis`, which
       renders `fr-isolation-guard` and `fr-isolation-required` BOTH as
       `fr-isol…` — worse than plain truncation, because two rows become
       indistinguishable rather than obviously cut.
    2. `scope_note` text moves out of the cells into numbered footnotes. A note
       is a sentence or two; inline, it blows the table's width out and every
       other column pays for it. The single-harness view has the room, so there
       notes stay inline and the footnote list comes back empty.
    3. One table per `kind` instead of a `kind` COLUMN. Seven columns do not fit
       in eighty characters, and `kind` was the one carrying least — as a
       heading it costs no width and groups the rows besides.
    """
    inline_notes = harness_filter is not None
    if harness_filter:
        columns, collapsed = [harness_filter], []
    else:
        # A harness that is `unsupported` on EVERY row spends a whole column
        # saying one word. Collapse it to a footer line instead — data-driven,
        # not a hardcoded skip-list: the day a codex cell becomes anything
        # else, its column comes back on its own. (`--harness codex` and
        # `--format json` always show it regardless.)
        columns = [
            h
            for h in HARNESSES
            if any(s.harnesses[h].state != "unsupported" for s in matrix.surfaces)
        ]
        collapsed = [h for h in HARNESSES if h not in columns]

    footnotes: list[str] = []
    tables: list[Table] = []

    for kind, heading in (("hook", "Hooks"), ("interaction", "Interaction surfaces")):
        rows = [s for s in matrix.surfaces if s.kind == kind]
        if not rows:
            continue
        table = Table(title=f"Harness parity — {heading}")
        # The identifier is what the operator scans; give it the room first and
        # let the state columns (whose vocabulary is five short words) shrink.
        table.add_column("surface", overflow="fold", min_width=22)
        for col in columns:
            table.add_column(col, overflow="fold")
        for surface in rows:
            row = [surface.id]
            for col in columns:
                hstate = surface.harnesses[col]
                cell: str = hstate.state
                if hstate.scope_note:
                    if inline_notes:
                        cell = f"{cell} — {hstate.scope_note}"
                    else:
                        footnotes.append(
                            f"[{len(footnotes) + 1}] {surface.id} / {col}: {hstate.scope_note}"
                        )
                        cell = f"{cell} [{len(footnotes)}]"
                row.append(cell)
            table.add_row(*row)
        tables.append(table)

    if collapsed:
        footnotes.append(f"unsupported on every surface (column omitted): {', '.join(collapsed)}")

    return tables, footnotes


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

    tables, footnotes = _render(matrix, harness)
    for table in tables:
        console.print(table)
    for note in footnotes:
        console.print(note)


__all__ = ["harness_app"]
