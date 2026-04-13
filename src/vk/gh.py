"""GitHub CLI subprocess wrappers.

Thin wrappers around ``gh`` commands used by the vk toolchain.
Functions raise GhError on failure.  No direct GitHub API usage —
we leverage gh's existing auth.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass


class GhError(Exception):
    """Error from a gh CLI invocation."""


def _run_gh(args: list[str]) -> str:
    """Run a gh command and return stdout.  Raises GhError on failure."""
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() if exc.stderr else f"gh exited with code {exc.returncode}"
        raise GhError(msg) from exc
    return result.stdout.strip()


def extract_issue_number(url: str) -> int:
    """Extract the issue number from a GitHub Issue URL."""
    m = re.search(r"/issues/(\d+)", url)
    if not m:
        msg = f"Cannot extract issue number from URL: {url}"
        raise GhError(msg)
    return int(m.group(1))


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


def edit_issue_labels(
    *,
    repo: str,
    issue_number: int,
    add_labels: list[str],
) -> None:
    """Add labels to an existing issue."""
    args = ["issue", "edit", str(issue_number), "--repo", repo]
    for label in add_labels:
        args.extend(["--add-label", label])
    _run_gh(args)


def get_project_number(*, owner: str, project_name: str) -> int:
    """Look up a project board number by name."""
    output = _run_gh(
        [
            "project",
            "list",
            "--owner",
            owner,
            "--format",
            "json",
        ]
    )
    import json

    projects = json.loads(output).get("projects", [])
    for p in projects:
        if p.get("title") == project_name:
            return int(p["number"])
    msg = f"Project '{project_name}' not found for owner '{owner}'"
    raise GhError(msg)


def get_project_id(*, owner: str, project_number: int) -> str:
    """Get the internal project ID (PVT_...) from project number."""
    output = _run_gh(
        [
            "project",
            "view",
            str(project_number),
            "--owner",
            owner,
            "--format",
            "json",
        ]
    )
    import json

    data = json.loads(output)
    return str(data.get("id", ""))


def get_item_id(*, owner: str, project_number: int, issue_url: str) -> str:
    """Get the project item ID for an issue on a project board."""
    output = _run_gh(
        [
            "project",
            "item-list",
            str(project_number),
            "--owner",
            owner,
            "--format",
            "json",
        ]
    )
    import json

    data = json.loads(output)
    for item in data.get("items", []):
        content = item.get("content", {})
        if content.get("url") == issue_url:
            return str(item["id"])
    msg = f"Issue {issue_url} not found on project {project_number}"
    raise GhError(msg)


def get_field_id(*, owner: str, project_number: int, field_name: str) -> str:
    """Get the field ID for a named field on a project board."""
    output = _run_gh(
        [
            "project",
            "field-list",
            str(project_number),
            "--owner",
            owner,
            "--format",
            "json",
        ]
    )
    import json

    data = json.loads(output)
    for field in data.get("fields", []):
        if field.get("name") == field_name:
            return str(field["id"])
    msg = f"Field '{field_name}' not found on project {project_number}"
    raise GhError(msg)


def get_option_id(*, owner: str, project_number: int, field_name: str, option_name: str) -> str:
    """Get the option ID for a single-select field value."""
    output = _run_gh(
        [
            "project",
            "field-list",
            str(project_number),
            "--owner",
            owner,
            "--format",
            "json",
        ]
    )
    import json

    data = json.loads(output)
    for field in data.get("fields", []):
        if field.get("name") == field_name:
            for opt in field.get("options", []):
                if opt.get("name") == option_name:
                    return str(opt["id"])
    msg = f"Option '{option_name}' not found for field '{field_name}'"
    raise GhError(msg)


@dataclass
class BoardItem:
    """A project board item with lifecycle metadata."""

    title: str
    url: str
    repo: str
    number: int
    closed: bool
    lifecycle: str  # "unset" if missing
    status: str  # board status column
    labels: list[str]


def list_project_items(*, owner: str, project_number: int) -> list[BoardItem]:
    """List all items on a project board with lifecycle and status fields."""
    output = _run_gh(
        [
            "project",
            "item-list",
            str(project_number),
            "--owner",
            owner,
            "--format",
            "json",
        ]
    )
    import json

    data = json.loads(output)
    items: list[BoardItem] = []
    for item in data.get("items", []):
        content = item.get("content", {})
        if content.get("type") != "Issue":
            continue
        items.append(
            BoardItem(
                title=content.get("title", ""),
                url=content.get("url", ""),
                repo=content.get("repository", ""),
                number=content.get("number", 0),
                closed=False,  # use is_issue_closed() for live check
                lifecycle=item.get("lifecycle", "unset") or "unset",
                status=item.get("status", ""),
                labels=[lb for lb in item.get("labels", [])],
            )
        )
    return items


def is_issue_closed(*, repo: str, number: int) -> bool:
    """Check if an issue is closed."""
    output = _run_gh(
        [
            "issue",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "closed",
            "--jq",
            ".closed",
        ]
    )
    return output.strip().lower() == "true"


def auth_status() -> bool:
    """Check if gh is authenticated.  Returns True if logged in."""
    try:
        _run_gh(["auth", "status"])
    except GhError:
        return False
    else:
        return True
