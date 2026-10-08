"""GitHub CLI subprocess wrappers.

Thin wrappers around ``gh`` commands used by the vk toolchain.
Functions raise GhError on failure.  No direct GitHub API usage —
we leverage gh's existing auth.
"""

from __future__ import annotations

import contextvars
import os
import shlex
import subprocess
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar
from urllib.parse import quote

from fr.ghclient import HostRefusedError
from fr.labels import LabelDef

if TYPE_CHECKING:
    from fr.real_ghrestclient import RealGhRestClient

T = TypeVar("T")


def _rest() -> RealGhRestClient | None:
    """The REST-only client when `forge.api` is `rest` (spec 2026-10-07-cloud-triage
    §A, R3), else None: the helpers below that a GraphQL-backed `gh` verb serves
    check it once and delegate. Built per call with the host in scope, so a
    `host_scope` around the helper still applies."""
    from fr import forgeapi

    if forgeapi.resolve() != "rest":
        return None
    from fr.real_ghrestclient import RealGhRestClient

    return RealGhRestClient(host=_HOST.get())


def _records(value: Any) -> list[dict[str, object]]:
    return list(value)


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


class GhHostRefusedError(GhError, HostRefusedError):
    """The host trust gate refused a host gh is not logged into (spec
    2026-10-06-forge-remainder §4.E). A subclass so a soft-fail method can
    never mistake it for an ordinary forge miss: `RealGhClient` checks the
    gate before any method body runs (review p1-r1). `HostRefusedError` is
    the forge-neutral type `classify` reads it by (gh#1013)."""


GH_TIMEOUT_SECONDS = 120.0
"""How long one `gh` call may take before it is killed and fails as a transient
error. A stalled GraphQL call otherwise blocks its caller indefinitely: the wave
driver's loop once sat 16 minutes on a single `gh issue list` (gh#909)."""
GH_PAGE_SECONDS = 30.0
"""Added to a bulk list's bound per 100-record page past the first (gh#1025)."""
GH_LIST_TIMEOUT_CAP_SECONDS = 600.0
"""The most any one bulk list may take, however large its `--limit`."""


_HOST: contextvars.ContextVar[str | None] = contextvars.ContextVar("fr_gh_host", default=None)
"""The GitHub host the `gh` calls of the current context run against (spec
2026-10-06-forge-remainder §4.E). Only `host_scope` sets it — in fr, only
`RealGhClient(host=...)` — so a bare `fr.gh` call never sees a host."""


def _hosts_yml() -> Path:
    """gh's own `hosts.yml`: `$GH_CONFIG_DIR`, else `$XDG_CONFIG_HOME/gh`, else
    `~/.config/gh` — gh's lookup order."""
    if config_dir := os.environ.get("GH_CONFIG_DIR"):
        return Path(config_dir) / "hosts.yml"
    if xdg := os.environ.get("XDG_CONFIG_HOME"):
        return Path(xdg) / "gh" / "hosts.yml"
    return Path.home() / ".config" / "gh" / "hosts.yml"


def known_hosts() -> frozenset[str]:
    """The hosts gh is logged into — the top-level keys of its `hosts.yml`, the
    ones the operator ran `gh auth login` for (lowercased). A missing,
    unreadable or malformed file is the empty set: nothing is trusted."""
    import yaml

    try:
        data = yaml.safe_load(_hosts_yml().read_text())
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return frozenset()
    if not isinstance(data, dict):
        return frozenset()
    return frozenset(str(k).lower() for k in data)


def host_env() -> dict[str, str] | None:
    """The host overlay for a `gh` subprocess: None when no host is in scope
    (the SaaS path untouched), else `{"GH_HOST": host}` — what an injected
    `CommandRunner` is handed on top of its own environment (gh#1015).

    The ONE place the host trust gate is enforced, so every `gh` subprocess
    path inherits it (plan journal `p1-gh-host-trust-gate`). `GH_HOST` makes gh
    send `GH_ENTERPRISE_TOKEN` to that host, and the hosts fr threads come from
    PR/issue URLs and a cloned repo's committed `fr-profiles.yaml` — neither
    fully trusted. So a host gh is not logged into raises `GhError`, before any
    subprocess starts, and never falls back to github.com (#892's wrong-target
    write)."""
    host = _HOST.get()
    if host is None:
        return None
    if host.lower() not in known_hosts():
        raise GhHostRefusedError(
            f"GitHub host {host!r} is not one gh is logged into; run "
            f"`gh auth login --hostname {host}` (fr will not point gh, or its "
            "tokens, at an unknown host; a GH_ENTERPRISE_TOKEN alone does not "
            "count as a login)"
        )
    return {"GH_HOST": host}


def _env() -> dict[str, str] | None:
    """The full `env` for one of `fr.gh`'s own subprocesses: None (inherit) when
    no host is in scope, else a copy of `os.environ` plus `host_env()`."""
    overlay = host_env()
    return {**os.environ, **overlay} if overlay else None


@contextmanager
def host_scope(host: str | None) -> Iterator[None]:
    """Run the enclosed `gh` calls against `host` (None: gh's own resolution).
    The previous value is restored on exit, raise or not, so a host can never
    leak into a later call."""
    token = _HOST.set(host)
    try:
        yield
    finally:
        _HOST.reset(token)


def list_timeout(limit: int) -> float:
    """The bound for one bulk list of up to *limit* records (gh#1025): gh pages by
    100, so each page past the first gets `GH_PAGE_SECONDS` more, never past
    `GH_LIST_TIMEOUT_CAP_SECONDS` — still a bound, so a stalled list still fails."""
    pages = max(1, -(-limit // 100))
    return min(GH_TIMEOUT_SECONDS + (pages - 1) * GH_PAGE_SECONDS, GH_LIST_TIMEOUT_CAP_SECONDS)


def _bound(args: list[str]) -> float:
    """`GH_TIMEOUT_SECONDS`, or `list_timeout` for a call that pages (`--limit N`)."""
    if "--limit" in args:
        at = args.index("--limit") + 1
        if at < len(args) and args[at].isdigit():
            return list_timeout(int(args[at]))
    return GH_TIMEOUT_SECONDS


def _run_gh(args: list[str]) -> str:
    """Run a gh command and return stdout.  Raises GhError on failure, and on a
    call that outlives its bound (`_bound`; transient: `is_transient` is true)."""
    bound = _bound(args)
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=bound,
            env=_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise GhError(
            f"`{shlex.join(['gh', *args])}` timed out after {bound:g}s",
            stderr=f"timeout after {bound:g}s",
        ) from exc
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() if exc.stderr else f"gh exited with code {exc.returncode}"
        raise GhError(
            msg, stderr=exc.stderr or "", returncode=exc.returncode, stdout=exc.stdout or ""
        ) from exc
    return result.stdout.strip()


def view_pr_body(ref: str, *, cwd: Path | None = None) -> str:
    """The live body of pull request `ref` (a number, URL or branch), read
    with `gh pr view` from `cwd` (its repository). Raises GhError."""
    if (rest := _rest()) is not None:
        return rest.pr_body(ref, cwd=cwd or Path.cwd())
    try:
        done = subprocess.run(
            ["gh", "pr", "view", ref, "--json", "body", "--jq", ".body"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
            env=_env(),
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

    if (rest := _rest()) is not None:
        return dict(rest.view_issue_record(repo, number))
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
    if (rest := _rest()) is not None:
        rest.edit_issue_state(repo, number, state="CLOSED")
        return
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
    if (rest := _rest()) is not None:
        rest.edit_issue_labels(repo, issue_number, add=frozenset(add_labels), remove=frozenset())
        return
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
    if (rest := _rest()) is not None:
        return rest.view_issue_record(repo, number).get("state") == "CLOSED"
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

    if (rest := _rest()) is not None:
        return rest.list_labels(repo)
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
    exactly ``limit`` records (and so may be cut short) before filtering. Each record
    carries ``visibility`` lowercased when the forge gave it, so triage collect reads an
    org's visibility from the list rather than once per repo (cloud-triage §B, p3-r9).
    """
    import json

    if (rest := _rest()) is not None:
        listed = _records(rest.list_repos(owner, limit))
        return listed if include_archived else [r for r in listed if not r.get("isArchived")]
    out = _run_gh(
        [
            "repo",
            "list",
            owner,
            "--json",
            "name,isArchived,visibility",
            "--limit",
            str(limit),
        ]
    )
    repos: list[dict[str, object]] = json.loads(out) if out else []
    for r in repos:
        if isinstance(r.get("visibility"), str):
            r["visibility"] = str(r["visibility"]).lower()
    if include_archived:
        return repos
    return [r for r in repos if not r.get("isArchived", False)]


ISSUE_LIST_FIELDS = "number,title,labels,createdAt,updatedAt,url,body"
# `fr triage origins` alone needs how an issue ended; `stateReason` wants a newer gh, so no
# other issue-list verb asks for it.
ORIGINS_ISSUE_LIST_FIELDS = ISSUE_LIST_FIELDS + ",state,closedAt,stateReason"
# `author` and `isCrossRepository` are who opened a PR and whether from a fork: a batch
# PR is attributed by them, never by its head branch name alone (gh#936).
PR_LIST_FIELDS = (
    "number,title,state,isDraft,createdAt,mergedAt,url,headRefName,closingIssuesReferences,"
    "author,isCrossRepository"
)
OPEN_PR_LIST_FIELDS = (
    PR_LIST_FIELDS + ",files,statusCheckRollup,mergeable,mergeStateStatus,reviewDecision,headRefOid"
)


def list_issues(
    *, repo: str, state: str, limit: int, fields: str = ISSUE_LIST_FIELDS
) -> list[dict[str, object]]:
    """Return issues in *repo* via one bulk ``gh issue list``.

    ``--limit`` is always explicit: gh's default is 30, which would silently
    truncate any backlog past thirty issues.
    """
    import json

    if (rest := _rest()) is not None:
        return _records(rest.list_issues(repo, state, limit, fields))
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
            fields,
        ]
    )
    issues: list[dict[str, object]] = json.loads(out) if out else []
    return issues


def list_prs(*, repo: str, state: str, limit: int) -> list[dict[str, object]]:
    """Return PRs in *repo* via one bulk ``gh pr list`` (explicit ``--limit``)."""
    import json

    if (rest := _rest()) is not None:
        return _records(rest.list_prs(repo, state, limit))
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

    if (rest := _rest()) is not None:
        return _records(rest.list_open_prs(repo, limit))
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
    """Every PR (any state) whose head is *branch*: `PR_LIST_FIELDS` plus `headRefOid`
    and `files` (the wave driver attributes a merged archive PR by them)."""
    import json

    if (rest := _rest()) is not None:
        return _records(rest.list_prs_by_head(repo, branch)[:limit])
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
            PR_LIST_FIELDS + ",headRefOid,files",
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


def viewer_login() -> str:
    """The login of the user `gh` is authenticated as."""
    return _run_gh(["api", "user", "--jq", ".login"])


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


def classify(err: GhError) -> str:
    """`_classify_error`'s kinds for a `GhError`, by TYPE first: a host trust
    refusal is `unknown` (fail fast — never backed off, never retried) whatever
    its message says. Its message names the host, so by text a host called
    `git.timeout.example` read as transient (gh#1013). Only a raw gh failure
    falls through to the stderr text."""
    if isinstance(err, HostRefusedError):
        return "unknown"
    return _classify_error((err.stderr or "") + " " + str(err))


def is_transient(err: GhError) -> bool:
    """True if the error looks like a transient network/server failure
    that warrants retry. False for auth, 404, validation, and unknown
    errors (fail fast) — and, by type, for a host trust refusal (gh#1013)."""
    if isinstance(err, HostRefusedError):
        return False
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
