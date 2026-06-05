"""Shared CLI helpers — only `resolve_repo_root` survives the v1→v2 retirement."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def resolve_repo_root(cwd: Path | None = None) -> Path:
    """Resolve the repo root for a vk command.

    Honors `$VK_REPO_ROOT` first (so integration tests can point a
    command at `tmp_path` without spawning a fake git repo), then
    falls back to `git rev-parse --show-toplevel` (run from `cwd` if
    given), then to `Path.cwd()`.

    The returned path is always `.resolve()`-d so callers can safely
    use `Path.is_relative_to` / `Path.relative_to` against other
    resolved paths, even when the source value (env var, git output,
    or cwd) traversed a symlink.

    The empty string is treated like an unset env var (we fall through
    to git) — keeping `VK_REPO_ROOT=""` as a way to disable the
    override without unsetting it.
    """
    override = os.environ.get("VK_REPO_ROOT")
    if override:
        return Path(override).resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        return Path(result.stdout.strip()).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return (cwd or Path.cwd()).resolve()


def require_migrated_layout(repo_root: Path | None = None) -> None:
    """Hard-stop (exit 2) when the legacy archived-plans/ layout exists.

    2026-06-05 dispatch-guards spec: the canonical archive location is
    `docs/superpowers/implemented/{plans,specs}/`. Every verb that resolves
    the superpowers tree — read or mutating — refuses to run on a legacy
    layout so the migration happens at first use of the new version. (A
    banner would get overlooked; nothing here mutates, so a read verb
    refusing is still side-effect-free.) Exemptions: `vk migrate dirs`
    itself and verbs that never resolve the tree (isolation, init, skills,
    --version).

    No-op when there is no superpowers tree at all (e.g. running --help
    in an unrelated directory) — the guard targets repos that have plans.
    """
    root = repo_root if repo_root is not None else resolve_repo_root()
    legacy = root / "docs" / "superpowers" / "archived-plans"
    if legacy.is_dir():
        import typer

        # Plain echo, not rich — rich soft-wraps and can split the
        # copy-pasteable `vk migrate dirs --yes` across lines.
        typer.echo(f"legacy layout detected: {legacy}", err=True)
        typer.echo(
            "The archive location moved to docs/superpowers/implemented/. "
            "Run `vk migrate dirs --yes`, then commit the rename.",
            err=True,
        )
        raise typer.Exit(2)
