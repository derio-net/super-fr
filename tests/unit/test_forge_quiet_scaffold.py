"""R9 (spec 2026-11-04-repo-feature-settings): the CI fr scaffolds makes no forge write the
repo's settings turned off — under `forge.issues: off` no "Technical debt" issue step and
no archive-sweep PR step; under `forge.comments: off` no comment step."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance import scaffold
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.settings_repo import land_on_main, make_repo

WORKFLOW = ".github/workflows/acceptance-report.yml"


def _init(root: Path) -> scaffold.InitOutcome:
    return scaffold.init(
        root, "example-org", "widgets", "github", ci_type="github-actions", tracking_type="github"
    )


def test_by_default_the_debt_steps_are_scaffolded(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    _init(root)
    text = (root / WORKFLOW).read_text()
    assert "fr debt issue --yes" in text and "fr debt archive-pr --yes" in text


def test_issues_off_omits_the_debt_issue_and_archive_sweep_steps_and_says_why(
    tmp_path: Path,
) -> None:
    root = make_repo(tmp_path)
    land_on_main(root, "forge:\n  issues: 'off'\n")
    out = _init(root)
    text = (root / WORKFLOW).read_text()
    assert "fr debt issue" not in text and "archive-pr" not in text
    assert "issues: write" not in text
    assert any("forge.issues: off" in n for n in out.notices), out.notices
    assert "fr acceptance check" in text  # the gate itself stays


@pytest.mark.parametrize("ci_type", ["gitea-actions", "gitlab-ci"])
def test_issues_off_omits_the_debt_job_on_every_platform(tmp_path: Path, ci_type: str) -> None:
    root = make_repo(tmp_path)
    land_on_main(root, "forge:\n  issues: 'off'\n")
    tracking = {"gitea-actions": "gitea", "gitlab-ci": "gitlab"}[ci_type]
    assert scaffold.debt_steps(root, ci_type, tracking) == (
        False,
        "forge.issues: off — the weekly technical-debt steps are omitted",
    )


def test_comments_off_scaffolds_no_comment_step(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    land_on_main(root, "forge:\n  comments: 'off'\n")
    _init(root)
    text = (root / WORKFLOW).read_text().lower()
    assert "comment" not in "\n".join(
        line for line in text.splitlines() if line.strip().startswith(("- name:", "run:"))
    )


def test_refresh_ci_drops_the_debt_steps_once_issues_are_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path)
    (root / ".devcontainer").mkdir()
    (root / ".devcontainer" / "fr-profiles.yaml").write_text(
        "schema_version: 2\nforge: {type: github}\nci: {type: github-actions}\n"
        "tracking: {type: github}\n"
    )
    _init(root)
    assert "fr debt issue" in (root / WORKFLOW).read_text()
    land_on_main(root, "forge:\n  issues: 'off'\n")
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    result = CliRunner().invoke(app, ["acceptance", "init", "--refresh-ci"])
    assert result.exit_code == 0, result.output
    assert "fr debt issue" not in (root / WORKFLOW).read_text()
    assert "forge.issues: off" in result.output
