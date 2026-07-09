#!/usr/bin/env python3
"""Fail when a PR changes shipped behavior without bumping the plugin version."""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = pathlib.Path("pyproject.toml")
VERSION_RE = re.compile(r'^(version\s*=\s*")([^"]+)(")', re.M)

VERSION_REQUIRED_EXACT = {
    "scripts/install.sh",
    "scripts/install-validator-wrapper.sh",
    "scripts/validate-plans.sh",
}


def git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, check=True, capture_output=True, text=True
    ).stdout


def version_from(text: str) -> str:
    match = VERSION_RE.search(text)
    if not match:
        raise SystemExit("error: no version line found in pyproject.toml")
    return match.group(2)


def requires_bump(path: str) -> bool:
    if path in VERSION_REQUIRED_EXACT:
        return True
    if path.startswith("plugins/super-fr/skills/") or path.startswith("plugins/super-fr/rules/"):
        return True
    return path.startswith("packages/") and "/src/" in path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: scripts/check-version-bump-needed.py <base-ref>", file=sys.stderr)
        return 2
    base = sys.argv[1]
    changed = [p for p in git(["diff", "--name-only", f"{base}...HEAD"]).splitlines() if p]
    required = [p for p in changed if requires_bump(p)]
    if not required:
        print("ok — no version-bump-required paths changed")
        return 0

    base_version = version_from(git(["show", f"{base}:{PYPROJECT}"]))
    head_version = version_from((REPO / PYPROJECT).read_text())
    if base_version != head_version:
        print(f"ok — version bumped {base_version} -> {head_version}")
        return 0

    print("ERROR: user-observable super-fr changes require a version bump.", file=sys.stderr)
    print("Run `scripts/bump-version.py patch` (or minor/major if warranted).", file=sys.stderr)
    print("Changed paths requiring a bump:", file=sys.stderr)
    for path in required:
        print(f"  - {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
