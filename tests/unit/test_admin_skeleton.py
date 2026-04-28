"""Skeleton tests for vk admin labels-sync — body is in later phases."""

from typer.testing import CliRunner

from vk.commands.admin_cmd import admin_app

runner = CliRunner()


def test_labels_sync_help_lists_flags() -> None:
    result = runner.invoke(admin_app, ["labels-sync", "--help"])
    assert result.exit_code == 0
    for flag in ("--owner", "--repo", "--remove-defaults", "--dry-run", "--yes"):
        assert flag in result.stdout


def test_labels_sync_requires_owner() -> None:
    result = runner.invoke(admin_app, ["labels-sync"])
    assert result.exit_code != 0  # missing --owner
