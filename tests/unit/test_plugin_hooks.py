"""Plugin hook registration: hooks.json shape and shipped scripts."""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "plugins" / "super-fr" / "hooks"


class TestPluginHooks:
    def test_hooks_json_parses(self) -> None:
        data = json.loads((HOOKS_DIR / "hooks.json").read_text())
        events = data["hooks"]
        assert {m["matcher"] for m in events["PostToolUse"]} == {"Skill"}
        assert {m["matcher"] for m in events["PreToolUse"]} == {"Bash"}

    def test_registered_scripts_exist_and_are_executable(self) -> None:
        data = json.loads((HOOKS_DIR / "hooks.json").read_text())
        commands = [
            h["command"]
            for matchers in data["hooks"].values()
            for m in matchers
            for h in m["hooks"]
        ]
        assert commands, "no hook commands registered"
        for command in commands:
            assert command.startswith("${CLAUDE_PLUGIN_ROOT}/"), command
            rel = command.replace("${CLAUDE_PLUGIN_ROOT}/", "")
            script = REPO_ROOT / "plugins" / "super-fr" / rel
            assert script.is_file(), f"missing {script}"
            assert os.access(script, os.X_OK), f"not executable: {script}"
