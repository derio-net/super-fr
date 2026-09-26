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
    text = archived_usage_path(repo, "2026-09-01-feat-old").read_text()
    assert "laptop.corp.example" not in text


def test_a_run_with_transcripts_gets_exact_dollars(repo: Path) -> None:
    _backfill(repo)
    usage = load_usage(archived_usage_path(repo, "2026-09-21-feat-new"))
    assert usage is not None
    entry = next(s for s in usage.captures[0].sessions if s.session == CC_SESSION)
    assert entry.unavailable is None
    assert any(m.usd_source == "exact" and m.usd for m in entry.models.values())


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
