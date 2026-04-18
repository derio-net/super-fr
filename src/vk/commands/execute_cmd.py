"""vk execute — helpers for phase/task execution."""

from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.console import Console

from vk.plan.format import PlanFormat
from vk.plan.parser import parse_plan

console = Console()
err_console = Console(stderr=True)

execute_app = typer.Typer(help="Helpers for phase/task execution.")


def _locate_task_slice(
    text: str, phase_num: int | None, task_num: int
) -> tuple[int | None, int | None]:
    """Return the (start, end) offsets in ``text`` for the target task's block.

    For phased plans, the search is narrowed to the target phase first so that
    `### Task N:` headers in other phases don't collide. For flat plans, the
    search runs against the whole document.
    """
    if phase_num is not None:
        phase_match = re.search(rf"^## Phase {phase_num}:", text, re.MULTILINE)
        if not phase_match:
            return None, None
        phase_start = phase_match.end()
        next_phase = re.search(r"^## Phase \d+:", text[phase_start:], re.MULTILINE)
        phase_end = phase_start + next_phase.start() if next_phase else len(text)
    else:
        phase_start, phase_end = 0, len(text)

    task_match = re.search(rf"^### Task {task_num}:", text[phase_start:phase_end], re.MULTILINE)
    if not task_match:
        return None, None
    task_start = phase_start + task_match.end()
    next_boundary = re.search(
        r"^(### Task \d+:|## Phase \d+:)", text[task_start:phase_end], re.MULTILINE
    )
    task_end = task_start + next_boundary.start() if next_boundary else phase_end
    return task_start, task_end


def _parse_step_id(step_id: str) -> tuple[int | None, int, int]:
    """Parse step ID: P<n>.T<n>.S<n> (phased) or T<n>.S<n> (flat).

    Returns (phase_num_or_none, task_num, step_num).
    """
    phased_match = re.match(r"^P(\d+)\.T(\d+)\.S(\d+)$", step_id)
    if phased_match:
        return int(phased_match.group(1)), int(phased_match.group(2)), int(phased_match.group(3))

    flat_match = re.match(r"^T(\d+)\.S(\d+)$", step_id)
    if flat_match:
        return None, int(flat_match.group(1)), int(flat_match.group(2))

    msg = f"Invalid step ID: {step_id}. Use P<n>.T<n>.S<n> (phased) or T<n>.S<n> (flat)."
    raise typer.BadParameter(msg)


@execute_app.command(name="check-deps")
def check_deps(
    plan_path: Path = typer.Argument(..., help="Path to the plan file.", exists=True),
    target: int = typer.Argument(..., help="Phase number (phased) or task number (flat)."),
) -> None:
    """Check if dependencies for a phase/task are satisfied."""
    plan_path = plan_path.resolve()
    plan = parse_plan(plan_path)

    if plan.format is PlanFormat.PHASED:
        for phase in plan.phases:
            if phase.number >= target:
                break
            unchecked = sum(1 for t in phase.tasks for s in t.steps if s.state == " ")
            if unchecked > 0:
                err_console.print(
                    f"Phase {target} depends on Phase {phase.number} being complete. "
                    f"Phase {phase.number} has {unchecked} unchecked step(s)."
                )
                raise typer.Exit(1)
    else:
        for task in plan.tasks:
            if task.number >= target:
                break
            unchecked = sum(1 for s in task.steps if s.state == " ")
            if unchecked > 0:
                err_console.print(
                    f"Task {target} depends on Task {task.number} being complete. "
                    f"Task {task.number} has {unchecked} unchecked step(s)."
                )
                raise typer.Exit(1)

    kind = "Phase" if plan.format is PlanFormat.PHASED else "Task"
    console.print(f"Dependencies satisfied for {kind} {target}.")


@execute_app.command()
def scope(
    plan_path: Path = typer.Argument(..., help="Path to the plan file.", exists=True),
    target: int = typer.Argument(..., help="Phase number (phased) or task number (flat)."),
) -> None:
    """Print the work slice for a specific phase or task."""
    plan_path = plan_path.resolve()
    plan = parse_plan(plan_path)
    text = plan_path.read_text()

    if plan.format is PlanFormat.PHASED:
        pattern = rf"^(## Phase {target}:.*$)"
        match = re.search(pattern, text, re.MULTILINE)
        if not match:
            err_console.print(f"Phase {target} not found in plan.")
            raise typer.Exit(2)
        start = match.start()
        next_phase = re.search(r"^## Phase \d+:", text[match.end() :], re.MULTILINE)
        end = match.end() + next_phase.start() if next_phase else len(text)
        console.print(text[start:end].strip())
    else:
        pattern = rf"^(### Task {target}:.*$)"
        match = re.search(pattern, text, re.MULTILINE)
        if not match:
            err_console.print(f"Task {target} not found in plan.")
            raise typer.Exit(2)
        start = match.start()
        next_task = re.search(r"^### Task \d+:", text[match.end() :], re.MULTILINE)
        end = match.end() + next_task.start() if next_task else len(text)
        console.print(text[start:end].strip())


@execute_app.command(name="check-step")
def check_step(
    plan_path: Path = typer.Argument(..., help="Path to the plan file.", exists=True),
    step_id: str = typer.Argument(..., help="Step ID: P<n>.T<n>.S<n> or T<n>.S<n>."),
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
    target: int = typer.Argument(..., help="Phase number (phased) or task number (flat)."),
    issue: int | None = typer.Option(
        None,
        "--issue",
        help=(
            "GitHub Issue number to close. "
            "Auto-discovered from the phase's tracking comment if omitted."
        ),
    ),
) -> None:
    """Generate a standard PR body for a phase or task."""
    plan_path = plan_path.resolve()
    plan = parse_plan(plan_path)

    if plan.format is PlanFormat.PHASED:
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
    else:
        matching_tasks = [t for t in plan.tasks if t.number == target]
        if not matching_tasks:
            err_console.print(f"Task {target} not found.")
            raise typer.Exit(2)
        task = matching_tasks[0]
        title = f"Task {task.number}: {task.title}"

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
