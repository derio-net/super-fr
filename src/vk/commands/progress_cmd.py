"""vk progress — track work lifecycle.

Five subcommands: sync, board, create, transition, audit.
sync and create are dispatch-aware (branch on profile.dispatch_enabled).
audit and transition are unconditionally local: they operate on plan files
regardless of dispatch mode.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from vk.commands.common import (
    ConfirmAction,
    format_gate_refusal,
    resolve_action,
)
from vk.config import Profile, load_profile
from vk.plan.parser import parse_plan
from vk.spec_index import IndexEntry, read_index, upsert_entry

console = Console()
err_console = Console(stderr=True)

progress_app = typer.Typer(help="Track work lifecycle.")


def _find_repo_root(path: Path) -> Path:
    """Find git repo root from a file path."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=path.parent if path.is_file() else path,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return path.parent if path.is_file() else path


def _compute_status(plan_path: Path) -> str:
    """Derive plan status from checkbox states."""
    plan = parse_plan(plan_path)
    all_tasks = plan.all_tasks
    if not all_tasks:
        return "Not Started"

    total = 0
    checked = 0
    for task in all_tasks:
        for step in task.steps:
            total += 1
            if step.state in ("x", "-"):
                checked += 1

    if total == 0 or checked == 0:
        return "Not Started"
    if checked == total:
        return "Complete"
    return "In Progress"


def _rewrite_status(plan_path: Path, new_status: str) -> None:
    """Rewrite the **Status:** header in a plan file."""
    text = plan_path.read_text(encoding="utf-8")
    text = re.sub(
        r"^\*\*Status:\*\*\s*.+$",
        f"**Status:** {new_status}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    plan_path.write_text(text, encoding="utf-8")


def _resolve_spec(plan_path: Path, repo_root: Path | None = None) -> Path | None:
    """Resolve spec path from plan's Spec header.

    Pass ``repo_root`` when already known — avoids a git subprocess and makes
    the function usable in unit-test environments outside a git repository.
    """
    plan = parse_plan(plan_path)
    if not plan.spec:
        return None
    if repo_root is None:
        repo_root = _find_repo_root(plan_path)
    spec_path = repo_root / plan.spec
    return spec_path if spec_path.exists() else None


def _reconcile_spec_index(
    plan_path: Path,
    plan_title: str,
    status: str,
    repo_root: Path,
    *,
    dry_run: bool = False,
    prev_plan_path: Path | None = None,
) -> bool:
    """Reconcile spec index with current plan status. Returns True if updated."""
    spec_path = _resolve_spec(plan_path, repo_root)
    if not spec_path:
        return False

    entries = read_index(spec_path)
    rel_file = str(plan_path.relative_to(repo_root))
    lookup_path = str((prev_plan_path or plan_path).relative_to(repo_root))

    existing_entry = next((e for e in entries if e.file == lookup_path), None)
    if (
        existing_entry
        and existing_entry.status == status
        and existing_entry.plan == plan_title
        and rel_file == lookup_path
    ):
        return False

    if dry_run:
        console.print(f"Would update spec index for: {spec_path.name}")
        return True

    entry = IndexEntry(
        plan=plan_title,
        repo=existing_entry.repo if existing_entry else "",
        file=rel_file,
        status=status,
        depends_on=existing_entry.depends_on if existing_entry else "—",
    )
    match_file = lookup_path if lookup_path != rel_file else None
    upsert_entry(spec_path, entry, match_file=match_file)
    console.print(f"Spec index updated: {spec_path}")
    return True


def _plan_is_under_save_to(plan_path: Path, profile: Profile, repo_root: Path) -> bool:
    """Return True if plan_path resides under profile.plan.save_to."""
    try:
        plan_path.relative_to(repo_root / profile.plan.save_to)
        return True
    except ValueError:
        return False


def _archive_plan(
    plan_path: Path, profile: Profile, repo_root: Path, action: ConfirmAction
) -> Path | None:
    """Move a Complete plan to the archive directory. Returns new path or None.

    Interactive: prompt first (default No).
    --yes:       auto-archive.
    --dry-run:   print preview, no move.
    """
    dest_dir = repo_root / profile.plan.archive_to
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / plan_path.name

    if dest.exists():
        err_console.print(f"Archive destination already exists: {dest}. Refusing to overwrite.")
        raise typer.Exit(2)

    if action is ConfirmAction.DRY_RUN:
        console.print(f"Would archive: {plan_path} -> {dest}")
        return None
    if action is ConfirmAction.PROMPT:
        if not typer.confirm(
            f"Plan is Complete. Archive to {profile.plan.archive_to}?",
            default=False,
        ):
            return None

    try:
        subprocess.run(
            ["git", "mv", str(plan_path), str(dest)],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        shutil.move(str(plan_path), str(dest))
        subprocess.run(["git", "add", str(dest)], check=False, capture_output=True, cwd=repo_root)

    subprocess.run(
        ["git", "commit", "-m", f"chore(plan): archive {plan_path.stem} on completion"],
        check=True,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    console.print(f"Archived: {plan_path.name} -> {profile.plan.archive_to}")
    return dest


@progress_app.command()
def sync(
    plan_path: Path = typer.Argument(..., help="Path to the plan file.", exists=True),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without mutations."),
    yes: bool = typer.Option(False, "--yes", help="Execute without confirmation."),
) -> None:
    """Sync plan progress: checkboxes -> Status header -> spec index."""
    try:
        action = resolve_action(dry_run=dry_run, yes=yes)
    except Exception:
        err_console.print("Error: --dry-run and --yes are mutually exclusive")
        raise typer.Exit(1)

    plan_path = plan_path.resolve()
    plan = parse_plan(plan_path)
    new_status = _compute_status(plan_path)
    old_status = plan.status

    repo_root = _find_repo_root(plan_path)
    config_path = repo_root / "docs" / "superpowers" / "plan-config.yaml"
    profile = load_profile(config_path)

    mode = "dispatch" if profile.dispatch_enabled else "local"

    if old_status == new_status:
        # Plan status is correct, but spec index may be stale — reconcile it.
        spec_updated = _reconcile_spec_index(
            plan_path, plan.title, new_status, repo_root, dry_run=(action is ConfirmAction.DRY_RUN)
        )
        if not spec_updated:
            console.print(f"Status already {new_status}. Nothing to sync. (mode: {mode})")
        raise typer.Exit(0)

    if action is ConfirmAction.DRY_RUN:
        console.print(f"Would update Status: {old_status} -> {new_status} (mode: {mode})")
        _reconcile_spec_index(plan_path, plan.title, new_status, repo_root, dry_run=True)
        if new_status == "Complete" and _plan_is_under_save_to(plan_path, profile, repo_root):
            _archive_plan(plan_path, profile, repo_root, action)
        console.print("Local-only sync (dispatch disabled)" if not profile.dispatch_enabled else "")
        raise typer.Exit(0)

    if action is ConfirmAction.PROMPT:
        if not typer.confirm(f"Update Status: {old_status} -> {new_status}?", default=False):
            raise typer.Exit(0)

    _rewrite_status(plan_path, new_status)
    console.print(f"Status: {old_status} -> {new_status}")

    _reconcile_spec_index(plan_path, plan.title, new_status, repo_root)

    if new_status == "Complete" and _plan_is_under_save_to(plan_path, profile, repo_root):
        archived_path = _archive_plan(plan_path, profile, repo_root, action)
        if archived_path:
            _reconcile_spec_index(
                archived_path,
                plan.title,
                new_status,
                repo_root,
                prev_plan_path=plan_path,
            )

    if not profile.dispatch_enabled:
        console.print("Local-only sync (dispatch disabled)")


@progress_app.command()
def board(
    format_output: str = typer.Option("table", "--format", help="Output: table or json."),
) -> None:
    """Show plan status board."""
    repo_root = _find_repo_root(Path.cwd())
    config_path = repo_root / "docs" / "superpowers" / "plan-config.yaml"
    profile = load_profile(config_path)

    plans_dir = repo_root / profile.plan.save_to
    if not plans_dir.exists():
        console.print("No plans directory found.")
        raise typer.Exit(0)

    plan_files = sorted(plans_dir.glob("*.md"))
    if not plan_files:
        console.print("No plan files found.")
        raise typer.Exit(0)

    table = Table(title="Plan Status Board", show_header=True, header_style="bold")
    table.add_column("Plan")
    table.add_column("Status")
    table.add_column("Progress")

    for pf in plan_files:
        try:
            plan = parse_plan(pf)
            all_tasks = plan.all_tasks
            total = sum(len(t.steps) for t in all_tasks)
            done = sum(1 for t in all_tasks for s in t.steps if s.state in ("x", "-"))
            progress = f"{done}/{total}" if total > 0 else "—"
            table.add_row(plan.title, plan.status, progress)
        except (ValueError, FileNotFoundError):
            table.add_row(pf.name, "parse error", "—")

    console.print(table)


@progress_app.command()
def create(
    title: str = typer.Argument(..., help="Title for the new work item."),
    type_label: str = typer.Option("feature", "--type", help="Type: feature/bug/infra/skill."),
    repo: str | None = typer.Option(None, "--repo", help="Target repo (OWNER/REPO)."),
) -> None:
    """Create a new work item (GitHub Issue). Dispatch-only."""
    repo_root = _find_repo_root(Path.cwd())
    config_path = repo_root / "docs" / "superpowers" / "plan-config.yaml"
    profile = load_profile(config_path)

    if not profile.dispatch_enabled:
        err_console.print(format_gate_refusal())
        raise typer.Exit(1)

    dispatch_cfg = profile.dispatch
    assert dispatch_cfg is not None
    target_repo = repo or dispatch_cfg.default_repo

    from vk import gh

    try:
        url = gh.create_issue(
            repo=target_repo,
            title=title,
            body=f"Type: {type_label}",
            labels=[type_label],
        )
        console.print(f"Created: {url}")
    except gh.GhError as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(3)


@progress_app.command()
def transition(
    target: str = typer.Argument(..., help="Plan file path."),
    new_state: str = typer.Argument(..., help="New Status value."),
    yes: bool = typer.Option(False, "--yes", help="Execute without confirmation."),
) -> None:
    """Transition a plan's Status header (and spec-index entry)."""
    repo_root = _find_repo_root(Path.cwd())
    config_path = repo_root / "docs" / "superpowers" / "plan-config.yaml"
    profile = load_profile(config_path)

    plan_path = Path(target).resolve()
    if not plan_path.exists():
        err_console.print(f"Plan not found: {plan_path}")
        raise typer.Exit(2)

    plan = parse_plan(plan_path)
    allowed = profile.header.status_values
    if new_state not in allowed:
        err_console.print(f"Invalid status '{new_state}'. Allowed: {', '.join(allowed)}")
        raise typer.Exit(2)

    if not yes:
        if not typer.confirm(
            f"Transition {plan.title}: {plan.status} -> {new_state}?", default=False
        ):
            raise typer.Exit(0)

    _rewrite_status(plan_path, new_state)
    console.print(f"Status: {plan.status} -> {new_state}")

    spec_path = _resolve_spec(plan_path, repo_root)
    if spec_path:
        rel_file = str(plan_path.relative_to(repo_root))
        existing_entries = read_index(spec_path)
        existing_entry = next((e for e in existing_entries if e.file == rel_file), None)
        entry = IndexEntry(
            plan=plan.title,
            repo=existing_entry.repo if existing_entry else "",
            file=rel_file,
            status=new_state,
            depends_on=existing_entry.depends_on if existing_entry else "—",
        )
        upsert_entry(spec_path, entry)


def _extract_tracking_urls(plan_path: Path) -> list[str]:
    """Extract <!-- Tracking: URL --> comments from a plan file."""
    urls: list[str] = []
    text = plan_path.read_text(encoding="utf-8")
    for match in re.finditer(r"<!-- Tracking:\s*(https://[^\s]+)\s*-->", text):
        urls.append(match.group(1))
    return urls


def _parse_issue_url(url: str) -> tuple[str, int]:
    """Parse owner/repo and number from a GitHub Issue URL."""
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/issues/(\d+)", url)
    if not m:
        return ("", 0)
    return (m.group(1), int(m.group(2)))


@progress_app.command()
def audit(
    format_output: str = typer.Option("report", "--format", help="Output: report or json."),
) -> None:
    """Run drift checks and health audit."""
    repo_root = _find_repo_root(Path.cwd())
    config_path = repo_root / "docs" / "superpowers" / "plan-config.yaml"
    profile = load_profile(config_path)

    plans_dir = repo_root / profile.plan.save_to
    if not plans_dir.exists():
        console.print("No plans directory found.")
        raise typer.Exit(0)

    plan_files = sorted(plans_dir.glob("*.md"))
    issues: list[str] = []

    # Local checks (always run)
    for pf in plan_files:
        try:
            plan = parse_plan(pf)
        except (ValueError, FileNotFoundError):
            issues.append(f"Parse error: {pf.name}")
            continue

        computed = _compute_status(pf)
        if computed != plan.status:
            issues.append(
                f"Status drift: {plan.title} — header says '{plan.status}', "
                f"checkboxes say '{computed}'"
            )

        # Check spec index consistency
        if plan.spec:
            spec_path = _resolve_spec(pf, repo_root)
            if spec_path and spec_path.exists():
                entries = read_index(spec_path)
                rel_file = str(pf.relative_to(repo_root))
                matching = [e for e in entries if e.file == rel_file]
                for entry in matching:
                    if entry.status != plan.status:
                        issues.append(
                            f"Spec index drift: {plan.title} — plan says '{plan.status}', "
                            f"spec index says '{entry.status}'"
                        )

    console.print(f"\n[bold]Audit Report[/bold] — {len(plan_files)} plans scanned\n")

    if issues:
        console.print(f"[bold]Local checks:[/bold] {len(issues)} issue(s)")
        for issue in issues:
            console.print(f"  - {issue}")

    if not issues:
        console.print("[green]No issues found.[/green]")
