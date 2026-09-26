#!/usr/bin/env python3
"""Change fragments: the one schema (spec 2026-09-26-version-bump-churn §3.A).

A PR that needs a release adds `.changes/<branch-slug>.yaml`:

    bump: minor            # patch | minor | major
    summary: one line, non-empty

`bump` and `summary` are required and no other key is accepted. The CI gate
(`check-change-fragment.py`), the release script and the unit tests all import
this module, so there is exactly one definition of a valid fragment.

`.changes/` is super-fr's own release plumbing, not an fr artifact kind. The
format is a deliberately tiny subset of YAML — flat `key: scalar` lines, plain
or quoted — parsed here with the stdlib so it runs under `uv run --no-project`.
Anything richer (a block scalar, a continuation line, a nested value) is
refused rather than guessed at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

BUMPS = ("patch", "minor", "major")
KEYS = ("bump", "summary")
CHANGES_DIR = ".changes"
README = "README.md"

_LINE_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:(.*)$")


class FragmentError(ValueError):
    """An invalid fragment; the message names the file and the field."""


@dataclass(frozen=True)
class Fragment:
    path: Path
    bump: str
    summary: str


def _quoted(raw: str) -> str:
    """A quoted scalar, then optionally a ` #` comment; any other trailing text is refused."""
    quote, i = raw[0], 1
    while i < len(raw):
        if quote == "'" and raw.startswith("''", i):
            i += 2
            continue
        if quote == '"' and raw[i] == "\\":
            i += 2
            continue
        if raw[i] == quote:
            break
        i += 1
    else:
        raise ValueError("unterminated quoted value")
    body, rest = raw[1:i], raw[i + 1 :]
    if rest.strip() and not re.match(r"\s+#", rest):
        raise ValueError(f"unexpected text after the closing quote: {rest.strip()!r}")
    return body.replace("''", "'") if quote == "'" else body.replace('\\"', '"')


def _scalar(raw: str) -> str:
    """A plain or quoted YAML scalar on one line; either may carry a ` #` comment."""
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        return _quoted(raw)
    if raw.startswith("#"):
        return ""
    return re.split(r"\s+#", raw, maxsplit=1)[0].strip()


def parse_text(text: str, name: str) -> tuple[str, str]:
    """Validate fragment text; return `(bump, summary)` or raise naming `name`."""

    def fail(field: str, why: str) -> FragmentError:
        return FragmentError(f"{name}: {field}: {why}")

    values: dict[str, str] = {}
    last: str | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace():
            raise fail(last or "fragment", "must be a single line (continuation line found)")
        match = _LINE_RE.match(line)
        if not match:
            raise fail("fragment", f"not a `key: value` line: {line!r}")
        key, raw = match.group(1), match.group(2)
        if key not in KEYS:
            raise fail(key, f"unknown key (allowed: {', '.join(KEYS)})")
        if key in values:
            raise fail(key, "duplicate key")
        if raw.strip()[:1] in ("|", ">"):
            raise fail(key, "must be a single line (block scalar found)")
        try:
            values[key] = _scalar(raw)
        except ValueError as exc:
            raise fail(key, str(exc)) from None
        last = key

    bump = values.get("bump")
    if bump is None:
        raise fail("bump", "missing")
    if bump not in BUMPS:
        raise fail("bump", f"{bump!r} is not one of {', '.join(BUMPS)}")
    summary = values.get("summary")
    if summary is None:
        raise fail("summary", "missing")
    if not summary.strip():
        raise fail("summary", "must not be empty")
    if "\n" in summary:
        raise fail("summary", "must be a single line")
    return bump, summary.strip()


def parse_fragment(path: Path) -> Fragment:
    path = Path(path)
    bump, summary = parse_text(path.read_text(), str(path))
    return Fragment(path, bump, summary)


def is_fragment_path(rel: str) -> bool:
    """A repo-relative path that is a fragment: `.changes/<name>.yaml`, top level."""
    parts = rel.split("/")
    return len(parts) == 2 and parts[0] == CHANGES_DIR and parts[1].endswith(".yaml")


def aggregate(fragments: list[Fragment]) -> str | None:
    """The highest bump among `fragments`, or None when there are none."""
    if not fragments:
        return None
    return max((f.bump for f in fragments), key=BUMPS.index)


def bumped(version: str, bump: str | None) -> str:
    """`version` moved by `bump` (None leaves it as is)."""
    if bump is None:
        return version
    major, minor, patch = (int(p) for p in version.split("."))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"unknown bump {bump!r}")


def load_pending(repo: Path) -> list[Fragment]:
    """Every fragment under `<repo>/.changes/`, sorted by name; invalid ones raise."""
    directory = Path(repo) / CHANGES_DIR
    if not directory.is_dir():
        return []
    return [parse_fragment(p) for p in sorted(directory.glob("*.yaml")) if p.name != README]
