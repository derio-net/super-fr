#!/usr/bin/env python3
"""Hand-written `fr_version` floors (spec 2026-09-26-version-bump-churn §3.E).

A floor is a `>=X.Y.Z,<X.Y.Z` literal inside a Python string under
`packages/*/src` — `SCOPE_FR_VERSION = ">=4.20.0,<5.0.0"`, or the same text in
a refusal message. Only its **lower bound** matters: one newer than the base
version names a release that does not exist yet, and must equal the predicted
release (`base + this PR's fragment bump`, or at release time the version being
released). A lower bound at or below base names an existing release and always
passes, so reformatting a historical floor or moving an upper bound never trips.

Stdlib only, so it runs under `uv run --no-project`.
"""

from __future__ import annotations

import io
import re
import tokenize
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

FLOOR_RE = re.compile(
    r"(?<![\w.])>=\s*(\d+\.\d+\.\d+)\s*,\s*<\s*(\d+\.\d+\.\d+)(?![\w.])",
)
_STRING_TOKENS = {tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", tokenize.STRING)}


@dataclass(frozen=True)
class Floor:
    lower: str
    upper: str
    line: int


def parse_version(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in version.split("."))


def is_floor_path(rel: str) -> bool:
    """A repo-relative path whose floors count: Python under `packages/<pkg>/src/`."""
    parts = rel.split("/")
    return len(parts) >= 4 and parts[0] == "packages" and parts[2] == "src" and rel.endswith(".py")


def _floors_in(text: str, line_offset: int) -> list[Floor]:
    out = []
    for match in FLOOR_RE.finditer(text):
        line = line_offset + text.count("\n", 0, match.start())
        out.append(Floor(match.group(1), match.group(2), line))
    return out


def floors_in_source(source: str) -> list[Floor]:
    """Every floor inside a string literal of Python `source` (comments excluded)."""
    found: list[Floor] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type in _STRING_TOKENS:
                found.extend(_floors_in(tok.string, tok.start[0]))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        # Not valid Python: fall back to quoted literals found by text alone.
        found = [
            f
            for m in re.finditer(r"([\"'])(.*?)\1", source)
            for f in _floors_in(m.group(2), source.count("\n", 0, m.start()) + 1)
        ]
    return found


def scan_floors(repo: Path) -> list[tuple[str, Floor]]:
    """Every floor under `<repo>/packages/*/src`, as (repo-relative file, floor)."""
    repo = Path(repo)
    out: list[tuple[str, Floor]] = []
    for path in sorted((repo / "packages").glob("*/src/**/*.py")):
        rel = path.relative_to(repo).as_posix()
        out.extend((rel, f) for f in floors_in_source(path.read_text()))
    return out


def new_floors(before: str | None, after: str) -> list[Floor]:
    """Floors in `after` whose lower bound `before` does not already carry (a multiset)."""
    seen = Counter(f.lower for f in floors_in_source(before)) if before is not None else Counter()
    out = []
    for floor in floors_in_source(after):
        if seen[floor.lower]:
            seen[floor.lower] -= 1
        else:
            out.append(floor)
    return out


def lower_bound_ok(lower: str, base: str, predicted: str) -> bool:
    """At or below base (an existing release), or exactly the predicted release."""
    return parse_version(lower) <= parse_version(base) or lower == predicted
