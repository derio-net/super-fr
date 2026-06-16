"""`fr repos` CLI — instrument already-checked-out repos with a plan-config.yaml.

`fr repos sync` writes `docs/superpowers/plan-config.yaml` into each repo in the
collection (manifest ∪ positional args). It NEVER clones: a repo that isn't
checked out locally produces a warning, not a failure. Mutating, so dry-run is
the default; `--yes` writes.

Exit codes: 0 success (warnings don't fail it); 2 usage (no repos resolved,
bad manifest).
"""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from fr.repos import (
    DEFAULT_MANIFEST,
    ManifestError,
    RepoEntry,
    append_to_manifest,
    checkout_root,
    load_manifest,
    render_plan_config,
)

console = Console()
err_console = Console(stderr=True)

repos_app = typer.Typer(
    name="repos",
    help="Instrument locally-checked-out repos (driven by the operator's collection).",
    no_args_is_help=True,
)


def _manifest_path(manifest: Path | None) -> Path:
    if manifest is not None:
        return manifest
    env = os.environ.get("FR_REPOS_MANIFEST")
    return Path(env) if env else DEFAULT_MANIFEST


def _is_repo_ref(repo: str) -> bool:
    """True for a well-formed `owner/name` (exactly one slash, both parts set)."""
    owner, sep, name = repo.partition("/")
    return bool(sep) and bool(owner) and bool(name)


def _collection(manifest_path: Path, args: list[str]) -> list[RepoEntry]:
    """Manifest entries first, then positional args; deduped by repo (first wins)."""
    entries = load_manifest(manifest_path)
    by_repo: dict[str, RepoEntry] = {}
    for e in [*entries, *(RepoEntry(repo=a) for a in args)]:
        by_repo.setdefault(e.repo, e)
    return list(by_repo.values())


@repos_app.command()
def sync(
    repos: list[str] = typer.Argument(None, help="owner/repo to instrument (repeatable)."),
    manifest: Path = typer.Option(
        None,
        "--manifest",
        help="Repos manifest (default: $FR_REPOS_MANIFEST or ~/.config/fr/repos.yaml).",
    ),
    yes: bool = typer.Option(False, "--yes", help="Apply. Default is a dry-run preview."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing plan-config.yaml."),
    no_save: bool = typer.Option(
        False, "--no-save", help="Do not append positional args to the manifest."
    ),
) -> None:
    """Write docs/superpowers/plan-config.yaml into each checked-out repo.

    The file is a per-repo validator profile (read by scripts/validate-plans.sh).
    It is optional — a repo works without it — so this is convenience
    instrumentation, never a clone.
    """
    args = list(repos or [])
    mpath = _manifest_path(manifest)
    try:
        entries = _collection(mpath, args)
    except ManifestError as err:
        err_console.print(f"[red]error:[/red] {err}")
        raise typer.Exit(2) from err

    if not entries:
        err_console.print(
            "error: no repos resolved — pass owner/repo args or populate the manifest."
        )
        raise typer.Exit(2)

    for entry in entries:
        if not _is_repo_ref(entry.repo):
            console.print(f"WARN (malformed)  {entry.repo}  — expected owner/repo")
            continue
        root = checkout_root(entry)
        if not root.exists() or not (root / ".git").exists():
            console.print(f"WARN (missing)  {entry.repo}  — not checked out at {root}")
            continue
        cfg = root / "docs" / "superpowers" / "plan-config.yaml"
        if cfg.exists() and not force:
            console.print(f"SKIP (exists)   {entry.repo}  — {cfg}")
            continue
        if not yes:
            console.print(f"DRY-RUN (would write)  {entry.repo}  — {cfg}")
            continue
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(render_plan_config())
        console.print(f"WROTE           {entry.repo}  — {cfg}")

    # Durably record well-formed one-off args (idempotent) unless suppressed or previewing.
    if yes and not no_save:
        for a in args:
            if _is_repo_ref(a):
                append_to_manifest(mpath, a)
