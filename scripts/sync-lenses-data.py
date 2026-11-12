#!/usr/bin/env python3
"""Copy the shipped review lenses into the `fr` wheel (spec 2026-11-12-review-lenses R1).

`plugins/super-fr/lenses/<id>.yaml` is canonical. `packages/fr/src/fr/lens_manifests/`
is generated package data, read by `fr.lenses.resolve`, so every harness's `fr` knows the
shipped lenses without a marketplace clone. Never hand-edit the copy;
`tests/unit/test_tripwire_shipped_lenses.py` fails on drift.

Usage:
    uv run --no-project python scripts/sync-lenses-data.py          # write the copy
    uv run --no-project python scripts/sync-lenses-data.py --check  # exit 1 on drift
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "plugins" / "super-fr" / "lenses"
TARGET = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "lens_manifests"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report drift, write nothing")
    args = parser.parse_args(argv)
    drifted: list[str] = []
    wanted = {p.name for p in SOURCE.glob("*.yaml")}
    for src in sorted(SOURCE.glob("*.yaml")):
        dst = TARGET / src.name
        data = src.read_bytes()
        if dst.is_file() and dst.read_bytes() == data:
            continue
        drifted.append(str(dst.relative_to(REPO_ROOT)))
        if not args.check:
            TARGET.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
    for stale in sorted(TARGET.glob("*.yaml")) if TARGET.is_dir() else []:
        if stale.name not in wanted:
            drifted.append(str(stale.relative_to(REPO_ROOT)))
            if not args.check:
                stale.unlink()
    if args.check and drifted:
        print("drifted (run scripts/sync-lenses-data.py): " + ", ".join(drifted), file=sys.stderr)
        return 1
    for path in drifted:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
