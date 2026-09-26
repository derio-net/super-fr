#!/usr/bin/env python3
"""The one list of every place the workspace version is written.

Spec 2026-09-26-version-bump-churn §3.B: `bump-version.py`, the change-fragment
gate, `release.py` and `version-sync` all read `version_surfaces()`, so there is
exactly one list. A surface is a (file, locator, value) triple:

- the workspace-root `pyproject.toml` (canonical) and every
  `packages/*/pyproject.toml`            -> locator `project.version`
- every Claude Code `plugin.json`         -> locator `version`
- each `.claude-plugin/marketplace.json` plugin entry
                                          -> locator `plugins[<i>].version`
- `packages/fr-opencode-plugin/package.json` -> locator `version`
- each `uv.lock` `[[package]]` that is a workspace member (its `source` is
  `editable` or `virtual`; registry packages are not ours)
                                          -> locator `package[<name>].version`

Stdlib only, so it runs under `uv run --no-project`.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_PYPROJECT = "pyproject.toml"
MARKETPLACE_JSON = ".claude-plugin/marketplace.json"
OPENCODE_PACKAGE_JSON = "packages/fr-opencode-plugin/package.json"
UV_LOCK = "uv.lock"

# JSON indent each manifest is written with (preserves the committed layout).
_JSON_INDENT = {OPENCODE_PACKAGE_JSON: 2}
_TOML_VERSION_RE = re.compile(r'^(version\s*=\s*")([^"]+)(")', re.M)
_LOCK_BLOCK_RE = re.compile(r"^\[\[package\]\]\n", re.M)


@dataclass(frozen=True)
class Surface:
    file: str  # repo-relative, POSIX separators
    locator: str  # where in the file the value sits
    value: str


def member_pyprojects(repo: Path) -> list[Path]:
    return sorted((repo / "packages").glob("*/pyproject.toml"))


def plugin_jsons(repo: Path) -> list[Path]:
    """Every plugin manifest — per-plugin dirs since the split."""
    return sorted(
        {
            *(repo / ".claude-plugin").glob("**/plugin.json"),
            *(repo / "plugins").glob("*/.claude-plugin/plugin.json"),
        }
    )


def _rel(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def _toml_version(path: Path) -> str:
    version = tomllib.loads(path.read_text()).get("project", {}).get("version")
    if not isinstance(version, str):
        raise ValueError(f"no [project].version in {path}")
    return version


def _is_member(package: dict[str, Any]) -> bool:
    source = package.get("source", {})
    return isinstance(source, dict) and ("editable" in source or "virtual" in source)


def _lock_members(repo: Path) -> list[dict[str, Any]]:
    lock = repo / UV_LOCK
    if not lock.exists():
        return []
    return [p for p in tomllib.loads(lock.read_text()).get("package", []) if _is_member(p)]


def version_surfaces(repo: Path) -> list[Surface]:
    """Every (file, locator, value) the workspace version is written to."""
    repo = Path(repo)
    out: list[Surface] = []
    for toml in [repo / ROOT_PYPROJECT, *member_pyprojects(repo)]:
        out.append(Surface(_rel(repo, toml), "project.version", _toml_version(toml)))
    for pj in plugin_jsons(repo):
        out.append(Surface(_rel(repo, pj), "version", json.loads(pj.read_text())["version"]))
    opencode = repo / OPENCODE_PACKAGE_JSON
    if opencode.exists():
        out.append(
            Surface(OPENCODE_PACKAGE_JSON, "version", json.loads(opencode.read_text())["version"])
        )
    market = repo / MARKETPLACE_JSON
    if market.exists():
        for i, plugin in enumerate(json.loads(market.read_text())["plugins"]):
            out.append(Surface(MARKETPLACE_JSON, f"plugins[{i}].version", plugin["version"]))
    for package in _lock_members(repo):
        out.append(Surface(UV_LOCK, f"package[{package['name']}].version", package["version"]))
    return out


def _write_json_version(repo: Path, rel: str, new: str) -> None:
    path = repo / rel
    data = json.loads(path.read_text())
    if rel == MARKETPLACE_JSON:
        for plugin in data["plugins"]:
            plugin["version"] = new
    else:
        data["version"] = new
    path.write_text(json.dumps(data, indent=_JSON_INDENT.get(rel, 4)) + "\n")


def _write_lock_versions(repo: Path, new: str) -> None:
    path = repo / UV_LOCK
    members = {p["name"] for p in _lock_members(repo)}
    if not members:
        return
    text = path.read_text()
    starts = [m.start() for m in _LOCK_BLOCK_RE.finditer(text)]
    if not starts:
        return
    pieces = [text[: starts[0]]]
    for start, end in zip(starts, [*starts[1:], len(text)], strict=True):
        block = text[start:end]
        name = re.search(r'^name\s*=\s*"([^"]+)"', block, re.M)
        if name and name.group(1) in members and _is_member(tomllib.loads(block)["package"][0]):
            block = _TOML_VERSION_RE.sub(rf"\g<1>{new}\g<3>", block, count=1)
        pieces.append(block)
    path.write_text("".join(pieces))


def write_version(repo: Path, new: str) -> list[str]:
    """Write `new` to every surface; return the repo-relative files touched."""
    repo = Path(repo)
    files: list[str] = []
    for surface in version_surfaces(repo):
        if surface.file in files:
            continue
        files.append(surface.file)
        path = repo / surface.file
        if surface.file == UV_LOCK:
            _write_lock_versions(repo, new)
        elif path.suffix == ".toml":
            path.write_text(_TOML_VERSION_RE.sub(rf"\g<1>{new}\g<3>", path.read_text(), count=1))
        else:
            _write_json_version(repo, surface.file, new)
    return files
