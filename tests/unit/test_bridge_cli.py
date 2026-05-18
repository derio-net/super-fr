"""Unit tests for `vk.bridge.cli` — G1, G5.

Pins the version-stamped tick banner that ships in the first INFO
record of every tick, and that it flows through stdlib `logging`
rather than bare `print(...)`.

E1 (no public `vk bridge` verb) lives in `test_cli.py` — it asserts
on the public `vk` CLI surface, not the private bridge module.
"""

from __future__ import annotations

import logging
import re


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
