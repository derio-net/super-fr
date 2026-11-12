"""Whether Pages may publish the acceptance report (spec 2026-11-04 R21).

A Pages site is published only where it can be no more visible than the repo:
either the repo is public, or the forge says the site itself is access-controlled.
Everything else — Gitea, a forge that will not answer, an unexpected shape, no
`origin` — fails closed: no Pages, and the README badge points at the CI run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

CONTROLLED = "controlled"
"""The site is readable only by people who can read the repo."""
PUBLIC = "public"
"""The site is readable by anyone."""
UNKNOWN = "unknown"
"""The forge cannot say (Gitea, a failed read, an unexpected shape, no Pages site)."""


def from_github(raw: Any) -> str:
    """`GET /repos/{o}/{r}/pages`: `public` is whether anyone on the internet can read
    the site; false means only users with read access to the repository."""
    value = raw.get("public") if isinstance(raw, dict) else None
    if not isinstance(value, bool):
        return UNKNOWN
    return PUBLIC if value else CONTROLLED


def from_gitlab(raw: Any, *, access_control: bool) -> str:
    """The project's `pages_access_level` read with its `visibility` (GitLab Projects API
    and Pages access-control docs). `private` limits the site to project members, and
    `enabled` to everyone with access to the project, which is everyone on a public one;
    both hold only where the instance enforces Pages access control (`access_control`:
    gitlab.com always does; the API never proves it for a self-managed host). So:

    - `private` is CONTROLLED only with access control confirmed;
    - `enabled` is CONTROLLED only with it confirmed AND a private or internal project;
    - `public` is PUBLIC; everything else (`disabled`, a missing or odd value) is UNKNOWN,
      which fails closed."""
    if not isinstance(raw, dict):
        return UNKNOWN
    level, project = raw.get("pages_access_level"), raw.get("visibility")
    if level == "public":
        return PUBLIC
    if level == "private" and access_control:
        return CONTROLLED
    if level == "enabled" and access_control and project in ("private", "internal"):
        return CONTROLLED
    return UNKNOWN


def pages_allowed(root: Path, client: Any) -> tuple[bool, str]:
    """`(allowed, reason)` for publishing a Pages site from the repo at `root`.

    Allowed only when the forge proves it: a public repo, or access-controlled Pages.
    Any read error counts as unknown, which is not allowed."""
    from fr._hosts import origin_slug

    slug = origin_slug(root)
    if slug is None:
        return False, "no origin remote to read the repo's visibility from"
    visibility: str | None
    try:
        visibility = str(client.repo_visibility(slug)).lower()
    except Exception as exc:  # fail closed: any forge, auth or network failure
        visibility = None
        repo_note = f"the repo's visibility could not be read ({exc})"
    else:
        repo_note = f"the repo is {visibility}"
    if visibility == "public":
        return True, "the repo is public, so its Pages site is no wider than the repo"
    try:
        pages = client.pages_visibility(slug)
    except Exception as exc:
        pages = UNKNOWN
        pages_note = f"the Pages visibility could not be read ({exc})"
    else:
        pages_note = f"the Pages site is {pages}"
    if pages == CONTROLLED:
        return True, "the Pages site is access-controlled, so no wider than the repo"
    return False, (
        f"Pages are not published: {repo_note} and {pages_note}; "
        "fr publishes Pages only for a public repo or access-controlled Pages "
        "(visibility unknown fails closed)"
    )
