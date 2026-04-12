"""VK CLI — main entry point."""

import typer

from vk import __version__
from vk.commands.dispatch_cmd import dispatch
from vk.commands.execute_cmd import execute_app
from vk.commands.plan_cmd import plan_app
from vk.commands.progress_cmd import progress_app

app = typer.Typer(
    name="vk",
    help="VK toolchain: plans, dispatch, progress, execution.",
    no_args_is_help=True,
)

app.add_typer(plan_app, name="plan")
app.command(name="dispatch")(dispatch)
app.add_typer(progress_app, name="progress")
app.add_typer(execute_app, name="execute")


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"vk {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """VK toolchain: plans, dispatch, progress, execution."""


@app.command()
def init(
    dispatch: str | None = typer.Option(
        None, "--dispatch", help="Enable dispatch with OWNER/REPO."
    ),
    project: str | None = typer.Option(None, "--project", help="Project board name."),
) -> None:
    """Scaffold plan-config.yaml in a new repo."""
    typer.echo("vk init: not yet implemented")
    raise typer.Exit(1)


@app.command(name="install-skills")
def install_skills(
    copy: bool = typer.Option(False, "--copy", help="Copy instead of symlink."),
) -> None:
    """Symlink SKILL.md files into ~/.claude/skills/."""
    typer.echo("vk install-skills: not yet implemented")
    raise typer.Exit(1)
