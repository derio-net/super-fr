"""Segment-aware globs for `fr docs` (spec 2026-11-11-docs-currency R2)."""

from __future__ import annotations


def test_the_package_imports() -> None:
    import fr.docs

    assert fr.docs.__doc__
