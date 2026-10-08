"""`forge.api`: which GitHub API fr talks to on this host (spec 2026-10-07-cloud-triage §A, R3).

`rest` selects `fr.real_ghrestclient.RealGhRestClient`, which reaches GitHub only
through `gh api` REST routes: a Claude Code cloud session's proxy refuses GraphQL
(HTTP 403), and nearly every other `gh` command is GraphQL-backed. `graphql` (the
default) keeps the `gh`-CLI client every host has used so far.

The setting is resolved with no argument, no scope and no forge client, so the
run-path callers, which have none of those, resolve it exactly as triage does:
`FR_FORGE_API`, else `api:` in the host file `~/.config/fr/forge.yaml` (beside
`host-id`, the same `$HOME` rule as `fr.triage.scope_config.host_id_path`), else
`graphql`. A repo-level key is deliberately not offered. No process is spawned.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, cast, get_args

import yaml

ForgeApi = Literal["rest", "graphql"]
ENV = "FR_FORGE_API"
DEFAULT: ForgeApi = "graphql"
_VALUES = frozenset(get_args(ForgeApi))


class ForgeApiError(Exception):
    """A `forge.api` value fr cannot use; the message names where it came from."""


def config_path() -> Path:
    """`$HOME/.config/fr/forge.yaml` — `$HOME` read at call time, as `host_id_path` does."""
    return Path(os.environ.get("HOME", str(Path.home()))) / ".config" / "fr" / "forge.yaml"


def _checked(value: object, source: str) -> ForgeApi:
    if value not in _VALUES:
        raise ForgeApiError(f"{source}: forge.api must be one of {sorted(_VALUES)}, got {value!r}")
    return cast("ForgeApi", value)


def _from_file(path: Path) -> ForgeApi | None:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ForgeApiError(f"{path}: cannot read forge.api ({exc})") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ForgeApiError(f"{path}: not YAML ({exc})") from exc
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ForgeApiError(f"{path}: expected a mapping with an `api:` key")
    if "api" not in data:
        return None
    return _checked(data["api"], str(path))


def resolve() -> ForgeApi:
    """`FR_FORGE_API`, else the host file's `api:`, else `graphql`. Raises
    `ForgeApiError`, naming the env var or the file, on a value it cannot use."""
    env = os.environ.get(ENV)
    if env is not None and env.strip():
        return _checked(env.strip(), ENV)
    return _from_file(config_path()) or DEFAULT


def write_default(value: ForgeApi) -> bool:
    """Write `api: <value>` to the host file only when it is absent; whether it
    wrote. Never overwrites: the host file always wins over a restored default."""
    from fr.artifacts.atomic import write_text_atomic

    checked = _checked(value, "write_default")
    path = config_path()
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, f"api: {checked}\n")
    return True
