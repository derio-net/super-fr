"""VK CLI — main entry point.

Exit code conventions (uniform across every subcommand):
  0 = success
  1 = lint failure (e.g. `fr plan self-review` found errors)
  2 = usage error or plan-edit refusal (bad flags, missing args,
      `plan_ops.PlanEditError`)
  4 = gh / network failure during `fr apply`
  5 = plan parse error (`PlanSchemaError`)

Mutating commands (`fr apply`, `fr migrate v1-to-v2`) default to a
dry-run. Pass `--yes` to actually write changes.
"""

from __future__ import annotations

import typer

from fr import __version__
from fr.artifacts.trigger import ensure_artifacts_current
from fr.commands.acceptance_cmd import acceptance_app
from fr.commands.apply_cmd import apply_command
from fr.commands.archive_cmd import archive_command
from fr.commands.hermes_cmd import hermes_app
from fr.commands.init_cmd import init_app
from fr.commands.isolation_cmd import isolation_app
from fr.commands.journal_cmd import journal_app
from fr.commands.migrate_cmd import migrate_app
from fr.commands.models_cmd import models_app
from fr.commands.pickup_cmd import pickup_command
from fr.commands.plan_cmd import plan_app
from fr.commands.repair_cmd import repair_command
from fr.commands.repos_cmd import repos_app
from fr.commands.run_cmd import run_app
from fr.commands.skills_cmd import skills as skills_command
from fr.commands.spec_cmd import spec_app
from fr.commands.status_cmd import status_command
from fr.commands.undispatch_cmd import undispatch_command
from fr.commands.validate_cmd import validate_app
from fr.commands.workflow_cmd import workflow_app

app = typer.Typer(
    name="fr",
    help="super-fr: plan-as-folder superpowers toolchain, render → observe → diff → apply.",
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
app.command(
    name="repair",
    help="Normalize stale plan/spec refs + strip dead plan-config keys (dry-run; --yes to write).",
)(repair_command)
app.add_typer(acceptance_app, name="acceptance")
app.add_typer(plan_app, name="plan")
app.add_typer(spec_app, name="spec")
app.add_typer(migrate_app, name="migrate")
app.add_typer(isolation_app, name="isolation")
app.add_typer(init_app, name="init")
app.add_typer(repos_app, name="repos")
app.add_typer(journal_app, name="journal")
app.add_typer(models_app, name="models")
app.add_typer(hermes_app, name="hermes")
app.add_typer(workflow_app, name="workflow")
app.add_typer(run_app, name="run")
app.add_typer(validate_app, name="validate")
app.command(name="skills")(skills_command)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"fr {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool | None = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """VK toolchain: v2 plan-as-folder, render → observe → diff → apply."""
    # The obligatory artifact-migration trigger (spec §3.C). It runs before
    # every non-exempt command: in an interactive context stale artifacts are
    # migrated and committed and the typed command then runs, and in a daemon /
    # CI context the command is refused loudly with nothing written.
    #
    # The exemptions are EIGHT, not four (corrected in review r5-d1): `--help`,
    # `--version`, `FR_SKIP_MIGRATION=1`, `fr migrate` — and the five read-only
    # commands `status`, `skills`, `isolation`, `init`, `validate`. That
    # matters for reading the spec's own Test Plan: `fr status` is EXEMPT, so
    # it can never be the command that demonstrates a migration. The list lives
    # in `fr.artifacts.trigger.EXEMPTIONS` and is pinned literally by
    # `tests/unit/test_migration_trigger.py::test_the_exemption_list_is_exactly_these_things`.
    ensure_artifacts_current(invoked_subcommand=ctx.invoked_subcommand)
