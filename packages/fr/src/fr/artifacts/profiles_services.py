"""The `profiles` kind's 1 -> 2 migration (spec
`2026-09-28-fr-profiles-services-design.md` §3.D, R3).

Version 1 of `.devcontainer/fr-profiles.yaml` carried the forge as flat
top-level `backend:`/`host:`; version 2 nests it under `forge:` beside `ci:` and
`tracking:`. The rewrite MOVES two fields, so, per
`.claude/rules/artifact-versioning.md`:

1. **It reads version 1 only through the frozen `fr.services.legacy.ProfilesV1`**,
   never a live model. A v1 file with a key that model does not know (or an
   out-of-vocabulary `backend:`) is refused rather than guessed at.
2. **It builds the new body in memory and writes once**, through
   `write_text_atomic`. The rewrite is TEXTUAL — this file belongs to the
   operator: the top-level `backend:`/`host:` lines are dropped, the three
   service blocks are appended in the file's own line endings
   (`fr.services.render.render_services`, shared with `fr init scaffold`), and
   every other byte — comments, blank lines, ordering, a BOM — is kept. Before
   writing, the new text is parsed back and must say exactly what was intended;
   a file whose layout defeats the line surgery — a flow-style or indented
   top-level mapping, a quoted key, a `...` document end — is refused instead,
   whether the rewritten text then fails to parse or parses to the wrong thing.
   Every refusal fires before a byte moves, so a refused file
   is left byte-identical and reported as that one artifact's failure.
3. **It survives its own crash window.** `fn` writes the body; the runner writes
   the stamp. A body that is already wholly version 2 — service blocks that the
   live models accept and no `backend:`/`host:` left — is the one this migration
   wrote before dying, so `fn` returns and lets the runner stamp it. Answering
   "is this already v2?" is the one legitimate use of the live models here.

What it writes (§3.D.3): `forge` from `backend` (else a RECOGNISED origin, see
`v1_services`) with `host` only when one was declared; `ci` as detected offline
(`fr.services.detect.detected_ci_type` — fr's own acceptance scaffold is not
CI), the same function the resolver's legacy branch uses, so `fr services` shows
the same value before and after; `tracking` as the forge's own. A forge whose
type is only the `github` fallback is NOT declared (phase-2 review r1).

No network: this runs at the CLI-entry gate, often offline or in a pod. The
origin remote is read with `git remote get-url`, which is local.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.runner import MIGRATIONS, ArtifactMigrationError, SchemaMigration

MIGRATION_NAME = "profiles-services"

__all__ = [
    "MIGRATION_NAME",
    "PROFILES_SERVICES_MIGRATION",
    "UnmigratableProfilesError",
    "rewrite_to_services",
    "v1_services",
]

_LEGACY_KEYS = ("backend", "host")
_LEGACY_LINE_RE = re.compile(r"^(?:backend|host)[ \t]*:")


class UnmigratableProfilesError(ArtifactMigrationError):
    """A version-1 fr-profiles.yaml the migration will not rewrite."""


def _refuse(path: Path, why: str) -> UnmigratableProfilesError:
    return UnmigratableProfilesError(
        f"{path}: fr will not rewrite this fr-profiles.yaml to version 2 — {why}. "
        "Fix the file by hand (or declare `forge:`/`ci:`/`tracking:` yourself); it is "
        "left byte-identical on its current version and will be retried."
    )


def _is_wholly_v2(data: dict[str, Any]) -> bool:
    """The crash-window body: no legacy key, at least one service block, and
    every service block present reads through the live model."""
    from pydantic import ValidationError

    from fr.services.model import CiService, ForgeService, TrackingService

    if any(key in data for key in _LEGACY_KEYS):
        return False
    models = {"forge": ForgeService, "ci": CiService, "tracking": TrackingService}
    present = [key for key in models if key in data]
    if not present:
        return False
    try:
        for key in present:
            models[key].model_validate(data[key])
    except ValidationError:
        return False
    return True


def _service_problems(data: dict[str, Any]) -> str:
    """Why the service blocks in `data` do not read through the live models."""
    from pydantic import ValidationError

    from fr.services.model import CiService, ForgeService, TrackingService

    models = {"forge": ForgeService, "ci": CiService, "tracking": TrackingService}
    reasons: list[str] = []
    for key, model in models.items():
        if key not in data:
            continue
        try:
            model.model_validate(data[key])
        except ValidationError as e:
            reasons += [
                f"`{key}`: " + str(err["msg"]).removeprefix("Value error, ") for err in e.errors()
            ]
    return "; ".join(reasons)


def v1_services(
    repo_root: Path, backend: str | None, host: str | None
) -> dict[str, dict[str, str]]:
    """The service blocks a version-1 `backend:`/`host:` pair stands for in
    `repo_root` — what the migration writes.

    `forge:` (and with it `tracking:`) is declared only when its type is
    KNOWN (phase-2 review r1): from `backend:`; else from an origin (or a
    declared `host:`) that `DEFAULT_HOST_BACKENDS` recognises; else, for a
    `host:` with no `backend:`, `github` — `fr init scaffold` never wrote
    `backend: github` (it was the default), so that pair IS a declared GitHub
    Enterprise forge. With neither key and an unrecognised or missing origin,
    the type is only `detect_backend`'s `github` FALLBACK: declaring it would
    lock a possibly wrong forge in and silence the "not a recognized forge"
    warning, so both blocks are left out and resolve as `default`, exactly as
    before. `ci:` is then written only when the files decide it for the
    fallback type (real CI, or fr's own scaffold alone); with no CI config at
    all it is left to the resolver's own default, which says the same.
    """
    from fr._hosts import DEFAULT_HOST_BACKENDS, origin_hostname
    from fr.services.detect import detect_ci, detected_ci_type

    origin = origin_hostname(repo_root)
    forge_type = (
        backend
        or (DEFAULT_HOST_BACKENDS.get(origin) if origin else None)
        or (DEFAULT_HOST_BACKENDS.get(host) if host else None)
        or ("github" if host else None)
    )
    if forge_type is None:
        fallback = "github"
        if detect_ci(repo_root, fallback) == "absent":
            return {}
        return {"ci": {"type": detected_ci_type(repo_root, fallback)}}
    forge = {"type": forge_type}
    if host:
        forge["host"] = host
    return {
        "forge": forge,
        "ci": {"type": detected_ci_type(repo_root, forge_type)},
        "tracking": {"type": forge_type},
    }


def _drop_legacy_lines(text: str) -> str:
    """`text` without its top-level `backend:`/`host:` lines (and any indented
    continuation of their value). Every other line is kept byte-for-byte."""
    from fr.artifacts.registry import split_lines

    kept: list[str] = []
    dropping = False
    for line in split_lines(text):
        if _LEGACY_LINE_RE.match(line):
            dropping = True
            continue
        if dropping and line[:1] in (" ", "\t") and line.strip():
            continue
        dropping = False
        kept.append(line)
    return "".join(kept)


def rewrite_to_services(path: Path) -> None:
    """Rewrite `path` from the version-1 shape to the version-2 one. Never
    touches the stamp, which is the runner's."""
    from pydantic import ValidationError

    from fr.artifacts.registry import read_verbatim
    from fr.services.legacy import ProfilesV1
    from fr.services.render import render_services

    try:
        bom, text = read_verbatim(path)
        data: Any = yaml.safe_load(text)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        raise _refuse(path, f"it cannot be read ({e})") from e
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise _refuse(path, "its top level is not a mapping")
    if _is_wholly_v2(data):
        return
    if any(key in data for key in ("forge", "ci", "tracking")):
        if any(key in data for key in _LEGACY_KEYS):
            raise _refuse(
                path, "it mixes version-1 `backend:`/`host:` with version-2 service blocks"
            )
        raise _refuse(path, f"a service block is invalid ({_service_problems(data)})")
    try:
        v1 = ProfilesV1.model_validate(data)
    except ValidationError as e:
        raise _refuse(
            path, f"it is not a valid version-1 file ({e.error_count()} error(s): {e})"
        ) from e

    services = v1_services(path.parent.parent, v1.backend, v1.host)
    newline = "\r\n" if "\r\n" in text else "\n"
    body = _drop_legacy_lines(text)
    if body and not body.endswith("\n"):
        body += newline
    new_text = body + render_services(services, newline=newline)

    expected = {k: v for k, v in data.items() if k not in _LEGACY_KEYS} | services
    layout = (
        "its layout defeats a line-level rewrite (a flow-style or indented top-level "
        "mapping, a quoted key, an anchor or a `...` document end?)"
    )
    try:
        reread = yaml.safe_load(new_text)
    except yaml.YAMLError as e:
        raise _refuse(path, f"{layout}: the rewritten text does not parse ({e})") from e
    if reread != expected:
        raise _refuse(path, f"{layout}: the rewritten text does not say what was intended")
    write_text_atomic(path, bom + new_text)


PROFILES_SERVICES_MIGRATION = SchemaMigration(
    kind="profiles",
    from_version=1,
    to_version=2,
    fn=rewrite_to_services,
    description="fr-profiles: top-level `backend:`/`host:` become nested `forge:`, `ci:` and "
    "`tracking:` blocks — every other line kept; a file it cannot read is left untouched",
)

MIGRATIONS.register(PROFILES_SERVICES_MIGRATION)
