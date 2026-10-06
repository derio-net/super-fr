"""`fr archive` does its own follow-ups (spec 2026-10-06-archive-followups-design)."""

from __future__ import annotations

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
from fr.commands import archive_cmd

from tests.unit.fakes import FakeGhClient
from tests.unit.test_archive_cmd import _add_plan, _invoke, _repo, _seed


def test_the_followup_seams_import() -> None:
    from fr.archive import MoveLog, recording_moves

    assert MoveLog is not None and recording_moves is not None


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
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    assert spy == [True]


def test_after_moves_runs_once_for_all(tmp_path, monkeypatch, spy):
    repo, _ = _plan_repo(tmp_path)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert spy == [True]


def test_after_moves_runs_for_sweep_only(tmp_path, monkeypatch, spy):
    """p1-r5: the sweep really moves a spec, so the log is non-empty."""
    from tests.unit.test_archive_cmd import _add_spec, _strand_plan

    repo = _repo(tmp_path)
    _add_plan(repo, "2026-05-25-bookmarks", ticked=True, spec_name="2026-05-25-bm-design.md")
    _add_spec(
        repo,
        "2026-05-25-bm-design.md",
        [("bm", "derio-net/test", "docs/superpowers/implemented/plans/2026-05-25-bookmarks")],
    )
    _seed(repo)
    _strand_plan(repo, "2026-05-25-bookmarks")
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--sweep-only"])
    assert result.exit_code == 0, result.output
    assert (repo / "docs/superpowers/implemented/specs/2026-05-25-bm-design.md").exists()
    assert spy == [True]


def test_after_moves_runs_for_branch(tmp_path, monkeypatch, spy):
    """p1-r4: `--branch` on a merged branch that added a plan."""
    from tests.unit import test_archive_branch as tb

    repo = tb._base(tmp_path)
    tb._merged(repo, lambda r: tb._plan(r, tb.PLAN, ticked=True, spec=tb.SPEC))
    result = tb._invoke(monkeypatch, repo, ["archive", "--branch", tb.BRANCH])
    assert result.exit_code == 0, result.output
    assert (repo / tb.IMPL / "plans" / tb.PLAN).is_dir()
    assert spy == [True]


def test_after_moves_runs_for_all_when_only_an_owed_debug_journal_moves(tmp_path, monkeypatch, spy):
    """p1-r4: `--all` with no plan to archive — only an owed debug journal moves."""
    from tests.unit.test_archive_all_debug import SP, _write

    repo = _repo(tmp_path)
    _write(repo, SP / "journals" / "debug" / "on-ref.md", "# on ref\n")
    _seed(repo)
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert (repo / SP / "implemented/journals/debug/on-ref.md").exists()
    assert spy == [True]


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
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 2, result.output
    assert spy == [True]


# --- T4: the usage refresh step of _after_moves ---


def _usage_file(repo: Path) -> Path:
    p = repo / "docs/superpowers/implemented/usage/old-run.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("run: old-run\n")
    return p


def _patch_refresh(monkeypatch, fn):
    import fr.usage.backfill as bf

    calls: list[object] = []

    def fake(repo_root, env, *, skip=None, max_age_days=None):
        assert max_age_days == 30, "the archive path bounds the refresh"
        calls.append(skip)
        return fn(repo_root, skip)

    monkeypatch.setattr(bf, "refresh_archived", fake)
    return calls


def _staged(repo: Path) -> list[str]:
    return subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()


def test_an_archive_that_moved_something_stages_each_refreshed_usage_file(tmp_path, monkeypatch):
    from fr.usage.backfill import BackfillReport

    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-05-25-bookmarks", ticked=True)
    usage = _usage_file(repo)
    _seed(repo)

    def refresh(root, skip):
        usage.write_text("run: old-run\npriced: true\n")
        return BackfillReport(refreshed=[usage])

    _patch_refresh(monkeypatch, refresh)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    assert "  priced: docs/superpowers/implemented/usage/old-run.yaml" in result.output
    assert "docs/superpowers/implemented/usage/old-run.yaml" in _staged(repo)


def test_a_dirty_usage_file_is_skipped_with_a_note(tmp_path, monkeypatch):

    repo = _repo(tmp_path)
    plan_dir = _add_plan(repo, "2026-05-25-bookmarks", ticked=True)
    usage = _usage_file(repo)
    _seed(repo)
    usage.write_text("run: old-run\n# uncommitted\n")
    seen: list[bool] = []

    def refresh(root, skip):
        seen.append(skip(usage))
        return BackfillReport(dirty=["old-run"])

    from fr.usage.backfill import BackfillReport

    _patch_refresh(monkeypatch, refresh)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    assert seen == [True], "skip is paths_dirty"
    assert "uncommitted changes" in result.output
    assert "docs/superpowers/implemented/usage/old-run.yaml" not in _staged(repo)


def test_a_refresh_exception_prints_a_note_and_keeps_the_exit_code(tmp_path, monkeypatch):
    repo, plan_dir = _plan_repo(tmp_path)

    def refresh(root, skip):
        raise RuntimeError("kaboom")

    _patch_refresh(monkeypatch, refresh)
    result = _invoke(
        monkeypatch, repo, FakeGhClient(), ["archive", str(plan_dir.relative_to(repo))]
    )
    assert result.exit_code == 0, result.output
    assert "usage refresh skipped" in result.output and "kaboom" in result.output


def test_nothing_moved_means_no_refresh_call(tmp_path, monkeypatch):
    from fr.usage.backfill import BackfillReport

    repo = _repo(tmp_path)
    _seed(repo)
    calls = _patch_refresh(monkeypatch, lambda r, s: BackfillReport())
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert calls == []


def test_the_unpriced_note_promises_the_next_archive_will_price_it(capsys, tmp_path, monkeypatch):
    import os

    import fr.usage.capture as cap
    import fr.usage.file as uf
    from fr.archive import _note_unpriced
    from fr.run.model import RunState

    class _Usage:
        def host(self, label):
            return object()

    monkeypatch.setattr(uf, "load_usage", lambda p: _Usage())
    monkeypatch.setattr(cap, "unpriced_sessions", lambda mine: ["s-1"])
    _note_unpriced(tmp_path / "x.yaml", RunState.model_construct(run="r1"), os.environ)
    err = capsys.readouterr().err
    assert "s-1" in err
    assert "The next `fr archive` here will price it" in err
    assert "`fr usage backfill`" in err
    assert "commit" not in err
