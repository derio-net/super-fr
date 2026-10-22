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
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer

from fr.ops.model import PHASES
from fr.ops.trust import CODE_KEY, diff, tree_changes

if TYPE_CHECKING:
    from fr.ops.load import LoadedOp, OpsConfig, OpSet

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
) -> tuple[dict[str, str], dict[str, str]]:
    """The op set's fingerprint with HEAD's committed tree (minus fr's evidence files),
    and that tree. Refuses (exit 2) while any other path is uncommitted: a probe runs
    only against what a commit pins, so a grant names exactly what it trusted."""
    from fr.git import GitUnavailableError
    from fr.ops.trust import dirty_paths, fingerprint, head_tree, tree_digest

    try:
        dirty = dirty_paths(root)
        tree = head_tree(root)
    except GitUnavailableError as e:
        _refuse(f"cannot read the committed tree: {e}", verb)
    if dirty:
        _refuse(
            "paths have uncommitted changes; probes run only against committed "
            "code: " + ", ".join(dirty),
            verb,
        )
    return fingerprint(ops, config, root, code_tree=tree_digest(tree)), tree


@dataclass
class Selection:
    """What a verb works on: the loaded ops, the ones it selected in `needs` order,
    and the repo's `.fr/ops.yaml`. ONE selection for `status` and `apply`."""

    root: Path
    plan_dir: Path
    opset: OpSet
    ordered: list[LoadedOp]
    config: OpsConfig
    fingerprint: dict[str, str]
    tree: dict[str, str]


def _closure(ids: Sequence[str], ops: Sequence[LoadedOp]) -> list[LoadedOp]:
    """`ids` and every op they need, transitively, in carrier order."""
    book = {lo.op.id: lo for lo in ops}
    wanted: set[str] = set()
    stack = list(ids)
    while stack:
        oid = stack.pop()
        if oid in wanted or oid not in book:
            continue
        wanted.add(oid)
        stack.extend(book[oid].op.needs)
    return [lo for lo in ops if lo.op.id in wanted]


def _select(
    verb: str,
    op_id: str | None,
    plan: Path | None,
    runbook: bool,
    phase: str | None,
    *,
    with_needs: bool = False,
) -> Selection:
    """Load and order the selected ops; refuses (exit 2) on a bad carrier, a cycle, an
    unknown `needs`. `with_needs` (apply) pulls an op's whole `needs` closure in."""
    from fr.ops.engine import OrderError, order
    from fr.ops.load import OpsLoadError, load_ops, load_ops_config

    if phase is not None and phase not in PHASES:
        _refuse(f"--phase must be one of {', '.join(PHASES)} (got {phase!r})", verb)
    root, plan_dir = _plan_dir(verb, plan)
    ids = (op_id,) if op_id else ()
    try:
        opset = load_ops(plan_dir, root, runbook=runbook, ids=() if with_needs else ids)
        config = load_ops_config(root)
        if with_needs and ids:
            selected = _closure(ids, opset.ops)
        else:
            selected = [lo for lo in opset.ops if phase is None or lo.op.phase == phase]
        # A filter narrows the selection, never what exists: a need on a loaded op
        # of the other phase, or (for one op id) on any op, is known, not unknown.
        known = {lo.op.id for lo in opset.ops}
        if ids and not with_needs:
            known |= {n for lo in selected for n in lo.op.needs}
        ordered = order(selected, known=known)
    except (OpsLoadError, OrderError) as e:
        _refuse(str(e), verb)
    for warning in opset.warnings:
        typer.echo(f"fr ops {verb}: warning: {warning}", err=True)
    fp, tree = _current_fingerprint(verb, opset.ops, config, root)
    return Selection(root, plan_dir, opset, ordered, config, fp, tree)


def _require_trust(verb: str, sel: Selection, runbook: bool) -> None:
    """Refuse (exit 2) unless the operator trusted exactly this op set (R19)."""
    from fr.ops.trust import load_trust

    trusted = load_trust(sel.root, sel.plan_dir.name)
    changes = diff(sel.fingerprint, trusted)
    if not changes.untrusted:
        return
    since = f"changed since the grant of {trusted.granted}" if trusted else "never trusted"
    lines = changes.lines()
    if trusted is not None and CODE_KEY in changes.changed:
        paths = tree_changes(trusted.tree, sel.tree)
        lines.append("paths changed: " + (", ".join(paths) if paths else "(unknown)"))
    _refuse(
        f"the op set is not trusted ({since}); no probe ran.\n  "
        + "\n  ".join(lines)
        + f"\nReview the probes, then run `fr ops trust --plan {sel.plan_dir.relative_to(sel.root)}"
        + (" --runbook" if runbook else "")
        + "`.",
        verb,
    )


def _require_ops_profile(verb: str, plan: Path | None) -> None:
    """`apply`, `attest` and `seal` refuse (exit 2) outside an ops profile (R6), printing
    the ops-workspace route."""
    from fr.git import repo_root as git_repo_root
    from fr.ops.profile import in_ops_profile, refusal_route

    try:
        root = git_repo_root(Path.cwd())
    except Exception:  # noqa: BLE001
        _refuse("not inside a git repository", verb)
    if in_ops_profile(root):
        return
    slug = plan.name if plan is not None else plan_of_current_branch(root)
    slug = slug.name if isinstance(slug, Path) else slug
    _refuse(refusal_route(root, slug=slug or "<slug>"), verb)


def _runners(sel: Selection):  # type: ignore[no-untyped-def]
    from fr.ops.engine import ShellRunner
    from fr.ops.evidence import JournalEvidence
    from fr.ops.identity import LiveIdentities

    return (
        ShellRunner(
            sel.root, passthrough=sel.config.env_passthrough, timeout=sel.config.timeout_seconds
        ),
        LiveIdentities(sel.config, sel.root),
        JournalEvidence(sel.root, sel.plan_dir.name),
    )


def _recorder(sel: Selection):  # type: ignore[no-untyped-def]
    from fr.ops.evidence import record_op

    def record(**kw: object) -> object:
        return record_op(sel.root, sel.plan_dir.name, **kw)  # type: ignore[arg-type]

    return record


def _prompt():  # type: ignore[no-untyped-def]
    """The operator's terminal; a seam for tests."""
    from fr.ops.apply import TtyPrompt

    return TtyPrompt()


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
    from fr.ops.engine import exit_code
    from fr.ops.engine import status as op_status
    from fr.ops.profile import in_ops_profile

    sel = _select("status", op_id, plan, runbook, phase)
    if not in_ops_profile(sel.root):
        typer.echo(PROFILE_WARNING, err=True)
    _require_trust("status", sel, runbook)

    runner, identities, journal = _runners(sel)
    rows = op_status(sel.ordered, runner=runner, identities=identities, journal=journal)
    payload = [r.as_row() for r in rows]
    if as_json:
        typer.echo(json.dumps(payload, indent=2))
    elif payload:
        typer.echo(render_text(payload, explain=explain))
    else:
        typer.echo("no ops selected")
    raise typer.Exit(code=exit_code(rows))


@ops_app.command("apply")
def apply(
    op_id: Annotated[str | None, typer.Argument(help="One op (and what it needs).")] = None,
    plan: Annotated[Path | None, PLAN_OPTION] = None,
    runbook: Annotated[bool, RUNBOOK_OPTION] = False,
    phase: Annotated[str | None, typer.Option("--phase", help="pre-merge | post-merge")] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Confirm non-mutating ops.")] = False,
    yes_mutating: Annotated[
        bool, typer.Option("--yes-mutating", help="Also confirm mutating ops.")
    ] = False,
) -> None:
    """Apply one op, or a whole phase, in `needs` order; stop at the first failure.

    Each op is checked first and skipped when DONE or N/A. Runs only in an ops profile
    and only on a trusted op set (`fr ops trust`)."""
    from fr.ops.apply import ApplyRefused, ShellApplier, apply_ops
    from fr.ops.engine import OrderError

    if (op_id is None) == (phase is None):
        _refuse("name one op or pass --phase pre-merge|post-merge", "apply")
    _require_ops_profile("apply", plan)
    sel = _select("apply", op_id, plan, runbook, phase, with_needs=True)
    if plan is None and any(lo.runbook for lo in sel.ordered):
        _refuse("a runbook op's evidence needs a named plan: pass --plan <dir>", "apply")
    _require_trust("apply", sel, runbook)

    runner, identities, journal = _runners(sel)
    try:
        result = apply_ops(
            sel.ordered,
            runner=runner,
            applier=ShellApplier(
                sel.root,
                passthrough=sel.config.env_passthrough,
                timeout=sel.config.timeout_seconds,
            ),
            identities=identities,
            journal=journal,
            prompt=_prompt(),
            record=_recorder(sel),  # type: ignore[arg-type]
            yes=yes,
            yes_mutating=yes_mutating,
            known={lo.op.id for lo in sel.opset.ops},
        )
    except (ApplyRefused, OrderError) as e:
        _refuse(str(e), "apply")
    for step in result.steps:
        typer.echo(step.message)
    if not result.steps:
        typer.echo("no ops selected")
    raise typer.Exit(code=0 if result.ok else 1)


@ops_app.command("attest")
def attest(
    op_id: Annotated[str, typer.Argument(help="The UNVERIFIABLE op to close.")],
    note: Annotated[str, typer.Option("--note", help="What you did or saw.")],
    plan: Annotated[Path | None, PLAN_OPTION] = None,
    runbook: Annotated[bool, RUNBOOK_OPTION] = False,
) -> None:
    """Close an UNVERIFIABLE op as DONE (attested), at a terminal, in an ops profile.

    Status and the PR body always show it apart from a checked op."""
    from fr.ops.attest import AttestRefused, attest_op

    _require_ops_profile("attest", plan)
    sel = _select("attest", op_id, plan, runbook, None, with_needs=True)
    lo = next((x for x in sel.opset.ops if x.op.id == op_id), None)
    if lo is None:
        _refuse(f"no op {op_id!r}", "attest")
    if lo.runbook and plan is None:
        _refuse("a runbook op's evidence needs a named plan: pass --plan <dir>", "attest")
    _require_trust("attest", sel, runbook)
    runner, identities, journal = _runners(sel)
    try:
        row = attest_op(
            lo,
            note=note,
            runner=runner,
            identities=identities,
            journal=journal,
            prompt=_prompt(),
            record=_recorder(sel),  # type: ignore[arg-type]
        )
    except AttestRefused as e:
        _refuse(str(e), "attest")
    typer.echo(f"{op_id}: {row.label}")


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
    fp, tree = _current_fingerprint("trust", opset.ops, config, root)
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
    entry = grant_trust(root, plan_dir.name, fp, tree=tree)
    typer.echo(f"trusted: {entry.id} (sha256 {set_hash(fp)}); the grant is yours, not the repo's")


# --- safety helpers (R10): generic, tool-neutral ---------------------------------


def _helper_root(verb: str) -> Path:
    from fr.git import repo_root as git_repo_root

    try:
        return git_repo_root(Path.cwd())
    except Exception:  # noqa: BLE001
        _refuse("not inside a git repository", verb)


@ops_app.command("seal")
def seal(
    encrypt: Annotated[
        str,
        typer.Option(
            "--encrypt",
            help="Command that writes ciphertext to {out}; {in} is a 0600 plaintext temp "
            "file outside the repo (filled from stdin), {target} the target's name.",
        ),
    ],
    target: Annotated[Path, typer.Option("--target", help="The file to replace with {out}.")],
) -> None:
    """Encrypt stdin into --target without ever leaving plaintext behind.

    The target changes only when the command exits 0 and wrote a non-empty {out}.
    Runs only in an ops profile."""
    import sys

    from fr.ops import helpers

    _require_ops_profile("seal", None)
    root = _helper_root("seal")
    try:
        rc = helpers.seal(encrypt, target, sys.stdin.buffer.read(), repo_root=root)
    except helpers.HelperError as e:
        _refuse(str(e), "seal")
    if rc != 0:
        typer.echo(
            f"fr ops seal: the encrypt command failed (exit {rc}); {target} is unchanged", err=True
        )
    raise typer.Exit(code=rc)


@ops_app.command("secret")
def secret(
    source: Annotated[str, typer.Option("--from", help="Command that prints the value.")],
    command: Annotated[
        list[str], typer.Argument(help="Command to run; it reads the value on stdin.")
    ],
) -> None:
    """Read a value live and pass it to COMMAND on stdin; never to stdout."""
    from fr.ops import helpers

    root = _helper_root("secret")
    try:
        rc = helpers.secret(source, command, repo_root=root)
    except helpers.HelperError as e:
        _refuse(str(e), "secret")
    raise typer.Exit(code=rc)


@ops_app.command("clip")
def clip(
    source: Annotated[str, typer.Option("--from", help="Command that prints the value.")],
) -> None:
    """Put a value on the clipboard."""
    from fr.ops import helpers

    root = _helper_root("clip")
    try:
        rc = helpers.clip(source, repo_root=root)
    except helpers.HelperError as e:
        _refuse(str(e), "clip")
    raise typer.Exit(code=rc)


@ops_app.command("scratch")
def scratch(
    cleanup: Annotated[str, typer.Option("--cleanup", help="Command run on any exit.")],
    command: Annotated[list[str], typer.Argument(help="Command to run.")],
) -> None:
    """Run COMMAND, then --cleanup on success, failure, Ctrl-C or SIGTERM."""
    from fr.ops import helpers

    raise typer.Exit(code=helpers.scratch(cleanup, command))
