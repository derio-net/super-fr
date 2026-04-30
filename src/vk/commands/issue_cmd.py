"""vk issue — author bridge-compatible GitHub Issues."""

from __future__ import annotations

import json
import subprocess
import sys

import typer
from rich.console import Console

from vk.commands.dispatch_body_validator import BodyValidationError, validate_issue_body

console = Console()
err_console = Console(stderr=True)

issue_app = typer.Typer(help="Author bridge-compatible GitHub Issues.")


def _resolve_repo(repo: str | None) -> str:
    """Resolve owner/repo from --repo flag or git remote origin."""
    if repo:
        return repo
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
        if url.startswith("git@"):
            path_part = url.split(":", 1)[-1]
        else:
            path_part = "/".join(url.rstrip("/").split("/")[-2:])
        return path_part.removesuffix(".git")
    except subprocess.CalledProcessError:
        err_console.print("Error: could not resolve repo from git remote. Pass --repo explicitly.")
        raise typer.Exit(2)


def _build_issue_body(topic: str, skill: str, repos: str, blockers: str) -> str:
    """Build a bridge-compatible Issue body."""
    return (
        f"{topic}\n\n"
        f"---\n\n"
        f"## Instruction\n\n"
        f"Use {skill} to explore the above and produce deliverables.\n\n"
        f"## Workspace\n\n"
        f"Repos: {repos}\n\n"
        f"## Dependencies\n\n"
        f"{blockers}\n"
    )


@issue_app.command()
def create(
    topic: str = typer.Argument(
        ...,
        help="Free-form problem description. Pass '-' to read from stdin.",
    ),
    skill: str = typer.Option(
        "superpowers:brainstorming",
        "--skill",
        help="Skill the next agent should use.",
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        help="Target repo (owner/repo). Defaults to git remote origin.",
    ),
    blockers: str = typer.Option(
        "None — no blocking phases.",
        "--blockers",
        help="Dependency string for ## Dependencies section.",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Issue title. Defaults to first 72 chars of topic.",
    ),
    label: str = typer.Option(
        "vk-ready",
        "--label",
        help="Label to apply. Pass empty string to skip.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print output without creating Issue."),
) -> None:
    """Create a bridge-compatible GitHub Issue from a free-form topic."""
    if topic == "-":
        topic = sys.stdin.read().rstrip("\n")

    resolved_repo = _resolve_repo(repo)
    issue_title = title or topic[:72].rstrip()

    body = _build_issue_body(
        topic=topic,
        skill=skill,
        repos=resolved_repo,
        blockers=blockers,
    )

    try:
        validate_issue_body(body, phase_number=0)
    except BodyValidationError as exc:
        err_console.print(f"Error: generated body failed validation: {exc}")
        raise typer.Exit(1)

    if dry_run:
        console.print(f"[bold]Title:[/bold] {issue_title}")
        console.print("\n[bold]Body:[/bold]\n")
        console.print(body)
        raise typer.Exit(0)

    cmd = ["gh", "issue", "create", "--title", issue_title, "--body", body]
    if label:
        cmd += ["--label", label]
    cmd += ["--repo", resolved_repo]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        url = result.stdout.strip()
        console.print(f"Created: {url}")
    except subprocess.CalledProcessError as exc:
        err_console.print(f"Error: gh issue create failed: {exc.stderr.strip()}")
        raise typer.Exit(3)


_REQUIRED_SECTIONS = ("## Instruction", "## Workspace", "## Dependencies")


def _build_contract_block(skill: str, repos: str, blockers: str) -> str:
    """Build only the contract section block (no topic prefix)."""
    return (
        f"## Instruction\n\n"
        f"Use {skill} to explore the above and produce deliverables.\n\n"
        f"## Workspace\n\n"
        f"Repos: {repos}\n\n"
        f"## Dependencies\n\n"
        f"{blockers}\n"
    )


@issue_app.command()
def convert(
    number: int = typer.Argument(..., help="GitHub Issue number to convert."),
    repo: str | None = typer.Option(
        None,
        "--repo",
        help="Target repo (owner/repo). Defaults to git remote origin.",
    ),
    skill: str = typer.Option(
        "superpowers:brainstorming",
        "--skill",
        help="Skill the next agent should use.",
    ),
    blockers: str = typer.Option(
        "None — no blocking phases.",
        "--blockers",
        help="Dependency string for ## Dependencies section.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print converted body without editing the Issue.",
    ),
) -> None:
    """Append bridge contract sections to an existing GitHub Issue."""
    resolved_repo = _resolve_repo(repo)

    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(number), "--repo", resolved_repo, "--json", "body"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        err_console.print(f"Error: could not fetch Issue #{number}: {exc.stderr.strip()}")
        raise typer.Exit(2)

    existing_body = json.loads(result.stdout).get("body", "")

    if all(section in existing_body for section in _REQUIRED_SECTIONS):
        console.print(f"Issue #{number} already has contract sections. Nothing to do.")
        raise typer.Exit(0)

    contract_block = _build_contract_block(
        skill=skill,
        repos=resolved_repo,
        blockers=blockers,
    )
    new_body = existing_body.rstrip("\n") + "\n\n---\n\n" + contract_block

    try:
        validate_issue_body(new_body, phase_number=0)
    except BodyValidationError as exc:
        err_console.print(f"Error: converted body failed validation: {exc}")
        raise typer.Exit(1)

    if dry_run:
        console.print(f"[bold]Converted body for Issue #{number}:[/bold]\n")
        console.print(new_body)
        raise typer.Exit(0)

    try:
        subprocess.run(
            ["gh", "issue", "edit", str(number), "--repo", resolved_repo, "--body", new_body],
            capture_output=True,
            text=True,
            check=True,
        )
        console.print(f"Issue #{number} updated with bridge contract.")
    except subprocess.CalledProcessError as exc:
        err_console.print(f"Error: gh issue edit failed: {exc.stderr.strip()}")
        raise typer.Exit(3)
