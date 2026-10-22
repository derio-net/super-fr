"""Whether this process runs inside an ops profile (spec 2026-10-22-fr-ops R6).

`fr ops status` runs anywhere and only warns outside one; `apply`, `attest` and
`seal` refuse, printing `refusal_route`. Container evidence is the shared helper
`fr.isolation.where.container_evidence` (also the edit gate's notion), injectable
for tests.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import Path

from fr.isolation.where import container_evidence

PROFILE_ENV = "FR_PROFILE"


def ops_profiles(repo_root: Path) -> list[str]:
    """Names of the profiles declared `ops: true` in `.devcontainer/fr-profiles.yaml`."""
    from fr.isolation.types import profiles_config

    try:
        profiles = (profiles_config(repo_root) or {}).get("profiles") or {}
    except Exception:  # noqa: BLE001 — an unreadable file declares nothing
        return []
    return [
        name
        for name, entry in profiles.items()
        if isinstance(entry, dict) and entry.get("ops") is True
    ]


def in_ops_profile(
    repo_root: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    evidence: Callable[[], bool] = container_evidence,
) -> bool:
    """`FR_PROFILE` names a profile declared `ops: true` AND container evidence exists."""
    name = (os.environ if env is None else env).get(PROFILE_ENV)
    if not name or not evidence():
        return False
    return name in ops_profiles(repo_root or Path.cwd())


def refusal_route(repo_root: Path, *, slug: str = "<slug>", base: str = "origin/main") -> str:
    """The ops-workspace route printed when a verb refuses outside an ops profile."""
    names = ops_profiles(repo_root)
    profile = names[0] if names else "<ops-profile>"
    branch = f"chore/ops-{slug}"
    return (
        "not inside an ops profile; run it in an ops workspace:\n"
        f"  fr isolation up --profile {profile} --branch {branch} --base {base}\n"
        f"  fr isolation exec --branch {branch} -- fr ops …"
    )
