"""GitHub CLI subprocess wrappers.

Thin wrappers around ``gh`` commands used by the vk toolchain.
Functions raise GhError on failure.  No direct GitHub API usage —
we leverage gh's existing auth.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar
from urllib.parse import quote

from fr.labels import LabelDef

T = TypeVar("T")


class GhError(Exception):
    """Error from a gh CLI invocation."""

    def __init__(
        self, message: str, *, stderr: str = "", returncode: int = 0, stdout: str = ""
    ) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode
        # Some gh commands answer on a non-zero exit (`gh pr checks` exits 8
        # while checks are pending, with its JSON on stdout), so it is kept.
        self.stdout = stdout


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
        raise GhError(
            msg, stderr=exc.stderr or "", returncode=exc.returncode, stdout=exc.stdout or ""
        ) from exc
    return result.stdout.strip()


def view_pr_body(ref: str, *, cwd: Path | None = None) -> str:
    """The live body of pull request `ref` (a number, URL or branch), read
    with `gh pr view` from `cwd` (its repository). Raises GhError."""
    try:
        done = subprocess.run(
            ["gh", "pr", "view", ref, "--json", "body", "--jq", ".body"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise GhError("gh is not installed") from exc
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() if exc.stderr else f"gh exited with code {exc.returncode}"
        raise GhError(msg, stderr=exc.stderr or "", returncode=exc.returncode) from exc
    return done.stdout


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


# Shared by every caller: only ever ADD a field here, never drop one.
ISSUE_VIEW_FIELDS = "number,title,body,labels,state,url,closedAt"


def view_issue(repo: str, number: int) -> dict[str, object]:
    """Fetch one Issue via gh issue view --json (fields: ``ISSUE_VIEW_FIELDS``)."""
    import json

    out = _run_gh(["issue", "view", str(number), "--repo", repo, "--json", ISSUE_VIEW_FIELDS])
    result: dict[str, object] = json.loads(out)
    return result


def read_file_at_ref(*, repo: str, path: str, ref: str) -> str:
    """Read a repository file at *ref* through GitHub's contents API."""
    endpoint = f"repos/{repo}/contents/{quote(path, safe='/')}?ref={quote(ref, safe='')}"
    return _run_gh(["api", "-H", "Accept: application/vnd.github.raw+json", endpoint])


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
    already have X — which silently breaks ``fr apply`` on new repos.
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


def list_labels(*, repo: str) -> list[dict[str, str | None]]:
    """Return existing labels on the repo as parsed JSON.

    The GitHub API returns ``"description": null`` for labels with no
    description, so values are ``str | None``.
    """
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


def list_repos(
    *, owner: str, limit: int = 200, include_archived: bool = False
) -> list[dict[str, object]]:
    """Return repos under *owner* — non-archived only unless *include_archived*.

    ``include_archived`` exists so a caller can tell whether the list returned
    exactly ``limit`` records (and so may be cut short) before filtering.
    """
    import json

    out = _run_gh(
        [
            "repo",
            "list",
            owner,
            "--json",
            "name,isArchived",
            "--limit",
            str(limit),
        ]
    )
    repos: list[dict[str, object]] = json.loads(out) if out else []
    if include_archived:
        return repos
    return [r for r in repos if not r.get("isArchived", False)]


ISSUE_LIST_FIELDS = "number,title,labels,createdAt,updatedAt,url,body"
PR_LIST_FIELDS = (
    "number,title,state,isDraft,createdAt,mergedAt,url,headRefName,closingIssuesReferences"
)
OPEN_PR_LIST_FIELDS = (
    PR_LIST_FIELDS + ",files,statusCheckRollup,mergeable,mergeStateStatus,reviewDecision,headRefOid"
)


def list_issues(*, repo: str, state: str, limit: int) -> list[dict[str, object]]:
    """Return issues in *repo* via one bulk ``gh issue list``.

    ``--limit`` is always explicit: gh's default is 30, which would silently
    truncate any backlog past thirty issues.
    """
    import json

    out = _run_gh(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            state,
            "--limit",
            str(limit),
            "--json",
            ISSUE_LIST_FIELDS,
        ]
    )
    issues: list[dict[str, object]] = json.loads(out) if out else []
    return issues


def list_prs(*, repo: str, state: str, limit: int) -> list[dict[str, object]]:
    """Return PRs in *repo* via one bulk ``gh pr list`` (explicit ``--limit``)."""
    import json

    out = _run_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            state,
            "--limit",
            str(limit),
            "--json",
            PR_LIST_FIELDS,
        ]
    )
    prs: list[dict[str, object]] = json.loads(out) if out else []
    return prs


def list_open_prs(*, repo: str, limit: int) -> list[dict[str, object]]:
    import json

    out = _run_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            str(limit),
            "--json",
            OPEN_PR_LIST_FIELDS,
        ]
    )
    return json.loads(out) if out else []


def list_prs_by_head(*, repo: str, branch: str, limit: int = 100) -> list[dict[str, object]]:
    """Every PR (any state) whose head is *branch*: `PR_LIST_FIELDS` plus `headRefOid`."""
    import json

    out = _run_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--head",
            branch,
            "--state",
            "all",
            "--limit",
            str(limit),
            "--json",
            PR_LIST_FIELDS + ",headRefOid",
        ]
    )
    return json.loads(out) if out else []


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


def _classify_error(stderr: str) -> str:
    """Classify a `gh` stderr blob for the bridge's retry / backoff logic.

    Returns one of:

    - `"rate_limit"`: 403 with "API rate limit exceeded" — caller should
      back off the whole tick rather than retrying immediately.
    - `"info"`: 404 / "Not Found" — the target is gone, not a server
      problem; caller can treat as success-with-no-op.
    - `"warn"`: 5xx, network resets, timeouts — transient, may retry.
    - `"unknown"`: anything else.

    Ported from the legacy bridge's `_classify_gh_error` (concern M).
    The bridge's I3 guard reads this to decide rate-limit backoff
    versus raising.
    """
    text = (stderr or "").lower()
    if "403" in text and "rate limit" in text:
        return "rate_limit"
    if "404" in text or "not found" in text:
        return "info"
    for pat in _TRANSIENT_PATTERNS:
        if pat in text:
            return "warn"
    return "unknown"


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
