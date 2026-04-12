"""VK CLI — main entry point."""

import typer

from vk import __version__

app = typer.Typer(
    name="vk",
    help="VK toolchain: plans, dispatch, progress, execution.",
    no_args_is_help=True,
)

plan_app = typer.Typer(help="Write, save, and maintain plan files.")
dispatch_app = typer.Typer(help="Dispatch a phased plan to GitHub Issues.")
progress_app = typer.Typer(help="Track work lifecycle.")
execute_app = typer.Typer(help="Helpers for phase/task execution.")

app.add_typer(plan_app, name="plan")
app.add_typer(dispatch_app, name="dispatch")
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


# Stub subcommands so --help works for each group


@plan_app.callback(invoke_without_command=True)
def plan_callback(ctx: typer.Context) -> None:
    """Write, save, and maintain plan files."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@dispatch_app.callback(invoke_without_command=True)
def dispatch_callback(ctx: typer.Context) -> None:
    """Dispatch a phased plan to GitHub Issues."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@progress_app.callback(invoke_without_command=True)
def progress_callback(ctx: typer.Context) -> None:
    """Track work lifecycle."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@execute_app.callback(invoke_without_command=True)
def execute_callback(ctx: typer.Context) -> None:
    """Helpers for phase/task execution."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
