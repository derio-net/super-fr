"""`fr ops` — checkable, runnable manual operations (spec 2026-10-22-fr-ops).

The whole group is gated by the artifact trigger (R17): it is deliberately NOT in
`fr.artifacts.trigger.READ_ONLY_COMMANDS`, `status` included.
"""

from __future__ import annotations

import typer

ops_app = typer.Typer(
    help="Manual operations: check, apply, attest (spec 2026-10-22-fr-ops).",
    no_args_is_help=True,
)


@ops_app.command("status")
def status() -> None:
    """Report each selected op's state. Reads only; never writes."""
