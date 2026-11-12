"""`fr lenses` — the review lenses a repo has (spec 2026-11-12-review-lenses R1-R3).

Read-only: `lenses` is in `fr.artifacts.trigger.READ_ONLY_COMMANDS`. `check` exits 0 clean,
1 problems; a lens-config error that stops `list` or `show` is exit 2.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from fr.commands.common import resolve_repo_root
from fr.lenses.check import check_config
from fr.lenses.model import Lens, LensError
from fr.lenses.resolve import effective_lenses

lenses_app = typer.Typer(
    help="Review lenses: the angles a feature is reviewed from (read-only).",
    no_args_is_help=True,
)


def _effective() -> dict[str, Lens]:
    try:
        return effective_lenses(resolve_repo_root())
    except LensError as e:
        typer.echo(f"fr lenses: {e}", err=True)
        raise typer.Exit(2) from e


@lenses_app.command("list")
def list_cmd(
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
) -> None:
    """Print the effective lenses and where each comes from."""
    lenses = _effective()
    if as_json:
        rows = [{"id": x.id, "title": x.title, "source": x.source} for x in lenses.values()]
        typer.echo(json.dumps(rows, indent=2))
        return
    width = max((len(i) for i in lenses), default=0)
    for lens in lenses.values():
        typer.echo(f"{lens.id:<{width}}  {lens.title}  [{lens.source}]")


@lenses_app.command("show")
def show_cmd(lens_id: Annotated[str, typer.Argument(help="A lens id.")]) -> None:
    """Print one lens's instruction text."""
    lenses = _effective()
    lens = lenses.get(lens_id)
    if lens is None:
        typer.echo(
            f"fr lenses: no effective lens {lens_id!r}; effective lenses: "
            + ", ".join(sorted(lenses)),
            err=True,
        )
        raise typer.Exit(2)
    typer.echo(lens.brief.rstrip())


@lenses_app.command("check")
def check_cmd() -> None:
    """Fail (exit 1) when .fr/lenses.yaml has a problem."""
    problems = check_config(resolve_repo_root())
    for problem in problems:
        typer.echo(problem)
    if problems:
        raise typer.Exit(1)
    typer.echo("fr lenses: .fr/lenses.yaml is fine")
