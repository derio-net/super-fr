"""`fr harness parity` — render the declared harness-parity matrix.

2026-09-18 harness-parity-matrix spec §3.F.

Render reads ONLY the shipped `parity.yaml` (via `fr.harness.load_matrix`,
`importlib.resources` under the hood) — no repo, no registration files, so
it works on a pod with no plugin installed and no super-fr checkout.

`--check` is the other mode: it re-derives the matrix from the real
registration files and reports every disagreement. That needs a super-fr
checkout, so run outside one it says it cannot check and exits 0 — never
inventing a verdict from files it could not read (the `fr acceptance
check` precedent).

Exit codes: 0 render, or `--check` clean / declined; 1 `--check` found
drift; 2 usage (`--format`/`--harness` given a bad value) or an
unreadable registration file.
"""

from __future__ import annotations

import json as _json

import typer
from rich.console import Console
from rich.table import Table

from fr.commands.common import resolve_repo_root
from fr.harness import HARNESSES, load_matrix
from fr.harness.check import Finding, check, pairing
from fr.harness.model import HarnessError, Matrix
from fr.harness.observe import (
    OBSERVABLE_HARNESSES,
    is_super_fr_checkout,
    observe,
    shipped_scripts,
)

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


def _finding_json(finding: Finding) -> dict[str, str]:
    return {
        "surface_id": finding.surface_id,
        "harness": finding.harness,
        "declared": finding.declared,
        "observed": finding.observed,
        "message": finding.message,
    }


def _run_check(matrix: Matrix, output_format: str, harness: str | None) -> None:
    """`--check`: declared vs. observed, exit 1 on drift.

    Output goes through `typer.echo`, not the rich console: a finding
    message is one long line naming two file paths, and rich would wrap it
    at whatever width the console happened to snapshot at import — the
    fragility that made two Phase 1 tests width-dependent (finding r1-m6).
    """
    root = resolve_repo_root()
    if not is_super_fr_checkout(root):
        # It needs the registration files and there are none here. Say so and
        # exit 0: a verdict invented from files we could not read is worse
        # than no verdict, and this command is meant to be runnable from a
        # pod with nothing but the installed wheel.
        reason = (
            f"cannot check: {root} is not a super-fr checkout (no "
            "plugins/super-fr/hooks/hooks.json) — the declared matrix is "
            "unchecked, not verified. Run `fr harness parity` to render it."
        )
        # In json mode this must still be JSON (review r2-m2): the decline is
        # the ONE path designed to be benign, and emitting prose here makes it
        # the one path that crashes a consumer which always parses the output.
        typer.echo(
            _json.dumps({"checked": False, "reason": reason}) if output_format == "json" else reason
        )
        return

    try:
        observed = observe(root)
    except HarnessError as exc:
        # `typer.echo`, not `err_console` (review r2-m3): this message names a
        # file path, and rich wrapped one mid-path into something neither
        # greppable nor copy-pasteable — the same r1-m6 fragility the findings
        # below already avoid.
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc

    findings = check(matrix, observed) + pairing(matrix, shipped_scripts(root))
    if harness is not None:
        # A pairing finding is not about one harness (`harness="-"`), so it
        # survives the filter — a row missing entirely is everyone's problem.
        findings = [f for f in findings if f.harness in (harness, "-")]

    if output_format == "json":
        typer.echo(_json.dumps([_finding_json(f) for f in findings], indent=2))
    elif findings:
        typer.echo(f"harness parity: {len(findings)} disagreement(s) with the registration files")
        for finding in findings:
            typer.echo(f"  {finding.message}")
    elif harness is not None and harness not in OBSERVABLE_HARNESSES:
        # Silence is not evidence (review r2-m1). Everywhere else this command
        # is careful that "we cannot look" differs from "we looked and found
        # nothing"; claiming agreement here would throw that away in one line.
        typer.echo(
            f"harness parity on {harness}: fr reads no registration file for this "
            "harness, so nothing was checked — its cells are declared, not verified."
        )
    else:
        scope = f" on {harness}" if harness else ""
        typer.echo(f"harness parity{scope}: declared matrix agrees with the registration files")

    if findings:
        raise typer.Exit(1)


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
        help="Restrict to one harness (a single table column, or --check's findings).",
    ),
    check_drift: bool = typer.Option(
        False,
        "--check",
        help="Compare the declared matrix against the real registration files; exit 1 on drift.",
    ),
) -> None:
    """Render the declared harness-parity matrix (`fr.harness.parity.yaml`)."""
    if output_format not in ("table", "json"):
        err_console.print(f"--format must be 'table' or 'json', got {output_format!r}")
        raise typer.Exit(2)
    _validate_harness(harness)

    matrix = load_matrix()

    if check_drift:
        _run_check(matrix, output_format, harness)
        return

    if output_format == "json":
        console.print_json(_json.dumps(_matrix_json(matrix)))
        return

    tables, footnotes = _render(matrix, harness)
    for table in tables:
        console.print(table)
    for note in footnotes:
        console.print(note)


__all__ = ["harness_app"]
