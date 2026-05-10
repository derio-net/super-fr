"""`vk v2 spec status` CLI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from vk.v2.spec import compute_status, parse_spec, render_status_md

console = Console()
err_console = Console(stderr=True)

spec_app = typer.Typer(help="v2 spec status commands.", no_args_is_help=True)


@spec_app.command("status")
def status_cmd(
    spec_path: Path | None = typer.Argument(None, help="Path to spec markdown file."),
    all_specs: bool = typer.Option(False, "--all", help="Walk all specs in current repo."),
) -> None:
    """Compute and print spec status (markdown).

    Same code path as the GHA workflow uses — output is markdown
    suitable for posting as a PR comment.
    """
    if all_specs and spec_path is not None:
        err_console.print("--all and spec_path are mutually exclusive")
        raise typer.Exit(2)
    if not all_specs and spec_path is None:
        err_console.print("Either provide a spec_path or use --all")
        raise typer.Exit(2)

    repo_root = Path.cwd()

    if all_specs:
        specs_dir = repo_root / "docs" / "superpowers" / "specs"
        if not specs_dir.is_dir():
            err_console.print(f"specs dir not found: {specs_dir}")
            raise typer.Exit(2)
        targets = sorted(specs_dir.glob("*.md"))
    else:
        assert spec_path is not None
        targets = [spec_path]

    blocks: list[str] = []
    for sp in targets:
        meta = parse_spec(sp)
        st = compute_status(meta, repo_root)
        blocks.append(render_status_md(st))
    typer.echo("\n\n---\n\n".join(blocks))
