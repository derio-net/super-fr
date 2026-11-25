"""super-fr declares the mirrors that regenerate its generated files, and the globs of the
files they write in whole (spec 2026-11-24-ci-economy R13)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from fr.triage.model import TriageConfig
from fr.triage.regen import is_generated

pytestmark = pytest.mark.own_artifacts

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ("sync-readme", "sync-opencode", "sync-hermes", "sync-agents-data", "sync-defaults-data")


def _config() -> TriageConfig:
    data = yaml.safe_load((ROOT / ".fr" / "triage.yaml").read_text(encoding="utf-8"))
    return TriageConfig.model_validate(data)


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
    return [p for p in out.stdout.decode().split("\0") if p]


def test_the_mirrors_are_the_five_sync_scripts_through_uv_run_frozen() -> None:
    assert _config().mirrors == [
        ["uv", "run", "--frozen", "python", f"scripts/{name}.py"] for name in SCRIPTS
    ]


WRITTEN_IN_WHOLE = (
    ".opencode/skills/fr-triage/SKILL.md",
    ".opencode/instructions/docs-currency.md",
    ".opencode/agent/fr-phase-executor.md",
    ".opencode/commands/fr-triage.md",
    ".hermes/skills/fr/fr-triage/SKILL.md",
    ".hermes/SOUL.d/super-fr-rules.md",
    "packages/fr/src/fr/agents/fr-phase-executor.md",
    "packages/fr/src/fr/defaults/lenses/security.yaml",
    "packages/fr/src/fr/defaults/workflows/fr-goal.yaml",
)


@pytest.mark.parametrize("path", WRITTEN_IN_WHOLE)
def test_the_generated_globs_cover_what_the_mirrors_write_in_whole(path: str) -> None:
    assert is_generated(path, _config().generated)


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "docs/reference/cli.md",
        "packages/fr/src/fr/agents/__init__.py",
        ".opencode/plugins/fr-isolation-required.ts",
        ".hermes/config.snippet.yaml",
        "plugins/super-fr/skills/fr-triage/SKILL.md",
    ],
)
def test_the_generated_globs_leave_block_files_and_sources_out(path: str) -> None:
    assert not is_generated(path, _config().generated)


def test_each_generated_glob_matches_a_tracked_file() -> None:
    tracked = _tracked()
    for glob in _config().generated:
        assert any(is_generated(p, [glob]) for p in tracked), glob
