"""GitHub CLI subprocess wrappers.

Thin wrappers around ``gh`` commands used by the vk toolchain.
Functions raise GhError on failure.  No direct GitHub API usage —
we leverage gh's existing auth.
"""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from vk.labels import LabelDef

T = TypeVar("T")


class GhError(Exception):
    """Error from a gh CLI invocation."""

    def __init__(self, message: str, *, stderr: str = "", returncode: int = 0) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode


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
        raise GhError(msg, stderr=exc.stderr or "", returncode=exc.returncode) from exc
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


def view_issue(repo: str, number: int) -> dict[str, object]:
    """Fetch an Issue's title, body, labels, state via gh issue view --json."""
    import json

    out = _run_gh(
        ["issue", "view", str(number), "--repo", repo, "--json", "title,body,labels,state"]
    )
    result: dict[str, object] = json.loads(out)
    return result


def edit_issue(
    *,
    repo: str,
    number: int,
    title: str,
    body: str,
    add_labels: list[str],
) -> None:
    """Edit an Issue's title, body, and add labels in one call."""
    args = ["issue", "edit", str(number), "--repo", repo, "--title", title, "--body", body]
    for lbl in add_labels:
        args.extend(["--add-label", lbl])
    _run_gh(args)


def edit_issue_body(*, repo: str, number: int, body: str) -> None:
    """Update the body of an existing Issue via `gh issue edit`."""
    _run_gh(["issue", "edit", str(number), "--repo", repo, "--body", body])


def ensure_label(
    *,
    repo: str,
    name: str,
    color: str = "ededed",
    description: str = "",
) -> None:
    """Create (or update) a label on the target repo.

    Uses ``gh label create --force``, which is idempotent: creates the label
    if missing, updates its color/description if present. Without this,
    ``gh issue create --label X`` fails hard on any repo that doesn't
    already have X — which silently breaks ``vk dispatch`` on new repos.
    """
    args = [
        "label",
        "create",
        name,
        "--repo",
        repo,
        "--force",
        "--color",
        color,
    ]
    if description:
        args.extend(["--description", description])
    _run_gh(args)


def ensure_labels(*, repo: str, labels: list[LabelDef]) -> None:
    """Ensure every label exists on the repo with the right color and
    description. First failure propagates.

    Fails loud on the first error so callers can abort before creating
    Issues that would end up in a partial-label state.
    """
    for ld in labels:
        ensure_label(repo=repo, name=ld.name, color=ld.color, description=ld.description)


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


def swap_issue_labels(
    *,
    repo: str,
    number: int,
    add: list[str],
    remove: list[str],
) -> None:
    """Add and remove labels on an Issue in a single gh call.

    No-op if both lists are empty. Failure propagates as GhError.
    """
    if not add and not remove:
        return
    args = ["issue", "edit", str(number), "--repo", repo]
    for lbl in add:
        args.extend(["--add-label", lbl])
    for lbl in remove:
        args.extend(["--remove-label", lbl])
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


def list_labels(*, repo: str) -> list[dict[str, str]]:
    """Return existing labels on the repo as parsed JSON."""
    import json

    out = _run_gh(
        [
            "label",
            "list",
            "--repo",
            repo,
            "--json",
            "name,color,description",
            "--limit",
            "200",
        ]
    )
    return json.loads(out) if out else []


def list_repos(*, owner: str) -> list[dict[str, object]]:
    """Return non-archived repos under the given owner."""
    import json

    out = _run_gh(
        [
            "repo",
            "list",
            owner,
            "--json",
            "name,isArchived",
            "--limit",
            "200",
        ]
    )
    repos = json.loads(out) if out else []
    return [r for r in repos if not r.get("isArchived", False)]


def delete_label(*, repo: str, name: str) -> None:
    """Delete a label from the repo. `--yes` skips gh's confirmation prompt."""
    _run_gh(["label", "delete", name, "--repo", repo, "--yes"])


def count_issues_with_label(*, repo: str, name: str) -> int:
    """Count Issues (any state) that carry this label. Cap at 1000."""
    import json

    out = _run_gh(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--label",
            name,
            "--state",
            "all",
            "--json",
            "id",
            "--limit",
            "1000",
        ]
    )
    return len(json.loads(out)) if out else 0


def auth_status() -> bool:
    """Check if gh is authenticated.  Returns True if logged in."""
    try:
        _run_gh(["auth", "status"])
    except GhError:
        return False
    else:
        return True


_TRANSIENT_PATTERNS = (
    "http 5",  # 500, 502, 503, 504, ...
    "could not resolve",
    "connection reset",
    "connection refused",
    "timeout",
    "temporarily unavailable",
)


def is_transient(err: GhError) -> bool:
    """True if the error looks like a transient network/server failure
    that warrants retry. False for auth, 404, validation, and unknown
    errors (fail fast)."""
    text = (err.stderr + " " + str(err)).lower()
    return any(p in text for p in _TRANSIENT_PATTERNS)


def with_retry(
    op: Callable[[], T],
    *,
    max_attempts: int = 3,
    backoff_seconds: tuple[float, ...] = (1.0, 2.0, 4.0),
) -> T:
    """Run `op`; retry on transient GhError with backoff. Re-raise the
    last error if max_attempts is exhausted or the error is permanent.

    `backoff_seconds[i]` is the sleep before attempt i+1 (i.e. the gap
    between attempt i and attempt i+1). At most `max_attempts - 1` sleeps
    are performed, so `backoff_seconds` must contain at least that many
    entries."""
    if max_attempts < 1:
        msg = f"max_attempts must be >= 1, got {max_attempts}"
        raise ValueError(msg)
    if len(backoff_seconds) < max_attempts - 1:
        msg = (
            f"backoff_seconds has {len(backoff_seconds)} entries but "
            f"max_attempts={max_attempts} requires at least {max_attempts - 1}"
        )
        raise ValueError(msg)
    attempt = 0
    while True:
        try:
            return op()
        except GhError as exc:
            attempt += 1
            if attempt >= max_attempts or not is_transient(exc):
                raise
            time.sleep(backoff_seconds[attempt - 1])
