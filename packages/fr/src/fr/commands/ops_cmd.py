"""`fr ops` — checkable, runnable manual operations (spec 2026-10-22-fr-ops).

The whole group is gated by the artifact trigger (R17): it is deliberately NOT in
`fr.artifacts.trigger.READ_ONLY_COMMANDS`, `status` included.

`status` (R3) runs each op's probes against the live system and folds the plan
journal's recorded evidence, and it writes nothing. Probes are repo-authored code
and run only once `fr ops trust` (R19) accepted the exact op set. Exit 0 when every
op is DONE or N/A, 1 when any is OPEN, UNVERIFIABLE or CANNOT-VERIFY, 3 when any
ESCALATEs, 2 on a refusal.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer

from fr.ops.model import PHASES
from fr.ops.trust import CODE_KEY, code_paths_since, diff

if TYPE_CHECKING:
    from fr.ops.load import LoadedOp, OpsConfig

ops_app = typer.Typer(
    help="Manual operations: check, apply, attest (spec 2026-10-22-fr-ops).",
    no_args_is_help=True,
)

PROFILE_WARNING = (
    "fr ops status: not inside an ops profile — checks run with this environment's "
    "credentials, which may not be the ones the ops need"
)


def _refuse(message: str, verb: str = "status") -> NoReturn:
    typer.echo(f"fr ops {verb}: {message}", err=True)
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


PLAN_OPTION = typer.Option("--plan", help="Plan dir (default: the plan of this branch's run).")
RUNBOOK_OPTION = typer.Option("--runbook", help="Also select every op in the repo runbook.")


def _interactive() -> bool:
    """An operator at a terminal (the artifact gate's predicate); a seam for tests."""
    from fr.artifacts.trigger import is_interactive

    return is_interactive()


def _plan_dir(verb: str, plan: Path | None) -> tuple[Path, Path]:
    """`(repo root, plan dir)`, refusing (exit 2) when either cannot be found."""
    from fr.git import repo_root as git_repo_root

    try:
        root = git_repo_root(Path.cwd())
    except Exception:  # noqa: BLE001 — any git failure means "not in a repo"
        _refuse("not inside a git repository", verb)
    plan_dir = (root / plan) if plan is not None else plan_of_current_branch(root)
    if plan_dir is None:
        _refuse("no run on this branch records a plan; pass --plan <dir>", verb)
    if not plan_dir.is_dir():
        _refuse(f"no plan at {plan_dir}", verb)
    return root, plan_dir


def _current_fingerprint(
    verb: str, ops: Sequence[LoadedOp], config: OpsConfig, root: Path
) -> tuple[dict[str, str], str | None]:
    """The op set's fingerprint with HEAD's committed code tree, and HEAD. Refuses
    (exit 2) while any code path is uncommitted: a probe runs only against code a
    commit pins, so a grant always names exactly what it trusted."""
    from fr.ops.trust import dirty_code, fingerprint, head_code

    dirty = dirty_code(root)
    if dirty:
        _refuse(
            "code paths have uncommitted changes; probes run only against committed "
            "code: " + ", ".join(dirty),
            verb,
        )
    tree, commit = head_code(root)
    return fingerprint(ops, config, root, code_tree=tree), commit


@ops_app.command("status")
def status(
    op_id: Annotated[str | None, typer.Argument(help="One op to report.")] = None,
    plan: Annotated[Path | None, PLAN_OPTION] = None,
    runbook: Annotated[bool, RUNBOOK_OPTION] = False,
    phase: Annotated[str | None, typer.Option("--phase", help="pre-merge | post-merge")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="One JSON row per op.")] = False,
    explain: Annotated[
        bool, typer.Option("--explain", help="Show what a vacuous probe would look like.")
    ] = False,
) -> None:
    """Report each selected op's state, running its probes. Writes nothing.

    Probes are repo-authored code: they run only once `fr ops trust` accepted
    this exact op set, and status refuses (exit 2) while it differs."""
    from fr.ops.engine import OrderError, ShellRunner, exit_code, order
    from fr.ops.engine import status as op_status
    from fr.ops.evidence import JournalEvidence
    from fr.ops.identity import LiveIdentities
    from fr.ops.load import OpsLoadError, load_ops, load_ops_config
    from fr.ops.profile import in_ops_profile
    from fr.ops.trust import load_trust

    if phase is not None and phase not in PHASES:
        _refuse(f"--phase must be one of {', '.join(PHASES)} (got {phase!r})")
    root, plan_dir = _plan_dir("status", plan)
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

    fp, commit = _current_fingerprint("status", opset.ops, config, root)
    trusted = load_trust(root, plan_dir.name)
    changes = diff(fp, trusted)
    if changes.untrusted:
        since = f"changed since the grant of {trusted.granted}" if trusted else "never trusted"
        lines = changes.lines()
        if trusted is not None and CODE_KEY in changes.changed:
            paths = code_paths_since(root, trusted)
            lines.append("code paths changed: " + (", ".join(paths) if paths else "(unknown)"))
        _refuse(
            f"the op set is not trusted ({since}); no probe ran.\n  "
            + "\n  ".join(lines)
            + f"\nReview the probes, then run `fr ops trust --plan {plan_dir.relative_to(root)}"
            + (" --runbook" if runbook else "")
            + "`."
        )

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


@ops_app.command("trust")
def trust(
    plan: Annotated[Path | None, PLAN_OPTION] = None,
    runbook: Annotated[bool, RUNBOOK_OPTION] = False,
) -> None:
    """Show every probe and command of the selected ops and, confirmed at a
    terminal, record that you trust this exact set — in your own store outside the
    repo (a plan-journal line records it for audit). Probes are repo-authored code;
    nothing runs them until then."""
    from fr.ops.load import OpsLoadError, load_ops, load_ops_config
    from fr.ops.trust import describe, grant_trust, load_trust, set_hash

    root, plan_dir = _plan_dir("trust", plan)
    try:
        opset = load_ops(plan_dir, root, runbook=runbook)
        config = load_ops_config(root)
    except OpsLoadError as e:
        _refuse(str(e), "trust")
    fp, commit = _current_fingerprint("trust", opset.ops, config, root)
    trusted = load_trust(root, plan_dir.name)
    if trusted is not None and trusted.sha256 == set_hash(fp):
        typer.echo(f"already trusted (granted {trusted.granted}); nothing written")
        return
    typer.echo(describe(opset.ops, config, root))
    changes = diff(fp, trusted)
    if trusted is not None:
        typer.echo(f"since the grant of {trusted.granted}: " + "; ".join(changes.lines()))
    if not _interactive():
        _refuse("trust is granted only at a terminal; nothing written", "trust")
    if not typer.confirm(f"Trust these {len(opset.ops)} op(s) to run on this machine?"):
        typer.echo("not trusted; nothing written")
        raise typer.Exit(code=1)
    entry = grant_trust(root, plan_dir.name, fp, commit=commit)
    typer.echo(f"trusted: {entry.id} (sha256 {set_hash(fp)}); the grant is yours, not the repo's")
