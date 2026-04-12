"""GitHub CLI subprocess wrappers.

Thin wrappers around ``gh`` commands used by the vk toolchain.
All functions (except auth_status) raise subprocess.CalledProcessError
on failure.  No direct GitHub API usage — we leverage gh's existing auth.
"""

from __future__ import annotations

import subprocess


def _run_gh(args: list[str]) -> str:
    """Run a gh command and return stdout."""
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def create_issue(
    *,
    repo: str,
    title: str,
    body: str,
    labels: list[str],
) -> str:
    """Create a GitHub Issue and return its URL."""
    args = [
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        title,
        "--body",
        body,
    ]
    for label in labels:
        args.extend(["--label", label])
    return _run_gh(args)


def close_issue(*, repo: str, number: int) -> None:
    """Close a GitHub Issue by number."""
    _run_gh(
        [
            "issue",
            "close",
            "--repo",
            repo,
            str(number),
        ]
    )


def add_to_project(
    *,
    url: str,
    project_owner: str,
    project_number: int,
) -> str:
    """Add an issue to a GitHub Project board and return the item ID."""
    return _run_gh(
        [
            "project",
            "item-add",
            str(project_number),
            "--owner",
            project_owner,
            "--url",
            url,
            "--format",
            "json",
        ]
    )


def set_field(
    *,
    project_owner: str,
    project_number: int,
    item_id: str,
    field_name: str,
    field_value: str,
) -> None:
    """Set a field value on a project board item."""
    _run_gh(
        [
            "project",
            "item-edit",
            "--owner",
            project_owner,
            "--project-id",
            str(project_number),
            "--id",
            item_id,
            "--field-name",
            field_name,
            "--field-value",
            field_value,
        ]
    )


def auth_status() -> bool:
    """Check if gh is authenticated.  Returns True if logged in."""
    try:
        _run_gh(["auth", "status"])
    except subprocess.CalledProcessError:
        return False
    else:
        return True
