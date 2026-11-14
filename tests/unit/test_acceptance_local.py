"""The `local` acceptance status (spec 2026-11-14-acceptance-local-status)."""

from __future__ import annotations


def test_the_module_imports() -> None:
    import fr.acceptance.local as local

    assert "2026-11-14-acceptance-local-status" in (local.__doc__ or "")
