"""`fr hermes ...` CLI — install/uninstall super-fr into a Hermes Agent home.

Thin wrapper over `fr.hermes`; install.sh's opt-in Hermes path calls these so
every invasive, reversible mutation (cli-config.yaml hooks merge, allowlist,
SOUL.md managed block, hook-tree copy) is tested Python, not bash.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from fr import hermes

hermes_app = typer.Typer(help="Install/uninstall super-fr into a Hermes Agent home.")
_console = Console()


@hermes_app.command("install")
def install_cmd(
    source: Path = typer.Option(
        ..., "--source", help="super-fr repo/plugin root (holds .hermes/ and plugins/)."
    ),
    home: Path = typer.Option(
        None, "--home", help="Hermes home dir (default: $HERMES_HOME or ~/.hermes)."
    ),
) -> None:
    """Merge super-fr's hooks, allowlist them, and apply the SOUL.md block."""
    target = home or hermes.hermes_home()
    try:
        hermes.install(source, target)
    except hermes.HermesError as exc:
        _console.print(f"[red]fr hermes install:[/red] {exc}")
        raise typer.Exit(1) from exc
    _console.print(f"fr hermes: installed into {target}")


@hermes_app.command("uninstall")
def uninstall_cmd(
    source: Path = typer.Option(
        ..., "--source", help="super-fr repo/plugin root (holds .hermes/ and plugins/)."
    ),
    home: Path = typer.Option(
        None, "--home", help="Hermes home dir (default: $HERMES_HOME or ~/.hermes)."
    ),
) -> None:
    """Reverse install: strip super-fr's hooks, allowlist, SOUL block, hook tree."""
    target = home or hermes.hermes_home()
    try:
        hermes.uninstall(source, target)
    except hermes.HermesError as exc:
        _console.print(f"[red]fr hermes uninstall:[/red] {exc}")
        raise typer.Exit(1) from exc
    _console.print(f"fr hermes: uninstalled from {target}")
