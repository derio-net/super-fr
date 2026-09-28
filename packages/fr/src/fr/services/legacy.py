"""The frozen reader of a version-1 `.devcontainer/fr-profiles.yaml`.

Version 1 carried the forge as flat top-level keys, `backend:` and `host:`;
version 2 nests it under `forge:` beside `ci:` and `tracking:` (spec
2026-09-28-fr-profiles-services §3.A). A version-1 file is still READ — the
read-only commands are exempt from the migration gate and must keep working on
an unmigrated repo — and it is read through THIS model, never the live one
(.claude/rules/artifact-versioning.md, "Removing or moving a field freezes the
old shape").

FROZEN. Closed-world (`extra="forbid"`), with its vocabulary INLINED rather
than imported from `fr.services.model` or `fr._hosts`: a frozen reader that
follows a live vocabulary stops being a reader of the old version the day the
vocabulary moves. Every edit fails `FROZEN_CLASS_SHA256` and has to be argued
for in a diff to it; a later shape change freezes a `…V2` beside this one.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ProfilesV1(BaseModel):
    """FROZEN. `.devcontainer/fr-profiles.yaml` as version 1 wrote it."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] | None = None
    profiles: dict[str, Any] = {}
    default: str | None = None
    backend: Literal["github", "gitlab", "gitea"] | None = None
    host: str | None = None


FROZEN_CLASS_SHA256: dict[str, str] = {
    "ProfilesV1": "bf80ddf500f2fac0fa111375b0bc0e0b7a79f7baf2310b1fc510f9cc96f47f94",
}
"""SHA-256 of each frozen class's own source, as `inspect.getsource` returns it."""
