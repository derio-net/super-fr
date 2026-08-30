"""`fr migrate v1-to-v2 / dirs / artifacts` CLI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from fr.commands.common import require_migrated_layout
from fr.migrate import MigrationError, migrate_repo

console = Console()
err_console = Console(stderr=True)

migrate_app = typer.Typer(help="v2 migration tools.", no_args_is_help=True)


@migrate_app.command("v1-to-v2")
def v1_to_v2_cmd(
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Apply the migration. Without this flag, runs as a preview (dry-run is the default).",
    ),
    include_in_progress: bool = typer.Option(
        False,
        "--include-in-progress",
        help="Migrate plans even if Status != Complete.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=(
            "Re-migrate plans whose v2 folder already exists by restoring the "
            "paired `.md.v1-archive`. Use to repair migrations done by older "
            "versions (pre-2.0.4) that silently dropped non-canonical step formats."
        ),
    ),
    target_repo: str | None = typer.Option(
        None,
        "--target-repo",
        help=(
            "owner/repo Issues should be filed against. Required for plans that "
            "declare no '**Target repo:**' line (never defaults to the plugin's "
            "own repo). Also resolves plans whose phases declare conflicting repos."
        ),
    ),
) -> None:
    """Convert every v1 .md plan in this repo to a v2 folder + rewrite spec tables.

    Defaults to a preview. Pass --yes to actually write changes.
    """
    repo_root = Path.cwd()
    require_migrated_layout(repo_root)
    try:
        outcomes = migrate_repo(
            repo_root,
            dry_run=not yes,
            include_in_progress=include_in_progress,
            force=force,
            target_repo=target_repo,
        )
    except MigrationError as e:
        err_console.print(f"[red]migration error:[/red] {e}")
        raise typer.Exit(2) from e

    for o in outcomes:
        console.print(f"  {o.plan_path.name}: {o.reason}")
        for w in o.warnings:
            err_console.print(f"    [yellow]warning:[/yellow] {w}")
    n_migrated = sum(1 for o in outcomes if "migrated" in o.reason)
    n_skipped = sum(1 for o in outcomes if o.reason.startswith("skipped"))
    suffix = "" if yes else " (dry-run; pass --yes to apply)"
    console.print(f"\n{n_migrated} migrated, {n_skipped} skipped.{suffix}")


@migrate_app.command("dirs")
def dirs_cmd(
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Perform the moves. Without this flag, runs as a preview (dry-run is the default).",
    ),
) -> None:
    """Migrate the legacy archived-plans/ layout to implemented/{plans,specs}/.

    Renames docs/superpowers/archived-plans -> implemented/plans (v1 flat
    archives ride along untouched) and moves every spec whose plans are all
    implemented into implemented/specs/. Moves are `git mv`; committing is
    the operator's job. This is the ONLY verb exempt from the legacy-layout
    hard-stop.
    """
    from fr.migrate import MigrationError, migrate_dirs

    repo_root = Path.cwd()
    try:
        moves, notes = migrate_dirs(repo_root, dry_run=not yes)
    except MigrationError as e:
        err_console.print(f"[red]migration error:[/red] {e}")
        raise typer.Exit(2) from e

    if not moves:
        typer.echo("nothing to migrate — layout is already current.")
        for n in notes:
            typer.echo(f"  note: {n}")
        return
    verb = "moved" if yes else "would move"
    for m in moves:
        typer.echo(f"  {verb}: {m.src} -> {m.dst}")
    for n in notes:
        typer.echo(f"  note: {n}")
    if yes:
        # Repair in passing (2026-06-06 spec-path-repair): refs to the
        # relocated tree normalize in the same operator commit.
        from fr.repair import repair_repo

        repair = repair_repo(repo_root, write=True)
        for r in repair.rewrites:
            typer.echo(f"  repaired: {r.file.name} · {r.field}: {r.old} → {r.new}")
        for w in repair.warnings:
            err_console.print(f"[yellow]warning:[/yellow] {w}")
        typer.echo("\nmoves staged via git mv — review and commit them.")
    else:
        typer.echo("\n(dry-run; pass --yes to apply)")


@migrate_app.command("artifacts")
def artifacts_cmd(
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Apply the migrations. Without this flag, runs as a preview (dry-run is the default).",
    ),
) -> None:
    """Bring every live artifact up to the version this fr writes.

    Walks the artifact registry (plans, journals, runs, the acceptance matrix,
    specs), applies each registered migration whose guard says it is needed,
    and reports what it did. Archived artifacts under `implemented/` are never
    touched — they record what shipped.

    Dry-run by default, like every other fr mutation. Committing is a separate
    concern (spec §3.D); this verb only rewrites files.
    """
    from fr.artifacts.runner import MigrationChainError, run_migrations
    from fr.commands.common import resolve_repo_root

    repo_root = resolve_repo_root()
    require_migrated_layout(repo_root)
    try:
        report = run_migrations(repo_root, dry_run=not yes)
    except MigrationChainError as e:
        err_console.print(f"[red]migration error:[/red] {e}")
        raise typer.Exit(2) from e

    verb = "migrated" if yes else "would migrate"
    for action in report.applied:
        # Plain echo, not rich: rich soft-wraps and splits long paths.
        typer.echo(f"  {verb}: {_rel(action.path, repo_root)} · {action.summary}")
    for skip in report.skipped:
        typer.echo(f"  skipped (already done by another writer): {_rel(skip.path, repo_root)}")
    for failure in report.failed:
        typer.echo(f"  FAILED: {_rel(failure.path, repo_root)} · {failure.error}", err=True)

    if not report.applied and not report.failed:
        typer.echo("every artifact is already current.")
        return
    if not yes:
        typer.echo(f"\n{len(report.applied)} to migrate (dry-run; pass --yes to apply)")
    else:
        typer.echo(f"\n{len(report.applied)} migrated.")
    if report.failed:
        typer.echo(
            f"{len(report.failed)} artifact(s) could not be migrated and were left unmodified.",
            err=True,
        )
        raise typer.Exit(2)


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:  # pragma: no cover — every artifact is under the root
        return str(path)
