"""Copies of the shipped hook tree that read a chosen release (spec 2026-11-28-s1-followups
R7, R10).

The edit gate's library decides whether S1's transition has ended from its own release:
`$lib/../../.claude-plugin/plugin.json` in the Claude Code plugin, `$lib/../VERSION` in the
Hermes hook tree. A test that drives the REAL hook tree would read the repo's plugin.json,
so it would change sides the day the release crosses 9.2. A test of either side runs a copy
instead, whose version source it chose: `open_hooks()` (9.1.0, the pre-9.2 side) or
`hooks_tree(root, version, layout=...)`. `side_env()` drops an inherited `FR_OLD_PATHS`,
which `pytest --fr-ended` sets for every test and which would end the transition for the
open-side copy too.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS = REPO_ROOT / "plugins" / "super-fr" / "hooks"
OPEN_VERSION = "9.1.0"
ENDED_VERSION = "9.2.0"

Layout = Literal["claude", "hermes", "none"]


def hooks_tree(root: Path, version: str | None, *, layout: Layout = "claude") -> Path:
    """A copy of the shipped hook tree under *root*, reading *version*; returns its hooks dir.

    `claude`: `<root>/super-fr/hooks` beside `<root>/super-fr/.claude-plugin/plugin.json`.
    `hermes`: `<root>/super-fr-hooks` holding `VERSION`, as `fr hermes install` lays it out.
    `none`: `<root>/hooks` with no version source at all. A None *version* writes none.
    """
    if layout == "claude":
        hooks = root / "super-fr" / "hooks"
    elif layout == "hermes":
        hooks = root / "super-fr-hooks"
    else:
        hooks = root / "hooks"
    shutil.copytree(HOOKS, hooks)
    if version is not None and layout == "claude":
        manifest = root / "super-fr" / ".claude-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": "super-fr", "version": version}, indent=2) + "\n")
    elif version is not None and layout == "hermes":
        (hooks / "VERSION").write_text(f"{version}\n")
    return hooks


_OPEN: Path | None = None


def open_hooks() -> Path:
    """One process-wide copy of the hook tree on the pre-9.2 side (a 9.1.0 plugin.json)."""
    global _OPEN
    if _OPEN is None:
        root = Path(tempfile.mkdtemp(prefix="fr-open-hooks-"))
        atexit.register(shutil.rmtree, root, ignore_errors=True)
        _OPEN = hooks_tree(root, OPEN_VERSION)
    return _OPEN


def side_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """`os.environ` with no inherited `FR_OLD_PATHS`, plus *extra*."""
    env = {k: v for k, v in os.environ.items() if k != "FR_OLD_PATHS"}
    env.update(extra or {})
    return env
