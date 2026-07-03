"""`fr spec status` CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from fr.commands.common import require_migrated_layout
from fr.spec import compute_status, parse_spec, render_status_md

if TYPE_CHECKING:
    from fr.ghclient import GhClient

console = Console()
err_console = Console(stderr=True)

spec_app = typer.Typer(help="v2 spec status commands.", no_args_is_help=True)


def _make_gh_client() -> GhClient:
    """Factory hook — tests monkeypatch this (same seam as archive_cmd)."""
    from fr.real_ghclient import RealGhClient

    return RealGhClient()


@spec_app.command("status")
def status_cmd(
    spec_path: Path | None = typer.Argument(None, help="Path to spec markdown file."),
    all_specs: bool = typer.Option(False, "--all", help="Walk all specs in current repo."),
    no_gh: bool = typer.Option(
        False,
        "--no-gh",
        help="Resolve locally only; cross-repo rows stay Unreachable (no network).",
    ),
) -> None:
    """Compute and print spec status (markdown).

    Same code path as the GHA workflow uses — output is markdown
    suitable for posting as a PR comment. Cross-repo plan rows are resolved
    via the gh contents API by default; pass --no-gh for pure-local output.
    """
    require_migrated_layout()
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

    gh = None if no_gh else _make_gh_client()

    blocks: list[str] = []
    for sp in targets:
        meta = parse_spec(sp)
        st = compute_status(meta, repo_root, gh=gh)
        blocks.append(render_status_md(st))
    typer.echo("\n\n---\n\n".join(blocks))
