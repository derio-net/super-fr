"""`fr workflow ...` CLI — resolve + validate workflow shape manifests
(spec §4.A, Phase 6).

`fr workflow check <name>` resolves a shape (repo > shipped,
`fr.workflow.resolve.resolve_workflow`) and reports every problem found —
whether a parse-time `WorkflowError` (bad schema, unknown key) or a
semantic `check_workflow` finding (dangling needs, cycle, unknown
capability, `for_each`/`unit` conflict) — through the SAME exit-1 report,
so an operator never has to know which layer a shape failed at.
`--all` validates every manifest discoverable in any of the lookup
sources (`fr.workflow.resolve.shipped_workflow_dirs`) — and **fails when
there are none**. It used to print "no workflow shapes found" and exit 0,
which made smoke step §8.0.3 of the 2026-08-14 spec pass on a host where
nothing was installed: the exact state the step exists to detect (review
r5-b5).

Exit codes: 0 clean, 1 any manifest failed to resolve or validate — or `--all`
found nothing to validate at all, 2 usage (neither a name nor `--all` given).
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

from fr._shipped import DEFAULTS_ENV_VAR
from fr.commands.common import resolve_repo_root
from fr.workflow.check import check_workflow
from fr.workflow.model import WorkflowError
from fr.workflow.resolve import (
    REPO_WORKFLOWS_REL,
    repo_workflows_dir,
    resolve_workflow,
    shipped_workflow_dirs,
)

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

workflow_app = typer.Typer(
    help="Workflow shape manifests: resolve (repo > shipped) and validate.",
    no_args_is_help=True,
)


def _search_dirs(repo_root: Path, shipped_dir: Path | None) -> list[Path]:
    """Every directory `resolve_workflow` would look in, in the same order.

    Derived from `shipped_workflow_dirs` rather than restated, so discovery
    and resolution cannot disagree about where a shape lives.
    """
    return [repo_workflows_dir(repo_root), *shipped_workflow_dirs(shipped_dir)]


def _discover_names(repo_root: Path, shipped_dir: Path | None) -> list[str]:
    names: set[str] = set()
    for d in _search_dirs(repo_root, shipped_dir):
        if d.is_dir():
            names |= {p.stem for p in d.glob("*.yaml")}
    return sorted(names)


def _check_one(name: str, repo_root: Path, shipped_dir: Path | None) -> list[str]:
    try:
        manifest = resolve_workflow(name, repo_root, shipped_root=shipped_dir)
    except WorkflowError as e:
        return [str(e)]
    return check_workflow(manifest, repo_root)


@workflow_app.command("check")
def check_cmd(
    name: str | None = typer.Argument(None, help="Shape name (resolved repo > shipped)."),
    all_: bool = typer.Option(False, "--all", help="Validate every discoverable shape."),
) -> None:
    """Validate one shape by name, or every discoverable shape with --all."""
    repo_root = resolve_repo_root()
    # No explicit root: the one walk `fr run start` resolves through (`fr._shipped`).
    shipped_dir: Path | None = None

    if all_:
        try:
            names = _discover_names(repo_root, shipped_dir)
        except WorkflowError as e:  # e.g. a per-kind variable refused past fr 9.2 (R6)
            err_console.print(f"[red]{escape(str(e))}[/red]", soft_wrap=True)
            raise typer.Exit(2) from e
        if not names:
            # Exit 1, not 0 (review r5-b5). "Nothing to validate" is a broken
            # installation, not a clean bill of health, and reporting it as
            # success is what let the 2026-08-14 spec's §8.0.3 smoke step pass
            # against a host with no shapes installed at all.
            err_console.print("[red]no workflow shapes found — nothing to validate.[/red]")
            err_console.print("Searched:")
            for d in _search_dirs(repo_root, shipped_dir):
                # soft_wrap: these are paths the operator inspects and pastes;
                # rich's default folding would break one across lines.
                err_console.print(f"  {d}", soft_wrap=True)
            err_console.print(
                f"Install the super-fr plugin, author a shape under {REPO_WORKFLOWS_REL}, "
                f"or point ${DEFAULTS_ENV_VAR} at a tree holding workflows/.",
                soft_wrap=True,
            )
            raise typer.Exit(1)
    elif name:
        names = [name]
    else:
        err_console.print("provide a shape name or --all.")
        raise typer.Exit(2)

    had_errors = False
    for shape_name in names:
        errors = _check_one(shape_name, repo_root, shipped_dir)
        if errors:
            had_errors = True
            for err in errors:
                err_console.print(f"[red]{shape_name}:[/red] {err}")
        else:
            console.print(f"{shape_name}: ok")

    if had_errors:
        raise typer.Exit(1)
