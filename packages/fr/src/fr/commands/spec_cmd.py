"""`fr spec status` / `fr spec requirements` CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from fr.acceptance.check import resolve_identity
from fr.acceptance.model import AcceptanceError, Matrix, load_matrix
from fr.commands.common import require_migrated_layout
from fr.journal.model import parse_journal, resolve_journal_read_path, spec_journal_slug
from fr.requirements import check_requirements, is_input_entry, parse_requirements
from fr.spec import compute_status, parse_spec, render_status_md

if TYPE_CHECKING:
    from fr.ghclient import GhClient

console = Console()
err_console = Console(stderr=True)

spec_app = typer.Typer(help="v2 spec status commands.", no_args_is_help=True)


def _make_gh_client() -> GhClient:
    """Factory hook — tests monkeypatch this (same seam as archive_cmd)."""
    from fr.hostclient import client_for

    return client_for(Path.cwd())


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


@spec_app.command("requirements")
def requirements_cmd(
    spec_path: Path = typer.Argument(..., help="Path to spec markdown file."),
    journal_path: Path | None = typer.Option(
        None,
        "--journal",
        help="Spec journal path (default: derived from the spec with spec_journal_slug).",
    ),
    matrix_path: Path = typer.Option(
        Path("docs/acceptance/matrix.yaml"), "--matrix", help="Acceptance matrix path."
    ),
) -> None:
    """Check a spec's `## Requirements` section (spec 2026-09-28 §C).

    Exits 2 and prints each problem when the capture is unsound; exits 0 with
    a one-line summary otherwise. A spec journal with no input entry yet is
    reported as pending, not unsound: this pre-check runs before the
    brainstorm resolve that writes it (#776). The only implementation of §C — the
    `requirements` derived-evidence gate on `fr run resolve` calls the same
    `check_requirements`, never a copy.
    """
    require_migrated_layout()
    if not spec_path.exists():
        err_console.print(f"no such spec: {spec_path}")
        raise typer.Exit(2)
    repo_root = Path.cwd()
    spec_text = spec_path.read_text()

    slug = spec_journal_slug(spec_path.stem)
    jpath = (
        journal_path
        if journal_path is not None
        else resolve_journal_read_path(repo_root, "spec", slug)
    )
    entries = parse_journal(jpath.read_text()) if jpath.exists() else []

    matrix = load_matrix(matrix_path) if matrix_path.exists() else Matrix()
    try:
        _, repo = resolve_identity(matrix, repo_root)
    except AcceptanceError as e:
        err_console.print(str(e))
        raise typer.Exit(2) from e
    spec_ref = f"{repo}:{spec_path.as_posix()}"

    problems = check_requirements(spec_text, entries, matrix, spec_ref, input_pending=True)
    if problems:
        for p in problems:
            err_console.print(f"- {p}")
        raise typer.Exit(2)
    n = len(parse_requirements(spec_text).items)
    typer.echo(f"{n} requirements")
    if not any(is_input_entry(e) for e in entries):
        typer.echo(
            "input entry: pending — none in the spec journal yet, so input quotes are "
            "unchecked. The brainstorm record's `journal:` entry with `input: true` is "
            "written by its `fr run resolve`, which re-runs this check against it "
            "(standalone: `fr journal add --scope spec --kind discovery --input`)."
        )
