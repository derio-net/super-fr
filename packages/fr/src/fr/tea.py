"""Gitea CLI (`tea`) subprocess wrappers.

Thin wrappers around ``tea`` commands, mirroring `fr.gh`'s shape (same
function names/signatures where the operation maps 1:1). Functions raise
TeaError on failure. Everything goes through `tea` — writes through its
subcommands, reads through `tea api` — so tea's existing auth (`tea login
add`) is the only credential, same architecture as `fr.gh`/`fr.glab` (see
docs/superpowers/specs/2026-07-09-multi-backend-git-host-adapters-design.md).

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

Reads go through `api_json` (`tea api -i`), never tea's `--fields` /
`--output json` renderings. Found live against tea 0.16.0 (Phase 9 walk of
the multi-backend plan; fixtures in `tests/fixtures/gitea/`): those
renderings are tea's own shape, not Gitea's — `pulls list` has no `merged`
field and renders `head` as a bare string and state as open|closed|merged,
`pulls <n>` says `hasMerged` and drops `draft`, `repos` lists repos (no
`default_branch`), and `issues list` renders `index` as a string and
`labels` space-separated. And `tea api` exits 0 whatever the HTTP status,
so the `-i` status line on stderr is the only error signal.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from fr.ghclient import CommandRunner, run_cli
from fr.labels import LabelDef

T = TypeVar("T")


class TeaError(Exception):
    """Error from a tea CLI invocation."""

    def __init__(self, message: str, *, stderr: str = "", returncode: int = 0) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode


def _run_tea(args: list[str], *, cwd: Path | None = None) -> str:
    """Run a tea command and return stdout. Raises TeaError on failure.

    `cwd` is the checkout tea resolves its repository and login from when
    the call names no `--repo` (gh#742); `None` keeps this process's."""
    try:
        result = subprocess.run(
            ["tea", *args],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() if exc.stderr else f"tea exited with code {exc.returncode}"
        raise TeaError(msg, stderr=exc.stderr or "", returncode=exc.returncode) from exc
    return result.stdout.strip()


_STATUS_LINE = re.compile(r"^HTTP/\S+\s+(\d{3})\b")
_LOCATION = re.compile(r"^location:\s*(\S+)", re.IGNORECASE | re.MULTILINE)


def api_result(result: subprocess.CompletedProcess[str]) -> Any:
    """Gitea's JSON body from one `tea api -i` run, or TeaError.

    Refuses a non-zero exit, a missing status line (`-i` was not passed, or
    tea printed something else), any status outside 2xx, and a body that is
    not JSON. A 3xx is almost always an SSO / forward-auth proxy in front of
    the instance answering with its login page, so it is named as one."""
    stderr = result.stderr or ""
    if result.returncode != 0:
        msg = stderr.strip() or f"tea exited with code {result.returncode}"
        raise TeaError(msg, stderr=stderr, returncode=result.returncode)
    first = stderr.lstrip().splitlines()[0] if stderr.strip() else ""
    m = _STATUS_LINE.match(first)
    if not m:
        raise TeaError("`tea api -i` printed no HTTP status line", stderr=stderr)
    status = int(m.group(1))
    if 300 <= status < 400:
        loc = _LOCATION.search(stderr)
        where = f" to {loc.group(1)}" if loc else ""
        raise TeaError(
            f"HTTP {status}: the Gitea API redirected{where} — an SSO or forward-auth "
            "proxy is likely in front of it; exempt its /api/ paths or use an internal URL",
            stderr=stderr,
        )
    if not 200 <= status < 300:
        detail = ""
        try:
            body = json.loads(result.stdout or "null")
            if isinstance(body, dict) and body.get("message"):
                detail = f": {body['message']}"
        except json.JSONDecodeError:
            pass
        raise TeaError(f"HTTP {status}{detail}", stderr=stderr)
    out = (result.stdout or "").strip()
    try:
        return json.loads(out) if out else None
    except json.JSONDecodeError as exc:
        # tea follows redirects, so a forward-auth proxy's login page can arrive
        # as a 200: an HTML body is the only sign of it left.
        if out.startswith("<") or "text/html" in stderr.lower():
            raise TeaError(
                f"HTTP {status} with an HTML body, not Gitea's JSON — an SSO or "
                "forward-auth login page, most likely; exempt the instance's /api/ "
                "paths or use an internal URL",
                stderr=stderr,
            ) from exc
        raise TeaError(f"HTTP {status} with a body that is not JSON: {exc}", stderr=stderr) from exc


def api_json(path: str, *, cwd: Path | None = None, run: CommandRunner | None = None) -> Any:
    """GET one Gitea API endpoint through `tea api -i` — tea's auth, and its
    `{owner}`/`{repo}` placeholders resolved from the checkout at *cwd*.

    *run* is the caller's `CommandRunner` (the isolation lifecycle passes its
    own, for its network env and timeout); `None` is `run_cli`."""
    runner = run or run_cli
    return api_result(runner(["tea", "api", "-i", path], cwd=cwd or Path.cwd()))


def api_pages(path: str, *, max_items: int | None = None) -> list[Any]:
    """Every item of a paginated list endpoint (*path* may carry a query).

    Gitea clamps a page to its own maximum (50 by default) whatever `limit`
    asks, so page until an empty page — a single page is a silent cap."""
    items: list[Any] = []
    sep = "&" if "?" in path else "?"
    page = 1
    while max_items is None or len(items) < max_items:
        chunk = api_json(f"{path}{sep}limit=50&page={page}")
        if not isinstance(chunk, list):
            raise TeaError(f"{path}: expected a JSON list, got {type(chunk).__name__}")
        if not chunk:
            break
        items.extend(chunk)
        page += 1
    return items if max_items is None else items[:max_items]


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


def edit_issue(*, repo: str, number: int, title: str, body: str) -> None:
    """Replace an Issue's title and description (`tea issues edit`)."""
    _run_tea(
        ["issues", "edit", str(number), "--repo", repo, "--title", title, "--description", body]
    )


def comment_close_issue(*, repo: str, number: int, comment: str) -> None:
    """Comment on an Issue, then close it."""
    _run_tea(["comments", "add", str(number), comment, "--repo", repo])
    close_issue(repo=repo, number=number)


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
    """Create one label on the target repo, unconditionally.

    Gitea ALLOWS two labels with the same name — a create never refuses
    with "already exists" the way GitLab's does — so this alone does not
    converge. `ensure_labels` is the idempotent entry point.
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
    """Ensure every label NAME exists on the repo, creating only the missing.

    The existing names are read first, because Gitea accepts a duplicate
    name and two `ensure_labels` calls would otherwise leave two labels
    (and issues created after carrying both). Colour/description drift on
    an existing label is tolerated, as `fr.glab.ensure_labels` tolerates it.
    First failure propagates (mirrors `fr.gh.ensure_labels`)."""
    existing = {
        str(lbl.get("name")) for lbl in api_pages(f"/repos/{repo}/labels") if isinstance(lbl, dict)
    }
    for ld in labels:
        if ld.name in existing:
            continue
        ensure_label(repo=repo, name=ld.name, color=ld.color, description=ld.description)
        existing.add(ld.name)


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
