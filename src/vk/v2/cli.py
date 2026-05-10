"""v2 typer subapp — mounted at `vk v2 ...` during the v1↔v2 coexistence.

Phase 4 retires v1 and promotes these commands to top-level (e.g.
`vk v2 apply` becomes `vk apply`). Until then, the `v2` namespace
keeps v2 commands cleanly separated from v1's surface so name
collisions (e.g. `vk plan rework` exists in both) don't fight.
"""

from __future__ import annotations

import typer

from vk.v2.commands.apply_cmd import apply_command
from vk.v2.commands.migrate_cmd import migrate_app
from vk.v2.commands.pickup_cmd import pickup_command
from vk.v2.commands.plan_cmd import plan_app
from vk.v2.commands.spec_cmd import spec_app

v2_app = typer.Typer(
    name="v2",
    help="v2 commands (will be promoted to top-level in Phase 4).",
    no_args_is_help=True,
)

v2_app.command(name="apply", help="Render + observe + diff + apply for a v2 plan.")(apply_command)
v2_app.command(name="pickup", help="Output phase scope (markdown) for an agent.")(pickup_command)
v2_app.add_typer(plan_app, name="plan")
v2_app.add_typer(spec_app, name="spec")
v2_app.add_typer(migrate_app, name="migrate")
