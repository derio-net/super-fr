"""Probe: edit gate allows write in valid fr worktree with marker (negative control)."""

import pytest


def test_edit_gate_allows_placeholder():
    """Placeholder - requires fr worktree setup with valid .fr-isolation marker."""
    pytest.skip("Full probe requires fr worktree with valid isolation marker - see issue #563")
