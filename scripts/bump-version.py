#!/usr/bin/env python3
"""Bump or verify the plugin/library version.

`pyproject.toml` `[project].version` is the canonical source. The two
plugin JSONs (`.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json`) must match it byte-for-byte. Python
code reads the version dynamically via `importlib.metadata`, so it
follows pyproject automatically — no other surfaces need updating.

Usage:
    scripts/bump-version.py patch        # 2.1.7 -> 2.1.8
    scripts/bump-version.py minor        # 2.1.7 -> 2.2.0
    scripts/bump-version.py major        # 2.1.7 -> 3.0.0
    scripts/bump-version.py 2.3.1        # set explicitly
    scripts/bump-version.py --check      # verify the three files agree; exit 1 on drift
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"
PLUGIN_JSON = REPO / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO / ".claude-plugin" / "marketplace.json"

VERSION_RE = re.compile(r'^(version\s*=\s*")([^"]+)(")', re.M)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def read_pyproject_version() -> str:
    m = VERSION_RE.search(PYPROJECT.read_text())
    if not m:
        sys.exit(f"error: no `version = \"...\"` line in {PYPROJECT}")
    return m.group(2)


def read_plugin_json_version() -> str:
    return json.loads(PLUGIN_JSON.read_text())["version"]


def read_marketplace_json_version() -> str:
    return json.loads(MARKETPLACE_JSON.read_text())["plugins"][0]["version"]


def check() -> int:
    py = read_pyproject_version()
    pj = read_plugin_json_version()
    mp = read_marketplace_json_version()
    print(f"pyproject.toml          {py}")
    print(f"plugin.json             {pj}")
    print(f"marketplace.json[0]     {mp}")
    if py == pj == mp:
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


def write_pyproject(new: str) -> None:
    PYPROJECT.write_text(VERSION_RE.sub(rf'\g<1>{new}\g<3>', PYPROJECT.read_text(), count=1))


def write_plugin_json(new: str) -> None:
    data = json.loads(PLUGIN_JSON.read_text())
    data["version"] = new
    PLUGIN_JSON.write_text(json.dumps(data, indent=4) + "\n")


def write_marketplace_json(new: str) -> None:
    data = json.loads(MARKETPLACE_JSON.read_text())
    data["plugins"][0]["version"] = new
    MARKETPLACE_JSON.write_text(json.dumps(data, indent=4) + "\n")


def bump(arg: str) -> int:
    old = read_pyproject_version()
    new = compute_new(old, arg)
    if new == old:
        print(f"already at {new}, nothing to do")
        return 0

    write_pyproject(new)
    write_plugin_json(new)
    write_marketplace_json(new)
    print(f"bumped {old} -> {new} in 3 files")

    # uv sync refreshes uv.lock with the new `vk==X.Y.Z` entry.
    print("running `uv sync`...")
    subprocess.run(["uv", "sync"], check=True, cwd=REPO)

    # Verify the entry point reports the new number.
    result = subprocess.run(
        ["uv", "run", "vk", "--version"],
        check=True,
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    reported = result.stdout.strip()
    print(f"`vk --version` -> {reported}")
    if new not in reported:
        sys.exit(f"error: vk --version output {reported!r} doesn't contain {new!r}")
    return 0


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
