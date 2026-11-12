"""Drift guard: `plugins/super-fr/lenses/` rides install.sh's wholesale marketplace rsync
(spec 2026-11-12-review-lenses R1), as `plugins/super-fr/workflows/` does."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_the_shipped_lenses_exist() -> None:
    assert sorted(p.name for p in (REPO_ROOT / "plugins" / "super-fr" / "lenses").glob("*.yaml"))


def test_the_marketplace_rsync_does_not_exclude_lenses() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    m = re.search(r'rsync[\s\S]{0,200}?"\$PLUGIN_ROOT/"\s+"\$MARKETPLACE_DIR/"', install)
    assert m, "install.sh must rsync $PLUGIN_ROOT/ -> $MARKETPLACE_DIR/"
    assert "lens" not in m.group(0).lower()
    assert "*.yaml" not in m.group(0)


def test_the_shipped_lens_dir_is_found() -> None:
    from fr.lenses.resolve import shipped_lens_dir

    found = shipped_lens_dir()

    assert found is not None
    assert {p.stem for p in found.glob("*.yaml")} >= {"security", "tests", "simplicity", "errors"}
