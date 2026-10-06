"""Probe, classifier and cache for `fr.bindings` (spec 2026-10-06-model-binding-churn §A)."""

from __future__ import annotations


def test_the_bindings_package_imports() -> None:
    import fr.bindings

    assert fr.bindings.__doc__
