"""`fr workflow ...` CLI — resolve + validate workflow shape manifests
(spec §4.A, Phase 6).

`fr workflow check <name>` resolves a shape (repo > shipped,
`fr.workflow.resolve.resolve_workflow`) and reports every problem found —
whether a parse-time `WorkflowError` (bad schema, unknown key) or a
semantic `check_workflow` finding (dangling needs, cycle, unknown
capability, `for_each`/`unit` conflict) — through the SAME exit-1 report,
so an operator never has to know which layer a shape failed at.
`--all` validates every manifest discoverable in either directory.

Exit codes: 0 clean, 1 any manifest failed to resolve or validate, 2 usage
(neither a name nor `--all` given).
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from fr.commands.common import resolve_repo_root
from fr.workflow.check import check_workflow
from fr.workflow.model import WorkflowError
from fr.workflow.resolve import (
    REPO_WORKFLOWS_REL,
    default_shipped_workflows_dir,
    resolve_workflow,
)

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

workflow_app = typer.Typer(
    help="Workflow shape manifests: resolve (repo > shipped) and validate.",
    no_args_is_help=True,
)


def _discover_names(repo_root: Path, shipped_dir: Path) -> list[str]:
    repo_dir = repo_root / REPO_WORKFLOWS_REL
    names = {p.stem for p in repo_dir.glob("*.yaml")} if repo_dir.is_dir() else set()
    if shipped_dir.is_dir():
        names |= {p.stem for p in shipped_dir.glob("*.yaml")}
    return sorted(names)


def _check_one(name: str, repo_root: Path, shipped_dir: Path) -> list[str]:
    try:
        manifest = resolve_workflow(name, repo_root, shipped_root=shipped_dir)
    except WorkflowError as e:
        return [str(e)]
    return check_workflow(manifest)


@workflow_app.command("check")
def check_cmd(
    name: str | None = typer.Argument(None, help="Shape name (resolved repo > shipped)."),
    all_: bool = typer.Option(False, "--all", help="Validate every discoverable shape."),
) -> None:
    """Validate one shape by name, or every discoverable shape with --all."""
    repo_root = resolve_repo_root()
    shipped_dir = default_shipped_workflows_dir()

    if all_:
        names = _discover_names(repo_root, shipped_dir)
        if not names:
            console.print("no workflow shapes found.")
            return
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
