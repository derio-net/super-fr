"""VK CLI — main entry point.

Exit code conventions (uniform across every subcommand):
  0 = success
  1 = lint failure (e.g. `vk plan self-review` found errors)
  2 = usage error or plan-edit refusal (bad flags, missing args,
      `plan_ops.PlanEditError`)
  4 = gh / network failure during `vk apply`
  5 = plan parse error (`PlanSchemaError`)

Mutating commands (`vk apply`, `vk migrate v1-to-v2`) default to a
dry-run. Pass `--yes` to actually write changes.
"""

from __future__ import annotations

import typer

from vk import __version__
from vk.commands.apply_cmd import apply_command
from vk.commands.archive_cmd import archive_command
from vk.commands.init_cmd import init_app
from vk.commands.isolation_cmd import isolation_app
from vk.commands.migrate_cmd import migrate_app
from vk.commands.pickup_cmd import pickup_command
from vk.commands.plan_cmd import plan_app
from vk.commands.repair_cmd import repair_command
from vk.commands.skills_cmd import skills as skills_command
from vk.commands.spec_cmd import spec_app
from vk.commands.status_cmd import status_command
from vk.commands.undispatch_cmd import undispatch_command

app = typer.Typer(
    name="vk",
    help="VK toolchain: v2 plan-as-folder, render → observe → diff → apply.",
    no_args_is_help=True,
)

app.command(name="apply", help="Render + observe + diff + apply for a plan.")(apply_command)
app.command(name="status", help="Read-only plan report (allowlist-safe; never mutates).")(
    status_command
)
app.command(name="archive", help="Move finished plans (and specs) to implemented/.")(
    archive_command
)
app.command(name="undispatch", help="Close a plan's tracking Issues and null the fields.")(
    undispatch_command
)
app.command(name="pickup", help="Output phase scope (markdown) for an agent.")(pickup_command)
app.command(name="repair", help="Normalize stale plan/spec refs (dry-run; --yes to write).")(
    repair_command
)
app.add_typer(plan_app, name="plan")
app.add_typer(spec_app, name="spec")
app.add_typer(migrate_app, name="migrate")
app.add_typer(isolation_app, name="isolation")
app.add_typer(init_app, name="init")
app.command(name="skills")(skills_command)


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
    """VK toolchain: v2 plan-as-folder, render → observe → diff → apply."""
