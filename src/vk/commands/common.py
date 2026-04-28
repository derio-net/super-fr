"""Shared CLI helpers: tri-state flags, error formatting, confirmation prompts."""

from __future__ import annotations

import enum
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

import typer
from rich.console import Console
from rich.text import Text

err_console = Console(stderr=True)


def resolve_repo_root(cwd: Path | None = None) -> Path:
    """Resolve the repo root for a vk command.

    Honors ``$VK_REPO_ROOT`` first (so integration tests can point a command
    at ``tmp_path`` without spawning a fake git repo), then falls back to
    ``git rev-parse --show-toplevel`` (run from ``cwd`` if given), then to
    ``Path.cwd()``.

    The returned path is always ``.resolve()``-d so callers can safely use
    ``Path.is_relative_to`` / ``Path.relative_to`` against other resolved
    paths, even when the source value (env var, git output, or cwd) traversed
    a symlink.

    The empty string is treated like an unset env var (we fall through to
    git) — keeping ``VK_REPO_ROOT=""`` as a way to disable the override
    without unsetting it.
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


class ConfirmAction(enum.Enum):
    """Result of resolving --dry-run / --yes flags."""

    DRY_RUN = "dry_run"
    PROMPT = "prompt"
    APPLY = "apply"


class MutuallyExclusiveError(typer.BadParameter):
    """Raised when --dry-run and --yes are both set."""

    def __init__(self) -> None:
        super().__init__("--dry-run and --yes are mutually exclusive")


def resolve_action(*, dry_run: bool, yes: bool) -> ConfirmAction:
    """Resolve the tri-state: dry-run, interactive prompt, or immediate apply.

    Raises MutuallyExclusiveError if both flags are set.
    """
    if dry_run and yes:
        raise MutuallyExclusiveError()
    if dry_run:
        return ConfirmAction.DRY_RUN
    if yes:
        return ConfirmAction.APPLY
    return ConfirmAction.PROMPT


def confirm_or_exit(message: str = "Proceed?") -> None:
    """Prompt the user for confirmation. Exit with code 0 if declined."""
    if not typer.confirm(message, default=False):
        raise typer.Exit(0)


def format_error(message: str, *, hint: str | None = None) -> str:
    """Format an error message with optional fix hint."""
    lines = [f"Error: {message}"]
    if hint:
        lines.append(f"Hint: {hint}")
    return "\n".join(lines)


def die(message: str, *, code: int = 1, hint: str | None = None) -> NoReturn:
    """Print a Rich-formatted error to stderr and exit."""
    text = Text(f"Error: {message}", style="bold red")
    err_console.print(text)
    if hint:
        err_console.print(Text(f"Hint: {hint}", style="dim"))
    sys.exit(code)


_GATE_REFUSAL_TEMPLATE = """\
Dispatch unavailable -- no `dispatch:` block in \
`docs/superpowers/plan-config.yaml` for this repo.

To enable, add this to the file:

  dispatch:
    target: github-issues
    owner: <your-github-owner>
    default_repo: <owner>/<repo>
    labels:
      agentic: vk-ready
      manual: manual"""


def format_gate_refusal() -> str:
    """Return the canonical dispatch gate refusal message with paste-ready template."""
    return _GATE_REFUSAL_TEMPLATE
