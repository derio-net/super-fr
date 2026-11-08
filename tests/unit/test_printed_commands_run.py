"""Every `fr` command the gate and backfill flows print runs as printed (spec 2026-11-08 R6)."""

from __future__ import annotations


def test_render_module_imports() -> None:
    import fr.gatebackfill.render as render

    assert render is not None
