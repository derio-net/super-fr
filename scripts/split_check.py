"""CI's proof that a leg's shards ran exactly the tests it collects.

Spec 2026-11-01-ci-speed §3.B (R5). Stdlib only, so CI runs it with
`uv run --no-project python scripts/split_check.py`.

  check --collected <txt> <shard.json>...   exit 1 naming each problem
  merge -o <out> <shard.json>...            union the shards' duration files
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def parse_collected(stdout: str) -> list[str]:
    """Node ids are the lines containing `::`; the summary and blanks drop out."""
    return [line.strip() for line in stdout.splitlines() if "::" in line]


def check(collected: list[str], shard_files: dict[str, dict[str, float]]) -> list[str]:
    expected = set(collected)
    seen: dict[str, list[str]] = {}
    for shard, durations in shard_files.items():
        for node in durations:
            seen.setdefault(node, []).append(shard)
    problems = [f"missing (collected, ran in no shard): {n}" for n in sorted(expected - set(seen))]
    problems += [f"extra (ran, not collected): {n}" for n in sorted(set(seen) - expected)]
    problems += [
        f"duplicated (ran in {' and '.join(sorted(s))}): {n}"
        for n, s in sorted(seen.items())
        if len(s) > 1
    ]
    if len(collected) != len(expected):
        dupes = sorted(n for n, c in Counter(collected).items() if c > 1)
        problems += [f"collected twice: {n}" for n in dupes]
    return problems


def merge(shard_files: dict[str, dict[str, float]]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for durations in shard_files.values():
        merged.update(durations)
    return dict(sorted(merged.items()))


def _load(paths: list[str]) -> dict[str, dict[str, float]]:
    return {p: json.loads(Path(p).read_text()) for p in paths}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--collected", required=True)
    c.add_argument("shards", nargs="+")
    m = sub.add_parser("merge")
    m.add_argument("-o", "--output", required=True)
    m.add_argument("shards", nargs="+")
    args = ap.parse_args(argv)
    shards = _load(args.shards)
    if args.cmd == "check":
        collected = parse_collected(Path(args.collected).read_text())
        problems = check(collected, shards)
        if problems:
            print("\n".join(problems))
            return 1
        print(f"split-check: {len(set(collected))} tests, {len(shards)} shards, complete")
        return 0
    Path(args.output).write_text(json.dumps(merge(shards), indent=4) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
