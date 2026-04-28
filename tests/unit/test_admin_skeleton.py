"""Skeleton tests for vk admin labels-sync — body is in later phases."""

import re

from typer.testing import CliRunner

from vk.commands.admin_cmd import admin_app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes so flag-name assertions are portable across Rich versions."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_labels_sync_help_lists_flags() -> None:
    result = runner.invoke(admin_app, ["labels-sync", "--help"])
    assert result.exit_code == 0
    output = _strip_ansi(result.stdout)
    for flag in ("--owner", "--repo", "--remove-defaults", "--dry-run", "--yes"):
        assert flag in output, f"Expected {flag!r} in help output"


def test_labels_sync_requires_owner() -> None:
    result = runner.invoke(admin_app, ["labels-sync"])
    assert result.exit_code != 0  # missing --owner
