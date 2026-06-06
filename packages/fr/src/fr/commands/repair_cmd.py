"""`fr repair` CLI — idempotent stale-ref normalization (2026-06-06 spec).

Dry-run by default; `--yes` writes. Exit codes: 0 success / clean
dry-run (warnings don't fail it — a report, not a gate); 2 usage,
legacy layout, dirty tree; 4 write failures; 5 parse error.
"""

from __future__ import annotations

import json as _json

import typer
from rich.console import Console

from fr.archive import paths_dirty
from fr.commands.common import require_migrated_layout, resolve_repo_root
from fr.repair import RepairResult, repair_repo

console = Console()
err_console = Console(stderr=True)


def _emit_text(result: RepairResult, *, applied: bool) -> None:
    verb = "repaired" if applied else "would repair"
    for r in result.rewrites:
        console.print(f"{verb}: {r.file.name} · {r.field}: {r.old} → {r.new}")
    for w in result.warnings:
        err_console.print(f"[yellow]warning:[/yellow] {w}")
    for f in result.failures:
        err_console.print(f"[red]failed:[/red] {f}")
    if not result.rewrites and not result.warnings and not result.failures:
        console.print("nothing to repair — all refs canonical and resolvable.")
    elif not applied and result.rewrites:
        console.print(
            f"\n{len(result.rewrites)} rewrite(s) planned — run `fr repair --yes` to apply."
        )


def _emit_json(result: RepairResult, *, applied: bool) -> None:
    payload = {
        "applied": applied,
        "rewrites": [
            {"file": str(r.file), "field": r.field, "old": r.old, "new": r.new}
            for r in result.rewrites
        ],
        "warnings": list(result.warnings),
        "failures": list(result.failures),
    }
    console.print_json(_json.dumps(payload))


def repair_command(
    yes: bool = typer.Option(False, "--yes", help="Apply rewrites. Default is a dry-run preview."),
    format_: str = typer.Option("text", "--format", help="Output format: text | json."),
) -> None:
    """Normalize stale plan/spec refs to the lifecycle-independent form."""
    require_migrated_layout()
    repo_root = resolve_repo_root()
    sp = repo_root / "docs" / "superpowers"

    if yes and paths_dirty(repo_root, sp):
        err_console.print(
            "refusing to repair: uncommitted changes under docs/superpowers/ — "
            "commit or stash first (dirty tree)."
        )
        raise typer.Exit(2)

    result = repair_repo(repo_root, write=yes)

    if format_ == "json":
        _emit_json(result, applied=yes)
    else:
        _emit_text(result, applied=yes)

    if result.failures:
        raise typer.Exit(4)
