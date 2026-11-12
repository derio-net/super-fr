"""Smoke: the settings package exists and `fr settings` is wired in (spec R3)."""

from __future__ import annotations

from fr.cli import app
from typer.testing import CliRunner


def test_the_settings_package_exports_its_surface() -> None:
    from fr.settings import SettingsError, disabled, forge_allows, load_settings

    assert callable(load_settings) and callable(disabled) and callable(forge_allows)
    assert issubclass(SettingsError, Exception)


def test_fr_settings_help_lists_init_show_check() -> None:
    result = CliRunner().invoke(app, ["settings", "--help"])
    assert result.exit_code == 0
    for verb in ("init", "show", "check"):
        assert verb in result.output
