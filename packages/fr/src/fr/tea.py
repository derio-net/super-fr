"""Gitea CLI (`tea`) subprocess wrappers.

Thin wrappers around ``tea`` commands, mirroring `fr.gh`'s shape (same
function names/signatures where the operation maps 1:1). Functions raise
TeaError on failure. No direct Gitea API usage — we leverage tea's
existing auth (`tea login add`), same architecture as `fr.gh`/`fr.glab`
(see docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md).

Concrete differences from `gh`/`glab`, verified directly against the
installed `tea` binary's `--help` output and Gitea's live swagger spec
(gitea.com/swagger.v1.json) — not assumed by analogy:
- `tea issues create` takes `--description` (like glab, not gh's `--body`)
  and `--labels` (plural), a SINGLE comma-joined value — not one flag per
  label the way gh/glab repeat their flag.
- Viewing a single issue has no `view` subcommand: `tea issues <n> --repo
  ... --output json` alone shows it in detail.
- `tea issues edit` uses `--add-labels`/`--remove-labels`, also
  comma-joined.
- Gitea's label color needs a leading `#` on write
  (`CreateLabelOption.color` example `"#00aabb"`) — the same as GitLab,
  NOT bare hex like GitHub as originally assumed; corrected after
  checking the live swagger spec instead of guessing by analogy.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from typing import TypeVar

from fr.labels import LabelDef

T = TypeVar("T")


class TeaError(Exception):
    """Error from a tea CLI invocation."""

    def __init__(self, message: str, *, stderr: str = "", returncode: int = 0) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode


def _run_tea(args: list[str]) -> str:
    """Run a tea command and return stdout. Raises TeaError on failure."""
    try:
        result = subprocess.run(
            ["tea", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() if exc.stderr else f"tea exited with code {exc.returncode}"
        raise TeaError(msg, stderr=exc.stderr or "", returncode=exc.returncode) from exc
    return result.stdout.strip()


def create_issue(
    *,
    repo: str,
    title: str,
    body: str,
    labels: list[str],
) -> str:
    """Create a Gitea Issue and return its URL."""
    args = [
        "issues",
        "create",
        "--repo",
        repo,
        "--title",
        title,
        "--description",
        body,
    ]
    if labels:
        args.extend(["--labels", ",".join(labels)])
    return _run_tea(args)


def view_issue(repo: str, number: int) -> dict[str, object]:
    """Fetch an Issue's title, body, labels, state.

    No `view` subcommand exists — `tea issues <n> --output json` alone
    shows the issue in detail (per `tea issues --help`)."""
    import json

    out = _run_tea(["issues", str(number), "--repo", repo, "--output", "json"])
    result: dict[str, object] = json.loads(out)
    return result


def close_issue(*, repo: str, number: int) -> None:
    """Close a Gitea Issue by index."""
    _run_tea(["issues", "close", str(number), "--repo", repo])


def reopen_issue(*, repo: str, number: int) -> None:
    """Reopen a closed Gitea Issue by index."""
    _run_tea(["issues", "reopen", str(number), "--repo", repo])


def edit_issue_body(*, repo: str, number: int, body: str) -> None:
    """Update the body of an existing Issue via `tea issues edit
    --description` (tea's flag name, like glab's, unlike gh's `--body`)."""
    _run_tea(["issues", "edit", str(number), "--repo", repo, "--description", body])


def swap_issue_labels(
    *,
    repo: str,
    number: int,
    add: list[str],
    remove: list[str],
) -> None:
    """Add and remove labels on an Issue in a single tea call.

    No-op if both lists are empty. Each of `--add-labels`/`--remove-labels`
    takes ONE comma-joined value (not a repeated flag) — a real CLI
    difference from gh/glab, verified against `tea issues edit --help`.
    """
    if not add and not remove:
        return
    args = ["issues", "edit", str(number), "--repo", repo]
    if add:
        args.extend(["--add-labels", ",".join(add)])
    if remove:
        args.extend(["--remove-labels", ",".join(remove)])
    _run_tea(args)


def ensure_label(
    *,
    repo: str,
    name: str,
    color: str = "ededed",
    description: str = "",
) -> None:
    """Create a label on the target repo.

    Like glab, `tea labels create` has no documented idempotent-update
    flag equivalent to `gh label create --force` — a pre-existing label
    name is tolerated the same way as fr.glab.ensure_label (see that
    module's docstring for the rationale).
    """
    args = [
        "labels",
        "create",
        "--name",
        name,
        "--repo",
        repo,
        "--color",
        f"#{color}",
    ]
    if description:
        args.extend(["--description", description])
    _run_tea(args)


def ensure_labels(*, repo: str, labels: list[LabelDef]) -> None:
    """Ensure every label exists on the repo with the right color and
    description. First failure propagates (mirrors `fr.gh.ensure_labels`)."""
    for ld in labels:
        ensure_label(repo=repo, name=ld.name, color=ld.color, description=ld.description)


_TRANSIENT_PATTERNS = (
    "500",
    "502",
    "503",
    "504",
    "no such host",
    "connection reset",
    "connection refused",
    "context deadline exceeded",
    "timeout",
)


def is_transient(err: TeaError) -> bool:
    """True if the error looks like a transient network/server failure
    that warrants retry. False for auth, 404, validation, and unknown
    errors (fail fast). Patterns are tea's own stderr vocabulary, distinct
    from gh's/glab's — see the module docstring and the design doc's
    capability matrix."""
    text = (err.stderr + " " + str(err)).lower()
    return any(p in text for p in _TRANSIENT_PATTERNS)


def with_retry(
    op: Callable[[], T],
    *,
    max_attempts: int = 3,
    backoff_seconds: tuple[float, ...] = (1.0, 2.0, 4.0),
) -> T:
    """Run `op`; retry on transient TeaError with backoff. Mirrors
    `fr.gh.with_retry` exactly."""
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
        except TeaError as exc:
            attempt += 1
            if attempt >= max_attempts or not is_transient(exc):
                raise
            time.sleep(backoff_seconds[attempt - 1])
