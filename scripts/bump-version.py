#!/usr/bin/env python3
"""Bump or verify the workspace version (lockstep).

The workspace-root `pyproject.toml` `[project].version` is the canonical
source. Every member pyproject under `packages/*/pyproject.toml` and
every plugin version in `.claude-plugin/{plugin.json,marketplace.json}`
and the standalone OpenCode plugin package version must match it byte-for-byte.
Python code reads its version dynamically via `importlib.metadata`, so it
follows the member pyprojects automatically — no other surfaces need updating.

Usage:
    scripts/bump-version.py patch        # 2.1.7 -> 2.1.8
    scripts/bump-version.py minor        # 2.1.7 -> 2.2.0
    scripts/bump-version.py major        # 2.1.7 -> 3.0.0
    scripts/bump-version.py 2.3.1        # set explicitly
    scripts/bump-version.py --check      # verify the whole set agrees; exit 1 on drift
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"
PLUGIN_DIR = REPO / ".claude-plugin"
MARKETPLACE_JSON = PLUGIN_DIR / "marketplace.json"
OPENCODE_PLUGIN_PACKAGE_JSON = REPO / "packages" / "fr-opencode-plugin" / "package.json"

VERSION_RE = re.compile(r'^(version\s*=\s*")([^"]+)(")', re.M)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def member_pyprojects() -> list[pathlib.Path]:
    return sorted((REPO / "packages").glob("*/pyproject.toml"))


def plugin_jsons() -> list[pathlib.Path]:
    """Every plugin manifest — per-plugin dirs since the split."""
    return sorted(
        [
            *PLUGIN_DIR.glob("**/plugin.json"),
            *(REPO / "plugins").glob("*/.claude-plugin/plugin.json"),
        ]
    )


def read_version(toml: pathlib.Path) -> str:
    m = VERSION_RE.search(toml.read_text())
    if not m:
        sys.exit(f'error: no `version = "..."` line in {toml}')
    return m.group(2)


def check() -> int:
    versions: dict[str, str] = {"pyproject.toml": read_version(PYPROJECT)}
    for member in member_pyprojects():
        versions[str(member.relative_to(REPO))] = read_version(member)
    for pj in plugin_jsons():
        versions[str(pj.relative_to(REPO))] = json.loads(pj.read_text())["version"]
    versions[str(OPENCODE_PLUGIN_PACKAGE_JSON.relative_to(REPO))] = json.loads(
        OPENCODE_PLUGIN_PACKAGE_JSON.read_text()
    )["version"]
    for i, plugin in enumerate(json.loads(MARKETPLACE_JSON.read_text())["plugins"]):
        versions[f"marketplace.json[{i}]"] = plugin["version"]
    width = max(len(k) for k in versions)
    for k, v in versions.items():
        print(f"{k:<{width}}  {v}")
    if len(set(versions.values())) == 1:
        print("ok — versions agree")
        return 0
    print("DRIFT — run `scripts/bump-version.py <patch|minor|major|X.Y.Z>` to resync")
    return 1


def compute_new(old: str, arg: str) -> str:
    if SEMVER_RE.match(arg):
        return arg
    maj, mi, pa = (int(x) for x in old.split("."))
    if arg == "major":
        return f"{maj + 1}.0.0"
    if arg == "minor":
        return f"{maj}.{mi + 1}.0"
    if arg == "patch":
        return f"{maj}.{mi}.{pa + 1}"
    sys.exit(f"error: expected patch|minor|major|X.Y.Z, got {arg!r}")


def write_toml(toml: pathlib.Path, new: str) -> None:
    toml.write_text(VERSION_RE.sub(rf"\g<1>{new}\g<3>", toml.read_text(), count=1))


def bump(arg: str) -> int:
    old = read_version(PYPROJECT)
    new = compute_new(old, arg)
    if new == old:
        print(f"already at {new}, nothing to do")
        return 0

    tomls = [PYPROJECT, *member_pyprojects()]
    for toml in tomls:
        write_toml(toml, new)
    for pj in plugin_jsons():
        data = json.loads(pj.read_text())
        data["version"] = new
        pj.write_text(json.dumps(data, indent=4) + "\n")
    data = json.loads(OPENCODE_PLUGIN_PACKAGE_JSON.read_text())
    data["version"] = new
    OPENCODE_PLUGIN_PACKAGE_JSON.write_text(json.dumps(data, indent=2) + "\n")
    data = json.loads(MARKETPLACE_JSON.read_text())
    for plugin in data["plugins"]:
        plugin["version"] = new
    MARKETPLACE_JSON.write_text(json.dumps(data, indent=4) + "\n")
    n_files = len(tomls) + len(plugin_jsons()) + 2
    print(f"bumped {old} -> {new} in {n_files} files")

    # uv sync refreshes uv.lock with the new member entries.
    print("running `uv sync`...")
    subprocess.run(["uv", "sync"], check=True, cwd=REPO)

    # Verify the entry point reports the new number. The script name is
    # `vk` until the Phase 3 rebrand flips it to `fr`; probe both.
    for cli in ("fr", "vk"):
        result = subprocess.run(
            ["uv", "run", cli, "--version"],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            reported = result.stdout.strip()
            print(f"`{cli} --version` -> {reported}")
            if new not in reported:
                sys.exit(f"error: {cli} --version output {reported!r} doesn't contain {new!r}")
            return 0
    sys.exit("error: neither `fr` nor `vk` entry point responded to --version")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    arg = sys.argv[1]
    if arg == "--check":
        return check()
    return bump(arg)


if __name__ == "__main__":
    sys.exit(main())
