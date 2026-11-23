"""Smoke: the settle package exists (spec 2026-11-23-pr-readiness-wait)."""

from __future__ import annotations


def test_the_settle_package_names_its_spec() -> None:
    import fr.settle

    assert fr.settle.__doc__ is not None
    assert "2026-11-23-pr-readiness-wait" in fr.settle.__doc__
