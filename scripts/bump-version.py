#!/usr/bin/env python3
"""Bump or verify the workspace version (lockstep).

The workspace-root `pyproject.toml` `[project].version` is the canonical
source. Every surface `scripts/version_surfaces.py` lists — member pyprojects,
plugin manifests, marketplace entries, the standalone OpenCode plugin package
and the `uv.lock` entries of workspace members — must match it byte-for-byte.
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

import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

# The surface list lives in one module (spec 2026-09-26-version-bump-churn
# §3.B); every reader — this script, the change-fragment gate, release.py —
# imports it so there is exactly one list.
sys.path.insert(0, str(REPO / "scripts"))
from version_surfaces import Surface, version_surfaces, write_version  # noqa: E402


def root_version() -> str:
    return next(s.value for s in version_surfaces(REPO) if s.file == "pyproject.toml")


_BRACKET_RE = re.compile(r"\[([^\]]+)\]")


def _label(surface: Surface) -> str:
    """`marketplace.json[0]`, `uv.lock[fr]`, else the file itself."""
    m = _BRACKET_RE.search(surface.locator)
    return f"{pathlib.PurePosixPath(surface.file).name}[{m.group(1)}]" if m else surface.file


def check() -> int:
    versions = {_label(s): s.value for s in version_surfaces(REPO)}
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


def bump(arg: str) -> int:
    old = root_version()
    new = compute_new(old, arg)
    if new == old:
        print(f"already at {new}, nothing to do")
        return 0

    files = write_version(REPO, new)
    print(f"bumped {old} -> {new} in {len(files)} files")

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
