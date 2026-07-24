"""Drift guard: install.sh must deliver super-fr to a Hermes Agent home too.

Hermes discovers skills from ~/.hermes/skills/<category>/<name>/SKILL.md and
loads its own config.yaml / SOUL.md — so install.sh gates a Hermes block on
opt-in, byte-copies the fr-category skills, and delegates the invasive,
reversible mutations (hooks, allowlist, SOUL block) to the tested
`fr hermes install` subcommand. A shipped skill install.sh never copies there is
invisible to every Hermes consumer.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _install() -> str:
    return (REPO_ROOT / "scripts" / "install.sh").read_text()


def test_defines_hermes_home_at_dot_hermes() -> None:
    install = _install()
    assert "HERMES_HOME" in install, "install.sh must define HERMES_HOME"
    assert ".hermes" in install, "HERMES_HOME must root at ~/.hermes"


def test_gates_hermes_delivery_on_opt_in() -> None:
    install = _install()
    assert "HERMES_SKILLS_INSTALL" in install, (
        "install.sh must gate Hermes delivery on HERMES_SKILLS_INSTALL=1 or an "
        "existing ~/.hermes directory — never assume every operator uses Hermes."
    )


def test_copies_fr_category_skills() -> None:
    install = _install()
    assert ".hermes/skills/fr" in install, (
        "install.sh must copy the fr-category skills mirror into $HERMES_HOME/skills/fr"
    )


def test_invokes_fr_hermes_install() -> None:
    install = _install()
    assert "fr hermes install" in install, (
        "install.sh must delegate the invasive mutations to `fr hermes install`"
    )


def test_uninstall_uses_source_tree_fr_and_removes_skills() -> None:
    install = _install()
    uninstall_block = install.split('"${1:-}" == "--uninstall"', 1)[1]
    assert 'uv run --project "$PLUGIN_ROOT/packages/fr" fr hermes uninstall' in uninstall_block, (
        "install.sh --uninstall must use this checkout's fr code, not a stale installed binary"
    )
    assert "HERMES_HOME" in uninstall_block, (
        "install.sh --uninstall must remove the Hermes skill copies it created"
    )
