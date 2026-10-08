#!/usr/bin/env python3
"""Copy the agents fr renders into a repo into the `fr` wheel (spec 2026-10-07-cloud-triage §H).

`plugins/super-fr/agents/<name>.md` is canonical. `packages/fr/src/fr/agents/<name>.md`
is generated package data, read by `fr.agents.canonical_text`, so every harness's `fr`
can render the `agents` artifact kind without a marketplace clone. Never hand-edit the
copy; `tests/unit/test_tripwire_agents_data.py` fails on drift.

Usage:
    uv run --no-project python scripts/sync-agents-data.py          # write the copy
    uv run --no-project python scripts/sync-agents-data.py --check  # exit 1 on drift
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "plugins" / "super-fr" / "agents"
TARGET = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "agents"
NAMES = ("fr-spec-reviewer", "fr-phase-executor")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report drift, write nothing")
    args = parser.parse_args(argv)
    drifted: list[str] = []
    for name in NAMES:
        src, dst = SOURCE / f"{name}.md", TARGET / f"{name}.md"
        data = src.read_bytes()
        if dst.is_file() and dst.read_bytes() == data:
            continue
        drifted.append(str(dst.relative_to(REPO_ROOT)))
        if not args.check:
            dst.write_bytes(data)
    if args.check and drifted:
        print("drifted (run scripts/sync-agents-data.py): " + ", ".join(drifted), file=sys.stderr)
        return 1
    for path in drifted:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
