"""`vk archive` CLI — move finished plans (and their specs) to implemented/.

Gate per plan (vk.render.archive_gate): every phase `_phase_complete` OR
(undispatched AND `plan_locally_complete`). `--force` overrides — single
plan only; `--force --all` is refused because blanket-forcing is how the
2026-06-05 incident happens in reverse.

Exit codes: 0 archived (or clean no-op for --all); 2 gate failure, dirty
tree, usage, legacy layout; 5 parse error.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from vk.archive import ArchiveError, archive_plan_dir, paths_dirty, spec_archive_sweep
from vk.commands.common import build_plan_report, require_migrated_layout, resolve_repo_root
from vk.parser import PlanSchemaError
from vk.render import archive_gate
from vk.repair import repair_repo

if TYPE_CHECKING:
    from vk.ghclient import GhClient

console = Console()
err_console = Console(stderr=True)


def _make_gh_client() -> GhClient:
    """Factory hook — tests monkeypatch this (same seam as apply_cmd)."""
    from vk.real_ghclient import RealGhClient

    return RealGhClient()


def archive_command(
    plan_dir: Path | None = typer.Argument(None, help="Path to plan folder."),
    all_plans: bool = typer.Option(
        False, "--all", help="Archive every finished plan under docs/superpowers/plans/."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Archive even when the gate reports incomplete phases (single plan only).",
    ),
) -> None:
    """Move a finished plan to implemented/plans/ (and its spec when ready).

    Moves are `git mv`; review and commit them (PR per repo workflow).
    """
    require_migrated_layout()
    if all_plans and plan_dir is not None:
        err_console.print("--all and plan_dir are mutually exclusive")
        raise typer.Exit(2)
    if not all_plans and plan_dir is None:
        err_console.print("Either provide a plan_dir argument or use --all")
        raise typer.Exit(2)
    if all_plans and force:
        err_console.print(
            "--force with --all is refused: blanket-forcing archives work that "
            "may not be done. Force individual plans explicitly."
        )
        raise typer.Exit(2)

    repo_root = resolve_repo_root()
    gh = _make_gh_client()

    if all_plans:
        plans_root = repo_root / "docs" / "superpowers" / "plans"
        targets = (
            sorted(p for p in plans_root.iterdir() if p.is_dir() and (p / "_meta.yaml").exists())
            if plans_root.is_dir()
            else []
        )
    else:
        assert plan_dir is not None
        targets = [plan_dir]

    archived: list[Path] = []
    skipped: list[str] = []
    for target in targets:
        # Under-repo check FIRST — `git status -- <path>` (the dirty check)
        # and `git mv` both fail opaquely on out-of-repo paths.
        try:
            target.resolve().relative_to(repo_root)
        except ValueError:
            msg = f"{target} is not under this repo root ({repo_root})"
            if not all_plans:
                err_console.print(f"refusing to archive — {msg}")
                raise typer.Exit(2) from None
            skipped.append(f"{target.name}: skipped — {msg}")
            continue
        try:
            report = build_plan_report(target, gh)
        except PlanSchemaError as e:
            if not all_plans:
                err_console.print(f"parse error: {e}")
                raise typer.Exit(5) from e
            skipped.append(f"{target.name}: parse error: {e}")
            continue

        blockers = archive_gate(report.plan, report.observed)
        if blockers and not force:
            if not all_plans:
                err_console.print("refusing to archive — plan is not complete:")
                for b in blockers:
                    err_console.print(f"  {b}")
                err_console.print("(override with --force if you know the work is done)")
                raise typer.Exit(2)
            skipped.append(f"{target.name}: skipped — {'; '.join(blockers)}")
            continue

        if paths_dirty(repo_root, target):
            msg = f"{target.name}: worktree dirty at the plan path — commit or stash first"
            if not all_plans:
                err_console.print(f"refusing to archive — {msg}")
                raise typer.Exit(2)
            skipped.append(f"{target.name}: skipped — dirty worktree")
            continue

        try:
            new_path = archive_plan_dir(repo_root, target.resolve())
        except ArchiveError as e:
            if not all_plans:
                err_console.print(str(e))
                raise typer.Exit(2) from e
            skipped.append(f"{target.name}: {e}")
            continue
        archived.append(new_path)
        typer.echo(f"  archived: {target} -> {new_path.relative_to(repo_root)}")

    # Spec decision once, after all plan moves (order independence in --all).
    # Runs even when nothing archived this run: a spec stranded by a prior
    # run (cross-repo row unresolved then, resolved now) must still get
    # swept — `vk migrate dirs` evaluates specs unconditionally and the two
    # archive paths must agree (review finding, 2026-06-06).
    specs_moved = False
    if archived or all_plans:
        sweep = spec_archive_sweep(repo_root, gh)
        specs_moved = bool(sweep.moves)
        for m in sweep.moves:
            typer.echo(f"  archived spec: {m.src} -> {m.dst}")
        for n in sweep.notes:
            typer.echo(f"  note: {n}")

    # Repair in passing (2026-06-06 spec-path-repair): the move and the
    # ref normalization land in the same operator commit.
    if archived or specs_moved:
        repair = repair_repo(repo_root, write=True)
        for r in repair.rewrites:
            typer.echo(f"  repaired: {r.file.name} · {r.field}: {r.old} → {r.new}")
        for w in repair.warnings:
            err_console.print(f"[yellow]warning:[/yellow] {w}")

    for s in skipped:
        typer.echo(f"  skipped: {s}")
    if archived or specs_moved:
        typer.echo("\nmoves staged via git mv — review, commit, and PR them.")
    elif all_plans:
        typer.echo("nothing to archive.")
