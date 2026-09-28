"""The three services of `.devcontainer/fr-profiles.yaml` (spec
2026-09-28-fr-profiles-services §3.A, R1/R2).

Each service is a mapping with its own `type` and optional `host`, and keeps
any type-specific key beside them (`extra="allow"`, so a future `job:` or
`project:` round-trips untouched). Step 1 of #774 knows the forge's own
systems only; `jenkins` / `jira` and a tracker on another forge are step 2,
and every refusal names where that work lives (`FOLLOW_UP`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, field_validator

FOLLOW_UP = "derio-net/super-fr#795"
"""The follow-up issue that owns the Jenkins / Jira adapters and the
cross-forge tracker (#774 step 2)."""

Source = Literal["declared", "default", "legacy"]

FORGE_TYPES: tuple[str, ...] = ("github", "gitlab", "gitea")
CI_TYPES: tuple[str, ...] = ("none", "github-actions", "gitlab-ci", "gitea-actions")
TRACKING_TYPES: tuple[str, ...] = ("none", *FORGE_TYPES)
DEFERRED_TYPES: tuple[str, ...] = ("jenkins", "jira")
"""Named by the operator's input, built by #774 step 2 — refused, naming it."""

CI_FOR_FORGE: dict[str, str] = {
    "github": "github-actions",
    "gitlab": "gitlab-ci",
    "gitea": "gitea-actions",
}
"""Each forge's own pipeline type — what an undeclared `ci` defaults to."""


class ServicesError(ValueError):
    """A services declaration fr cannot honour."""


class _Service(BaseModel):
    model_config = ConfigDict(extra="allow")

    SERVICE: ClassVar[str]
    TYPES: ClassVar[tuple[str, ...]]

    type: str
    host: str | None = None

    @field_validator("type")
    @classmethod
    def _type(cls, value: str) -> str:
        if value in DEFERRED_TYPES:
            raise ValueError(
                f"{cls.SERVICE} type {value!r} is not supported yet — it arrives with {FOLLOW_UP}"
            )
        if value not in cls.TYPES:
            raise ValueError(
                f"unknown {cls.SERVICE} type {value!r}; expected one of {', '.join(cls.TYPES)}"
            )
        return value


class ForgeService(_Service):
    SERVICE = "forge"
    TYPES = FORGE_TYPES


class CiService(_Service):
    SERVICE = "ci"
    TYPES = CI_TYPES


class TrackingService(_Service):
    SERVICE = "tracking"
    TYPES = TRACKING_TYPES


def is_native(service: str, type_: str, forge_type: str) -> bool:
    """Whether `type_` is the forge's own system for `service` (`none` counts:
    it needs no host either)."""
    if type_ == "none":
        return True
    own = CI_FOR_FORGE[forge_type] if service == "ci" else forge_type
    return type_ == own


def validate_services(forge: ForgeService, ci: CiService, tracking: TrackingService) -> None:
    """The cross-service rules no single service can check (spec §3.A, R1/R2).

    - tracking is `none` or the forge's own type: fr files issues through the
      forge client, and a tracker on another forge needs the adapter seam
      #774 step 2 builds;
    - a service whose type is not the forge's own needs its own `host`, since
      it cannot borrow the forge's.
    """
    if tracking.type not in ("none", forge.type):
        raise ServicesError(
            f"tracking type {tracking.type!r} differs from the forge's ({forge.type!r}); "
            f"a tracker on another forge arrives with {FOLLOW_UP} — use "
            f"`tracking: {{type: {forge.type}}}` or `tracking: {{type: none}}`"
        )
    for name, service in (("ci", ci), ("tracking", tracking)):
        if not is_native(name, service.type, forge.type) and not service.host:
            raise ServicesError(
                f"{name} type {service.type!r} is not the {forge.type} forge's own, "
                f"so its host is required (`{name}: {{type: {service.type}, host: ...}}`)"
            )


@dataclass(frozen=True)
class ResolvedService:
    """One service as `resolve_services` found it: its values plus where they
    came from. `host_source` is separate from `source` because a host can be
    inferred (from the origin remote, or from the forge) for a service whose
    type was declared — and only a declared host is an operator expectation
    (gh#486's `declared_host`)."""

    type: str
    host: str | None
    source: Source
    host_source: Source | None = None


@dataclass(frozen=True)
class Services:
    forge: ResolvedService
    ci: ResolvedService
    tracking: ResolvedService
