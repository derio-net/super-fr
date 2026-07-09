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


def client_for_backend(backend: _hosts.HostBackend) -> GhClient:
    """Return the `GhClient`-shaped adapter for an already-resolved
    backend. The shared dispatch table `client_for()` and any caller with
    its own backend-resolution path (e.g. `fr_vk.pr_observe`, which
    resolves from a bare PR URL's hostname via
    `fr._hosts.backend_for_hostname` rather than a local checkout) both
    go through this."""
    if backend == "gitlab":
        return RealGlabClient()
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
    """
    return client_for_backend(_hosts.detect_backend(repo_root))
