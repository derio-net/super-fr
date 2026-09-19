"""Backend identity — which git-forge CLI a repo talks to.

`detect_backend()` is the single place that answers "gh, glab, or tea for
this repo?" for the whole codebase (fr apply's CLI wiring, fr-vk's dispatch
bridge, the isolation lifecycle, and scaffold all resolve through this
instead of hardcoding gh). Resolution order:

1. `.devcontainer/fr-profiles.yaml`'s top-level `backend:` key, if present —
   authoritative. It's the only way to declare Gitea (no free SaaS-hostname
   default exists for it — self-hosting is the norm) or a self-hosted
   GitLab/GitHub Enterprise instance.
2. Else: `git remote get-url origin`'s hostname, matched against
   `DEFAULT_HOST_BACKENDS` (github.com / gitlab.com only).
3. Else: `"github"` — today's only behavior, preserved so a repo that
   configures nothing sees no change.

Two separate questions about the instance *hostname* are answered here,
and the split is load-bearing rather than cosmetic (gh-486, spec §4.D):

- `declared_host(repo_root)` — the raw `host:` key, and nothing inferred.
  An operator expectation, so `hostclient.client_for` may warn when fr
  cannot honour it for the resolved backend.
- `host_for(repo_root)` — what a forge CLI should actually be pointed at:
  the declared host, else the origin's hostname when it is not one of
  `DEFAULT_HOST_BACKENDS`, else None. A *derived* host is an inference,
  never an expectation, and must not be warned about: a GitHub Enterprise
  repo derives one for backend `github`, a configuration that works fine
  because `gh` resolves the same host itself.

See docs/superpowers/specs/2026-07-09-multi-backend-git-host-adapters-design.md
for the research behind this design (§1), and
docs/superpowers/specs/2026-09-19-gitlab-contents-ref-and-self-hosted-hosts-design.md
§4.C for the host-resolution fallback.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fr.isolation.types import profiles_config

HostBackend = Literal["github", "gitlab", "gitea"]

# Only the two hosts with a fixed, universally-recognized SaaS domain.
# Deliberately no "gitea.com" entry: unlike GitHub/GitLab, self-hosting is
# the norm for Gitea specifically, so even a gitea.com-hosted repo should
# name its backend explicitly rather than have it inferred — see
# test_gitea_requires_explicit_config.
DEFAULT_HOST_BACKENDS: dict[str, HostBackend] = {
    "github.com": "github",
    "gitlab.com": "gitlab",
}

# Shared with fr_vk._cardref (VK card-title tag) and fr_dispatch.prompt
# (dispatched-agent prompt wording) — lives here, not in fr_vk, since
# fr_dispatch depends only on `fr`, never on the fr_vk runner adapter
# (fr_dispatch is meant to be runner-agnostic; a future non-VK runner
# needs this map too). See docs/superpowers/specs/
# 2026-07-09-multi-backend-git-host-adapters-design.md §2/§7.
TAG_FOR_BACKEND: dict[HostBackend, str] = {"github": "gh", "gitlab": "gl", "gitea": "gt"}
BACKEND_FOR_TAG: dict[str, HostBackend] = {v: k for k, v in TAG_FOR_BACKEND.items()}

_REMOTE_HOST_RE = re.compile(r"^(?:[\w+.-]+://)?(?:[^@/]+@)?([^/:]+)")

# Warn-once guard for `detect_backend`'s unrecognized-origin-host fallback
# (gh-486 gap 2, spec §4.D) — module-level and keyed on the bare hostname,
# since `detect_backend` is called often (fr apply, isolation lifecycle,
# scaffold) and must not become chatty across repeated calls for the same
# repo/host.
_WARNED_UNKNOWN_HOSTS: set[str] = set()


def _origin_hostname(repo_root: Path) -> str | None:
    """Best-effort hostname from `git remote get-url origin`. None on any
    failure (no repo, no remote, git not found) — callers fall through."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    url = (result.stdout or "").strip()
    if not url:
        return None
    m = _REMOTE_HOST_RE.match(url)
    return m.group(1) if m else None


def backend_for_hostname(hostname: str | None) -> HostBackend:
    """Resolve a backend from a bare hostname alone — the plain heuristic
    tier of `detect_backend`, for contexts that only have a URL, not a
    `repo_root` to read explicit config from (e.g. fr-vk's PR-status
    poller, which may be watching cards across repos on different
    backends from one bridge process — see `fr_vk.pr_observe`). Falls
    back to "github" the same way `detect_backend` does when nothing
    else resolves.
    """
    if hostname and hostname in DEFAULT_HOST_BACKENDS:
        return DEFAULT_HOST_BACKENDS[hostname]
    return "github"


# A forge URL's PATH identifies the forge where its HOSTNAME cannot.
# `backend_for_hostname` knows two SaaS domains, so every self-hosted
# instance falls through to "github" — fine as a default for a repo that
# can declare `backend:`, useless for a bare URL, which is all the VK
# bridge has (gh-486 gap 2).
#
# Each pattern is ANCHORED on a route keyword followed by a complete
# numeric segment, and that anchoring is the whole correctness argument.
# A plain `"/merge_requests/" in path` test cannot tell a route from a
# NAME, so `github.com/owner/merge_requests/pull/5` — a real GitHub PR in
# a repo that happens to be called `merge_requests` — classified as
# GitLab, and `owner/pulls/pull/5` as Gitea. Both were found in review;
# both are unusual repo names, neither is absurd. Requiring `/<n>` after
# the keyword means a name only collides if it is ALSO followed by a bare
# number, and the ordering then resolves that: a real route later in the
# path still wins because the more specific forge patterns are tried
# first.
#
# Residual, accepted: a BRANCH named `merge_requests/12` inside a
# non-route URL (`/o/r/tree/merge_requests/12`) still reads as GitLab.
# These three call sites only ever receive PR/MR and Issue URLs, never a
# tree URL, so closing it would mean parsing forge route grammars — more
# machinery than the risk earns.
_URL_SHAPES: tuple[tuple[re.Pattern[str], HostBackend], ...] = (
    # /-/merge_requests/7 and pre-dash /merge_requests/7 alike
    (re.compile(r"/(?:-/)?merge_requests/\d+(?:/|$)"), "gitlab"),
    (re.compile(r"/-/issues/\d+(?:/|$)"), "gitlab"),
    (re.compile(r"/pulls/\d+(?:/|$)"), "gitea"),
    (re.compile(r"/pull/\d+(?:/|$)"), "github"),
)


def backend_for_url(url: str) -> HostBackend:
    """Resolve a backend from a forge URL: its path shape first, its
    hostname second.

    For `fr_vk.pr_observe`/`pr_state` and `fr_dispatch.prompt`, which hold
    a URL and no checkout, so `detect_backend`'s config tier is
    unavailable. A bare `/issues/N` is deliberately NOT a shape: it is
    both GitHub's and Gitea's, so it falls through to the hostname rather
    than being guessed — the same documented Gitea boundary as before.
    (GitLab's `/-/issues/N` IS unambiguous, thanks to the route infix.)
    See spec §4.C2 and `_URL_SHAPES` on why each pattern is anchored."""
    parsed = urlparse(url)
    for pattern, backend in _URL_SHAPES:
        if pattern.search(parsed.path):
            return backend
    return backend_for_hostname(parsed.hostname)


def detect_backend(repo_root: Path) -> HostBackend:
    """Resolve which git-forge backend `repo_root` talks to. See module
    docstring for the 3-tier resolution order. Never raises — a malformed
    or absent `.devcontainer/fr-profiles.yaml` and an unreadable git remote
    both fall through to the next tier rather than erroring."""
    try:
        config = profiles_config(repo_root)
    except Exception:  # noqa: BLE001 — malformed config must not crash detection
        config = {}
    explicit = config.get("backend")
    if explicit == "github":
        return "github"
    if explicit == "gitlab":
        return "gitlab"
    if explicit == "gitea":
        return "gitea"

    hostname = _origin_hostname(repo_root)
    if hostname and hostname not in DEFAULT_HOST_BACKENDS and hostname not in _WARNED_UNKNOWN_HOSTS:
        _WARNED_UNKNOWN_HOSTS.add(hostname)
        print(
            f"warning: origin host {hostname!r} is not a recognized forge; "
            'assuming backend "github". Declare it as `backend: gitlab` '
            "(or gitea) in .devcontainer/fr-profiles.yaml, or run "
            "`fr init scaffold --backend <b>`.",
            file=sys.stderr,
        )
    return backend_for_hostname(hostname)


def declared_host(repo_root: Path) -> str | None:
    """The `host:` key from `.devcontainer/fr-profiles.yaml`, and nothing
    inferred. An operator EXPECTATION, which is why
    `hostclient.client_for` warns when fr cannot honour it for the
    resolved backend — see spec §4.D. Use `host_for` to actually target
    an instance; use this only when the *provenance* matters."""
    try:
        config = profiles_config(repo_root)
    except Exception:  # noqa: BLE001 — same tolerance as detect_backend
        return None
    host = config.get("host")
    return host if isinstance(host, str) and host else None


def self_hosted_hostname(hostname: str | None) -> str | None:
    """The hostname, but only when it is NOT a recognized SaaS domain —
    else None. `github.com`/`gitlab.com` need no override, and naming one
    would make an ordinary repo look self-hosted. Shared by `host_for`
    (which has a checkout) and `fr_vk.pr_observe` (which has only a PR
    URL), so the rule cannot drift between them — see gh-486, spec §4.C."""
    if hostname and hostname not in DEFAULT_HOST_BACKENDS:
        return hostname
    return None


def host_for(repo_root: Path) -> str | None:
    """Which instance hostname this repo's forge CLI should talk to: the
    declared `host:`, else the origin's own hostname when it is not a
    recognized SaaS domain, else None.

    The fallback is what makes `backend: gitlab` sufficient on its own for
    a self-hosted repo (gh-486 gap 1): the host is already in the remote
    the operator has. `github.com`/`gitlab.com` return None so nothing
    changes for a SaaS repo — returning a host there would make every
    normal repo look self-hosted. Never raises, same as `declared_host`."""
    declared = declared_host(repo_root)
    if declared:
        return declared
    return self_hosted_hostname(_origin_hostname(repo_root))
