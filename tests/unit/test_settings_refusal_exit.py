"""A settings refusal is a clean message and exit 2, never a traceback (spec R2, p2-r1)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row
from tests.unit.settings_repo import git

runner = CliRunner()


@pytest.fixture
def unresolvable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A remote WITH tracking refs but no default: R2 step 1 refuses."""
    root = make_repo(tmp_path, row(), git=False)
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(tmp_path / "o.git"))
    git(root, "init", "-q", "-b", "main")
    git(root, "remote", "add", "origin", str(tmp_path / "o.git"))
    git(root, "add", "-A")
    git(root, "commit", "-qm", "seed")
    git(root, "push", "-q", "origin", "main:feature")
    git(root, "fetch", "-q", "origin")
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    monkeypatch.chdir(root)
    return root


@pytest.mark.parametrize(
    "argv",
    [
        ["acceptance", "status"],
        ["acceptance", "digest"],
        ["acceptance", "check"],
        ["debt", "--offline"],
    ],
    ids=lambda a: "-".join(a),
)
def test_a_settings_refusal_exits_2_cleanly(unresolvable: Path, argv: list[str]) -> None:
    result = runner.invoke(app, argv)
    assert result.exit_code == 2, (result.output, result.exception)
    assert "Traceback" not in result.output
    assert "fr: settings: cannot find the default branch of remote `origin`" in result.output


def test_the_real_entry_point_prints_no_traceback(unresolvable: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k != "FR_HARNESS_FR"}
    done = subprocess.run(
        [sys.executable, "-P", "-m", "fr", "acceptance", "status"],
        cwd=unresolvable,
        env={**env, "FR_SKIP_IDENTITY": "1"},
        capture_output=True,
        text=True,
    )
    assert done.returncode == 2, done.stderr
    assert "Traceback" not in done.stderr
    assert "fr: settings:" in done.stderr
