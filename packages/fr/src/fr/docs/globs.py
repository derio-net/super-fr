"""Segment-aware path globs (spec 2026-11-11-docs-currency R2).

`*` and `?` stay inside one path segment; `**` spans segments. `fnmatch`, where
`*` crosses `/`, is deliberately not used: `docs/*.md` must not reach
`docs/superpowers/x.md`. `scripts/build-site.py` carries a copy of this matcher
because it runs without `fr`; a test keeps the two page sets equal.
"""

from __future__ import annotations

import re
from functools import cache


@cache
def compile_glob(pattern: str) -> re.Pattern[str]:
    """The anchored regex for `pattern`; compiled once per pattern."""
    out: list[str] = []
    i, n = 0, len(pattern)
    while i < n:
        ch = pattern[i]
        if pattern.startswith("**", i):
            i += 2
            if pattern.startswith("/", i):
                out.append("(?:.*/)?")  # `**/` is zero or more whole segments
                i += 1
            else:
                out.append(".*")
        elif ch == "*":
            out.append("[^/]*")
            i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("".join(out) + r"\Z")


def match(pattern: str, path: str) -> bool:
    """Whether `path` (repo-relative, `/`-separated) matches `pattern`."""
    return compile_glob(pattern).match(path) is not None
