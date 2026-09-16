"""Drift guard: the shipped output style must survive install.sh's rsync.

`plugins/super-fr/output-styles/` is a new shipped category (spec
2026-09-14-ste-output-tone §5.D). Like `plugins/super-fr/workflows/`, it lives
INSIDE `plugins/super-fr/`, so it rides the wholesale `$PLUGIN_ROOT/` ->
`$MARKETPLACE_DIR/` rsync and has no per-file `cp` line to grep for. What this
pins is that nothing in that rsync would drop it — an `--exclude` added for an
unrelated reason, or a narrower source path. Modelled on
`test_install_copies_workflows.py` (phase 8 review, finding M6).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STYLES_DIR = REPO_ROOT / "plugins" / "super-fr" / "output-styles"


def _marketplace_rsync_line(install_text: str) -> str:
    m = re.search(r'rsync[\s\S]{0,200}?"\$PLUGIN_ROOT/"\s+"\$MARKETPLACE_DIR/"', install_text)
    assert m, "install.sh must rsync $PLUGIN_ROOT/ -> $MARKETPLACE_DIR/ (the marketplace copy)"
    return m.group(0)


def test_at_least_one_shipped_output_style_exists() -> None:
    styles = sorted(STYLES_DIR.glob("*.md"))
    assert styles, "no shipped output style found — expected simplified-technical-english.md"


def test_the_shipped_style_is_opt_in() -> None:
    """A forced style would override the operator's own choice (spec d7)."""
    for style in sorted(STYLES_DIR.glob("*.md")):
        assert "force-for-plugin" not in style.read_text(), f"{style.name} forces itself on"


def test_the_marketplace_rsync_does_not_exclude_output_styles() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    rsync_line = _marketplace_rsync_line(install)
    assert "output-style" not in rsync_line.lower(), (
        "the marketplace rsync must not carry an output-styles --exclude — "
        "the style is delivered by NOT being excluded from the wholesale copy"
    )
    assert "*.md" not in rsync_line, "must not exclude *.md wholesale"
