"""The services `fr init scaffold` writes (spec 2026-09-28-fr-profiles-services
§3.C, R8): `--ci` / `--tracking` values, `auto` detection, and refusal — never
a guess — when detection is inconclusive.

Detection here is stricter than the 1 -> 2 migration's, which must always
produce a value: the migration reads fr's own acceptance scaffold as "no CI",
this reads it as inconclusive, because an operator is present to ask.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from fr.services.model import (
    CI_FOR_FORGE,
    CI_TYPES,
    DEFERRED_TYPES,
    FOLLOW_UP,
    FORGE_TYPES,
    TRACKING_TYPES,
    CiService,
    ForgeService,
    ServicesError,
    TrackingService,
    validate_services,
)

AUTO = "auto"


def issues_enabled_for(repo_root: Path, forge_type: str, host: str | None) -> bool | None:
    """Ask the forge whether issues are on for `repo_root`'s origin project.
    None — unknown — on every failure, and always for tea."""
    from fr._hosts import origin_slug
    from fr.hostclient import client_for_backend

    slug = origin_slug(repo_root)
    if slug is None or forge_type not in FORGE_TYPES:
        return None
    return client_for_backend(forge_type, host=host).issues_enabled(slug)  # type: ignore[arg-type]


def _check_type(service: str, value: str, allowed: tuple[str, ...], flag: str) -> None:
    if value in DEFERRED_TYPES:
        raise ServicesError(f"{flag} {value!r} is not supported yet — it arrives with {FOLLOW_UP}")
    if value not in (*allowed, AUTO):
        raise ServicesError(f"{flag} must be one of {', '.join((*allowed, AUTO))}; got {value!r}")


def resolve_init_services(
    repo_root: Path,
    existing: dict[str, Any],
    *,
    backend: str | None,
    host: str | None,
    ci: str = AUTO,
    tracking: str = AUTO,
) -> dict[str, dict[str, str]]:
    """The `forge` / `ci` / `tracking` blocks `fr init scaffold` writes.

    `existing` is the parsed profiles file (already version 2 — the caller
    migrates first). A block already declared there is kept unless its own
    flag is given explicitly; an undeclared forge stays undeclared unless
    `--backend`/`--host` name it or the origin is a recognised forge.
    Raises `ServicesError` naming the flag to pass when `auto` cannot decide.
    """
    from fr.artifacts.profiles_services import v1_services
    from fr.services.detect import detect_ci

    _check_type("ci", ci, CI_TYPES, "--ci")
    _check_type("tracking", tracking, TRACKING_TYPES, "--tracking")

    forge: dict[str, str] | None
    if backend is not None or host is not None:
        old = existing.get("forge")
        old_type = old.get("type") if isinstance(old, dict) else None
        forge = {"type": backend or old_type or "github"}
        if host:
            forge["host"] = host
    elif isinstance(existing.get("forge"), dict):
        forge = {str(k): str(v) for k, v in existing["forge"].items()}
    else:
        forge = v1_services(repo_root, None, None).get("forge")
    forge_type = forge["type"] if forge else "github"
    if forge_type not in FORGE_TYPES:
        raise ServicesError(f"forge type {forge_type!r} is not one of {', '.join(FORGE_TYPES)}")
    forge_host = forge.get("host") if forge else None

    def kept(name: str) -> dict[str, str] | None:
        block = existing.get(name)
        return {str(k): str(v) for k, v in block.items()} if isinstance(block, dict) else None

    ci_block: dict[str, str] | None
    if ci != AUTO:
        ci_block = {"type": ci}
    elif (ci_block := kept("ci")) is None:
        presence = detect_ci(repo_root, forge_type)
        if presence == "fr-only":
            raise ServicesError(
                "cannot tell whether this repo has CI: its only CI config is fr's own "
                "acceptance pipeline — pass `--ci none` or `--ci "
                f"{CI_FOR_FORGE[forge_type]}`"
            )
        ci_block = {"type": CI_FOR_FORGE[forge_type] if presence == "real" else "none"}

    tracking_block: dict[str, str] | None
    if tracking != AUTO:
        tracking_block = {"type": tracking}
    elif (tracking_block := kept("tracking")) is None:
        enabled = issues_enabled_for(repo_root, forge_type, forge_host)
        if enabled is None:
            raise ServicesError(
                "cannot tell whether the forge has issues enabled — pass "
                f"`--tracking none` or `--tracking {forge_type}`"
            )
        tracking_block = {"type": forge_type if enabled else "none"}

    try:
        validate_services(
            ForgeService(**(forge or {"type": forge_type})),
            CiService(**ci_block),
            TrackingService(**tracking_block),
        )
    except (ServicesError, ValidationError) as e:
        raise ServicesError(str(e)) from e
    out: dict[str, dict[str, str]] = {}
    if forge:
        out["forge"] = forge
    out["ci"] = ci_block
    out["tracking"] = tracking_block
    return out
