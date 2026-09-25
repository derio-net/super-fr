"""`fr plan ...` CLI-layer behaviour (the library is covered by test_plan_ops.py)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    (repo / "README.md").write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
    return repo


def test_plan_create_reports_a_foreign_wrapper_on_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The warning is fr's own output, not Python's last-resort log handler (gh#610 r2)."""
    repo = _git_repo(tmp_path)
    wrapper = repo / "scripts" / "validate-plans.sh"
    wrapper.parent.mkdir()
    foreign = "#!/usr/bin/env bash\n# our own house validator\nexit 0\n"
    wrapper.write_text(foreign)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")

    res = CliRunner().invoke(
        app,
        ["plan", "create", "--slug", "2026-05-10-foreign", "--target-repo", "o/r"],
    )

    assert res.exit_code == 0, res.output
    assert wrapper.read_text() == foreign
    assert "warning:" in res.stderr
    assert "validate-plans.sh" in res.stderr


# --- gh#610 §3.C: fr plan commits its own writes ------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _feature_repo(tmp_path: Path) -> Path:
    repo = _git_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feat/p")
    return repo


_PHASES = """
- number: 1
  title: One
  tag: agentic
  tier: standard
  tasks:
    - number: 1
      title: T
      steps:
        - {id: P1.T1.S1, text: do it}
"""


def _create(repo: Path, tmp_path: Path, slug: str = "2026-09-25-p"):
    phases = tmp_path / "phases.yaml"
    phases.write_text(_PHASES)
    return CliRunner().invoke(
        app,
        [
            "plan", "create", "--slug", slug, "--target-repo", "o/r",
            "--phases-file", str(phases),
        ],
    )  # fmt: skip


def test_plan_create_commits_the_plan_journal_and_wrapper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _feature_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    (repo / "unrelated.md").write_text("executor's own work\n")
    _git(repo, "add", "--", "unrelated.md")

    res = _create(repo, tmp_path)

    assert res.exit_code == 0, res.output
    assert _git(repo, "log", "-1", "--format=%s") == "chore(fr): plan 2026-09-25-p — create"
    files = _git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert "scripts/validate-plans.sh" in files
    assert "docs/superpowers/journals/plans/2026-09-25-p.md" in files
    assert "docs/superpowers/plans/2026-09-25-p/_meta.yaml" in files
    assert "unrelated.md" not in files
    assert _git(repo, "status", "--porcelain", "--", "docs", "scripts") == ""
    assert _git(repo, "diff", "--cached", "--name-only") == "unrelated.md"


def test_plan_edit_tick_and_complete_each_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _feature_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    assert _create(repo, tmp_path).exit_code == 0
    plan = "docs/superpowers/plans/2026-09-25-p"

    res = CliRunner().invoke(app, ["plan", "edit", plan, "--tick", "P1.T1.S1"])
    assert res.exit_code == 0, res.output
    assert _git(repo, "log", "-1", "--format=%s") == "chore(fr): plan 2026-09-25-p — tick P1.T1.S1"
    assert _git(repo, "status", "--porcelain", "--", "docs") == ""

    res = CliRunner().invoke(app, ["plan", "edit", plan, "--complete-phase", "1"])
    assert res.exit_code == 0, res.output
    assert (
        _git(repo, "log", "-1", "--format=%s") == "chore(fr): plan 2026-09-25-p — complete phase 1"
    )
    assert _git(repo, "status", "--porcelain", "--", "docs") == ""
