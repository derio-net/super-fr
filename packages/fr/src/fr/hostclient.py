"""The single factory that turns "which backend" into "which client."

Every call site that used to hardcode `RealGhClient()` calls `client_for()`
instead — this is the seam that makes `fr apply`, the isolation lifecycle,
and the fr-vk dispatch bridge all work against GitLab/Gitea repos without
each one re-deriving backend detection itself. See docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md §3.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Literal, cast, get_args
from urllib.parse import urlparse

from fr import _hosts
from fr import gh as _gh
from fr.gh import GhError
from fr.ghclient import GhClient, HostRefusedError
from fr.glab import GlabError
from fr.real_ghclient import RealGhClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient
from fr.tea import TeaError

# What a `GhClient` adapter raises when the FORGE refuses or fails: one error
# class per backend CLI. A caller that collects per-item forge failures catches
# exactly these, so a programming error is never reported as a forge failure.
FORGE_ERRORS: tuple[type[Exception], ...] = (GhError, GlabError, TeaError)

ForgeErrorKind = Literal["rate_limit", "info", "warn", "unknown"]
_KINDS = frozenset(get_args(ForgeErrorKind))


def forge_error_kind(exc: BaseException) -> ForgeErrorKind:
    """Classify any forge error for retry / back-off (spec
    2026-10-06-forge-remainder §4.C): `rate_limit` (back off the whole tick),
    `info` (the target is gone), `warn` (transient) or `unknown`.

    A host trust refusal (`HostRefusedError`, any backend) is `unknown` by
    TYPE, before any text is read: its message names the host, and a host can
    be called anything (gh#1013). Otherwise a `GhError` is `fr.gh.classify`'s
    call, and a `GlabError` / `TeaError` gets the same text rules over its
    stderr and message, with GitLab's and Gitea's 429 counted as a rate limit
    beside GitHub's 403. Anything that is not a forge error is `unknown`."""
    if isinstance(exc, HostRefusedError):
        return "unknown"
    if isinstance(exc, GhError):
        kind = _gh.classify(exc)
        return cast("ForgeErrorKind", kind) if kind in _KINDS else "unknown"
    if not isinstance(exc, (GlabError, TeaError)):
        return "unknown"
    text = ((exc.stderr or "") + " " + str(exc)).lower()
    if ("403" in text or "429" in text) and "rate limit" in text:
        return "rate_limit"
    if "404" in text or "not found" in text:
        return "info"
    if any(pat in text for pat in _gh._TRANSIENT_PATTERNS):
        return "warn"
    return "unknown"


# The command fr names when it tells an agent to open, edit or ready a PR,
# per backend (gh#742: a refusal that says `gh pr create` on a GitLab
# checkout sends the agent to a CLI that cannot help). `{body}` is a file
# holding the body and `{ref}` the PR. Each template was checked against its
# CLI's own `--help`: glab and tea take the description as a value, not a
# file, and tea's `--draft`/`--ready` are its WIP-title-prefix toggles.
PR_COMMANDS: dict[_hosts.HostBackend, dict[str, str]] = {
    "github": {
        "create": "gh pr create --draft --body-file {body}",
        "edit": "gh pr edit {ref} --body-file {body}",
        "ready": "gh pr ready {ref}",
        "fill": "gh pr create --fill",
    },
    "gitlab": {
        "create": 'glab mr create --draft --description "$(cat {body})"',
        "edit": 'glab mr update {ref} --description "$(cat {body})"',
        "ready": "glab mr update {ref} --ready",
        "fill": "glab mr create --fill --yes",
    },
    "gitea": {
        "create": 'tea pulls create --draft --description "$(cat {body})"',
        "edit": 'tea pulls edit {ref} --description "$(cat {body})"',
        "ready": "tea pulls edit {ref} --ready",
        "fill": 'tea pulls create --title "<title>"',
    },
}


_TRAILING_NUMBER = re.compile(r"^https?://.*/(\d+)/?$")  # a URL only: `fix/742` is a branch


def pr_command(repo_root: Path, op: str, **fields: str) -> str:
    """The `op` (create | edit | ready | fill) command for `repo_root`'s forge,
    with `fields` filled in — see `PR_COMMANDS`. `glab mr update` and
    `tea pulls edit` take no URL, so there a PR URL `ref` is reduced to its
    number, which both resolve against the checkout they run in."""
    backend = _hosts.detect_backend(repo_root)
    ref = fields.get("ref")
    if backend != "github" and ref and (m := _TRAILING_NUMBER.search(ref)):
        fields = {**fields, "ref": m.group(1)}
    return PR_COMMANDS[backend][op].format(**fields)


# Warn-once guard for a DECLARED host fr cannot thread to the resolved
# backend (gh-486, spec §4.D) — keyed on (host, backend) so a repo that
# later changes backend gets a fresh warning. Lives here, not in `_hosts`,
# and is deliberately NOT shared with `_hosts._WARNED_UNKNOWN_HOSTS` (see
# plan journal no-refactor-because P5.T2): the two warnings key on
# different things, and coupling them would put hostclient's provenance
# rule inside `_hosts`, undoing the split spec §4.D introduced.
_WARNED_DECLARED_HOSTS: set[tuple[str, str]] = set()


def client_for_backend(backend: _hosts.HostBackend, *, host: str | None = None) -> GhClient:
    """Return the `GhClient`-shaped adapter for an already-resolved
    backend. The shared dispatch table `client_for()` and any caller with
    its own backend-resolution path (e.g. `fr_vk.pr_observe`, which
    resolves from a bare PR URL via `fr._hosts.backend_for_url` rather
    than a local checkout) both go through this.

    `host` names a self-hosted instance. This function is deliberately
    PROVENANCE-BLIND: it never reads config and cannot tell a declared
    `host:` from one derived from a remote or a PR URL, which is exactly
    why `client_for` — not this — owns the warning about a host fr cannot
    honour (gh-486; spec §4.D). The GitLab adapter threads it to `glab`,
    the GitHub one as `GH_HOST` (spec 2026-10-06-forge-remainder §4.E);
    `tea` still resolves its own host."""
    if backend == "gitlab":
        # gitlab.com likewise: never a GITLAB_HOST, so a SaaS repo needs no
        # glab config login past the trust gate (gh#1014).
        return RealGlabClient(host=_hosts.self_hosted_hostname(host))
    if backend == "gitea":
        return RealTeaClient()
    # A SaaS host (github.com) is gh's own default, never a GH_HOST: threading
    # it would demand a hosts.yml login that token-only CI does not have
    # (review p1-r2).
    return RealGhClient(host=_hosts.self_hosted_hostname(host))


def client_for_url(url: str) -> GhClient:
    """The client for the forge AND instance *url* lives on — the backend from
    the URL's path shape (else its hostname), and a host only when it is not a
    recognized SaaS domain (spec 2026-10-06-forge-remainder §4.D). For callers
    holding a URL and no checkout: `fr_vk.pr_state` and the triage batch verbs.

    A self-hosted GitLab URL with no MR path shape still reads as github
    here; triage facts are GitHub-only, so it cannot arise from them."""
    return client_for_backend(
        _hosts.backend_for_url(url),
        host=_hosts.self_hosted_hostname(urlparse(url).hostname),
    )


def client_for(repo_root: Path) -> GhClient:
    """Return the `GhClient`-shaped adapter for the repo checked out at
    `repo_root`, resolved via `fr._hosts.detect_backend`.

    Takes a local checkout path, not a bare `owner/repo` string: backend
    detection reads `repo_root`'s `.devcontainer/fr-profiles.yaml` and git
    remote, which requires being physically in that checkout. This means
    a cross-repo plan whose phase targets a DIFFERENT repo/backend than
    `repo_root` isn't resolved correctly by this call alone — a known,
    narrow scope limit (see the design doc's non-goals) rather than a
    silently-wrong guess: today's callers all resolve `repo_root` as
    `Path.cwd()`, matching the existing single-repo assumption `fr apply`
    already made before this factory existed.

    Being the only layer that HAS a `repo_root`, this is also the only one
    that can resolve a self-hosted instance hostname at all — and the only
    one that can tell a declared `host:` from one derived from the origin
    remote (`_hosts.declared_host` vs `_hosts.host_for`). That distinction
    is what spec §4.D's warning rests on, so it must stay here rather than
    move down into `client_for_backend`.

    GitHub is given only the DECLARED host (spec 2026-10-06-forge-remainder
    §4.E): inside a checkout `gh` infers the host from the remote itself, and
    a derived origin host may be an SSH alias, which must never become
    `GH_HOST`. GitLab keeps the derived host too. Only Gitea, which threads
    no host at all, still warns about a declared one.
    """
    backend = _hosts.detect_backend(repo_root)
    declared = _hosts.declared_host(repo_root)
    if declared and backend == "gitea" and (declared, backend) not in _WARNED_DECLARED_HOSTS:
        _WARNED_DECLARED_HOSTS.add((declared, backend))
        print(
            f"warning: host {declared!r} is declared in "
            ".devcontainer/fr-profiles.yaml but fr does not thread a host "
            f'to backend "{backend}" — the CLI\'s own host resolution '
            "applies instead. See gh-486.",
            file=sys.stderr,
        )
    if backend == "github":
        return client_for_backend(backend, host=declared)
    return client_for_backend(backend, host=_hosts.host_for(repo_root))
