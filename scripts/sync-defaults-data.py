#!/usr/bin/env python3
"""Copy super-fr's shipped defaults into the `fr` wheel (spec 2026-11-19 a-la-carte R15).

`plugins/super-fr/defaults/<kind>/<name>.yaml` (`workflows`, `verifications`, `lenses`)
is canonical. `packages/fr/src/fr/defaults/<kind>/` is generated package data, read by
`fr._shipped`, so every harness's `fr` knows the shipped defaults without a marketplace
clone. Never hand-edit the copy; `tests/unit/test_tripwire_shipped_defaults.py` fails on
drift. The write copies every manifest and deletes a copied one the plugin no longer has.

Usage:
    uv run --no-project python scripts/sync-defaults-data.py          # write the copy
    uv run --no-project python scripts/sync-defaults-data.py --check  # exit 1 on drift
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "plugins" / "super-fr" / "defaults"
TARGET = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "defaults"
KINDS = ("workflows", "verifications", "lenses")


def _sync_kind(kind: str, *, check: bool) -> list[tuple[str, str]]:
    """Every drifted copy of *kind* as `(verb, path)`: `wrote` a copy, `removed` a stale one."""
    source, target = SOURCE / kind, TARGET / kind
    drifted: list[tuple[str, str]] = []
    wanted = {p.name for p in source.glob("*.yaml")}
    for src in sorted(source.glob("*.yaml")):
        dst = target / src.name
        data = src.read_bytes()
        if dst.is_file() and dst.read_bytes() == data:
            continue
        drifted.append(("wrote", str(dst.relative_to(REPO_ROOT))))
        if not check:
            target.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
    for stale in sorted(target.glob("*.yaml")) if target.is_dir() else []:
        if stale.name not in wanted:
            drifted.append(("removed", str(stale.relative_to(REPO_ROOT))))
            if not check:
                stale.unlink()
    return drifted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report drift, write nothing")
    args = parser.parse_args(argv)
    drifted = [path for kind in KINDS for path in _sync_kind(kind, check=args.check)]
    if args.check and drifted:
        paths = ", ".join(path for _, path in drifted)
        print("drifted (run scripts/sync-defaults-data.py): " + paths, file=sys.stderr)
        return 1
    for verb, path in drifted:
        print(f"{verb} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
