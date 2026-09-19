"""GitLab CLI (`glab`) subprocess wrappers.

Thin wrappers around ``glab`` commands, mirroring `fr.gh`'s shape exactly
(same function names/signatures where the operation maps 1:1, so the two
files diff cleanly). Functions raise GlabError on failure. No direct
GitLab API usage — we leverage glab's existing auth, same architecture as
`fr.gh` for GitHub (see docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md).

Concrete flag differences from `gh`, verified directly against the
installed `glab` binary's `--help` output (not assumed by analogy):
- `glab issue create` takes `--description`, not `--body`.
- `glab issue update <iid> --label X --unlabel Y` (not `--add-label`/
  `--remove-label`).
- `glab label create --color` wants a leading `#` (default `#428BCA`);
  `ensure_label` prepends it here — `LabelDef` itself stays bare-hex.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from typing import TypeVar

from fr.labels import LabelDef

T = TypeVar("T")


class GlabError(Exception):
    """Error from a glab CLI invocation."""

    def __init__(
        self, message: str, *, stderr: str = "", stdout: str = "", returncode: int = 0
    ) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.stdout = stdout
        self.returncode = returncode


def _run_glab(args: list[str]) -> str:
    """Run a glab command and return stdout. Raises GlabError on failure."""
    try:
        result = subprocess.run(
            ["glab", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        # glab splits an error across both streams: its own summary on
        # stderr, the API's JSON body on stdout. Keeping only stderr
        # turned "ref is missing, ref is empty" into a bare "glab: HTTP
        # 400" — the fault named, then forgotten (gh-486; spec §2.A).
        parts = [s for s in (exc.stderr.strip(), (exc.stdout or "").strip()) if s]
        msg = " — ".join(parts) or f"glab exited with code {exc.returncode}"
        raise GlabError(
            msg,
            stderr=exc.stderr or "",
            stdout=exc.stdout or "",
            returncode=exc.returncode,
        ) from exc
    return result.stdout.strip()


def create_issue(
    *,
    repo: str,
    title: str,
    body: str,
    labels: list[str],
) -> str:
    """Create a GitLab Issue and return its URL."""
    args = [
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        title,
        "--description",
        body,
    ]
    for label in labels:
        args.extend(["--label", label])
    return _run_glab(args)


def view_issue(repo: str, number: int) -> dict[str, object]:
    """Fetch an Issue's title, description, labels, state via `glab issue
    view --output json`."""
    import json

    out = _run_glab(["issue", "view", str(number), "--repo", repo, "--output", "json"])
    result: dict[str, object] = json.loads(out)
    return result


def close_issue(*, repo: str, number: int) -> None:
    """Close a GitLab Issue by IID."""
    _run_glab(["issue", "close", str(number), "--repo", repo])


def reopen_issue(*, repo: str, number: int) -> None:
    """Reopen a closed GitLab Issue by IID."""
    _run_glab(["issue", "reopen", str(number), "--repo", repo])


def edit_issue_body(*, repo: str, number: int, body: str) -> None:
    """Update the description of an existing Issue via `glab issue update
    --description` (glab's flag name for what gh calls `--body`)."""
    _run_glab(["issue", "update", str(number), "--repo", repo, "--description", body])


def swap_issue_labels(
    *,
    repo: str,
    number: int,
    add: list[str],
    remove: list[str],
) -> None:
    """Add and remove labels on an Issue in a single glab call.

    No-op if both lists are empty. Failure propagates as GlabError.
    """
    if not add and not remove:
        return
    args = ["issue", "update", str(number), "--repo", repo]
    for lbl in add:
        args.extend(["--label", lbl])
    for lbl in remove:
        args.extend(["--unlabel", lbl])
    _run_glab(args)


def ensure_label(
    *,
    repo: str,
    name: str,
    color: str = "ededed",
    description: str = "",
) -> None:
    """Create a label on the target repo.

    Unlike `gh label create --force`, `glab label create` has no
    documented idempotent-update flag — a pre-existing label name causes
    an error, which the caller (RealGlabClient.ensure_labels) tolerates
    (a label that already exists with the right shape is a no-op in
    effect; a real color/description drift is a rarer, acceptable gap
    versus GitHub's `--force` convenience, noted for Phase 9's manual
    verification).
    """
    args = [
        "label",
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
    _run_glab(args)


def ensure_labels(*, repo: str, labels: list[LabelDef]) -> None:
    """Ensure every label exists on the repo with the right color and
    description. First failure propagates (mirrors `fr.gh.ensure_labels`)."""
    for ld in labels:
        ensure_label(repo=repo, name=ld.name, color=ld.color, description=ld.description)


_TRANSIENT_PATTERNS = (
    "http 5",  # 500, 502, 503, 504, ...
    "no such host",
    "connection reset",
    "connection refused",
    "context deadline exceeded",
    "timeout",
)


def _haystack(err: GlabError) -> str:
    """Lowercase text to pattern-match glab error classification against.
    Shared by `is_transient` and `is_not_found` — each keeps its own
    pattern tuple and docstring; only the construction is common.
    Includes `stdout` (the API's JSON body, folded into the message by
    `_run_glab`) so a not-found signalled only in the body — with no
    "HTTP 404" on stderr — still classifies (gh-486; spec §2.A)."""
    return (err.stderr + " " + err.stdout + " " + str(err)).lower()


def is_transient(err: GlabError) -> bool:
    """True if the error looks like a transient network/server failure
    that warrants retry. False for auth, 404, validation, and unknown
    errors (fail fast). Patterns are glab's own stderr vocabulary
    (dial/net-style Go error text), distinct from gh's — see the module
    docstring and the design doc's capability matrix."""
    return any(p in _haystack(err) for p in _TRANSIENT_PATTERNS)


# glab's own not-found vocabulary, captured live 2026-09-19 (spec §2.A).
# BOTH markers are anchored deliberately: a bare `"404" in text` would
# match a PROBED PATH containing 404 and read a genuine 400 as "absent",
# which is the bug class this function exists to close. The
# `"message":"404 ` form only becomes reachable once T4 gives GlabError
# the stdout the API's body arrives on; it is listed now because the
# vocabulary is one table, not two.
_NOT_FOUND_PATTERNS = ("http 404", '"message":"404 ')


def is_not_found(err: GlabError) -> bool:
    """True when GitLab said the thing is absent, as opposed to saying
    the request was wrong or unauthorized.

    `file_exists` may translate ONLY this into `False`. Anything else is
    a protocol or auth fault and must propagate: a malformed request
    that reads as "not found" is indistinguishable from an absent file,
    which is how gh-486 turned a 400 into a wrong answer."""
    return any(p in _haystack(err) for p in _NOT_FOUND_PATTERNS)


def with_retry(
    op: Callable[[], T],
    *,
    max_attempts: int = 3,
    backoff_seconds: tuple[float, ...] = (1.0, 2.0, 4.0),
) -> T:
    """Run `op`; retry on transient GlabError with backoff. Mirrors
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
        except GlabError as exc:
            attempt += 1
            if attempt >= max_attempts or not is_transient(exc):
                raise
            time.sleep(backoff_seconds[attempt - 1])
