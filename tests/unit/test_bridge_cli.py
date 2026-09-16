"""Unit tests for `fr_dispatch.cli` — G1, G5.

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

    If `fr_dispatch.cli` ever drops back to bare `print(...)`, caplog
    captures nothing and the test fails.
    """
    from fr_vk import bridge_cli as cli

    with caplog.at_level(logging.INFO, logger="fr_dispatch"):
        rc = cli.main(["--dry-run"])
    assert rc == 0
    assert len(caplog.records) > 0


def test_tick_first_log_line_has_version_and_timestamp(caplog):  # G5
    """First INFO record matches the documented banner shape."""
    from fr_vk import bridge_cli as cli

    with caplog.at_level(logging.INFO, logger="fr_dispatch"):
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


# ---------- fr-spelling rename (#272): lock path + FR_BRIDGE_* dual-read ----------


def test_default_lock_paths_are_fr_spelled():
    from fr_vk import bridge_cli as cli

    assert cli._DEFAULT_LOCK_PATH == "/var/run/fr-bridge.lock"
    assert cli._FALLBACK_LOCK_PATH == "/tmp/fr-bridge.lock"


def test_bridge_env_fr_first(monkeypatch, capsys):
    from fr_vk.config import bridge_env

    monkeypatch.setenv("FR_BRIDGE_LOCK_PATH", "/tmp/a")
    monkeypatch.setenv("VK_BRIDGE_LOCK_PATH", "/tmp/b")
    assert bridge_env("LOCK_PATH") == "/tmp/a"
    assert "legacy" not in capsys.readouterr().err


def test_bridge_env_vk_ignored(monkeypatch, capsys):
    from fr_vk.config import bridge_env

    monkeypatch.delenv("FR_BRIDGE_REPOS", raising=False)
    monkeypatch.setenv("VK_BRIDGE_REPOS", "/x")
    assert bridge_env("REPOS") is None
    assert "legacy" not in capsys.readouterr().err


def test_bridge_env_absent_is_none(monkeypatch, capsys):
    from fr_vk.config import bridge_env

    monkeypatch.delenv("FR_BRIDGE_REPOS", raising=False)
    monkeypatch.delenv("VK_BRIDGE_REPOS", raising=False)
    assert bridge_env("REPOS") is None
    assert capsys.readouterr().err == ""


def test_vibekanban_domain_env_not_renamed():
    """VK_DERIO_OPS_PROJECT_ID names the VibeKanban board (product domain,
    not rebrand residue) — it must NOT move to the FR_ prefix."""
    import inspect

    from fr_vk import bridge_cli as cli

    src = inspect.getsource(cli)
    assert "VK_DERIO_OPS_PROJECT_ID" in src
    assert "FR_DERIO_OPS_PROJECT_ID" not in src
