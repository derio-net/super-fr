"""`fr archive` does its own follow-ups (spec 2026-10-06-archive-followups-design)."""

from __future__ import annotations


def test_the_followup_seams_import() -> None:
    from fr.archive import MoveLog, recording_moves

    assert MoveLog is not None and recording_moves is not None


import subprocess
from pathlib import Path

import pytest
from fr.archive import (
    ArchiveError,
    MoveLog,
    archive_journal,
    archive_plan_dir,
    recording_moves,
)
from fr.cli import app
from fr.commands import archive_cmd
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.test_archive_cmd import _add_plan, _invoke, _repo, _seed


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _tiny_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    plan = repo / "docs/superpowers/plans/p1"
    plan.mkdir(parents=True)
    (plan / "_meta.yaml").write_text("x: 1\n")
    j = repo / "docs/superpowers/journals/plans"
    j.mkdir(parents=True)
    (j / "p1.md").write_text("# j\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@e", "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-qm", "seed")
    return repo


def test_moves_are_recorded_only_inside_the_context(tmp_path: Path) -> None:
    repo = _tiny_repo(tmp_path)
    assert not MoveLog()
    with recording_moves() as log:
        archive_plan_dir(repo, repo / "docs/superpowers/plans/p1")
        archive_journal(repo, "plan", "p1")
    assert bool(log)
    assert log.moves == [
        (
            Path("docs/superpowers/plans/p1"),
            Path("docs/superpowers/implemented/plans/p1"),
        ),
        (
            Path("docs/superpowers/journals/plans/p1.md"),
            Path("docs/superpowers/implemented/journals/plans/p1.md"),
        ),
    ]
    # outside the context: behaves as before, records nothing
    (repo / "a.txt").write_text("a")
    _git(repo, "add", "a.txt")
    from fr.archive import _git_mv

    _git_mv(repo, Path("a.txt"), Path("b.txt"))
    assert (repo / "b.txt").exists()
    assert len(log.moves) == 2


def test_a_failed_move_is_not_recorded(tmp_path: Path) -> None:
    repo = _tiny_repo(tmp_path)
    from fr.archive import _git_mv

    with recording_moves() as log, pytest.raises(ArchiveError):
        _git_mv(repo, Path("nope"), Path("also-nope"))
    assert not log


# --- T3: _after_moves runs in a finally on every entry mode ---


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    calls: list[bool] = []

    def fake(repo_root, log, opts):  # noqa: ANN001
        calls.append(bool(log))

    monkeypatch.setattr(archive_cmd, "_after_moves", fake)
    return calls


def _plan_repo(tmp_path: Path, slug: str = "2026-05-25-bookmarks") -> tuple[Path, Path]:
    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, slug, ticked=True)
    _seed(repo)
    return repo, plan_dir


def test_after_moves_runs_once_for_a_single_plan(tmp_path, monkeypatch, spy):
    repo, plan_dir = _plan_repo(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))])
    assert result.exit_code == 0, result.output
    assert spy == [True]


def test_after_moves_runs_once_for_all(tmp_path, monkeypatch, spy):
    repo, _ = _plan_repo(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert spy == [True]


def test_after_moves_runs_for_sweep_only(tmp_path, monkeypatch, spy):
    from tests.unit.test_archive_cmd import _add_spec

    repo = _repo(tmp_path)
    _add_spec(repo, "2026-05-01-done-design.md", [])
    _seed(repo)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--sweep-only"])
    assert result.exit_code == 0, result.output
    assert len(spy) == 1


def test_after_moves_sees_an_empty_log_when_nothing_moved(tmp_path, monkeypatch, spy):
    repo = _repo(tmp_path)
    _seed(repo)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert spy == [False]


def test_after_moves_runs_when_a_follower_move_exits_2(tmp_path, monkeypatch, spy):
    repo, plan_dir = _plan_repo(tmp_path)
    import fr.archive as arch

    def boom(*a, **k):
        raise ArchiveError("boom")

    monkeypatch.setattr(arch, "_archive_run", boom)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))])
    assert result.exit_code == 2, result.output
    assert spy == [True]
