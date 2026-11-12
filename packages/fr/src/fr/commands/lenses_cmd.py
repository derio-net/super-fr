"""`fr lenses` — the review lenses a repo has (spec 2026-11-12-review-lenses R1-R3, R5, R7).

Read-only: `lenses` is in `fr.artifacts.trigger.READ_ONLY_COMMANDS`. `check` exits 0 clean,
1 problems; a lens-config error that stops `list`, `show` or `status` is exit 2.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer

from fr.commands.common import resolve_repo_root
from fr.lenses.accumulate import LensEntry, LensSet, lens_set
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


def _branch_run(root: Any, run_id: str | None) -> Any:
    from fr.run.model import RunStateError, load_run_state

    if run_id is not None:
        try:
            return load_run_state(root, run_id)
        except RunStateError as e:
            typer.echo(f"fr lenses: {e}", err=True)
            raise typer.Exit(2) from e
    from fr.commands.run_cmd import _runs_on_this_branch

    runs = _runs_on_this_branch(root)
    if len(runs) != 1:
        found = ", ".join(r.run for r in runs) or "none"
        typer.echo(
            f"fr lenses: status needs one run on this branch (found: {found}); pass --run <id>",
            err=True,
        )
        raise typer.Exit(2)
    return runs[0]


def _line(entry: LensEntry) -> str:
    parts = [
        f'"{r.text}" ({f"step {r.step}" if r.step else "command line"}, {r.entry})'
        for r in entry.reasons
    ]
    if entry.rule is not None:
        parts.append(f"rule {', '.join(entry.rule)} matches {entry.file}")
    return f"{entry.lens}: " + "; ".join(parts)


def _as_json(run: str, found: LensSet) -> str:
    return json.dumps(
        {
            "run": run,
            "lenses": [
                {
                    "lens": e.lens,
                    "reasons": [
                        {"reason": r.text, "step": r.step, "entry": r.entry, "scope": r.scope}
                        for r in e.reasons
                    ],
                    "rule": list(e.rule) if e.rule is not None else None,
                    "file": e.file,
                }
                for e in found.lenses
            ],
            "warnings": list(found.warnings),
        },
        indent=2,
    )


@lenses_app.command("status")
def status_cmd(
    run_id: Annotated[
        str | None, typer.Option("--run", help="A run id (default: this branch's run).")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
) -> None:
    """Print the feature's lens set: each lens with every reason and the step that
    added it, or the path rule that requires it and one matching file."""
    root = resolve_repo_root()
    run = _branch_run(root, run_id)
    try:
        found = lens_set(root, run)
    except LensError as e:
        typer.echo(f"fr lenses: {e}", err=True)
        raise typer.Exit(2) from e
    if as_json:
        typer.echo(_as_json(run.run, found))
        return
    for warning in found.warnings:
        typer.echo(f"warning: {warning}", err=True)
    if not found.lenses:
        typer.echo("no lens requested")
        return
    for entry in found.lenses:
        typer.echo(_line(entry))
