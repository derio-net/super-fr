"""`fr docs` — a docs-currency gate (spec 2026-11-11-docs-currency, R1-R8).

Read-only: `docs` is in `fr.artifacts.trigger.READ_ONLY_COMMANDS`. Exit 0 clean,
1 findings, 2 usage or environment error (bad config, no git, no base).
"""

from __future__ import annotations

from typing import Annotated

import typer

from fr.commands.common import resolve_repo_root
from fr.docs import render
from fr.docs.check import check
from fr.docs.load import (
    DocsEnvError,
    changed_paths,
    load_config,
    load_pages,
    resolve_base,
    tracked_files,
)

docs_app = typer.Typer(
    help="Docs currency: pages must keep up with the code they cover (read-only).",
    no_args_is_help=True,
)


def _die(message: str) -> typer.Exit:
    typer.echo(f"fr docs: {message}", err=True)
    return typer.Exit(2)


@docs_app.command("check")
def check_cmd(
    base: Annotated[
        str | None,
        typer.Option("--base", help="Ref to diff from (default: the remote's default branch)."),
    ] = None,
) -> None:
    """Fail when a covered path changed and its page did not (exit 1)."""
    root = resolve_repo_root()
    try:
        config = load_config(root)
        if config is None:
            typer.echo("fr docs: no .fr/docs.yaml, nothing to check")
            return
        tracked = tracked_files(root)
        pages, errors = load_pages(root, config, tracked)
        changed = changed_paths(root, resolve_base(root, base))
    except DocsEnvError as e:
        raise _die(str(e)) from e
    findings = check(pages, errors, tracked, changed, config.must_cover)
    if findings:
        typer.echo(render.findings_text(findings))
        raise typer.Exit(1)
    scope = "structure only" if changed is None else f"{len(changed)} changed path(s)"
    typer.echo(f"fr docs: {len(pages)} page(s) current ({scope})")


@docs_app.command("status")
def status_cmd(
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
) -> None:
    """List every page with its covered globs and its `reviewed` stamp."""
    root = resolve_repo_root()
    try:
        config = load_config(root)
        if config is None:
            typer.echo('{"pages": [], "errors": []}' if as_json else "fr docs: no .fr/docs.yaml")
            return
        pages, errors = load_pages(root, config, tracked_files(root))
    except DocsEnvError as e:
        raise _die(str(e)) from e
    typer.echo(render.status_json(pages, errors) if as_json else render.status_text(pages, errors))
