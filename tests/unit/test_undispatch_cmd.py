"""`vk undispatch` — inverse of dispatch (2026-06-05 spec, Phase 6)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from fr.cli import app
from fr.commands import undispatch_cmd
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
REPO = "derio-net/superpowers-for-vk"


def _dispatched_plan_repo(tmp_path: Path) -> Path:
    """Plan with phase 1 dispatched to issue #7."""
    plan_dir = tmp_path / "docs" / "superpowers" / "plans" / "2026-05-09-fixture-minimal"
    shutil.copytree(FIXTURE, plan_dir)
    phase = plan_dir / "01.yaml"
    phase.write_text(
        phase.read_text().replace(
            "tracking_issue: null",
            f"tracking_issue: https://github.com/{REPO}/issues/7",
        )
    )
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
    ):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    return plan_dir


def _invoke(monkeypatch, tmp_path, gh, argv):
    monkeypatch.setattr(undispatch_cmd, "_make_gh_client", lambda: gh)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    return CliRunner().invoke(app, argv)


def test_undispatch_dry_run_lists_actions_without_mutating(tmp_path, monkeypatch):
    plan_dir = _dispatched_plan_repo(tmp_path)
    gh = FakeGhClient()
    gh.add_issue(REPO, 7, state="OPEN")
    result = _invoke(monkeypatch, tmp_path, gh, ["undispatch", str(plan_dir.relative_to(tmp_path))])
    assert result.exit_code == 0, result.output
    assert "would close" in result.output
    assert "issues/7" in result.output
    assert gh.attempted_mutations == 0
    assert "tracking_issue: https" in (plan_dir / "01.yaml").read_text()
    assert "dry-run" in result.output


def test_undispatch_yes_closes_with_comment_and_nulls_field(tmp_path, monkeypatch):
    plan_dir = _dispatched_plan_repo(tmp_path)
    gh = FakeGhClient()
    gh.add_issue(REPO, 7, state="OPEN")
    result = _invoke(
        monkeypatch,
        tmp_path,
        gh,
        ["undispatch", str(plan_dir.relative_to(tmp_path)), "--yes"],
    )
    assert result.exit_code == 0, result.output
    comments = [c for c in gh.calls if c[0] == "comment_issue"]
    assert len(comments) == 1
    assert "vk undispatch" in comments[0][1]["body"]
    assert "2026-05-09-fixture-minimal" in comments[0][1]["body"]
    closes = [c for c in gh.calls if c[0] == "edit_issue_state"]
    assert len(closes) == 1
    assert closes[0][1]["state"] == "CLOSED"
    assert closes[0][1]["reason"] == "not planned"
    assert "tracking_issue: null" in (plan_dir / "01.yaml").read_text()


def test_undispatch_is_idempotent(tmp_path, monkeypatch):
    """Re-run after success: already-closed Issue and already-null field
    are skipped, exit 0."""
    plan_dir = _dispatched_plan_repo(tmp_path)
    gh = FakeGhClient()
    gh.add_issue(REPO, 7, state="OPEN")
    first = _invoke(
        monkeypatch,
        tmp_path,
        gh,
        ["undispatch", str(plan_dir.relative_to(tmp_path)), "--yes"],
    )
    assert first.exit_code == 0
    second = _invoke(
        monkeypatch,
        tmp_path,
        gh,
        ["undispatch", str(plan_dir.relative_to(tmp_path)), "--yes"],
    )
    assert second.exit_code == 0, second.output
    assert "nothing to undispatch" in second.output.lower()
    # No second close/comment fired.
    assert len([c for c in gh.calls if c[0] == "edit_issue_state"]) == 1
    assert len([c for c in gh.calls if c[0] == "comment_issue"]) == 1


def test_undispatch_skips_already_closed_issue_but_nulls_field(tmp_path, monkeypatch):
    plan_dir = _dispatched_plan_repo(tmp_path)
    gh = FakeGhClient()
    gh.add_issue(REPO, 7, state="CLOSED")
    result = _invoke(
        monkeypatch,
        tmp_path,
        gh,
        ["undispatch", str(plan_dir.relative_to(tmp_path)), "--yes"],
    )
    assert result.exit_code == 0, result.output
    assert [c for c in gh.calls if c[0] == "edit_issue_state"] == []
    assert "tracking_issue: null" in (plan_dir / "01.yaml").read_text()


def test_undispatch_accumulates_gh_failures_exit_4(tmp_path, monkeypatch):
    plan_dir = _dispatched_plan_repo(tmp_path)
    gh = FakeGhClient()
    gh.add_issue(REPO, 7, state="OPEN")
    gh.fail_on_mutation = 0  # first mutation (the comment) raises
    result = _invoke(
        monkeypatch,
        tmp_path,
        gh,
        ["undispatch", str(plan_dir.relative_to(tmp_path)), "--yes"],
    )
    assert result.exit_code == 4, result.output
    assert "failure" in result.output.lower()
    # tracking_issue retained so the retry can find the Issue again.
    assert "tracking_issue: https" in (plan_dir / "01.yaml").read_text()


def test_undispatch_clears_field_when_issue_deleted(tmp_path, monkeypatch):
    """A DELETED upstream Issue is terminal — undispatch clears the field
    instead of looping at exit 4 forever (review finding, 2026-06-06)."""
    plan_dir = _dispatched_plan_repo(tmp_path)
    gh = FakeGhClient()  # issue #7 never added -> view_issue raises KeyError
    result = _invoke(
        monkeypatch,
        tmp_path,
        gh,
        ["undispatch", str(plan_dir.relative_to(tmp_path)), "--yes"],
    )
    assert result.exit_code == 0, result.output
    assert "no longer exists" in result.output
    assert "tracking_issue: null" in (plan_dir / "01.yaml").read_text()
