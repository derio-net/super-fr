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
from rich.markup import escape

from fr.artifacts.paths import LEGACY_CONFIG, REPO, config_kind_path
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


def _sync_one(repo: str, root: Path, *, yes: bool, force: bool) -> None:
    """Instrument one checkout (review p4-r9). The file is read through
    `fr.config.space.located`, so the old `docs/superpowers/plan-config.yaml` counts as the
    repo's file until it moves (R13), and `--force` under `repo` writes the new path and
    removes the old one (never both, R12). Under quiet and stealth the file lives on the
    configuration branch, which changes only by a pull request (`fr.config.change`,
    honouring `git.pr`): fr proposes it there, or refuses naming how to create the space,
    and never writes the configuration checkout directly."""
    from fr.config.space import config_space, located

    space = config_space(root)
    old = root / LEGACY_CONFIG["plan-config"]
    cfg = located(root, "plan-config")
    if cfg.exists() and not force:
        console.print(f"SKIP (exists)   {repo}  — {cfg}")
        return
    if space.placement != REPO:
        _propose(repo, root, yes=yes)
        return
    target = config_kind_path(root, "plan-config")
    if not yes:
        console.print(f"DRY-RUN (would write)  {repo}  — {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_plan_config())
    if old.exists() and old != target:
        old.unlink()
    console.print(f"WROTE           {repo}  — {target}")


def _propose(repo: str, root: Path, *, yes: bool) -> None:
    from fr.config import migrate as moves
    from fr.config.space import config_space
    from fr.settings import SettingsError

    space = config_space(root)
    tree_path = space.tree_path("plan-config.yaml")
    if not yes:
        console.print(f"DRY-RUN (would propose)  {repo}  — {tree_path} on {space.ref}")
        return
    try:
        writer = moves.writer_for(root)
        writer.fetch()
        if not writer.exists():
            console.print(
                f"REFUSED         {repo}  — {space.placement}: there is no configuration "
                "branch yet; create it with `fr migrate artifacts --yes` (or `fr settings "
                "init`), then run `fr repos sync` again"
            )
            return
        url = writer.propose(
            tree_path, render_plan_config(), moves._message(root, "plan-config.yaml")
        )
    except SettingsError as err:
        console.print(f"REFUSED         {repo}  — {escape(str(err))}")
        return
    console.print(f"PROPOSED        {repo}  — {tree_path} on {space.ref}: {url}")


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
    """Write .fr/plan-config.yaml into each checked-out repo (a pull request to the
    configuration branch under quiet and stealth).

    The file is a per-repo validator profile (read by scripts/validate-plans.sh).
    It is optional — a repo works without it — so this is convenience
    instrumentation, never a clone.
    """
    args = list(repos or [])
    mpath = _manifest_path(manifest)
    try:
        entries = _collection(mpath, args)
    except ManifestError as err:
        err_console.print(f"[red]error:[/red] {escape(str(err))}")
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
        _sync_one(entry.repo, root, yes=yes, force=force)

    # Durably record well-formed one-off args (idempotent) unless suppressed or previewing.
    if yes and not no_save:
        for a in args:
            if _is_repo_ref(a):
                append_to_manifest(mpath, a)
