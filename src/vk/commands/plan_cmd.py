"""vk plan — write, save, and maintain plan files."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import typer
from rich.console import Console

from vk.commands.common import (
    ConfirmAction,
    resolve_action,
)
from vk.config import load_profile
from vk.plan.convert import (
    MixedPlanError,
    add_deps,
    to_phased_group_by_tag,
    to_phased_one_per_task,
    to_phased_single,
)
from vk.plan.parser import parse_plan
from vk.plan.validate import DagValidationError, validate_dag
from vk.plan.writer import write_plan
from vk.spec_index import IndexEntry, upsert_entry

console = Console()
err_console = Console(stderr=True)

_CANONICAL_TRACKS = {"development", "operations", "decision"}

plan_app = typer.Typer(help="Write, save, and maintain plan files.")


def _resolve_repo_root(cwd: Path | None = None) -> Path:
    """Resolve repo root for a plan command.

    Honors ``$VK_REPO_ROOT`` first (so integration tests can point the
    command at ``tmp_path`` without spawning a fake git repo), then falls
    back to ``git rev-parse`` (run from ``cwd`` if given), then to
    ``Path.cwd()``.

    The returned path is always ``.resolve()``-d so callers can safely use
    ``Path.is_relative_to`` / ``Path.relative_to`` against other resolved
    paths, even when the source value (env var, git output, or cwd) traversed
    a symlink.

    The empty string is treated like an unset env var (we fall through to
    git) — keeping ``VK_REPO_ROOT=""`` as a way to disable the override
    without unsetting it.
    """
    override = os.environ.get("VK_REPO_ROOT")
    if override:
        return Path(override).resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        return Path(result.stdout.strip()).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return (cwd or Path.cwd()).resolve()


@plan_app.command(name="format")
def plan_format(
    target: Path = typer.Argument(".", help="Plan file path or repository root."),
) -> None:
    """Print the plan's actual format.

    - If ``target`` is a plan file: parse and print the detected shape.
    - If ``target`` is a directory: fall back to the repo's dispatch config for
      the expected shape (legacy behavior).

    Output is either ``phased`` or ``flat``. A ``flat`` result means the plan
    is a legacy artifact and must be migrated before any execute or dispatch
    command will accept it — see ``vk plan convert --to phased``.
    """
    target = target.resolve()
    if not target.exists():
        err_console.print(f"Error: {target} does not exist.")
        raise typer.Exit(2)
    if target.is_file():
        try:
            plan = parse_plan(target)
        except ValueError as exc:
            err_console.print(f"Error: could not parse plan at {target}: {exc}")
            raise typer.Exit(2)
        console.print(plan.format.value)
        return
    config_path = target / "docs" / "superpowers" / "plan-config.yaml"
    profile = load_profile(config_path)
    console.print(profile.format.value)


@plan_app.command(name="new")
def plan_new(
    name: str = typer.Argument(..., help="Plan name (kebab-case)."),
    spec: str | None = typer.Option(None, "--spec", help="Path to spec file."),
    save: bool = typer.Option(False, "--save", help="Write to plans directory."),
) -> None:
    """Generate a new plan file skeleton."""
    from datetime import date

    repo_root = _resolve_repo_root()

    config_path = repo_root / "docs" / "superpowers" / "plan-config.yaml"
    profile = load_profile(config_path)

    today = date.today().isoformat()
    filename = profile.plan.filename.replace("YYYY-MM-DD", today).replace("{name}", name)

    lines = [
        f"# {name.replace('-', ' ').title()} Implementation Plan",
        "",
    ]
    if spec and "Spec" in profile.header.required:
        lines.append(f"**Spec:** `{spec}`")
    lines.extend(
        [
            "**Status:** Not Started",
            "",
            "**Goal:** [One sentence]",
            "",
            "---",
            "",
        ]
    )

    lines.extend(
        [
            "## Phase 1: [Name] [agentic]",
            "",
            "### Task 1: [Component]",
            "",
            "- [ ] **Step 1: [Action]**",
            "",
        ]
    )

    content = "\n".join(lines)

    if save:
        plans_dir = repo_root / profile.plan.save_to
        plans_dir.mkdir(parents=True, exist_ok=True)
        out_path = plans_dir / filename
        out_path.write_text(content, encoding="utf-8")
        console.print(f"Created: {out_path}")
    else:
        console.print(content)


@plan_app.command(name="self-review")
def plan_self_review(
    plan_path: Path = typer.Argument(..., help="Path to the plan file.", exists=True),
) -> None:
    """Run automated quality checks on a plan file."""
    plan_path = plan_path.resolve()
    text = plan_path.read_text()
    issues: list[str] = []

    # Placeholder scan
    placeholders = ["TBD", "TODO", "fill in", "implement later", "to be determined"]
    for ph in placeholders:
        if ph.lower() in text.lower():
            issues.append(f"Placeholder found: '{ph}'")

    # Parse and check structure
    try:
        plan = parse_plan(plan_path)
    except ValueError as exc:
        issues.append(f"Parse error: {exc}")
        _report_issues(issues)
        return

    # Phase/task tag consistency
    if plan.phases:
        for phase in plan.phases:
            if not phase.tag:
                issues.append(f"Phase {phase.number} missing [manual]/[agentic] tag")
    elif plan.tasks:
        for task in plan.tasks:
            if not task.tag:
                issues.append(f"Task {task.number} missing [manual]/[agentic] tag")

    # Canonical **Track:** lint. First word (case-insensitive) must be one of
    # the canonical labels; transitions like "decision → development" pass on
    # the first token.
    for phase in plan.phases:
        if phase.track_label is None:
            continue
        first = phase.track_label.strip().split()[0].lower()
        if first not in _CANONICAL_TRACKS:
            issues.append(
                f"Phase {phase.number} has non-canonical **Track:** value "
                f"'{phase.track_label}' (expected development / operations / decision)."
            )

    # Structural DAG validation (cycle / forward-ref / self-ref / unknown-ref).
    # Report any previously-collected issues first so basic plan-shape errors
    # surface before dependency-grammar complaints.
    if issues:
        _report_issues(issues)
        return

    try:
        validate_dag(plan, plan_path=plan_path)
    except DagValidationError as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(1)

    _report_issues(issues)


def _report_issues(issues: list[str]) -> None:
    if issues:
        err_console.print(f"[yellow]{len(issues)} issue(s) found:[/yellow]")
        for issue in issues:
            err_console.print(f"  - {issue}")
        raise typer.Exit(1)
    else:
        console.print("[green]Self-review passed.[/green]")


@plan_app.command(name="spec-index")
def plan_spec_index(
    plan_path: Path = typer.Argument(..., help="Path to the plan file.", exists=True),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without mutations."),
    yes: bool = typer.Option(False, "--yes", help="Execute without confirmation."),
) -> None:
    """Update the spec's Implementation Plans table for this plan."""
    try:
        action = resolve_action(dry_run=dry_run, yes=yes)
    except Exception:
        err_console.print("Error: --dry-run and --yes are mutually exclusive")
        raise typer.Exit(1)

    plan_path = plan_path.resolve()
    plan = parse_plan(plan_path)

    if not plan.spec:
        console.print("No **Spec:** header in plan. Nothing to update.")
        raise typer.Exit(0)

    repo_root = _resolve_repo_root(cwd=plan_path.parent)

    spec_path = repo_root / plan.spec
    if not spec_path.exists():
        console.print(f"Spec file not found: {spec_path}")
        raise typer.Exit(2)

    entry = IndexEntry(
        plan=plan.title,
        repo="",
        file=str(plan_path.relative_to(repo_root)),
        status=plan.status,
        depends_on="—",
    )

    if action is ConfirmAction.DRY_RUN:
        console.print(f"Would update spec index: {spec_path}")
        console.print(f"  Plan: {plan.title}, Status: {plan.status}")
        raise typer.Exit(0)

    if action is ConfirmAction.PROMPT:
        if not typer.confirm(f"Update spec index in {spec_path}?", default=False):
            raise typer.Exit(0)

    upsert_entry(spec_path, entry)
    console.print(f"Spec index updated: {spec_path}")


@plan_app.command(name="convert")
def plan_convert(
    plan_path: Path = typer.Argument(..., help="Path to the plan file.", exists=True),
    to: str = typer.Option("phased", "--to", help="Target format. Only 'phased' is supported."),
    single_phase: bool = typer.Option(False, "--single-phase", help="Wrap in one phase."),
    one_per_task: bool = typer.Option(False, "--one-per-task", help="One phase per task."),
    group_by_tag: bool = typer.Option(
        False, "--group-by-tag", help="Group consecutive same-tag tasks."
    ),
    add_deps_flag: bool = typer.Option(
        False,
        "--add-deps",
        help="Migration: add **Depends on:** lines to a legacy phased plan.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without mutations."),
    yes: bool = typer.Option(False, "--yes", help="Execute without confirmation."),
) -> None:
    """Migrate a legacy flat plan to phased format, or add deps to a legacy phased plan.

    One of --single-phase, --one-per-task, --group-by-tag, or --add-deps selects
    the migration strategy. --add-deps is mutually exclusive with the other
    three (it operates on already-phased plans missing dependency declarations).
    """
    try:
        action = resolve_action(dry_run=dry_run, yes=yes)
    except Exception:
        err_console.print("Error: --dry-run and --yes are mutually exclusive")
        raise typer.Exit(1)

    # --add-deps is mutually exclusive with the flat->phased conversion flags.
    if add_deps_flag and (single_phase or one_per_task or group_by_tag):
        err_console.print(
            "Error: --add-deps is mutually exclusive with --single-phase, "
            "--one-per-task, and --group-by-tag."
        )
        raise typer.Exit(2)

    plan_path = plan_path.resolve()

    if add_deps_flag:
        _plan_convert_add_deps(plan_path, action)
        return

    if to != "phased":
        err_console.print(
            f"Error: --to '{to}' is not supported. The only valid target is 'phased'."
        )
        raise typer.Exit(2)

    plan = parse_plan(plan_path)

    try:
        if single_phase:
            converted = to_phased_single(plan)
        elif one_per_task:
            converted = to_phased_one_per_task(plan)
        elif group_by_tag:
            converted = to_phased_group_by_tag(plan)
        else:
            err_console.print(
                "Error: --to phased requires one of: --single-phase, --one-per-task, --group-by-tag"
            )
            raise typer.Exit(2)
    except ValueError as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(2)

    if action is ConfirmAction.DRY_RUN:
        console.print(f"Would convert: {plan.format.value} -> phased")
        console.print(f"  Tasks: {len(plan.all_tasks)} -> {len(converted.all_tasks)}")
        if converted.phases:
            console.print(f"  Phases: {len(converted.phases)}")
        raise typer.Exit(0)

    if action is ConfirmAction.PROMPT:
        if not typer.confirm(f"Convert {plan.format.value} -> phased?", default=False):
            raise typer.Exit(0)

    write_plan(converted, plan_path)
    console.print(f"Converted: {plan.format.value} -> phased")


@plan_app.command(name="rework")
def plan_rework(
    parent_path: Path = typer.Argument(..., help="Path to the parent plan file."),
) -> None:
    """Scaffold a rework plan against a parent."""
    from vk.plan.rework import scaffold_rework

    repo_root = _resolve_repo_root()

    try:
        out_path, warnings = scaffold_rework(parent_path, repo_root=repo_root)
    except ValueError as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(2)

    for w in warnings:
        err_console.print(f"warn: {w}")
    console.print(f"Created: {out_path}")


def _plan_convert_add_deps(plan_path: Path, action: ConfirmAction) -> None:
    """Implement the --add-deps migration branch of `vk plan convert`.

    Flow is uniform across all three action modes: compute the proposed
    migration on a temporary copy, show the diff, then decide to write.
    PROMPT mode genuinely prompts (previous implementation wrote first and
    pretended to prompt — surfaced in the PR #32 review as M-3).
    """
    import difflib
    import tempfile

    original = plan_path.read_text()

    # Compute what the migration WOULD produce on a throwaway copy.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
        tmp.write(original)
        tmp_path = Path(tmp.name)
    try:
        try:
            add_deps(tmp_path)
        except MixedPlanError as exc:
            err_console.print(f"Error: {exc}")
            raise typer.Exit(2)
        proposed = tmp_path.read_text()
    finally:
        tmp_path.unlink(missing_ok=True)

    if proposed == original:
        console.print("No changes — plan already has all **Depends on:** lines.")
        raise typer.Exit(0)

    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            proposed.splitlines(keepends=True),
            fromfile=str(plan_path),
            tofile=str(plan_path),
        )
    )

    if action is ConfirmAction.DRY_RUN:
        console.print(diff)
        raise typer.Exit(0)

    if action is ConfirmAction.PROMPT:
        console.print(diff)
        if not typer.confirm("Apply this migration?", default=False):
            console.print("Aborted — no changes written.")
            raise typer.Exit(0)

    # APPLY path (either --yes or PROMPT-confirmed): write the file and commit.
    plan_path.write_text(proposed)

    try:
        root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=plan_path.parent,
        )
        repo_root = Path(root_result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        repo_root = plan_path.parent

    subprocess.run(["git", "add", str(plan_path)], check=True, cwd=repo_root)
    subprocess.run(
        ["git", "commit", "-m", "chore(plan): add **Depends on:** lines (migration)"],
        check=True,
        cwd=repo_root,
    )
    console.print(f"Updated and committed: {plan_path}")
