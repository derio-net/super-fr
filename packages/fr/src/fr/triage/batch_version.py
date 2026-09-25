"""Version reservations (spec 2026-09-25-triage-batches §3.D).

Pure: a version text in, a version out. Reading the `source` manifest from
`origin/<default>` is the caller's (through `fr.triage.gitseam`); this module
parses it by extension and at the declared key only, and never reads any other
manifest.
"""

from __future__ import annotations

import fnmatch
import json
import re
import tomllib
from collections.abc import Iterable, Sequence
from typing import Any

from fr.triage.errors import TriageError
from fr.triage.model import Bump, VersionSource

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

Version = tuple[int, int, int]


def parse_version(text: str) -> Version:
    m = _SEMVER.match(text.strip())
    if m is None:
        raise TriageError(f"version {text!r} is not MAJOR.MINOR.PATCH")
    return int(m[1]), int(m[2]), int(m[3])


def format_version(v: Version) -> str:
    return f"{v[0]}.{v[1]}.{v[2]}"


def bump_version(text: str, bump: Bump) -> str:
    major, minor, patch = parse_version(text)
    if bump == "major":
        return format_version((major + 1, 0, 0))
    if bump == "minor":
        return format_version((major, minor + 1, 0))
    return format_version((major, minor, patch + 1))


def is_above(candidate: str, base: str) -> bool:
    return parse_version(candidate) > parse_version(base)


def read_source(text: str, source: VersionSource) -> str:
    """The version at `source.key` of a manifest's *text*, parsed by extension."""
    data: Any
    try:
        if source.file.endswith(".toml"):
            data = tomllib.loads(text)
        elif source.file.endswith(".json"):
            data = json.loads(text)
        else:
            raise TriageError(f"version source {source.file}: only .toml and .json are read")
    except (tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        raise TriageError(f"version source {source.file} does not parse: {exc}") from exc
    for part in source.key.split("."):
        if not isinstance(data, dict) or part not in data:
            raise TriageError(f"version source {source.file} has no key {source.key!r}")
        data = data[part]
    if not isinstance(data, str):
        raise TriageError(f"{source.file} {source.key} is not a version string: {data!r}")
    parse_version(data)
    return data


def reserve(source_version: str, live: Iterable[str], bump: Bump) -> str:
    """The next version after the highest of *source_version* and every *live*
    reservation, bumped by the batch's *bump* (§3.D Reserve)."""
    top = max([source_version, *live], key=parse_version)
    return bump_version(top, bump)


def slot_versions(main_version: str, bumps: Sequence[Bump]) -> list[str]:
    """The version each queued batch must carry, in merge order (§3.D Reconcile):
    each slot is the previous one bumped by that batch's level, starting at main."""
    out: list[str] = []
    current = main_version
    for bump in bumps:
        current = bump_version(current, bump)
        out.append(current)
    return out


def all_version_files(paths: Iterable[str], globs: Sequence[str]) -> bool:
    """Whether every path matches one of the declared `version.files` globs."""
    return all(any(fnmatch.fnmatch(p, g) for g in globs) for p in paths)
