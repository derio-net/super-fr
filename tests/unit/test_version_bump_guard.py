from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-version-bump-needed.py"
spec = importlib.util.spec_from_file_location("check_version_bump_needed", SCRIPT)
assert spec and spec.loader
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_requires_bump_for_shipped_surfaces() -> None:
    assert guard.requires_bump("packages/fr/src/fr/cli.py")
    assert guard.requires_bump("packages/fr-opencode-plugin/src/index.ts")
    assert guard.requires_bump("plugins/super-fr/skills/fr-goal/SKILL.md")
    assert guard.requires_bump("plugins/super-fr/rules/fr-isolation-required.md")
    assert guard.requires_bump("scripts/install.sh")


def test_ignores_docs_tests_and_manifests() -> None:
    assert not guard.requires_bump("README.md")
    assert not guard.requires_bump("AGENTS.md")
    assert not guard.requires_bump("tests/unit/test_version.py")
    assert not guard.requires_bump(".github/workflows/ci.yml")
    assert not guard.requires_bump("packages/fr-opencode-plugin/package.json")
