"""`fr plan ...` CLI subcommands — wraps vk.plan_ops."""

from __future__ import annotations

from pathlib import Path

import typer
from click.core import ParameterSource
from rich.console import Console
from rich.table import Table

from fr import parse
from fr.commands.common import require_migrated_layout
from fr.parser import PlanSchemaError
from fr.plan_ops import (
    PhaseSpec,
    PlanEditError,
    complete_phase,
    create,
    rework_add_origin,
    rework_create,
    rework_list,
    self_review,
    tick,
)

console = Console()
err_console = Console(stderr=True)

# Widened past the 3.19.0 -> 4.0.0 major bump (Phase 11 of the 2026-08-14
# workflow-shapes plan) — a <4.0.0 ceiling would make every plan created on
# 4.0.0+ fr fail its own version gate at parse time. See that plan's spec
# §5 "fr_version must span the bump".
DEFAULT_FR_VERSION = ">=3.0.0,<5.0.0"

# The floor a plan that names a `workflow:` shape must carry (spec §4.A.1).
# `PlanMeta` is extra="forbid", so fr < 4.0.0 does not skip the unknown key
# — it fails the parse outright. The constraint is the plan telling older fr
# not to try.
WORKFLOW_FR_VERSION = ">=4.0.0,<5.0.0"

_PRE_4_PROBES = ("0.1.0", "2.0.0", "3.0.0", "3.19.0", "3.999.999")


def _admits_pre_4(constraint: str) -> bool:
    """Does `constraint` allow an fr older than 4.0.0 to load the plan?

    Probes rather than parses the specifier's bounds: `SpecifierSet` has no
    "minimum version" accessor, and probing is what actually matters — the
    question is whether some real fr 3.x would consider itself allowed.
    An unparseable constraint answers False; `fr.parser` fails it loudly at
    parse time and duplicating that error here would only mask it.
    """
    from packaging.specifiers import InvalidSpecifier, SpecifierSet

    try:
        spec = SpecifierSet(constraint)
    except InvalidSpecifier:
        return False
    return any(spec.contains(v) for v in _PRE_4_PROBES)


plan_app = typer.Typer(help="v2 plan editing commands.", no_args_is_help=True)


@plan_app.callback()
def _plan_guard() -> None:
    """Runs before every `fr plan ...` subcommand (legacy-layout hard-stop)."""
    require_migrated_layout()


@plan_app.command("create")
def create_cmd(
    ctx: typer.Context,
    slug: str = typer.Option(..., "--slug", help="Plan slug (becomes folder name)."),
    target_repo: str = typer.Option(..., "--target-repo", help="owner/repo for phases."),
    spec: Path | None = typer.Option(
        None, "--spec", help="Spec path relative to repo root (optional)."
    ),
    fr_version: str = typer.Option(
        DEFAULT_FR_VERSION,
        "--fr-version",
        help="fr_version constraint for the plan.",
    ),
    workflow: str | None = typer.Option(
        None,
        "--workflow",
        help=(
            "Workflow shape this plan dispatches at (repo > shipped). "
            "Omitted, the plan resolves the default phase-dispatch shape "
            "and the key is not written at all."
        ),
    ),
    phases_file: Path | None = typer.Option(
        None, "--phases-file", help="YAML file with a list of phase specs."
    ),
    prose_file: Path | None = typer.Option(
        None, "--prose-file", help="Markdown file with the plan's prose body."
    ),
) -> None:
    """Scaffold a new v2 plan folder + append spec row.

    --phases-file YAML shape:
      - {number, title, tag (agentic|manual), depends_on: [N,...],
         tasks: [{number, title, steps: [{id, text}, ...]}, ...]}
      - ...

    --prose-file is the plan's narrative markdown. If omitted, a
    minimal stub is generated.
    """
    import yaml

    repo_root = Path.cwd()
    phases: list[PhaseSpec] = []
    if phases_file is not None:
        raw = yaml.safe_load(phases_file.read_text())
        for p in raw or []:
            phases.append(
                PhaseSpec(
                    number=p["number"],
                    title=p["title"],
                    tag=p.get("tag", "agentic"),
                    depends_on=tuple(p.get("depends_on") or ()),
                    tasks=tuple(p.get("tasks") or ()),
                    acceptance=tuple(p.get("acceptance") or ()),
                )
            )
    prose = prose_file.read_text() if prose_file is not None else f"# {slug}\n\nPlan-level prose.\n"

    if workflow is not None:
        # "Did the operator state a constraint?" is asked of click, not of the
        # VALUE: an explicit `--fr-version '>=3.0.0,<5.0.0'` is byte-identical
        # to the default, and silently upgrading it would be exactly the kind
        # of quiet substitution this phase exists to stop.
        explicit = ctx.get_parameter_source("fr_version") is not ParameterSource.DEFAULT
        if not explicit:
            # No constraint stated, so the shape decides it.
            fr_version = WORKFLOW_FR_VERSION
        elif _admits_pre_4(fr_version):
            # An explicit constraint is the operator's, so it is refused
            # rather than silently rewritten — but one that invites fr 3.x
            # to load a plan whose `workflow:` key it cannot parse is a
            # promise the plan cannot keep.
            err_console.print(
                f"[red]error:[/red] --workflow requires an fr_version floored at 4.0.0 "
                f"(PlanMeta forbids unknown keys, so fr < 4.0.0 cannot parse a plan "
                f"carrying `workflow:`); got {fr_version!r}. Use "
                f"--fr-version '{WORKFLOW_FR_VERSION}' or drop --workflow."
            )
            raise typer.Exit(2)

    try:
        plan = create(
            repo_root=repo_root,
            slug=slug,
            spec=str(spec) if spec else None,
            target_repo=target_repo,
            fr_version=fr_version,
            phases=phases,
            prose=prose,
            workflow=workflow,
        )
        console.print(f"created plan: {plan.dir}")
    except PlanEditError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2) from e


@plan_app.command("edit")
def edit(
    plan_dir: Path = typer.Argument(..., help="Path to plan folder."),
    tick_step: str | None = typer.Option(None, "--tick", help="Step ID to tick (P<n>.T<n>.S<n>)."),
    state: str = typer.Option("x", "--state", help="State for --tick: x | -"),
    note: str | None = typer.Option(None, "--note", help="Note (required for --state -)"),
    complete_phase_n: int | None = typer.Option(
        None, "--complete-phase", help="Phase number to mark complete."
    ),
) -> None:
    """Mutate plan state — tick a step OR complete a phase."""
    if (tick_step is None) == (complete_phase_n is None):
        err_console.print("Provide exactly one of --tick or --complete-phase")
        raise typer.Exit(2)

    try:
        if tick_step is not None:
            if state not in ("x", "-"):
                err_console.print(f"--state must be 'x' or '-', got {state!r}")
                raise typer.Exit(2)
            tick(plan_dir, tick_step, state=state, note=note)  # type: ignore[arg-type]
            console.print(f"ticked {tick_step} → {state}")
        else:
            assert complete_phase_n is not None
            complete_phase(plan_dir, complete_phase_n, note=note)
            console.print(f"phase {complete_phase_n}: marked complete")
            _acceptance_flip_nudge(plan_dir, complete_phase_n)
    except PlanEditError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2) from e


def _acceptance_flip_nudge(plan_dir: Path, phase_n: int) -> None:
    """A completed phase whose linked acceptance rows are still
    `not-implemented` gets a warning naming them (2026-07-04 spec, fr-execute
    integration). Best-effort: a broken plan or matrix must never block the
    completion that already happened."""
    try:
        plan = parse(plan_dir)
        phase = next(p for p in plan.phases if p.phase.number == phase_n)
        ids = phase.phase.acceptance
        if not ids or plan.repo_root is None:
            return
        from fr.acceptance.model import load_matrix

        matrix_path = plan.repo_root / "docs" / "acceptance" / "matrix.yaml"
        if not matrix_path.exists():
            return
        status_by_id = {r.id: r.status for r in load_matrix(matrix_path).rows}
        unflipped = [rid for rid in ids if status_by_id.get(rid) == "not-implemented"]
        if unflipped:
            typer.echo(
                f"warning: phase {phase_n} completed but its acceptance rows are "
                f"still not-implemented: {', '.join(unflipped)} — flip them "
                f"(edit status + cite the test refs) or record why in notes."
            )
    except Exception as e:  # noqa: BLE001 — nudge only, never a gate
        typer.echo(f"warning: acceptance flip-nudge skipped ({e})")


@plan_app.command("rework")
def rework(
    parent_plan_dir: Path = typer.Argument(
        ..., help="Path to parent plan folder (Complete + archived)."
    ),
) -> None:
    """Scaffold a sibling rework plan + append spec row."""
    try:
        plan = rework_create(parent_plan_dir)
        console.print(f"created rework plan: {plan.dir}")
    except PlanEditError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2) from e


@plan_app.command("rework-add")
def rework_add(
    rework_dir: Path = typer.Argument(..., help="Rework plan folder."),
    item: str = typer.Option(..., "--item", help="Origin item description."),
    source: str = typer.Option(..., "--source", help="Where the item came from."),
    track: str = typer.Option(
        ...,
        "--track",
        help=(
            "Free-form. Canonical: development | operations | decision. "
            "Compounds like 'decision → development' or 'development (future-triggered)' OK."
        ),
    ),
) -> None:
    """Append an origin item to a rework plan's _meta.origin_items."""
    try:
        new_id = rework_add_origin(rework_dir, item=item, source=source, track=track)
        console.print(f"added origin item #{new_id}")
    except PlanEditError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2) from e


@plan_app.command("rework-list")
def rework_list_cmd(
    include_archived: bool = typer.Option(
        False, "--include-archived", help="Also scan archived-plans/"
    ),
) -> None:
    """List rework plans in the current repo."""
    repo_root = Path.cwd()
    records = rework_list(repo_root, include_archived=include_archived)
    if not records:
        console.print("no rework plans found.")
        return
    table = Table(title="Rework plans")
    table.add_column("Parent")
    table.add_column("N", justify="right")
    table.add_column("Status")
    table.add_column("Open steps", justify="right")
    table.add_column("Origin items", justify="right")
    table.add_column("By track")
    table.add_column("Folder")
    for r in records:
        track_summary = ", ".join(f"{t}={n}" for t, n in r.by_track) if r.by_track else "—"
        table.add_row(
            r.parent_slug,
            str(r.rework_number),
            r.status,
            str(r.open_steps),
            str(r.origin_item_count),
            track_summary,
            str(r.folder_path),
        )
    console.print(table)


@plan_app.command("self-review")
def self_review_cmd(
    plan_dir: Path = typer.Argument(..., help="Path to plan folder."),
) -> None:
    """Soft lints beyond schema validation."""
    try:
        plan = parse(plan_dir)
    except PlanSchemaError as e:
        err_console.print(f"[red]parse error:[/red] {e}")
        raise typer.Exit(2) from e

    issues = self_review(plan)
    if not issues:
        console.print("[green]self-review passed[/green]")
        return
    for issue in issues:
        console.print(str(issue))
    if any(issue.severity == "error" for issue in issues):
        raise typer.Exit(1)
