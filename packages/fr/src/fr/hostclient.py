"""The single factory that turns "which backend" into "which client."

Every call site that used to hardcode `RealGhClient()` calls `client_for()`
instead — this is the seam that makes `fr apply`, the isolation lifecycle,
and the fr-vk dispatch bridge all work against GitLab/Gitea repos without
each one re-deriving backend detection itself. See docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md §3.
"""

from __future__ import annotations

from pathlib import Path

from fr import _hosts
from fr.ghclient import GhClient
from fr.real_ghclient import RealGhClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient


def client_for_backend(backend: _hosts.HostBackend, *, host: str | None = None) -> GhClient:
    """Return the `GhClient`-shaped adapter for an already-resolved
    backend. The shared dispatch table `client_for()` and any caller with
    its own backend-resolution path (e.g. `fr_vk.pr_observe`, which
    resolves from a bare PR URL's hostname via
    `fr._hosts.backend_for_hostname` rather than a local checkout) both
    go through this.

    `host` names a self-hosted instance. This function is deliberately
    PROVENANCE-BLIND: it never reads config and cannot tell a declared
    `host:` from one derived from a remote or a PR URL, which is exactly
    why `client_for` — not this — owns the warning about a host fr cannot
    honour (gh-486; spec §4.D). Only the GitLab adapter threads it; `gh`
    and `tea` resolve their own hosts (§1 non-goals)."""
    if backend == "gitlab":
        return RealGlabClient(host=host)
    if backend == "gitea":
        return RealTeaClient()
    return RealGhClient()


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
    """
    return client_for_backend(_hosts.detect_backend(repo_root), host=_hosts.host_for(repo_root))
