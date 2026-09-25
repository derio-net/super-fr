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
