"""Tests for the public `fr` CLI surface.

Specifically: no bridge daemon may appear as a public subcommand (E1).
Surfacing one as a `bridge` verb would let operators run it ad-hoc and
bypass its lock-file guard.
"""

from __future__ import annotations

import subprocess
import sys


def test_no_bridge_verb_exposed() -> None:  # E1
    """`fr --help` must NOT advertise a `bridge` subcommand."""
    result = subprocess.run(
        [sys.executable, "-m", "fr", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "bridge" not in result.stdout.lower(), (
        f"`bridge` must not appear in `fr --help`:\n{result.stdout}"
    )
