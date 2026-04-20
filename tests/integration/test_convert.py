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

    def test_add_deps_prompt_confirms_before_writing(self, tmp_repo: Path) -> None:
        """PROMPT mode (no --yes / --dry-run) shows the diff and asks Y/N.

        Regression for PR #32 review M-3: previously PROMPT wrote the file
        BEFORE reaching the prompt branch, so 'no' still left the file
        modified and no commit was made. Fix restructured the flow to
        compute on a temp, prompt, then write only on confirmation.
        """
        src = Path(__file__).parent.parent / "fixtures" / "plans" / "phased-no-deps.md"
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan = plans_dir / "2026-04-20-legacy-prompt.md"
        shutil.copy(src, plan)
        before = plan.read_text()

        # User answers "n" → no write, no commit, file unchanged.
        result = runner.invoke(app, ["plan", "convert", str(plan), "--add-deps"], input="n\n")
        assert result.exit_code == 0, result.stdout
        assert "Aborted" in result.stdout
        assert plan.read_text() == before, "file must not change when prompt is declined"

        # User answers "y" → write + commit, file changed.
        result = runner.invoke(app, ["plan", "convert", str(plan), "--add-deps"], input="y\n")
        assert result.exit_code == 0, result.stdout
        after = plan.read_text()
        assert after != before
        assert "**Depends on:** —" in after
