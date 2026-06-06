"""Lifecycle-independent plan/spec ref normalization + resolution.

The canonical ref form is the bare slug (a plan's folder name, a spec's
filename) — it cannot go stale when `fr archive` / `fr migrate dirs`
relocate the underlying directory. The read side accepts every
historical form forever: bare slug, active path, `implemented/` path,
legacy `archived-plans/` path, and backticked/annotated spec-table
cells (2026-06-06 spec-path-repair design).

Resolution order is documented and stable: the ACTIVE root wins; all
matches are surfaced on `RefResolution.matches` so callers can warn on
ambiguity, and `RefResolution.tried` carries every candidate for loud
not-found reporting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PLACEHOLDERS = ("—", "-", "")

# Roots tried in order — active first, canonical archive, legacy archive.
PLAN_ROOTS = ("plans", "implemented/plans", "archived-plans")
SPEC_ROOTS = ("specs", "implemented/specs", "archived-specs")

_BACKTICK_RE = re.compile(r"`([^`]*)`")


@dataclass(frozen=True)
class RefResolution:
    """Outcome of resolving one ref against the lifecycle roots."""

    slug: str
    path: Path | None  # first match in root order; None when absent
    tried: tuple[Path, ...]  # every candidate, in order
    matches: tuple[Path, ...]  # all roots that matched (ambiguity signal)


def _token(ref: str) -> str:
    """Extract the path token from a raw cell/field value.

    A backticked span wins (annotated cells: `` `path` (note) ``);
    otherwise the first whitespace-delimited token.
    """
    s = ref.strip()
    m = _BACKTICK_RE.search(s)
    if m:
        return m.group(1).strip()
    return s.split()[0] if s.split() else ""


def plan_slug(ref: str) -> str:
    """Normalize any historical ref form to the bare slug.

    Strips backticks/annotations, trailing slashes, and any directory
    prefix — the slug is always the last path segment. Placeholders
    (`—`, `-`, empty) normalize to the empty string.
    """
    token = _token(ref)
    if token in _PLACEHOLDERS:
        return ""
    return token.rstrip("/").rsplit("/", 1)[-1]


def _resolve(
    ref: str, repo_root: Path, roots: tuple[str, ...], *, is_dir: bool, suffix: str = ""
) -> RefResolution:
    slug = plan_slug(ref)
    if not slug:
        return RefResolution(slug="", path=None, tried=(), matches=())
    if suffix and not slug.endswith(suffix):
        slug += suffix
    sp = repo_root / "docs" / "superpowers"
    tried = tuple(sp.joinpath(*root.split("/")) / slug for root in roots)
    exists = Path.is_dir if is_dir else Path.is_file
    matches = tuple(p for p in tried if exists(p))
    return RefResolution(
        slug=slug,
        path=matches[0] if matches else None,
        tried=tried,
        matches=matches,
    )


def resolve_plan_ref(ref: str, repo_root: Path) -> RefResolution:
    """Resolve a plan ref (any form) to its directory, active root first."""
    return _resolve(ref, repo_root, PLAN_ROOTS, is_dir=True)


def resolve_spec_ref(ref: str, repo_root: Path) -> RefResolution:
    """Resolve a spec ref (any form) to its file, active root first.

    Forgiving on the extension: a bare name without `.md` gets it
    appended (the canonical form keeps the extension).
    """
    return _resolve(ref, repo_root, SPEC_ROOTS, is_dir=False, suffix=".md")
