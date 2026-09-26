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
import sys
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
_PROJECT_HEADER_RE = re.compile(r"^\[project\][ \t]*(#.*)?$", re.M)
# The next real table header; a bare `[` line (an array continuation) is not one.
_TABLE_HEADER_RE = re.compile(r"^\[\[?[A-Za-z0-9_\"'.\- ]+\]\]?[ \t]*(#.*)?$", re.M)
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
    return [
        p for p in tomllib.loads(_required(lock).read_text()).get("package", []) if _is_member(p)
    ]


def _required(path: Path) -> Path:
    """A single-instance surface that must exist: a lost manifest is drift, never a skip."""
    if not path.exists():
        sys.exit(f"error: version surface {path} is missing")
    return path


def version_surfaces(repo: Path) -> list[Surface]:
    """Every (file, locator, value) the workspace version is written to."""
    repo = Path(repo)
    out: list[Surface] = []
    for toml in [repo / ROOT_PYPROJECT, *member_pyprojects(repo)]:
        out.append(Surface(_rel(repo, toml), "project.version", _toml_version(toml)))
    for pj in plugin_jsons(repo):
        out.append(Surface(_rel(repo, pj), "version", json.loads(pj.read_text())["version"]))
    opencode = _required(repo / OPENCODE_PACKAGE_JSON)
    out.append(
        Surface(OPENCODE_PACKAGE_JSON, "version", json.loads(opencode.read_text())["version"])
    )
    market = _required(repo / MARKETPLACE_JSON)
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


def _set_project_version(text: str, new: str, path: Path) -> str:
    """`text` with `[project].version` set to `new`, touching no other table."""
    header = _PROJECT_HEADER_RE.search(text)
    if not header:
        raise ValueError(f"no [project] table in {path}")
    start = header.end()
    boundary = _TABLE_HEADER_RE.search(text, start)
    end = boundary.start() if boundary else len(text)
    body, count = _TOML_VERSION_RE.subn(rf"\g<1>{new}\g<3>", text[start:end], count=1)
    if not count:
        raise ValueError(f"no double-quoted [project].version to rewrite in {path}")
    out = text[:start] + body + text[end:]
    # Belt and braces for a boundary the regexes misread: the only parsed
    # difference may be [project].version.
    expected = tomllib.loads(text)
    expected["project"]["version"] = new
    if tomllib.loads(out) != expected:
        raise ValueError(f"rewriting [project].version in {path} would change something else")
    return out


def write_version(repo: Path, new: str) -> list[str]:
    """Write `new` to every surface; return the repo-relative files touched.

    Every pyproject rewrite is computed before any file is written, so a
    refusal there leaves the tree untouched (the JSON and uv.lock writes that
    follow have no refusal path on well-formed input).
    """
    repo = Path(repo)
    files: list[str] = []
    for surface in version_surfaces(repo):
        if surface.file not in files:
            files.append(surface.file)
    tomls = {
        f: _set_project_version((repo / f).read_text(), new, repo / f)
        for f in files
        if f != UV_LOCK and f.endswith(".toml")
    }
    for f in files:
        if f == UV_LOCK:
            _write_lock_versions(repo, new)
        elif f in tomls:
            (repo / f).write_text(tomls[f])
        else:
            _write_json_version(repo, f, new)
    return files
