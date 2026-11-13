"""`git.history: squash-unpushed` under stealth names nothing of fr (review pr1431-r4).

R24 lets only the code commits reach a stealth target. The squash's commit message used
to credit `fr push` in its body; under stealth it is the subject and the folded subjects
alone, and a folded subject that would name fr refuses before anything is rewritten.

Target and tracking repos are LOCAL bare repos; nothing reaches a forge.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.settings_repo import git
from tests.unit.stealth_repo import stealth_home, stealth_pair
from tests.unit.test_settings_stealth import _push_target_settings, _up

__all__ = ["stealth_home"]

SQUASH = "placement: stealth\ngit:\n  history: squash-unpushed\n"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FR_REPO_ROOT", raising=False)
    monkeypatch.setenv("FR_ISOLATION_TARGET", "worktree")


def _ws(tmp_path: Path) -> tuple[Path, Path]:
    target, track = stealth_pair(tmp_path)
    _push_target_settings(track, tmp_path, SQUASH)
    return _up(target, track, "feat/q").worktree, tmp_path / "origin.git"


def _commit(ws: Path, name: str, subject: str) -> None:
    (ws / name).write_text(subject + "\n")
    git(ws, "add", name)
    git(ws, "commit", "-qm", subject)


def _push(ws: Path):  # type: ignore[no-untyped-def]
    return CliRunner().invoke(app, ["push"], env={**os.environ, "FR_REPO_ROOT": str(ws)})


def test_the_squashed_commit_on_the_target_carries_no_fr_attribution(tmp_path: Path) -> None:
    ws, origin = _ws(tmp_path)
    _commit(ws, "a.txt", "feat: one")
    _commit(ws, "b.txt", "fix: two")
    result = _push(ws)
    assert result.exit_code == 0, result.output
    bodies = git(origin, "log", "--format=%B", "main..feat/q")
    assert "feat: one" in bodies and "fix: two" in bodies
    for word in ("fr push", "squash-unpushed", "Squashed by", "Fr-Commit", "stealth"):
        assert word not in bodies, bodies
    assert len(git(origin, "rev-list", "main..feat/q").split()) == 1


def test_a_folded_subject_naming_fr_refuses_before_rewriting(tmp_path: Path) -> None:
    ws, origin = _ws(tmp_path)
    _commit(ws, "a.txt", "feat: one")
    _commit(ws, "b.txt", "chore(fr): note")
    head = git(ws, "rev-parse", "HEAD").strip()
    result = _push(ws)
    assert result.exit_code == 2
    assert "chore(fr): note" in result.output
    assert git(ws, "rev-parse", "HEAD").strip() == head
    assert git(origin, "for-each-ref", "refs/heads/feat").strip() == ""
