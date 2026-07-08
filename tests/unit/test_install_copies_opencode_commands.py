"""Drift guard: install.sh must deliver super-fr's OpenCode slash commands to
the global commands directory too (companion to
test_install_copies_opencode_skills.py, #opencode-command-support).

OpenCode discovers slash commands from ~/.config/opencode/commands/<name>.md
(its native global path, docs: https://opencode.ai/docs/commands) — a
different mechanism from skills, but the same "OpenCode has no
plugin/marketplace concept" gap applies: a command shipped under
.opencode/commands/ that install.sh never copies there is invisible to every
OpenCode-using consumer, exactly the failure mode
test_install_copies_opencode_skills.py guards for skills.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_install_copies_every_generated_command_to_opencode_dir() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    commands = sorted((REPO_ROOT / ".opencode" / "commands").glob("*.md"))
    assert commands, "no generated commands found — expected at least fr-goal.md"
    assert "OPENCODE_COMMANDS_DIR" in install, (
        "install.sh must define an OPENCODE_COMMANDS_DIR pointing at OpenCode's "
        "native global commands path (~/.config/opencode/commands)"
    )
    assert ".config/opencode/commands" in install, (
        "OPENCODE_COMMANDS_DIR must point at ~/.config/opencode/commands — OpenCode's "
        "own global path"
    )
    assert ".opencode/commands" in install and "OPENCODE_COMMANDS_DIR" in install, (
        "install.sh must copy from the repo's own .opencode/commands/ into "
        "OPENCODE_COMMANDS_DIR"
    )


def test_install_gates_opencode_command_delivery_on_opt_in() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    # Must reuse the SAME opt-in gate as skill delivery, not invent a second one.
    assert "OPENCODE_SKILLS_INSTALL" in install, (
        "install.sh must gate OpenCode command delivery on the same "
        "OPENCODE_SKILLS_INSTALL=1 / existing ~/.config/opencode opt-in as skill "
        "delivery — it must not assume every operator uses OpenCode."
    )


def test_uninstall_removes_opencode_command_copies() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    uninstall_block = install.split('"${1:-}" == "--uninstall"', 1)[1]
    assert "OPENCODE_COMMANDS_DIR" in uninstall_block, (
        "install.sh --uninstall must remove the OpenCode command copies it created"
    )
