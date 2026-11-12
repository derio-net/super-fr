"""Smoke: the fragment and fold modules exist (plan 2026-11-12-acceptance-fragments P1.T1)."""

from __future__ import annotations

from pathlib import Path


def test_the_fragment_and_fold_modules_import() -> None:
    from fr.acceptance.fold import fold
    from fr.acceptance.fragment import FRAGMENTS_DIR, parse_fragment

    assert callable(parse_fragment)
    assert callable(fold)
    assert FRAGMENTS_DIR == Path("docs/acceptance/features")
