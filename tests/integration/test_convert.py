"""CLI integration tests for vk plan convert."""

from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


class TestAddDepsCli:
    def test_add_deps_via_cli_modifies_file_and_commits(self, tmp_repo: Path) -> None:
        src = Path(__file__).parent.parent / "fixtures" / "plans" / "phased-no-deps.md"
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan = plans_dir / "2026-04-20-legacy.md"
        shutil.copy(src, plan)

        result = runner.invoke(
            app,
            ["plan", "convert", str(plan), "--add-deps", "--yes"],
        )
        assert result.exit_code == 0, result.stdout

        text = plan.read_text()
        assert "**Depends on:** —" in text
        assert "**Depends on:** Phase 1" in text
