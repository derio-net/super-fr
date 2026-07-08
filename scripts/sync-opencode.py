#!/usr/bin/env python3
"""Sync super-fr skills and rules into OpenCode-discoverable mirrors.

OpenCode (github.com/anomalyco/opencode) discovers skills as plain
`SKILL.md` files under `.opencode/skills/<name>/`, `.claude/skills/<name>/`,
or `.agents/skills/<name>/` — it has no concept of the Claude Code
plugin/marketplace layout this repo ships skills through
(`plugins/super-fr/skills/<name>/SKILL.md`). Its project-level custom-
instructions surface is `opencode.json`'s `instructions` array (arbitrary
markdown files), not a `~/.claude/rules/` directory. This script generates
both mirrors so OpenCode sessions in this repo (or any repo that receives it
via install.sh) see the same skills and rules with zero extra setup.

`plugins/super-fr/skills/` and `plugins/super-fr/rules/` (plus
`.claude/rules/acceptance-matrix.md`, a repo-local-only rule with no plugin
equivalent) stay the canonical sources — never hand-edit
`.opencode/skills/<name>/SKILL.md` or `.opencode/instructions/<rule>.md`
directly; both are overwritten on sync.

Usage:
    scripts/sync-opencode.py          # write/update both mirrors
    scripts/sync-opencode.py --check  # exit non-zero on drift, no writes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SKILLS_CANONICAL_DIR = REPO_ROOT / "plugins" / "super-fr" / "skills"
SKILLS_MIRROR_DIR = REPO_ROOT / ".opencode" / "skills"

# Canonical rule sources: every installer-shipped rule, plus the one
# repo-local-only rule that has no plugins/super-fr/rules/ counterpart.
RULES_CANONICAL_DIR = REPO_ROOT / "plugins" / "super-fr" / "rules"
REPO_LOCAL_ONLY_RULES = (REPO_ROOT / ".claude" / "rules" / "acceptance-matrix.md",)
INSTRUCTIONS_MIRROR_DIR = REPO_ROOT / ".opencode" / "instructions"


# ---------------------------------------------------------------------------
# skills


def canonical_skills() -> dict[str, Path]:
    """Map of skill name -> canonical SKILL.md path."""
    return {p.parent.name: p for p in sorted(SKILLS_CANONICAL_DIR.glob("*/SKILL.md"))}


def mirror_skills() -> dict[str, Path]:
    """Map of skill name -> existing mirror SKILL.md path (if any)."""
    if not SKILLS_MIRROR_DIR.is_dir():
        return {}
    return {p.parent.name: p for p in sorted(SKILLS_MIRROR_DIR.glob("*/SKILL.md"))}


def find_drift() -> list[str]:
    """Human-readable skill mirror drift descriptions; empty means in sync."""
    canonical = canonical_skills()
    mirror = mirror_skills()
    problems = []

    missing = sorted(set(canonical) - set(mirror))
    extra = sorted(set(mirror) - set(canonical))
    for name in missing:
        problems.append(f"{name}: missing from .opencode/skills/")
    for name in extra:
        problems.append(f"{name}: present in .opencode/skills/ with no canonical source")

    for name in sorted(set(canonical) & set(mirror)):
        if canonical[name].read_text() != mirror[name].read_text():
            problems.append(f"{name}: .opencode/skills/ content differs from canonical")

    return problems


def sync_skills() -> None:
    """Write/overwrite the skills mirror to match canonical exactly."""
    canonical = canonical_skills()

    for name, path in mirror_skills().items():
        if name not in canonical:
            skill_dir = path.parent
            for child in skill_dir.iterdir():
                child.unlink()
            skill_dir.rmdir()

    for name, src in canonical.items():
        dest_dir = SKILLS_MIRROR_DIR / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "SKILL.md"
        dest.write_text(src.read_text())
        # Sibling breadcrumb pointing back at the canonical source — purely
        # informational, never parsed by OpenCode (it only reads SKILL.md).
        source_note = dest_dir / ".source"
        source_note.write_text(
            f"Generated from {src.relative_to(REPO_ROOT)} by "
            f"scripts/sync-opencode.py. Do not edit SKILL.md here directly.\n"
        )


# ---------------------------------------------------------------------------
# rules / instructions


def canonical_instructions() -> dict[str, Path]:
    """Map of rule name (no .md) -> canonical rule markdown path."""
    result = {p.stem: p for p in sorted(RULES_CANONICAL_DIR.glob("*.md"))}
    for path in REPO_LOCAL_ONLY_RULES:
        if path.is_file():
            result[path.stem] = path
    return result


def mirror_instructions() -> dict[str, Path]:
    """Map of rule name -> existing mirror markdown path (if any)."""
    if not INSTRUCTIONS_MIRROR_DIR.is_dir():
        return {}
    return {p.stem: p for p in sorted(INSTRUCTIONS_MIRROR_DIR.glob("*.md"))}


def find_instructions_drift() -> list[str]:
    """Human-readable instructions mirror drift descriptions; empty means in sync."""
    canonical = canonical_instructions()
    mirror = mirror_instructions()
    problems = []

    missing = sorted(set(canonical) - set(mirror))
    extra = sorted(set(mirror) - set(canonical))
    for name in missing:
        problems.append(f"{name}: missing from .opencode/instructions/")
    for name in extra:
        problems.append(f"{name}: present in .opencode/instructions/ with no canonical source")

    for name in sorted(set(canonical) & set(mirror)):
        if canonical[name].read_text() != mirror[name].read_text():
            problems.append(f"{name}: .opencode/instructions/ content differs from canonical")

    return problems


def sync_instructions() -> None:
    """Write/overwrite the instructions mirror to match canonical exactly."""
    canonical = canonical_instructions()

    for name, path in mirror_instructions().items():
        if name not in canonical:
            path.unlink()

    INSTRUCTIONS_MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    for name, src in canonical.items():
        dest = INSTRUCTIONS_MIRROR_DIR / f"{name}.md"
        dest.write_text(src.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if either mirror is out of sync; make no writes.",
    )
    args = parser.parse_args()

    if args.check:
        drift = find_drift() + find_instructions_drift()
        if drift:
            print("scripts/sync-opencode.py --check: drift detected:", file=sys.stderr)
            for line in drift:
                print(f"  - {line}", file=sys.stderr)
            print("Run `scripts/sync-opencode.py` (no --check) to fix.", file=sys.stderr)
            return 1
        print("scripts/sync-opencode.py --check: .opencode/ mirrors are in sync.")
        return 0

    sync_skills()
    sync_instructions()
    print(
        f"Synced {len(canonical_skills())} skill(s) into "
        f"{SKILLS_MIRROR_DIR.relative_to(REPO_ROOT)}/ and "
        f"{len(canonical_instructions())} instruction file(s) into "
        f"{INSTRUCTIONS_MIRROR_DIR.relative_to(REPO_ROOT)}/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
