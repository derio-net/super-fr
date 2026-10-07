"""`fr usage backfill` — usage files for runs archived before usage existed
(spec `2026-09-25-lean-cost-aware-process-design.md` §5.B.5).

It READS archived runs (left byte-identical, hash-checked) and any transcripts
still on this host, and writes NEW `implemented/usage/<run>.yaml` files with
`at: backfill`. Re-running is a no-op.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from fr.cli import app
from fr.usage.file import archived_usage_path, load_usage
from typer.testing import CliRunner

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "usage"
CC_SESSION = "145101c9-bdfc-4f5d-a8be-617eeced7485"

WITH_FIGURES = """schema_version: 5
run: 2026-09-01-feat-old
workflow: fr-goal@1
branch: feat/old
started: '2026-09-01T00:00:00+00:00'
cursor: deliver
steps:
  implement:
    state: done
    at: '2026-09-01T02:00:00+00:00'
    units:
      phase/1/implement-phase:
        state: done
        attempts:
        - dispatched: '2026-09-01T01:00:00+00:00'
          agent: a-gone
          agent_type: super-fr:fr-phase-executor
          harness: claude-code
          model: claude-opus-5-5
          session: no-such-session
          returned: '2026-09-01T01:30:00+00:00'
          outcome: done
          estimate:
            handoff_chars: 1234
          measured:
            input_tokens: 1
            cache_creation_input_tokens: 2
            cache_read_input_tokens: 3
            output_tokens: 4
  deliver:
    state: done
    at: '2026-09-01T03:00:00+00:00'
"""

WITH_TRANSCRIPT = f"""schema_version: 6
run: 2026-09-21-feat-new
workflow: fr-goal@1
branch: feat/new
started: '2026-09-21T11:00:00+00:00'
cursor: deliver
steps:
  implement:
    state: done
    at: '2026-09-21T13:00:00+00:00'
    units:
      step/implement:
        attempts:
        - dispatched: '2026-09-21T11:00:01+00:00'
          harness: claude-code
          session: {CC_SESSION}
"""


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "projects" / "-work-example"
    root.mkdir(parents=True)
    shutil.copy(FIXTURES / "claude-code" / f"{CC_SESSION}.jsonl", root)
    shutil.copytree(FIXTURES / "claude-code" / CC_SESSION, root / CC_SESSION)
    monkeypatch.setenv("FR_TRANSCRIPT_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("FR_HOSTNAME", "laptop.corp.example")
    repo = tmp_path / "repo"
    runs = repo / "docs" / "superpowers" / "implemented" / "runs"
    runs.mkdir(parents=True)
    (runs / "2026-09-01-feat-old.yaml").write_text(WITH_FIGURES)
    (runs / "2026-09-21-feat-new.yaml").write_text(WITH_TRANSCRIPT)
    return repo


def _hashes(repo: Path) -> dict[str, str]:
    runs = repo / "docs" / "superpowers" / "implemented" / "runs"
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(runs.iterdir())}


def _backfill(repo: Path):
    return CliRunner().invoke(app, ["usage", "backfill", "--repo", str(repo)])


def test_backfill_writes_one_new_file_per_archived_run_and_touches_no_run(repo: Path) -> None:
    before = _hashes(repo)

    result = _backfill(repo)

    assert result.exit_code == 0, result.output
    assert _hashes(repo) == before, "archived runs are history: byte-identical"
    for run in ("2026-09-01-feat-old", "2026-09-21-feat-new"):
        usage = load_usage(archived_usage_path(repo, run))
        assert usage is not None, run
        assert [c.at for c in usage.captures] == [("backfill",)]
        assert usage.schema_version == 2  # born stamped, never stale
    text = archived_usage_path(repo, "2026-09-01-feat-old").read_text()
    assert "laptop.corp.example" not in text


def test_a_run_with_transcripts_gets_exact_dollars(repo: Path) -> None:
    _backfill(repo)
    usage = load_usage(archived_usage_path(repo, "2026-09-21-feat-new"))
    assert usage is not None
    entry = next(s for s in usage.captures[0].sessions if s.session == CC_SESSION)
    assert entry.unavailable is None
    assert any(m.usd_source == "exact" and m.usd for m in entry.models.values())


def test_backfill_writes_no_main_subagent_or_unit_split(repo: Path) -> None:
    """Archived files are not re-shaped (cost-evidence spec R6): `backfill`
    passes no unit index, so neither section is written."""
    _backfill(repo)
    for run in ("2026-09-01-feat-old", "2026-09-21-feat-new"):
        text = archived_usage_path(repo, run).read_text()
        assert "steps_by_role" not in text and "units:" not in text
        for capture in load_usage(archived_usage_path(repo, run)).captures:  # type: ignore[union-attr]
            assert all(not s.steps_by_role and not s.units for s in capture.sessions)


def test_a_run_without_transcripts_keeps_its_cursor_figures_with_no_dollars(repo: Path) -> None:
    _backfill(repo)
    usage = load_usage(archived_usage_path(repo, "2026-09-01-feat-old"))
    assert usage is not None
    sessions = usage.captures[0].sessions
    figures = [s for s in sessions if s.models]
    assert figures, "the cursor's measured figures are carried"
    (model,) = figures[0].models.values()
    assert (model.cache_read, model.usd, model.usd_source) == (3, None, "none")
    assert figures[0].briefs == {"phase/1/implement-phase": 1234}


def test_rerunning_is_a_no_op(repo: Path) -> None:
    _backfill(repo)
    written = {
        run: archived_usage_path(repo, run).read_bytes()
        for run in ("2026-09-01-feat-old", "2026-09-21-feat-new")
    }
    result = _backfill(repo)
    assert result.exit_code == 0, result.output
    assert "0 backfilled" in result.output
    for run, data in written.items():
        assert archived_usage_path(repo, run).read_bytes() == data


NO_SESSIONS = """schema_version: 6
run: 2026-09-22-feat-sessionless
workflow: fr-goal@1
branch: feat/sessionless
started: '2026-09-22T11:00:00+00:00'
cursor: deliver
steps:
  deliver:
    state: done
    at: '2026-09-22T12:00:00+00:00'
"""


def test_a_run_naming_no_session_is_recorded_unavailable_never_empty(repo: Path) -> None:
    """#636's defect by the backfill path: a cursor that names no session and
    kept no figures must not become `sessions: []`, which reads as a free run."""
    from fr.usage.file import NO_SESSION_FOUND

    runs = repo / "docs" / "superpowers" / "implemented" / "runs"
    (runs / "2026-09-22-feat-sessionless.yaml").write_text(NO_SESSIONS)

    result = _backfill(repo)

    assert result.exit_code == 0, result.output
    usage = load_usage(archived_usage_path(repo, "2026-09-22-feat-sessionless"))
    assert usage is not None
    (entry,) = usage.captures[0].sessions
    assert (entry.session, entry.unavailable) == ("", NO_SESSION_FOUND)


# --- refresh_archived: the existing-file branch alone (spec 2026-10-06 §A, R1-R3) ---


def _unpriced_then_exited(repo: Path, tmp_path: Path) -> Path:
    """Backfill the transcript run while its session is still open (cost-state
    stripped); returns the transcript, restorable to the exited state."""
    transcript = next((tmp_path / "projects").rglob(f"{CC_SESSION}.jsonl"))
    full = transcript.read_text()
    transcript.write_text("".join(ln for ln in full.splitlines(True) if '"cost-state"' not in ln))
    assert _backfill(repo).exit_code == 0
    transcript.write_text(full)  # the session exits
    return transcript


def _refresh(repo: Path, skip=lambda _p: False):
    import os

    from fr.usage.backfill import refresh_archived

    return refresh_archived(repo, os.environ, skip=skip)


def test_refresh_archived_prices_an_unpriced_session_and_touches_nothing_else(
    repo: Path, tmp_path: Path
) -> None:
    _unpriced_then_exited(repo, tmp_path)
    old = archived_usage_path(repo, "2026-09-01-feat-old")
    old_bytes = old.read_bytes()
    runs_before = _hashes(repo)

    report = _refresh(repo)

    new = archived_usage_path(repo, "2026-09-21-feat-new")
    assert report.refreshed == [new]
    usage = load_usage(new)
    assert usage is not None
    entry = next(s for s in usage.captures[0].sessions if s.session == CC_SESSION)
    assert any(m.usd_source == "exact" for m in entry.models.values())
    assert old.read_bytes() == old_bytes, "an untouched (nothing to price) file stays"
    assert _hashes(repo) == runs_before
    assert not report.written and not report.failed


def test_refresh_archived_leaves_a_priced_file_untouched(repo: Path, tmp_path: Path) -> None:
    assert _backfill(repo).exit_code == 0  # transcript present: already priced
    before = archived_usage_path(repo, "2026-09-21-feat-new").read_bytes()
    report = _refresh(repo)
    assert report.refreshed == []
    assert archived_usage_path(repo, "2026-09-21-feat-new").read_bytes() == before


def test_refresh_archived_never_creates_a_file_for_a_run_without_one(repo: Path) -> None:
    report = _refresh(repo)
    assert report.refreshed == [] and report.written == []
    assert not archived_usage_path(repo, "2026-09-21-feat-new").exists()


def test_refresh_archived_reports_an_unreadable_cursor_in_failed(
    repo: Path, tmp_path: Path
) -> None:
    _unpriced_then_exited(repo, tmp_path)
    cursor = repo / "docs/superpowers/implemented/runs/2026-09-21-feat-new.yaml"
    cursor.write_text(": : not yaml [")
    report = _refresh(repo)
    assert [r for r, _ in report.failed] == ["2026-09-21-feat-new"]
    assert report.refreshed == []


def test_refresh_archived_skips_a_file_the_skip_predicate_names(repo: Path, tmp_path: Path) -> None:
    _unpriced_then_exited(repo, tmp_path)
    target = archived_usage_path(repo, "2026-09-21-feat-new")
    before = target.read_bytes()
    report = _refresh(repo, skip=lambda p: p == target)
    assert report.refreshed == [] and report.dirty == ["2026-09-21-feat-new"]
    assert target.read_bytes() == before


def test_a_priced_usage_file_is_skipped_without_reading_its_cursor(repo: Path) -> None:
    """p1-r1: the cursor is parsed only once the usage file has something to price."""
    assert _backfill(repo).exit_code == 0  # transcript present: priced
    cursor = repo / "docs/superpowers/implemented/runs/2026-09-21-feat-new.yaml"
    cursor.write_text(": : not yaml [")
    report = _refresh(repo)
    assert report.failed == [] and report.refreshed == []
    assert "2026-09-21-feat-new" in report.skipped


def _age_capture(repo: Path, run: str, captured_at: str) -> None:
    import re

    p = archived_usage_path(repo, run)
    p.write_text(re.sub(r"captured_at: .*", f"captured_at: '{captured_at}'", p.read_text()))


def test_refresh_archived_honours_max_age_days_on_both_sides(repo: Path, tmp_path: Path) -> None:
    """p1-r2: an unpriced file whose capture is older than the bound is not re-read."""
    import datetime as dt
    import os

    from fr.usage.backfill import refresh_archived

    _unpriced_then_exited(repo, tmp_path)
    run = "2026-09-21-feat-new"
    target = archived_usage_path(repo, run)
    old = (dt.datetime.now(dt.UTC) - dt.timedelta(days=45)).isoformat()
    _age_capture(repo, run, old)
    before = target.read_bytes()

    aged = refresh_archived(repo, os.environ, max_age_days=30)
    assert aged.refreshed == [] and target.read_bytes() == before

    unbounded = refresh_archived(repo, os.environ, max_age_days=None)
    assert unbounded.refreshed == [target]


def test_refresh_archived_refreshes_inside_the_age_bound(repo: Path, tmp_path: Path) -> None:
    import datetime as dt
    import os

    from fr.usage.backfill import refresh_archived

    _unpriced_then_exited(repo, tmp_path)
    run = "2026-09-21-feat-new"
    _age_capture(repo, run, (dt.datetime.now(dt.UTC) - dt.timedelta(days=5)).isoformat())
    report = refresh_archived(repo, os.environ, max_age_days=30)
    assert report.refreshed == [archived_usage_path(repo, run)]


def _git(repo: Path, *args: str) -> None:
    import subprocess

    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@e", *args],
        check=True,
        capture_output=True,
    )


def test_a_staged_but_unedited_usage_file_is_refreshed_and_a_worktree_edit_is_skipped(
    repo: Path, tmp_path: Path
) -> None:
    """p1-r3: the archive's own staged `git mv` is not an uncommitted edit."""
    import os

    from fr.commands.archive_cmd import _edited_in_worktree
    from fr.usage.backfill import refresh_archived

    _unpriced_then_exited(repo, tmp_path)
    target = archived_usage_path(repo, "2026-09-21-feat-new")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed")
    _git(repo, "mv", str(target.relative_to(repo)), str(target.relative_to(repo)) + ".x")
    _git(repo, "mv", str(target.relative_to(repo)) + ".x", str(target.relative_to(repo)))
    text = target.read_text()
    target.write_text(text + "\n")  # staged below: index == worktree, differs from HEAD
    _git(repo, "add", str(target.relative_to(repo)))
    skip = lambda p: _edited_in_worktree(repo, p)  # noqa: E731
    assert not _edited_in_worktree(repo, target)

    # a real worktree edit on top of the staged file is skipped, never rewritten
    staged = target.read_bytes()
    target.write_bytes(staged + b"# mine\n")
    assert _edited_in_worktree(repo, target)
    report = refresh_archived(repo, os.environ, skip=skip, max_age_days=30)
    assert report.refreshed == [] and report.dirty == ["2026-09-21-feat-new"]
    assert target.read_bytes() == staged + b"# mine\n"

    # staged-only (index == worktree): refreshed
    target.write_bytes(staged)
    report = refresh_archived(repo, os.environ, skip=skip, max_age_days=30)
    assert report.refreshed == [target] and report.dirty == []
