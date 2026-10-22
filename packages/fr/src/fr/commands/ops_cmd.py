"""`fr ops` — checkable, runnable manual operations (spec 2026-10-22-fr-ops).

The whole group is gated by the artifact trigger (R17): it is deliberately NOT in
`fr.artifacts.trigger.READ_ONLY_COMMANDS`, `status` included.

`status` (R3) reads: it runs each op's probes against the live system and folds
the plan journal's recorded evidence, and it writes nothing. Exit 0 when every
op is DONE or N/A, 1 when any is OPEN, UNVERIFIABLE or CANNOT-VERIFY, 3 when any
ESCALATEs, 2 on a refusal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from fr.ops.model import PHASES

ops_app = typer.Typer(
    help="Manual operations: check, apply, attest (spec 2026-10-22-fr-ops).",
    no_args_is_help=True,
)

PROFILE_WARNING = (
    "fr ops status: not inside an ops profile — checks run with this environment's "
    "credentials, which may not be the ones the ops need"
)


def _refuse(message: str) -> NoReturn:
    typer.echo(f"fr ops status: {message}", err=True)
    raise typer.Exit(code=2)


def plan_of_current_branch(repo_root: Path) -> Path | None:
    """The plan dir recorded by the run whose `branch` is the one checked out
    here; `None` when there is no such run, or the runs disagree."""
    from fr.record.model import RUNS_REL
    from fr.run.adopt import current_branch
    from fr.run.model import RunStateError, parse_run_state

    branch = current_branch(repo_root)
    runs_dir = repo_root / RUNS_REL
    if branch is None or not runs_dir.is_dir():
        return None
    plans: set[str] = set()
    for path in sorted(runs_dir.glob("*.yaml")):
        try:
            state = parse_run_state(path.read_text())
        except (RunStateError, OSError):
            continue
        if state.branch != branch:
            continue
        plans |= {
            r.emitted["plan"] for r in state.steps.values() if r.emitted and "plan" in r.emitted
        }
    return repo_root / plans.pop() if len(plans) == 1 else None


def render_text(rows: list[dict[str, object]], *, explain: bool) -> str:
    """The text rendering of `StatusRow.as_row()` rows — the same rows `--json` prints."""
    width = max((len(str(r["label"])) for r in rows), default=0)
    lines = []
    for r in rows:
        detail = r["reason"] or r["summary"]
        who = f" (as {r['identity']})" if r["identity"] else ""
        lines.append(f"{r['label']!s:<{width}}  {r['op']}  [{r['phase']}]  {detail}{who}")
        if explain and r["vacuous_if"]:
            lines.append(f"{'':<{width}}    vacuous if: {r['vacuous_if']}")
    return "\n".join(lines)


@ops_app.command("status")
def status(
    op_id: Annotated[str | None, typer.Argument(help="One op to report.")] = None,
    plan: Annotated[
        Path | None,
        typer.Option("--plan", help="Plan dir (default: the plan of this branch's run)."),
    ] = None,
    runbook: Annotated[
        bool, typer.Option("--runbook", help="Also select every op in the repo runbook.")
    ] = False,
    phase: Annotated[str | None, typer.Option("--phase", help="pre-merge | post-merge")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="One JSON row per op.")] = False,
    explain: Annotated[
        bool, typer.Option("--explain", help="Show what a vacuous probe would look like.")
    ] = False,
) -> None:
    """Report each selected op's state. Reads only; never writes."""
    from fr.git import repo_root as git_repo_root
    from fr.ops.engine import OrderError, ShellRunner, exit_code, order
    from fr.ops.engine import status as op_status
    from fr.ops.evidence import JournalEvidence
    from fr.ops.identity import LiveIdentities
    from fr.ops.load import OpsLoadError, load_ops, load_ops_config
    from fr.ops.profile import in_ops_profile

    if phase is not None and phase not in PHASES:
        _refuse(f"--phase must be one of {', '.join(PHASES)} (got {phase!r})")
    try:
        root = git_repo_root(Path.cwd())
    except Exception:  # noqa: BLE001 — any git failure means "not in a repo"
        _refuse("not inside a git repository")
    plan_dir = (root / plan) if plan is not None else plan_of_current_branch(root)
    if plan_dir is None:
        _refuse("no run on this branch records a plan; pass --plan <dir>")
    if not plan_dir.is_dir():
        _refuse(f"no plan at {plan_dir}")
    if not in_ops_profile():
        typer.echo(PROFILE_WARNING, err=True)

    ids = (op_id,) if op_id else ()
    try:
        opset = load_ops(plan_dir, root, runbook=runbook, ids=ids)
        selected = [lo for lo in opset.ops if phase is None or lo.op.phase == phase]
        # A filter narrows the selection, never what exists: a need on a loaded op
        # of the other phase, or (for one op id) on any op, is known, not unknown.
        known = {lo.op.id for lo in opset.ops}
        if ids:
            known |= {n for lo in selected for n in lo.op.needs}
        ordered = order(selected, known=known)
        config = load_ops_config(root)
    except (OpsLoadError, OrderError) as e:
        _refuse(str(e))
    for warning in opset.warnings:
        typer.echo(f"fr ops status: warning: {warning}", err=True)

    rows = op_status(
        ordered,
        runner=ShellRunner(
            root, passthrough=config.env_passthrough, timeout=config.timeout_seconds
        ),
        identities=LiveIdentities(config, root),
        journal=JournalEvidence(root, plan_dir.name),
    )
    payload = [r.as_row() for r in rows]
    if as_json:
        typer.echo(json.dumps(payload, indent=2))
    elif payload:
        typer.echo(render_text(payload, explain=explain))
    else:
        typer.echo("no ops selected")
    raise typer.Exit(code=exit_code(rows))
