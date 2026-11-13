"""Under stealth the PR's title and body name nothing of fr (review pr1431-n5).

R24 lets one minimal draft PR reach the target. The body was checked for fr's markers
only; the title and the prose were the agent's. Under stealth both are now checked for
fr's naming (its commit scopes, its commands, the placement), before any forge call.
Target and tracking repos are LOCAL bare repos; the forge is never reached.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.cli import app
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.placement import stealth
from typer.testing import CliRunner

from tests.unit.settings_repo import make_repo
from tests.unit.stealth_repo import make_tracking, stealth_home

__all__ = ["stealth_home"]


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")


def _create(tmp_path: Path, title: str, body: str):  # type: ignore[no-untyped-def]
    target = make_repo(tmp_path)
    track = make_tracking(tmp_path)
    ws = (
        HostWorktreeTarget(target)
        .up(profile=None, branch="feat/p", stealth=stealth.parse_ref(f"{track}@main"))
        .worktree
    )
    body_file = tmp_path / "body.md"
    body_file.write_text(body)
    return CliRunner().invoke(
        app,
        ["pr", "create", "--title", title, "--body-file", str(body_file)],
        env={**os.environ, "FR_REPO_ROOT": str(ws)},
    )


def test_a_title_naming_fr_refuses_under_stealth(tmp_path: Path) -> None:
    result = _create(tmp_path, "chore(fr): placement stealth run", "A plain summary.\n")
    assert result.exit_code == 2
    assert "title" in result.output


def test_body_prose_naming_fr_refuses_under_stealth(tmp_path: Path) -> None:
    result = _create(tmp_path, "feat: a change", "Pushed with fr push under stealth.\n")
    assert result.exit_code == 2
    assert "fr push" in result.output


def test_a_plain_title_and_body_pass_the_check(tmp_path: Path) -> None:
    # It goes on to the forge step, which a local origin cannot name: no forge call.
    result = _create(tmp_path, "feat: a change", "A plain summary.\n")
    assert "forge repository" in result.output
