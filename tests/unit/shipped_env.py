"""`FR_SHIPPED_DEFAULTS_DIR` for a test that built a flat directory of one kind's manifests.

The per-kind `FR_SHIPPED_WORKFLOWS_DIR` / `_VERIFICATIONS_DIR` / `_LENSES_DIR` are refused
from fr 9.2 (spec 2026-11-28-s1-followups R6), so a test that set one would turn red the
day a release crosses the gate (R10). `defaults_root(flat, kind)` gives the one variable's
value instead: a tree beside *flat* whose `<kind>/` is a link to it, so the test keeps
writing its manifests where it always did.
"""

from __future__ import annotations

import os
from pathlib import Path


def defaults_root(flat: Path, kind: str = "workflows") -> Path:
    """A `FR_SHIPPED_DEFAULTS_DIR` whose `<kind>/` is *flat* (created if missing)."""
    flat = Path(flat).absolute()
    if flat.name == kind:  # already `<root>/<kind>`: nothing to build
        return flat.parent
    root = flat.parent / f"{flat.name}.defaults"
    link = root / kind
    if not link.is_symlink():
        root.mkdir(parents=True, exist_ok=True)
        # Relative, so a tree copied from a fixture template still points at its own copy.
        link.symlink_to(os.path.relpath(flat, root), target_is_directory=True)
    return root
