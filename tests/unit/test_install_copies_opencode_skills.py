"""Drift guard: install.sh must deliver super-fr's skills to OpenCode's global
skill directory too (#opencode-adaptation).

OpenCode discovers skills from ~/.config/opencode/skills/<name>/SKILL.md (its
native global path — deliberately not ~/.claude/skills/, which would shadow
the Claude Code plugin-managed copy for operators running both agents). A
skill shipped under plugins/super-fr/skills/ that install.sh never copies
there is invisible to every OpenCode-using consumer, exactly the failure mode
test_install_copies_rules.py guards for rules.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_install_copies_every_shipped_skill_to_opencode_dir() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    skills = sorted((REPO_ROOT / "plugins" / "super-fr" / "skills").glob("*/SKILL.md"))
    assert skills, "no shipped skills found — expected at least fr-goal/SKILL.md"
    assert "OPENCODE_SKILLS_DIR" in install, (
        "install.sh must define an OPENCODE_SKILLS_DIR pointing at OpenCode's "
        "native global skills path (~/.config/opencode/skills)"
    )
    assert ".config/opencode/skills" in install, (
        "OPENCODE_SKILLS_DIR must point at ~/.config/opencode/skills — OpenCode's "
        "own global path, not ~/.claude/skills (would shadow the Claude plugin copy)"
    )
    assert "plugins/super-fr/skills" in install and "OPENCODE_SKILLS_DIR" in install, (
        "install.sh must copy from plugins/super-fr/skills/ into OPENCODE_SKILLS_DIR"
    )


def test_install_gates_opencode_delivery_on_opt_in() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    assert "OPENCODE_SKILLS_INSTALL" in install, (
        "install.sh must gate OpenCode skill delivery on OPENCODE_SKILLS_INSTALL=1 "
        "or an existing ~/.config/opencode directory — it must not assume every "
        "operator uses OpenCode."
    )


def test_uninstall_removes_opencode_skill_copies() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    uninstall_block = install.split('"${1:-}" == "--uninstall"', 1)[1]
    assert "OPENCODE_SKILLS_DIR" in uninstall_block, (
        "install.sh --uninstall must remove the OpenCode skill copies it created"
    )
