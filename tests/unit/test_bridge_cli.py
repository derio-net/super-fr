"""Unit tests for `vk.bridge.cli` — E1, G1, G5.

Pins the CLI surface (no public `bridge` verb on the `vk` command) and
the version-stamped tick banner that ships in the first INFO record of
every tick.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys


def test_no_bridge_verb_exposed():  # E1
    """`vk --help` must NOT advertise a `bridge` subcommand.

    The bridge runs via `python -m vk.bridge` from a wrapper installed
    by `install.sh --install-bridge`; surfacing it as a public verb
    would let operators run it ad-hoc and bypass the lock-file guard.
    """
    result = subprocess.run(
        [sys.executable, "-m", "vk", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "bridge" not in result.stdout.lower(), (
        f"`bridge` must not appear in `vk --help`:\n{result.stdout}"
    )


def test_logging_uses_stdlib_logging(caplog):  # G1
    """A tick emits its banner through the stdlib `logging` framework.

    If `vk.bridge.cli` ever drops back to bare `print(...)`, caplog
    captures nothing and the test fails.
    """
    from vk.bridge import cli

    with caplog.at_level(logging.INFO, logger="vk.bridge"):
        rc = cli.main(["--dry-run"])
    assert rc == 0
    assert len(caplog.records) > 0


def test_tick_first_log_line_has_version_and_timestamp(caplog):  # G5
    """First INFO record matches the documented banner shape."""
    from vk.bridge import cli

    with caplog.at_level(logging.INFO, logger="vk.bridge"):
        rc = cli.main(["--dry-run"])
    assert rc == 0
    first_record = caplog.records[0]
    pattern = (
        r"^\[bridge\] - v\d+\.\d+\.\d+ - "
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC - tick$"
    )
    assert re.match(pattern, first_record.getMessage()), (
        f"banner did not match: {first_record.getMessage()!r}"
    )
