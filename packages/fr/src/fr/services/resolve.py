"""Resolution of the forge / ci / tracking services (spec
2026-09-28-fr-profiles-services §3.B).

`resolve_services(repo_root)` is the only reader of the three services;
`fr.isolation.types.profiles_config` stays the raw reader it is. Per service:

1. **forge** — the declared `forge:` block; else, for a version-1 file, its
   flat `backend:`/`host:` (`legacy`); else the origin remote's hostname, with
   the `github` fallback (`default`).
2. **ci** — declared; else, for a version-1 file, the migration's own offline
   detection (fr's scaffold discounted, `legacy`), so `fr services` shows the
   same value before and after the migration; else the forge's own pipeline
   type if `fr.acceptance.ci.ci_config` finds a CI config, else `none`
   (`default` — #787's raw probe, unchanged).
3. **tracking** — declared, else the forge's own type.
4. **host** — declared, else the forge host when the type is the forge's own;
   any other type with no host is refused (`validate_services`).

A version-1 file is still READ, through the frozen `ProfilesV1`: the read-only
commands are exempt from the migration gate and must keep working on an
unmigrated repo.

`lenient=True` is for the forge consumers in `fr._hosts`, which have always
promised never to raise: an unreadable file is treated as absent and an
invalid declaration falls back to the next tier instead of refusing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from fr._hosts import HostBackend, backend_for_hostname, origin_hostname, self_hosted_hostname
from fr.acceptance.ci import ci_config
from fr.isolation.types import profiles_config
from fr.services.detect import detect_ci
from fr.services.legacy import ProfilesV1
from fr.services.model import (
    CI_FOR_FORGE,
    FORGE_TYPES,
    CiService,
    ForgeService,
    ResolvedService,
    Services,
    ServicesError,
    Source,
    TrackingService,
    is_native,
    validate_services,
)

SERVICE_KEYS: tuple[str, ...] = ("forge", "ci", "tracking")


def is_version_two(config: dict[str, Any]) -> bool:
    """A file is version 2 once it carries a stamp past 1 or any service block."""
    stamp = config.get("schema_version")
    if isinstance(stamp, int) and stamp >= 2:
        return True
    return any(key in config for key in SERVICE_KEYS)


def _read_config(repo_root: Path, *, lenient: bool) -> dict[str, Any] | None:
    """The raw file as a mapping, or None when there is no file."""
    if not (repo_root / ".devcontainer" / "fr-profiles.yaml").is_file():
        return None
    try:
        config = profiles_config(repo_root)
    except (OSError, yaml.YAMLError) as exc:
        if lenient:
            return None
        raise ServicesError(f"cannot read .devcontainer/fr-profiles.yaml: {exc}") from exc
    if not isinstance(config, dict):
        if lenient:
            return None
        raise ServicesError(".devcontainer/fr-profiles.yaml is not a mapping")
    return config


def _refusal(exc: ValidationError, where: str) -> ServicesError:
    reasons = "; ".join(str(err["msg"]).removeprefix("Value error, ") for err in exc.errors())
    return ServicesError(f".devcontainer/fr-profiles.yaml {where}: {reasons}")


def _declared(config: dict[str, Any], key: str, model: type[Any], *, lenient: bool) -> Any | None:
    """The declared `key:` block validated through `model`, or None when it is
    absent (or, leniently, invalid)."""
    if key not in config:
        return None
    try:
        return model.model_validate(config[key])
    except ValidationError as exc:
        if lenient:
            return None
        raise _refusal(exc, f"`{key}:`") from exc


def _legacy_v1(config: dict[str, Any], *, lenient: bool) -> ProfilesV1:
    try:
        return ProfilesV1.model_validate(config)
    except ValidationError as exc:
        if not lenient:
            raise _refusal(exc, "(version 1)") from exc
        backend = config.get("backend")
        host = config.get("host")
        return ProfilesV1(
            backend=backend if backend in FORGE_TYPES else None,
            host=host if isinstance(host, str) and host else None,
        )


def _forge(repo_root: Path, config: dict[str, Any] | None, *, lenient: bool) -> ResolvedService:
    origin = origin_hostname(repo_root)
    inferred_type: str = backend_for_hostname(origin)
    inferred_host = self_hosted_hostname(origin)
    if config is None:
        return ResolvedService(inferred_type, inferred_host, "default", _src(inferred_host))
    if is_version_two(config):
        declared = _declared(config, "forge", ForgeService, lenient=lenient)
        if declared is None:
            return ResolvedService(inferred_type, inferred_host, "default", _src(inferred_host))
        if declared.host:
            return ResolvedService(declared.type, declared.host, "declared", "declared")
        return ResolvedService(declared.type, inferred_host, "declared", _src(inferred_host))
    v1 = _legacy_v1(config, lenient=lenient)
    type_, type_source = (v1.backend, "legacy") if v1.backend else (inferred_type, "default")
    if v1.host:
        return ResolvedService(type_, v1.host, cast(Source, type_source), "legacy")
    return ResolvedService(type_, inferred_host, cast(Source, type_source), _src(inferred_host))


def _src(host: str | None) -> Source | None:
    return "default" if host else None


def _with_host(
    service: str, type_: str, host: str | None, source: Source, forge: ResolvedService
) -> ResolvedService:
    """Fill a service's host: declared, else the forge's for a native type."""
    if host:
        return ResolvedService(type_, host, source, source)
    if type_ != "none" and is_native(service, type_, forge.type):
        return ResolvedService(type_, forge.host, source, _src(forge.host))
    return ResolvedService(type_, None, source, None)


def _ci(
    repo_root: Path, config: dict[str, Any] | None, forge: ResolvedService, *, lenient: bool
) -> ResolvedService:
    own = CI_FOR_FORGE[forge.type]
    if config is not None and is_version_two(config):
        declared = _declared(config, "ci", CiService, lenient=lenient)
        if declared is not None:
            return _with_host("ci", declared.type, declared.host, "declared", forge)
    elif config is not None:
        presence = detect_ci(repo_root, forge.type)
        return _with_host("ci", own if presence == "real" else "none", None, "legacy", forge)
    found = ci_config(repo_root, cast(HostBackend, forge.type))
    return _with_host("ci", own if found else "none", None, "default", forge)


def _tracking(
    config: dict[str, Any] | None, forge: ResolvedService, *, lenient: bool
) -> ResolvedService:
    if config is not None and is_version_two(config):
        declared = _declared(config, "tracking", TrackingService, lenient=lenient)
        if declared is not None:
            return _with_host("tracking", declared.type, declared.host, "declared", forge)
    return _with_host("tracking", forge.type, None, "default", forge)


def resolve_services(repo_root: Path, *, lenient: bool = False) -> Services:
    """Resolve `repo_root`'s forge, ci and tracking services with provenance.

    Raises `ServicesError` on a declaration fr cannot honour (an unknown or
    deferred type, a cross-forge tracker, a missing required host, an invalid
    version-1 file) — unless `lenient`, which never raises."""
    config = _read_config(repo_root, lenient=lenient)
    forge = _forge(repo_root, config, lenient=lenient)
    ci = _ci(repo_root, config, forge, lenient=lenient)
    tracking = _tracking(config, forge, lenient=lenient)
    services = Services(forge=forge, ci=ci, tracking=tracking)
    try:
        validate_services(
            ForgeService(type=forge.type, host=forge.host),
            CiService(type=ci.type, host=ci.host),
            TrackingService(type=tracking.type, host=tracking.host),
        )
    except ServicesError:
        if not lenient:
            raise
    return services
