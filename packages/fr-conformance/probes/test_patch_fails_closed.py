"""Probe: patch on base-clone target is refused."""

import pytest


def test_patch_fails_closed_placeholder():
    """Placeholder - requires fr-enabled repo base clone."""
    pytest.skip("Full probe requires live OpenCode session with plugin - see issue #563")
