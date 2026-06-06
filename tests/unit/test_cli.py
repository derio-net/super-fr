"""Tests for the public `vk` CLI surface.

Specifically: the bridge daemon must NOT appear as a public subcommand
(E1). It's invoked from a wrapper that `install.sh --install-bridge`
writes, which exec's `python -m fr_dispatch`. Surfacing it as a `vk
bridge` verb would let operators run it ad-hoc and bypass the
lock-file guard.
"""

from __future__ import annotations

import subprocess
import sys


def test_no_bridge_verb_exposed() -> None:  # E1
    """`vk --help` must NOT advertise a `bridge` subcommand."""
    result = subprocess.run(
        [sys.executable, "-m", "fr", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "bridge" not in result.stdout.lower(), (
        f"`bridge` must not appear in `vk --help`:\n{result.stdout}"
    )
