"""install.sh registers fr's WorktreeCreate/WorktreeRemove hooks in settings.json.

Found live on 2026-09-24 (Claude Code 2.1.281): the plugin's ``hooks.json``
registers both hooks, but ``claude --worktree <name>`` never invokes a
PLUGIN-registered ``WorktreeCreate``. The session lands in Claude's native
``<repo>/.claude/worktrees/<name>``, outside fr. The same scripts registered in
``~/.claude/settings.json`` do fire, for creation and for removal on exit.
So install.sh registers them there too, and the tests below pin that the
registration is:

- present, exactly once per event, pointing at the plugin cache's ``current``
  link (so it follows every upgrade without being rewritten);
- idempotent, and converging: a stale fr entry (an older path) is replaced,
  not duplicated;
- polite: another tool's hook on the same event is kept;
- reversible: ``--uninstall`` removes exactly fr's entries.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.integration.test_install_marketplace_namespace import (  # noqa: F401
    fake_home,
    home_with_plugin_state,
)
from tests.integration.test_install_sh import _run_install

EVENTS = {"WorktreeCreate": "fr-worktree-create.sh", "WorktreeRemove": "fr-worktree-remove.sh"}
FOREIGN = {"type": "command", "command": "echo someone-elses-hook"}


def _settings(home: Path) -> dict:
    return json.loads((home / ".claude" / "settings.json").read_text())


def _expected(home: Path, script: str) -> str:
    return (
        f'bash "{home}/.claude/plugins/cache/derio-net--super-fr/super-fr/current/hooks/{script}"'
    )


def _commands(settings: dict, event: str) -> list[str]:
    return [
        h["command"]
        for group in settings.get("hooks", {}).get(event, [])
        for h in group.get("hooks", [])
    ]


def test_install_registers_both_worktree_hooks_once(home_with_plugin_state: Path) -> None:  # noqa: F811
    home = home_with_plugin_state
    _run_install(home)
    settings = _settings(home)
    for event, script in EVENTS.items():
        assert _commands(settings, event) == [_expected(home, script)], event


def test_install_is_idempotent(home_with_plugin_state: Path) -> None:  # noqa: F811
    home = home_with_plugin_state
    _run_install(home)
    _run_install(home)
    settings = _settings(home)
    for event, script in EVENTS.items():
        assert _commands(settings, event) == [_expected(home, script)], event


def test_install_replaces_a_stale_fr_entry_instead_of_adding_one(
    home_with_plugin_state: Path,  # noqa: F811
) -> None:
    home = home_with_plugin_state
    stale = {
        event: [{"hooks": [{"type": "command", "command": f"bash /old/versioned/path/{script}"}]}]
        for event, script in EVENTS.items()
    }
    (home / ".claude" / "settings.json").write_text(json.dumps({"hooks": stale}))
    _run_install(home)
    settings = _settings(home)
    for event, script in EVENTS.items():
        assert _commands(settings, event) == [_expected(home, script)], event


def test_install_keeps_another_tools_hook_on_the_same_event(
    home_with_plugin_state: Path,  # noqa: F811
) -> None:
    home = home_with_plugin_state
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"WorktreeCreate": [{"hooks": [FOREIGN]}]}})
    )
    _run_install(home)
    commands = _commands(_settings(home), "WorktreeCreate")
    assert FOREIGN["command"] in commands
    assert _expected(home, EVENTS["WorktreeCreate"]) in commands
    assert len(commands) == 2


def test_uninstall_removes_only_frs_worktree_hooks(home_with_plugin_state: Path) -> None:  # noqa: F811
    home = home_with_plugin_state
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"WorktreeCreate": [{"hooks": [FOREIGN]}]}})
    )
    _run_install(home)
    _run_install(home, "--uninstall")
    settings = _settings(home)
    assert _commands(settings, "WorktreeCreate") == [FOREIGN["command"]]
    assert "WorktreeRemove" not in settings.get("hooks", {}), (
        "an event left with no hooks must be dropped, not kept as an empty list"
    )


def test_command_survives_a_home_with_a_space(tmp_path: Path) -> None:
    """Claude Code runs `command` through a shell, so an unquoted path under a
    HOME like `/Users/Jane Doe` would word-split into two arguments."""
    import shlex

    home = tmp_path / "with space" / "home"
    (home / "bin").mkdir(parents=True)
    vk = home / "bin" / "vibe-kanban-mcp"
    vk.write_text("#!/bin/sh\necho stub\n")
    vk.chmod(0o755)
    plugins = home / ".claude" / "plugins"
    plugins.mkdir(parents=True)
    (plugins / "installed_plugins.json").write_text(json.dumps({"plugins": {}, "version": 2}))
    (plugins / "known_marketplaces.json").write_text(json.dumps({}))
    (home / ".claude" / "settings.json").write_text(json.dumps({}))
    _run_install(home)
    for event, script in EVENTS.items():
        (command,) = _commands(_settings(home), event)
        argv = shlex.split(command)
        assert argv == [
            "bash",
            f"{home}/.claude/plugins/cache/derio-net--super-fr/super-fr/current/hooks/{script}",
        ], command


def test_a_malformed_foreign_group_is_left_alone(home_with_plugin_state: Path) -> None:  # noqa: F811
    """A group with no `hooks` array must neither abort the install nor vanish."""
    home = home_with_plugin_state
    odd = {"matcher": "someone-elses"}
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"WorktreeCreate": [odd]}})
    )
    _run_install(home)
    groups = _settings(home)["hooks"]["WorktreeCreate"]
    assert odd in groups
    assert _commands(_settings(home), "WorktreeCreate") == [
        _expected(home, EVENTS["WorktreeCreate"])
    ]


def test_an_intentionally_empty_hooks_object_is_not_deleted(
    home_with_plugin_state: Path,  # noqa: F811
) -> None:
    home = home_with_plugin_state
    (home / ".claude" / "settings.json").write_text(json.dumps({"hooks": {}}))
    _run_install(home, "--uninstall")
    assert _settings(home) == {"hooks": {}}
