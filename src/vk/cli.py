"""VK CLI — main entry point."""

import typer

from vk import __version__
from vk.commands.dispatch_cmd import dispatch_app
from vk.commands.execute_cmd import execute_app
from vk.commands.init_cmd import init as init_command
from vk.commands.install_cmd import install_skills as install_skills_command
from vk.commands.plan_cmd import plan_app
from vk.commands.progress_cmd import progress_app

app = typer.Typer(
    name="vk",
    help="VK toolchain: plans, dispatch, progress, execution.",
    no_args_is_help=True,
)

app.add_typer(plan_app, name="plan")
app.add_typer(dispatch_app, name="dispatch")
app.add_typer(progress_app, name="progress")
app.add_typer(execute_app, name="execute")
app.command(name="init")(init_command)
app.command(name="install-skills")(install_skills_command)


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
