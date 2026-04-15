"""vk dispatch -- dispatch a phased plan to GitHub Issues."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TypedDict

import typer
from rich.console import Console
from rich.table import Table

from vk import gh
from vk.commands.common import (
    ConfirmAction,
    confirm_or_exit,
    format_gate_refusal,
    resolve_action,
)
from vk.commands.dispatch_body_validator import validate_issue_body
from vk.config import load_profile
from vk.plan.filename import derive_slug
from vk.plan.format import PlanFormat
from vk.plan.models import Phase
from vk.plan.parser import parse_plan

console = Console()
err_console = Console(stderr=True)

dispatch_app = typer.Typer(help="Dispatch plans to GitHub Issues.")


class _MigrateRewrite(TypedDict):
    repo: str
    number: int
    old_title: str
    new_title: str
    new_body: str


def _find_repo_root(plan_path: Path) -> Path:
    """Find the git repo root for the plan file."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=plan_path.parent,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return plan_path.parent


def _get_already_tracked(plan_text: str) -> dict[int, str]:
    """Extract phase_number -> tracking_url from existing tracking comments."""
    tracked: dict[int, str] = {}
    for match in re.finditer(
        r"^## Phase (\d+):.*\n<!-- Tracking: (https://\S+) -->",
        plan_text,
        re.MULTILINE,
    ):
        tracked[int(match.group(1))] = match.group(2)
    return tracked


def _inject_tracking_comment(plan_text: str, phase_number: int, issue_url: str) -> str:
    """Insert <!-- Tracking: URL --> after the phase header line."""
    tracking = f"<!-- Tracking: {issue_url} -->"
    pattern = rf"(^## Phase {phase_number}:.*$)"
    return re.sub(pattern, rf"\1\n{tracking}", plan_text, count=1, flags=re.MULTILINE)


def _build_issue_title(slug: str, phase: Phase, target_repo: str, total: int) -> str:
    """Human-readable title: [{repo}] {slug} · Phase {n}/{total} · {phase_title}."""
    return f"[{target_repo}] {slug} · Phase {phase.number}/{total} · {phase.title}"


def _build_issue_body(
    phase: Phase,
    plan_path: Path,
    target_repo: str,
    prev_num: int | None,
    total_phases: int,
    spec: str,
    goal: str,
) -> str:
    """Build an Issue body: tracking block + Instruction/Workspace/Dependencies.

    The body is consumed by the VK Issue Bridge, which requires the
    ``- Blocked by #N`` dash prefix in ``## Dependencies`` for gating.
    """
    if phase.number == 0:
        deps_block = "None — no blocking phases."
    elif prev_num is not None:
        deps_block = f"- Blocked by #{prev_num}"
    else:
        raise ValueError(
            f"Phase {phase.number} has no prev_num but is not phase 0. "
            "Cannot emit parseable dependency line. "
            "Fix: ensure earlier phases were dispatched first."
        )

    tracking_block = (
        f"📦 Repo:   {target_repo}\n"
        f"📋 Plan:   {plan_path}\n"
        f"📐 Spec:   {spec}\n"
        f"🎯 Phase:  {phase.number}/{total_phases} — {phase.title} [{phase.tag}]\n"
        f"🔗 Issue:  (assigned on create)\n"
        f"\n"
        f"**Goal (from plan):** {goal}\n"
    )

    return (
        f"{tracking_block}"
        f"\n---\n\n"
        f"## Instruction\n\n"
        f"Use superpowers-for-vk:vk-execute to implement Phase {phase.number} of this plan.\n\n"
        f"## Workspace\n\n"
        f"Repos: {target_repo}\n\n"
        f"## Dependencies\n\n"
        f"{deps_block}\n"
    )


def _print_dry_run(
    title: str, slug: str, repo: str, phases: list[Phase], skipped: set[int], total: int
) -> None:
    """Print dry-run preview table."""
    console.print()
    console.print("[bold]DRY RUN -- vk dispatch[/bold]")
    console.print(f"Plan: {title}")
    console.print(f"Slug: {slug}")
    console.print(f"Repo: {repo}")
    console.print()

    all_skipped = all(p.number in skipped for p in phases)
    if all_skipped:
        console.print("All phases already dispatched (noop).")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Phase")
    table.add_column("Type")
    table.add_column("Issue Title")
    table.add_column("Action")

    for phase in phases:
        issue_title = _build_issue_title(slug, phase, target_repo=repo, total=total)
        if phase.number in skipped:
            action = "[dim]skip (already tracked)[/dim]"
        else:
            action = "create"
        table.add_row(
            f"Phase {phase.number}: {phase.title}",
            str(phase.tag),
            issue_title,
            action,
        )

    console.print(table)
    pending = len(phases) - len(skipped)
    console.print(f"\nPhases to create: {pending}")


@dispatch_app.command("create")
def dispatch_create(
    plan_path: Path = typer.Argument(
        ...,
        help="Path to the phased plan file.",
        exists=True,
        readable=True,
    ),
    repo: str | None = typer.Option(
        None, "--repo", help="Target repo (OWNER/REPO). Defaults to config default_repo."
    ),
    project: str | None = typer.Option(
        None, "--project", help="Project board name. Defaults to config project_board."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without mutations."),
    yes: bool = typer.Option(False, "--yes", help="Execute without confirmation."),
) -> None:
    """Create GitHub Issues from a phased plan."""
    # Resolve action mode
    try:
        action = resolve_action(dry_run=dry_run, yes=yes)
    except Exception:
        err_console.print("Error: --dry-run and --yes are mutually exclusive")
        raise typer.Exit(1)

    plan_path_resolved = Path(plan_path).resolve()
    repo_root = _find_repo_root(plan_path_resolved)

    # Gate check
    config_path = repo_root / "docs" / "superpowers" / "plan-config.yaml"
    profile = load_profile(config_path)
    if not profile.dispatch_enabled:
        err_console.print(format_gate_refusal())
        raise typer.Exit(1)

    dispatch_cfg = profile.dispatch
    assert dispatch_cfg is not None

    target_repo = repo or dispatch_cfg.default_repo
    _ = project or dispatch_cfg.project_board  # reserved for project board operations

    # Parse and validate plan
    try:
        plan = parse_plan(plan_path_resolved)
    except (FileNotFoundError, ValueError) as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(2)

    if plan.format is not PlanFormat.PHASED:
        err_console.print("Error: Cannot dispatch a flat plan. Convert to phased first.")
        raise typer.Exit(2)

    if not plan.phases:
        err_console.print("Error: No phases found in plan.")
        raise typer.Exit(2)

    slug = derive_slug(plan_path_resolved)

    # Idempotency check
    plan_text = plan_path_resolved.read_text()
    already_tracked = _get_already_tracked(plan_text)
    skipped = set(already_tracked.keys())

    total = len(plan.phases)

    # Dry-run mode
    if action is ConfirmAction.DRY_RUN:
        _print_dry_run(plan.title, slug, target_repo, list(plan.phases), skipped, total=total)
        raise typer.Exit(0)

    # Prompt mode
    if action is ConfirmAction.PROMPT:
        _print_dry_run(plan.title, slug, target_repo, list(plan.phases), skipped, total=total)
        pending = [p for p in plan.phases if p.number not in skipped]
        if not pending:
            console.print("All phases already dispatched (noop).")
            raise typer.Exit(0)
        confirm_or_exit()

    # Check if all already dispatched
    pending_phases = [p for p in plan.phases if p.number not in skipped]
    if not pending_phases:
        console.print("All phases already dispatched (noop).")
        raise typer.Exit(0)

    # Apply mode: create issues
    results: dict[int, str] = {}
    errors: dict[int, str] = {}
    phase_to_issue: dict[int, int] = {}

    for phase_num, url in already_tracked.items():
        try:
            phase_to_issue[phase_num] = gh.extract_issue_number(url)
        except gh.GhError:
            pass

    for phase in plan.phases:
        if phase.number in skipped:
            continue

        title = _build_issue_title(slug, phase, target_repo=target_repo, total=len(plan.phases))
        prev_num = phase_to_issue.get(phase.number - 1)

        body = _build_issue_body(
            phase,
            plan_path_resolved,
            target_repo,
            prev_num,
            total_phases=len(plan.phases),
            spec=plan.spec or "",
            goal=plan.goal,
        )

        validate_issue_body(body, phase.number)

        try:
            tag_label = (
                dispatch_cfg.labels.get("agentic", "vk-ready")
                if phase.tag == "agentic"
                else dispatch_cfg.labels.get("manual", "manual")
            )
            issue_url = gh.create_issue(
                repo=target_repo,
                title=title,
                body=body,
                labels=[tag_label, f"plan:{slug}", f"phase:{phase.number}"],
            )
            issue_num = gh.extract_issue_number(issue_url)
            phase_to_issue[phase.number] = issue_num
            results[phase.number] = issue_url

            updated_body = body.replace("(assigned on create)", issue_url)
            gh.edit_issue_body(target_repo, issue_num, updated_body)

            plan_text = _inject_tracking_comment(plan_text, phase.number, issue_url)

        except gh.GhError as exc:
            errors[phase.number] = str(exc)
            continue

    # Write updated plan file
    plan_path_resolved.write_text(plan_text)

    # Commit
    subprocess.run(
        ["git", "add", str(plan_path_resolved)],
        check=True, capture_output=True, text=True, cwd=repo_root,
    )
    subprocess.run(
        ["git", "commit", "-m", "chore: link plan phases to GitHub Issues (vk dispatch)"],
        check=True, capture_output=True, text=True, cwd=repo_root,
    )

    # Print summary
    console.print()
    console.print("[bold]Dispatched[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Phase")
    table.add_column("Issue")
    table.add_column("State")

    for phase in plan.phases:
        if phase.number in skipped:
            table.add_row(f"Phase {phase.number}", "(skipped)", "--")
        elif phase.number in results:
            table.add_row(f"Phase {phase.number}", results[phase.number], "created")
        elif phase.number in errors:
            table.add_row(f"Phase {phase.number}", f"FAILED: {errors[phase.number]}", "error")

    console.print(table)

    if errors and results:
        raise typer.Exit(4)
    elif errors and not results:
        raise typer.Exit(3)
    raise typer.Exit(0)


@dispatch_app.command("migrate")
def migrate(
    plan_path: Path = typer.Argument(..., exists=True, help="Path to the phased plan file."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without mutations."),
    yes: bool = typer.Option(False, "--yes", help="Execute without confirmation."),
) -> None:
    """Retrofit existing open Issues to the new title/body format."""
    try:
        action = resolve_action(dry_run=dry_run, yes=yes)
    except Exception:
        err_console.print("Error: --dry-run and --yes are mutually exclusive")
        raise typer.Exit(1)

    plan_path_resolved = Path(plan_path).resolve()
    repo_root = _find_repo_root(plan_path_resolved)

    config_path = repo_root / "docs" / "superpowers" / "plan-config.yaml"
    profile = load_profile(config_path)
    if not profile.dispatch_enabled:
        err_console.print(format_gate_refusal())
        raise typer.Exit(1)

    dispatch_cfg = profile.dispatch
    assert dispatch_cfg is not None

    try:
        plan = parse_plan(plan_path_resolved)
    except (FileNotFoundError, ValueError) as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(2)

    if plan.format is not PlanFormat.PHASED:
        err_console.print("Error: Cannot migrate a flat plan.")
        raise typer.Exit(2)

    if not plan.phases:
        err_console.print("Error: No phases found in plan.")
        raise typer.Exit(2)

    slug = derive_slug(plan_path_resolved)
    plan_text = plan_path_resolved.read_text()
    tracked = _get_already_tracked(plan_text)

    missing = [p.number for p in plan.phases if p.number not in tracked]
    if missing:
        err_console.print(
            f"Phase(s) {missing} have no tracking comment in {plan_path}. "
            f"Run 'vk dispatch create <plan>' to create Issues for pending phases first."
        )
        raise typer.Exit(2)

    rewrites: list[_MigrateRewrite] = []
    for phase in plan.phases:
        url = tracked[phase.number]
        number = gh.extract_issue_number(url)
        issue_repo = url.split("/issues/")[0].replace("https://github.com/", "")

        info = gh.view_issue(issue_repo, number)
        if info.get("state") == "CLOSED":
            console.print(f"Skip #{number}: CLOSED")
            continue

        new_title = _build_issue_title(slug, phase, target_repo=issue_repo, total=len(plan.phases))
        prev_num = (
            gh.extract_issue_number(tracked[phase.number - 1])
            if phase.number > 0 and (phase.number - 1) in tracked
            else None
        )
        new_body = _build_issue_body(
            phase, plan_path_resolved, issue_repo, prev_num,
            total_phases=len(plan.phases), spec=plan.spec or "", goal=plan.goal,
        )

        rewrites.append(
            _MigrateRewrite(
                repo=issue_repo,
                number=number,
                old_title=str(info.get("title", "")),
                new_title=new_title,
                new_body=new_body,
            )
        )

    if not rewrites:
        console.print("Nothing to migrate (all issues closed or skipped).")
        raise typer.Exit(0)

    if action is ConfirmAction.DRY_RUN:
        for r in rewrites:
            console.print(f"\n#{r['number']}  {r['old_title']}  →  {r['new_title']}")
        raise typer.Exit(0)

    if action is ConfirmAction.PROMPT:
        for r in rewrites:
            console.print(f"\n#{r['number']}  {r['old_title']}  →  {r['new_title']}")
        confirm_or_exit("Apply these migrations?")

    for r in rewrites:
        try:
            gh.edit_issue(
                repo=r["repo"],
                number=r["number"],
                title=r["new_title"],
                body=r["new_body"],
                add_labels=[f"plan:{slug}"],
            )
            console.print(f"Migrated #{r['number']}")
        except gh.GhError as exc:
            err_console.print(f"Error migrating #{r['number']}: {exc}")
            raise typer.Exit(3)

    raise typer.Exit(0)
