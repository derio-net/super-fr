"""fr cloud — a Claude Code cloud session's environment (spec 2026-10-07-cloud-triage R23, §H).

`doctor` lists every prerequisite and exits 1 when one fails; `setup-script` prints the
environment setup script to paste into the cloud environment. Both write nothing, so the
group is in `fr.artifacts.trigger.READ_ONLY_COMMANDS`: it is what an operator runs when
the environment is not yet fit for fr, stale artifacts included.
"""

from __future__ import annotations

import typer

from fr import cloud

cloud_app = typer.Typer(
    name="cloud",
    help="Claude Code cloud sessions: check the environment, print its setup script.",
    no_args_is_help=True,
)


@cloud_app.command("doctor")
def doctor() -> None:
    """Every cloud prerequisite (forge.api, the plugin, the repo's agents artifact, a
    current fr, rsync) and its state; exits 1 when any fails."""
    checks = cloud.check(repo_root=cloud.repo_root_of())
    for c in checks:
        mark = "ok  " if c.ok else "FAIL"
        typer.echo(f"{mark} {c.name}: {c.detail}")
        if not c.ok:
            typer.echo(f"     fix: {c.fix}")
    failed = [c for c in checks if not c.ok]
    if not failed:
        typer.echo("every cloud prerequisite holds")
        return
    if cloud.detect():
        typer.echo("")
        typer.echo(cloud.remedy_block([c.item for c in failed]))
    raise typer.Exit(1)


@cloud_app.command("setup-script")
def setup_script() -> None:
    """Print the cloud environment setup script (paste it into the environment's
    Setup script; new sessions run it). fr never runs it."""
    root = cloud.repo_root_of()
    typer.echo(cloud.setup_script(root.name if root is not None else None), nl=False)
