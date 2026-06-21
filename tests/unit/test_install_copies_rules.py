"""Drift guard: every shipped rule must be installed by install.sh (#328).

A rule under `plugins/super-fr/rules/` that install.sh never `cp`s into
`~/.claude/rules/` ships dead — present in the repo, absent on every consumer.
This fails loud so a new rule cannot be added without wiring its install.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_install_copies_every_shipped_rule() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    rules = sorted((REPO_ROOT / "plugins" / "super-fr" / "rules").glob("*.md"))
    assert rules, "no shipped rules found — expected at least fr-plan-override.md"
    missing = [r.name for r in rules if f"rules/{r.name}" not in install]
    assert not missing, f"install.sh does not install these rules: {missing}"
