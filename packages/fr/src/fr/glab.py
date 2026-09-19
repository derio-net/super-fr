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

Every public helper takes a keyword-only `host: str | None = None` and
forwards it to `_run_glab`, which puts it in the child's `GITLAB_HOST`.
That is how a self-hosted instance is targeted; see `_run_glab` for why it
is an env var and not `--hostname`, and
docs/superpowers/specs/2026-09-19-gitlab-contents-ref-and-self-hosted-hosts-design.md
§4.C for the layer that supplies it.
"""

from __future__ import annotations

import os
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


def _run_glab(args: list[str], *, host: str | None = None) -> str:
    """Run a glab command and return stdout. Raises GlabError on failure.

    `host` targets a self-hosted instance by putting GITLAB_HOST in the
    CHILD's environment only — never `os.environ`, so a host resolved for
    one repo cannot leak into a call for another repo in the same process
    (gh-486; a bridge tick handles many repos per process).

    The env var is used rather than `--hostname` because only it is
    honoured by every glab subcommand: `glab api` accepts `--hostname`,
    `glab label create` does not, and `fr.glab` calls both (verified live
    against a self-hosted instance — spec §2.D). `host=None` passes
    `env=None`, so the child inherits this process's environment unchanged
    and glab's own resolution from the current git directory still
    applies."""
    env = {**os.environ, "GITLAB_HOST": host} if host else None
    try:
        result = subprocess.run(
            ["glab", *args],
            capture_output=True,
            text=True,
            check=True,
            env=env,
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
    host: str | None = None,
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
    return _run_glab(args, host=host)


def view_issue(repo: str, number: int, *, host: str | None = None) -> dict[str, object]:
    """Fetch an Issue's title, description, labels, state via `glab issue
    view --output json`."""
    import json

    out = _run_glab(["issue", "view", str(number), "--repo", repo, "--output", "json"], host=host)
    result: dict[str, object] = json.loads(out)
    return result


def close_issue(*, repo: str, number: int, host: str | None = None) -> None:
    """Close a GitLab Issue by IID."""
    _run_glab(["issue", "close", str(number), "--repo", repo], host=host)


def reopen_issue(*, repo: str, number: int, host: str | None = None) -> None:
    """Reopen a closed GitLab Issue by IID."""
    _run_glab(["issue", "reopen", str(number), "--repo", repo], host=host)


def edit_issue_body(*, repo: str, number: int, body: str, host: str | None = None) -> None:
    """Update the description of an existing Issue via `glab issue update
    --description` (glab's flag name for what gh calls `--body`)."""
    _run_glab(["issue", "update", str(number), "--repo", repo, "--description", body], host=host)


def swap_issue_labels(
    *,
    repo: str,
    number: int,
    add: list[str],
    remove: list[str],
    host: str | None = None,
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
    _run_glab(args, host=host)


def ensure_label(
    *,
    repo: str,
    name: str,
    color: str = "ededed",
    description: str = "",
    host: str | None = None,
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
    _run_glab(args, host=host)


def ensure_labels(*, repo: str, labels: list[LabelDef], host: str | None = None) -> None:
    """Ensure every label exists on the repo with the right color and
    description. First failure propagates (mirrors `fr.gh.ensure_labels`)."""
    for ld in labels:
        ensure_label(repo=repo, name=ld.name, color=ld.color, description=ld.description, host=host)


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

    `stdout` is read as well as `stderr`, and for anything `_run_glab`
    produces that is REDUNDANT: `_run_glab` already folds the body into
    the message, so `str(err)` carries it. The term earns its place only
    for a `GlabError` built directly with `stdout=` and no message —
    which today happens in tests alone. It is kept as the contract for
    any future construction site: put the body anywhere on the error and
    classification still sees it. Do not read the term as evidence that
    a body-only error reaches this function in production; it does not."""
    return (err.stderr + " " + err.stdout + " " + str(err)).lower()


def is_transient(err: GlabError) -> bool:
    """True if the error looks like a transient network/server failure
    that warrants retry. False for auth, 404, validation, and unknown
    errors (fail fast). Patterns are glab's own network-error vocabulary
    (dial/net-style Go error text), distinct from gh's — see the module
    docstring and the design doc's capability matrix.

    Since gh-486 this reads the API's response body too, not just
    stderr (`_haystack`). That is a wider input than the patterns were
    written against: a NON-transient error whose body happened to
    contain "timeout" or "http 5" would now be retried. No captured
    GitLab error body contains that vocabulary (spec §2.A), and a real
    gateway timeout SHOULD retry, so the widening is deliberate — but it
    is a widening, recorded here rather than discovered later."""
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
