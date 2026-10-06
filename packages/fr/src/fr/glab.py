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

import logging
import os
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from fr.ghclient import HostRefusedError
from fr.labels import LabelDef

T = TypeVar("T")

logger = logging.getLogger(__name__)


class GlabError(Exception):
    """Error from a glab CLI invocation."""

    def __init__(
        self, message: str, *, stderr: str = "", stdout: str = "", returncode: int = 0
    ) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.stdout = stdout
        self.returncode = returncode


class GlabHostRefusedError(GlabError, HostRefusedError):
    """The host trust gate refused a host glab is not logged into (gh#1014) —
    `fr.gh.GhHostRefusedError`'s GitLab twin. A `GlabError` so existing
    handlers see it; `RealGlabClient` checks the gate before any method body
    runs, so a soft-fail method can never read it as "no MR" / "no file"."""


def _config_yml() -> Path | None:
    """The config file glab itself reads (probed against glab 1.89):
    `$GLAB_CONFIG_DIR/config.yml` alone when that is set; otherwise the FIRST
    of `~/.config/glab-cli/config.yml` and `$XDG_CONFIG_HOME/glab-cli/
    config.yml` that exists — glab warns about the second and ignores it. Not
    gh's order: there XDG comes first. None when glab would find no file."""
    if config_dir := os.environ.get("GLAB_CONFIG_DIR"):
        return Path(config_dir) / "config.yml"
    candidates = [Path.home() / ".config" / "glab-cli" / "config.yml"]
    if xdg := os.environ.get("XDG_CONFIG_HOME"):
        candidates.append(Path(xdg) / "glab-cli" / "config.yml")
    return next((p for p in candidates if p.is_file()), None)


def known_hosts() -> frozenset[str]:
    """The hosts glab is configured for — the keys of its config's `hosts:`
    mapping (lowercased). `glab auth login` writes one, but so does `glab
    config set --host`, and glab seeds a token-less `gitlab.com`: a key is an
    OPERATOR's choice to point glab there, never a cloned repo's, which is
    what the gate needs. A missing,
    unreadable or malformed file is the empty set: nothing is trusted."""
    import yaml

    path = _config_yml()
    if path is None:
        return frozenset()
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return frozenset()
    hosts = data.get("hosts") if isinstance(data, dict) else None
    if not isinstance(hosts, dict):
        return frozenset()
    return frozenset(str(k).lower() for k in hosts)


def host_env(host: str | None) -> dict[str, str] | None:
    """The host overlay for a `glab` subprocess: None for no host (glab's own
    resolution), else `{"GITLAB_HOST": host}`.

    The ONE place the GitLab host trust gate is enforced (gh#1014), as
    `fr.gh.host_env` is for gh. glab sends `GITLAB_TOKEN` to whichever host
    it targets, and the hosts fr threads come from MR URLs and a cloned repo's
    committed `fr-profiles.yaml` — neither fully trusted. So a host glab is not
    logged into raises, before any subprocess starts."""
    if not host:  # "" is no host, as in `_run_glab`
        return None
    if host.lower() not in known_hosts():
        raise GlabHostRefusedError(
            f"GitLab host {host!r} is not one glab is logged into; run "
            f"`glab auth login --hostname {host}` (fr will not point glab, or a "
            "GITLAB_TOKEN, at an unknown host; a GITLAB_TOKEN alone does not "
            "count as a login)"
        )
    return {"GITLAB_HOST": host}


# The flags fr itself writes, every one of them value-taking. Anything else
# that starts with `-` is refused: see `check_argv`.
_FLAGS = frozenset(
    {"--repo", "--title", "--description", "--label", "--unlabel", "--message",
     "--name", "--color", "--output", "--jq", "-F"}
)  # fmt: skip

# A GitLab project path: two or more segments, each starting with a letter,
# digit or `_` (GitLab's own rule) — no spaces, no `:` or `@`, no leading `-`.
_REPO_PATH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)+")


def check_argv(args: list[str], host: str | None) -> None:
    """Refuse, before any process starts, a glab argv fr itself never writes
    (gh#1014 review). glab follows a host carried by an ARGUMENT whatever
    GITLAB_HOST says — probed live against glab 1.89: a URL or `user@host:`
    remote as the repo, in any flag spelling (`--repo=`, `-R`, `-Rv`, `-wRv`);
    a repo path led by a host glab is configured for, even one with a space
    in front (glab trims it); a positional value it parses as a flag (a
    branch `-R<url>`); a full-URL `api` endpoint.

    A deny-list of those shapes mirrors glab's parser and loses to the next
    corner of it, which happened twice. So this is an ALLOW-list of what fr
    writes, and needs no model of glab's parser:

    - a token starting with `-` is one of fr's own value-taking `_FLAGS`, or
      the value right after one (glab consumes a value as a value whatever it
      looks like — a body may say anything);
    - a `--repo` value is a strict GitLab path (`_REPO_PATH`) whose first
      segment is not a host glab knows: its config's, gitlab.com, the
      threaded host (compared lowercased; glab is case-sensitive, so this
      refuses more, never less);
    - an `api` endpoint starts with `projects/`."""
    if args[:1] == ["api"] and not (len(args) > 1 and args[1].startswith("projects/")):
        raise GlabHostRefusedError(
            f"glab api endpoint {args[1:2]!r} is not a `projects/` path fr writes; "
            "fr points glab at a host only through GITLAB_HOST"
        )
    known: frozenset[str] | None = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in _FLAGS:
            value = args[i + 1] if i + 1 < len(args) else ""
            if arg == "--repo":
                if known is None:
                    known = known_hosts() | {"gitlab.com"} | ({host.lower()} if host else set())
                if not _REPO_PATH.fullmatch(value) or value.split("/", 1)[0].lower() in known:
                    raise GlabHostRefusedError(
                        f"glab --repo {value!r} is not a plain GitLab path, or names its own "
                        "host; fr points glab at a host only through GITLAB_HOST, where the "
                        "trust gate checks it"
                    )
            i += 2
            continue
        if arg.startswith("-"):
            raise GlabHostRefusedError(
                f"glab argument {arg!r} is not a flag fr writes, and glab would parse it "
                "as one (a flag can name its own host); refused"
            )
        i += 1


def _run_glab(args: list[str], *, host: str | None = None, cwd: Path | None = None) -> str:
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
    applies. `cwd` picks that git directory for a call that names no
    `--repo` (gh#742); `None` keeps this process's. A host glab is not logged
    into is refused first (`host_env`, gh#1014), and so is an argument that
    would make glab pick a host of its own (`check_argv`)."""
    check_argv(args, host)
    overlay = host_env(host)
    env = {**os.environ, **overlay} if overlay else None
    try:
        result = subprocess.run(
            ["glab", *args],
            capture_output=True,
            text=True,
            check=True,
            env=env,
            cwd=cwd,
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
    idempotent-update flag, so a pre-existing label name raises. That is
    tolerated by `ensure_labels` below, via `is_already_exists` — NOT by
    `RealGlabClient.ensure_labels`, which this docstring used to name and
    which never did it. Colour/description drift on an existing label is
    left uncorrected; see `ensure_labels` for that trade.
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
    """Ensure every label exists on the repo.

    An ALREADY-EXISTS refusal is skipped and the remaining labels are still
    ensured; any other failure propagates (mirroring `fr.gh.ensure_labels`,
    which never sees this case because `gh label create --force` updates in
    place and `glab` has no equivalent).

    This tolerance is what `ensure_label`'s docstring has claimed since the
    multi-backend design landed, and it was never implemented: the first
    pre-existing label raised, and because label ensure runs before the Issue
    writes, the whole `fr apply` aborted. So a GitLab plan could be applied
    exactly once and never converge — found by gh-486's live walk, not by any
    test, because every test mocked the failure away.

    What it knowingly gives up: a label whose colour or description has DRIFTED
    is left as-is rather than corrected, since glab offers no update-in-place.
    That was already recorded as an accepted gap versus GitHub; it is now
    accepted here, in the function that acts on it, instead of one layer away.
    """
    for ld in labels:
        try:
            ensure_label(
                repo=repo, name=ld.name, color=ld.color, description=ld.description, host=host
            )
        except GlabError as exc:
            if is_already_exists(exc):
                # DEBUG, not a warning: on any re-apply EVERY label already
                # exists, so warning here would print once per label on every
                # run and train the operator to ignore it. A skip still leaves
                # a trail, so a false positive (see `is_already_exists`) is
                # diagnosable rather than invisible.
                logger.debug("glab: label %r already exists on %s — skipping", ld.name, repo)
                continue
            raise


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
    raw = err.stderr + " " + err.stdout + " " + str(err)
    # Whitespace is COLLAPSED, not merely lowercased: glab renders some errors
    # through rich, which line-wraps them to the console width and so can split
    # a phrase mid-match — the live 409 arrived as "Label already\n  exists",
    # where a plain `"already exists" in text` finds nothing. Wrapping also
    # depends on terminal width, so without this a predicate could pass in CI
    # and fail on an operator's machine (the same mechanism behind the
    # width-sensitive failures in tests/unit/test_run_workspace.py). Collapsing
    # hardens is_not_found and is_transient against the same trap.
    return " ".join(raw.split()).lower()


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
    is a widening, recorded here rather than discovered later.

    A host trust refusal is never transient, by TYPE: its message names the
    host, and a host can be called anything (gh#1013)."""
    if isinstance(err, HostRefusedError):
        return False
    return any(p in _haystack(err) for p in _TRANSIENT_PATTERNS)


def is_already_exists(err: GlabError) -> bool:
    """True when GitLab refused because the thing is already there.

    `glab label create` has no `--force` (gh's idempotent-update flag), so
    re-ensuring an existing label 409s, and `ensure_labels` treats that as a
    no-op — see its docstring for what that knowingly gives up.

    The phrase alone is enough, and is reachable only because `_haystack`
    collapses whitespace: real output arrives rich-wrapped as
    `Label already\n  exists`. A bare 409 is NOT enough on its own and is
    deliberately paired with the API's `{message:` envelope. Review called
    the unpaired form out, and the reason it matters is the asymmetry: a
    match here makes `ensure_labels` skip SILENTLY, so a false positive is a
    label that was never created and no error to say so — strictly less
    discoverable than the loud abort this replaced. Pairing keeps a stray
    gateway or proxy 409 from being read as "already there".

    Like `is_transient` and `is_not_found`, this reads stdout as well as
    stderr, which is a wider surface than the phrases were written against.
    That widening is deliberate and recorded rather than discovered.
    """
    text = _haystack(err)
    if "already exists" in text:
        return True
    return " 409 " in text and "{message:" in text


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
    which is how gh-486 turned a 400 into a wrong answer.

    Reads stdout as well as stderr via `_haystack`, which is a wider
    surface than these patterns were written against — the same deliberate,
    recorded widening `is_transient` carries. A host trust refusal is never
    "absent", by type (gh#1013)."""
    if isinstance(err, HostRefusedError):
        return False
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
