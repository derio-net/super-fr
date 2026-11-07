"""The briefs and `fr pickup` carry the commit templates (spec
2026-11-04-repo-feature-settings R14)."""

from __future__ import annotations

from pathlib import Path

from fr.commands.pickup_cmd import _commit_template_lines
from fr.commands.run_cmd import commit_templates_brief

from tests.unit.settings_repo import git, land_on_main, make_repo


def test_the_brief_carries_both_templates_and_selects_with_issue_by_the_runs_issue(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, 'git:\n  commit:\n    without_issue: "[{scope}] {summary}"\n')
    git(repo, "switch", "-q", "-c", "feat/x")

    assert commit_templates_brief(repo, None) == {
        "use": "without_issue",
        "with_issue": "{type}({scope}): {summary} (#{issue})",
        "without_issue": "[{scope}] {summary}",
        "issue": None,
    }
    assert commit_templates_brief(repo, 7)["use"] == "with_issue"


def test_pickup_prints_the_templates_and_fr_push(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    land_on_main(repo, 'git:\n  commit:\n    without_issue: "[{scope}] {summary}"\n')
    git(repo, "switch", "-q", "-c", "feat/x")

    text = "\n".join(_commit_template_lines(repo))

    assert "`[{scope}] {summary}`" in text
    assert "{type}({scope}): {summary} (#{issue})" in text
    assert "fr push" in text
