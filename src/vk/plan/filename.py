"""Filename slug derivation from plan file paths.

Handles both single-dash (YYYY-MM-DD-name.md) and double-dash
(YYYY-MM-DD--layer--details.md) patterns via lstrip("-").
See superpowers-for-vk#5 for discovery context.
"""

from __future__ import annotations

import re
from pathlib import Path


def derive_slug(plan_path: Path) -> str:
    """Extract the slug portion from a date-prefixed plan filename.

    Strips the YYYY-MM-DD prefix and any leading dashes, returning the
    remainder as the slug.  Raises ValueError if the filename has no
    date prefix or yields an empty slug.
    """
    stem = plan_path.stem
    m = re.match(r"^\d{4}-\d{2}-\d{2}", stem)
    if not m:
        msg = f"Plan filename must start with YYYY-MM-DD: {plan_path.name}"
        raise ValueError(msg)
    rest = stem[m.end() :]
    slug = rest.lstrip("-")
    if not slug:
        msg = f"Empty slug after stripping date prefix: {plan_path.name}"
        raise ValueError(msg)
    return slug


def derive_spec_slug(spec_path: Path | str) -> str:
    """Extract the spec slug from a spec filename.

    Strips the YYYY-MM-DD prefix if present (the canonical form is
    `<date>-<name>-design.md`), then strips any trailing `-design`
    suffix. Falls back to the bare stem for spec paths that don't carry
    a date prefix (tests, ad-hoc specs).
    """
    path = Path(spec_path) if isinstance(spec_path, str) else spec_path
    stem = path.stem
    m = re.match(r"^\d{4}-\d{2}-\d{2}", stem)
    rest = stem[m.end() :].lstrip("-") if m else stem
    if rest.endswith("-design"):
        rest = rest[: -len("-design")]
    if not rest:
        msg = f"Empty spec slug derived from: {path.name}"
        raise ValueError(msg)
    return rest


def derive_plan_name(plan_path: Path | str, spec_slug: str) -> str:
    """Extract a plan-name identifier from a plan filename, given the
    spec slug it belongs to.

    Strips the date prefix, the leading <spec_slug>- (if present), and
    any leading 'phase-N-' prefix (the conventional plan-within-spec
    numbering). Falls back to 'phase-N' when the filename has no
    descriptive tail beyond the phase number.

    Edge case: when the plan filename equals the spec slug (e.g. a
    spec with a single plan that shares its name), plan name and spec
    slug coincide. The Issue carries both `spec:<slug>` and
    `plan:<slug>` labels — redundant but consistent for query roll-up.
    """
    plan_path = Path(plan_path) if isinstance(plan_path, str) else plan_path
    full = derive_slug(plan_path)
    rest = full
    if rest.startswith(f"{spec_slug}-"):
        rest = rest[len(spec_slug) + 1 :]
    elif rest == spec_slug:
        rest = ""
    m = re.match(r"^phase-(\d+)(?:-(.+))?$", rest)
    if m:
        descriptor = m.group(2)
        return descriptor if descriptor else f"phase-{m.group(1)}"
    return rest or full
