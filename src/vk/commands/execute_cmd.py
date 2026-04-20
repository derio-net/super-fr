"""vk execute — helpers for phase execution."""

from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.console import Console

from vk.plan.format import PlanFormat
from vk.plan.parser import parse_plan

console = Console()
err_console = Console(stderr=True)

execute_app = typer.Typer(help="Helpers for phase execution.")


def _reject_flat(plan_path: Path) -> None:
    """Abort if ``plan_path`` is a legacy flat plan, or if it can't be parsed.

    Every execute sub-command runs this guard before doing work. Flat plans
    must be migrated with ``vk plan convert <plan> --to phased`` first —
    there is no path that executes a flat plan directly.
    """
    try:
        plan = parse_plan(plan_path)
    except (FileNotFoundError, ValueError) as exc:
        err_console.print(f"Error: could not parse {plan_path}: {exc}")
        raise typer.Exit(2)
    if plan.format is PlanFormat.FLAT:
        err_console.print(
            f"Error: {plan_path.name} is a legacy flat plan.\n"
            f"Migrate before executing:\n"
            f"  vk plan convert {plan_path} --to phased --single-phase --dry-run\n"
            f"  vk plan convert {plan_path} --to phased --single-phase --yes"
        )
        raise typer.Exit(2)


def _locate_task_slice(text: str, phase_num: int, task_num: int) -> tuple[int | None, int | None]:
    """Return the (start, end) offsets in ``text`` for the target task's block.

    The search is narrowed to the target phase first so that `### Task N:`
    headers in other phases don't collide.
    """
    phase_match = re.search(rf"^## Phase {phase_num}:", text, re.MULTILINE)
    if not phase_match:
        return None, None
    phase_start = phase_match.end()
    next_phase = re.search(r"^## Phase \d+:", text[phase_start:], re.MULTILINE)
    phase_end = phase_start + next_phase.start() if next_phase else len(text)

    task_match = re.search(rf"^### Task {task_num}:", text[phase_start:phase_end], re.MULTILINE)
    if not task_match:
        return None, None
    task_start = phase_start + task_match.end()
    next_boundary = re.search(
        r"^(### Task \d+:|## Phase \d+:)", text[task_start:phase_end], re.MULTILINE
    )
    task_end = task_start + next_boundary.start() if next_boundary else phase_end
    return task_start, task_end


def _parse_step_id(step_id: str) -> tuple[int, int, int]:
    """Parse step ID: P<n>.T<n>.S<n>.

    Returns (phase_num, task_num, step_num).
    """
    match = re.match(r"^P(\d+)\.T(\d+)\.S(\d+)$", step_id)
    if not match:
        msg = f"Invalid step ID: {step_id}. Use P<n>.T<n>.S<n>."
        raise typer.BadParameter(msg)
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


@execute_app.command(name="check-deps")
def check_deps(
    plan_path: Path = typer.Argument(..., help="Path to the plan file.", exists=True),
    target: int = typer.Argument(..., help="Phase number."),
) -> None:
    """Check if the target phase's declared dependencies are satisfied.

    Reads ``target_phase.depends_on`` and checks only those phases. Phases
    not declared as dependencies do not block pickup — this is the parallel
    DAG unlock that the Phase 1 grammar made possible.
    """
    plan_path = plan_path.resolve()
    _reject_flat(plan_path)
    plan = parse_plan(plan_path)

    phases_by_num = {p.number: p for p in plan.phases}
    target_phase = phases_by_num.get(target)
    if target_phase is None:
        err_console.print(f"Phase {target} not found in plan.")
        raise typer.Exit(2)

    for dep_num in target_phase.depends_on:
        dep_phase = phases_by_num.get(dep_num)
        if dep_phase is None:
            err_console.print(
                f"Phase {target} declares Phase {dep_num} as a dependency, "
                f"but Phase {dep_num} does not exist."
            )
            raise typer.Exit(1)
        unchecked = sum(1 for t in dep_phase.tasks for s in t.steps if s.state == " ")
        if unchecked > 0:
            err_console.print(
                f"Phase {target} depends on Phase {dep_num}, "
                f"which has {unchecked} unchecked step(s)."
            )
            raise typer.Exit(1)

    dep_list = (
        ", ".join(f"Phase {n}" for n in target_phase.depends_on)
        if target_phase.depends_on
        else "none (root phase)"
    )
    console.print(f"Dependencies satisfied for Phase {target} (checked: {dep_list}).")


@execute_app.command()
def scope(
    plan_path: Path = typer.Argument(..., help="Path to the plan file.", exists=True),
    target: int = typer.Argument(..., help="Phase number."),
) -> None:
    """Print the work slice for a specific phase."""
    plan_path = plan_path.resolve()
    _reject_flat(plan_path)
    text = plan_path.read_text()

    pattern = rf"^(## Phase {target}:.*$)"
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        err_console.print(f"Phase {target} not found in plan.")
        raise typer.Exit(2)
    start = match.start()
    next_phase = re.search(r"^## Phase \d+:", text[match.end() :], re.MULTILINE)
    end = match.end() + next_phase.start() if next_phase else len(text)
    console.print(text[start:end].strip())


@execute_app.command(name="check-step")
def check_step(
    plan_path: Path = typer.Argument(..., help="Path to the plan file.", exists=True),
    step_id: str = typer.Argument(..., help="Step ID: P<n>.T<n>.S<n>."),
    state: str = typer.Option("x", "--state", help="New state: x (done) or - (skipped)."),
    note: str | None = typer.Option(None, "--note", help="Note (required for skipped)."),
) -> None:
    """Mark a specific step as done or skipped. Stages but does not commit."""
    if state == "-" and not note:
        err_console.print("Error: --note is required when --state=- (skipped).")
        raise typer.Exit(2)

    if state not in ("x", "-"):
        err_console.print(f"Error: invalid state '{state}'. Use 'x' or '-'.")
        raise typer.Exit(2)

    plan_path = plan_path.resolve()
    _reject_flat(plan_path)
    phase_num, task_num, step_num = _parse_step_id(step_id)

    text = plan_path.read_text()

    slice_start, slice_end = _locate_task_slice(text, phase_num, task_num)
    if slice_start is None:
        err_console.print(f"Step {step_id} not found (unchecked) in plan.")
        raise typer.Exit(2)
    window = text[slice_start:slice_end]

    step_pattern = rf"^- \[ \] \*\*Step {step_num}:"
    step_done_pattern = rf"^- \[[x\-]\] \*\*Step {step_num}:"

    if re.search(step_done_pattern, window, re.MULTILINE):
        console.print(f"Step {step_id} already marked. No change (idempotent).")
        raise typer.Exit(0)

    match = re.search(step_pattern, window, re.MULTILINE)
    if not match:
        err_console.print(f"Step {step_id} not found (unchecked) in plan.")
        raise typer.Exit(2)

    abs_start = slice_start + match.start()
    line_end = text.index("\n", abs_start)
    old_line = text[abs_start:line_end]
    new_line = old_line.replace("- [ ]", f"- [{state}]", 1)
    if note:
        new_line += f" <!-- {note} -->"

    text = text[:abs_start] + new_line + text[line_end:]
    plan_path.write_text(text)

    # Stage the change
    import subprocess

    try:
        subprocess.run(
            ["git", "add", str(plan_path)],
            capture_output=True,
            text=True,
            cwd=plan_path.parent,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    console.print(f"Checked: {step_id} [{state}]")


@execute_app.command(name="pr-body")
def pr_body(
    plan_path: Path = typer.Argument(..., help="Path to the plan file.", exists=True),
    target: int = typer.Argument(..., help="Phase number."),
    issue: int | None = typer.Option(
        None,
        "--issue",
        help=(
            "GitHub Issue number to close. "
            "Auto-discovered from the phase's tracking comment if omitted."
        ),
    ),
) -> None:
    """Generate a standard PR body for a phase."""
    plan_path = plan_path.resolve()
    _reject_flat(plan_path)
    plan = parse_plan(plan_path)

    matching = [p for p in plan.phases if p.number == target]
    if not matching:
        err_console.print(f"Phase {target} not found.")
        raise typer.Exit(2)
    phase = matching[0]
    title = f"Phase {phase.number}: {phase.title}"
    if issue is None and phase.tracking_url:
        m = re.search(r"/issues/(\d+)", phase.tracking_url)
        if m:
            issue = int(m.group(1))

    lines = [
        f"## {title}",
        "",
        f"Implements {title} of `{plan_path.name}`.",
        "",
    ]

    if issue:
        lines.append(f"Closes #{issue}")
    else:
        lines.append(f"Implements {title} of `{plan_path}`")

    typer.echo("\n".join(lines))
