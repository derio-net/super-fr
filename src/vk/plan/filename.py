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
