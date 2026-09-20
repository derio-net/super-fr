"""Drift guard: install.sh must deliver super-fr's OpenCode agents to the
global agents directory too (companion to test_install_copies_opencode_skills.py
and test_install_copies_opencode_commands.py).

OpenCode discovers agents from ~/.config/opencode/agent/<name>.md
(its native global path) — a different mechanism from skills and commands,
but the same "OpenCode has no plugin/marketplace concept" gap applies: an
agent shipped under .opencode/agent/ that install.sh never copies there is
invisible to every OpenCode-using consumer, exactly the failure mode this test
guards against.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_install_copies_every_generated_agent_to_opencode_dir() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    agents = sorted((REPO_ROOT / ".opencode" / "agent").glob("*.md"))
    assert agents, "no generated agents found — expected at least fr-phase-executor.md"
    assert "OPENCODE_AGENTS_DIR" in install, (
        "install.sh must define an OPENCODE_AGENTS_DIR pointing at OpenCode's "
        "native global agents path (~/.config/opencode/agent)"
    )
    assert ".config/opencode/agent" in install, (
        "OPENCODE_AGENTS_DIR must point at ~/.config/opencode/agent — OpenCode's own global path"
    )
    assert ".opencode/agent" in install and "OPENCODE_AGENTS_DIR" in install, (
        "install.sh must copy from the repo's own .opencode/agent/ into OPENCODE_AGENTS_DIR"
    )


def test_install_gates_opencode_agent_delivery_on_opt_in() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    # Must reuse the SAME opt-in gate as skill/command delivery, not invent a third one.
    assert "OPENCODE_SKILLS_INSTALL" in install, (
        "install.sh must gate OpenCode agent delivery on the same "
        "OPENCODE_SKILLS_INSTALL=1 / existing ~/.config/opencode opt-in as skill/"
        "command delivery — it must not assume every operator uses OpenCode."
    )


def test_uninstall_removes_opencode_agent_copies() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    uninstall_block = install.split('"${1:-}" == "--uninstall"', 1)[1]
    assert "OPENCODE_AGENTS_DIR" in uninstall_block, (
        "install.sh --uninstall must remove the OpenCode agent copies it created"
    )


def test_install_runs_agents_delivery_after_fr_cli_install() -> None:
    """Agents delivery must run AFTER step 10 (fr CLI install) because it
    calls `fr models resolve`."""
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()

    # Find the section markers
    fr_cli_comment = "# 10. fr CLI"
    # The actual agent delivery implementation is marked by a comment unique to it
    agents_delivery_comment = "# Derive the tier from the filename suffix"

    fr_cli_idx = install.find(fr_cli_comment)
    agent_delivery_idx = install.find(agents_delivery_comment)

    assert fr_cli_idx != -1, "Could not find '# 10. fr CLI' section marker"
    assert agent_delivery_idx != -1, "Could not find agents delivery implementation"
    assert fr_cli_idx < agent_delivery_idx, (
        "Agents delivery implementation must appear AFTER the fr CLI install block "
        "(section 10) because it needs `fr models resolve`"
    )


def test_install_calls_fr_models_resolve_for_agents() -> None:
    """Agent delivery must attempt to resolve models using `fr models resolve`."""
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    assert "fr models resolve --harness opencode" in install, (
        "install.sh must call `fr models resolve --harness opencode` "
        "to resolve agent models from the operator's bindings"
    )
