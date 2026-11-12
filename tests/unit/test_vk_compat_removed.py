"""The retired `vk` command's compatibility paths are gone (spec 2026-11-12-remove-vk-compat)."""

from __future__ import annotations

import importlib.util


def test_smoke() -> None:
    assert True


def test_init_has_no_migrate_command() -> None:
    from fr.commands.init_cmd import init_app

    names = {c.name or (c.callback.__name__ if c.callback else "") for c in init_app.registered_commands}
    assert "migrate" not in names


def test_isolation_migrate_module_is_gone() -> None:
    assert importlib.util.find_spec("fr.isolation.migrate") is None
