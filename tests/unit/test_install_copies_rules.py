"""Drift guard: every shipped rule must be installed by install.sh (#328).

A rule under `plugins/super-fr/rules/` that is not listed in install.sh's
CLAUDE_RULES array ships dead — present in the repo, absent on every consumer.
This fails loud so a new rule cannot be added without wiring its install.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_install_copies_every_shipped_rule() -> None:
    install = (REPO_ROOT / "scripts" / "install.sh").read_text()
    rules = sorted((REPO_ROOT / "plugins" / "super-fr" / "rules").glob("*.md"))
    assert rules, "no shipped rules found — expected at least fr-plan-override.md"

    # Extract the CLAUDE_RULES array from install.sh
    match = re.search(r"CLAUDE_RULES=\(([^)]+)\)", install, re.DOTALL)
    assert match, "CLAUDE_RULES array not found in install.sh"

    # Extract filenames from the array
    array_content = match.group(1)
    installed_names = set(re.findall(r"([\w.-]+\.md)", array_content))
    assert installed_names, "CLAUDE_RULES array is empty or malformed"

    # Verify all shipped rules are in the array
    shipped_names = {r.name for r in rules}
    missing = shipped_names - installed_names
    assert not missing, f"install.sh's CLAUDE_RULES does not include these rules: {missing}"
