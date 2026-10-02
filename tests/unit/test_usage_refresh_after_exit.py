"""A run's dollars after its session ends (gh#756).

Reconstructed from #682's closeout: the capture inside `fr archive` DID run —
it appended `closeout` and re-read the delivering session — but that session
was still open, and Claude Code writes a session's dollars (`cost-state`) only
when it exits. The session exited the same second; `fr usage report` read
$4.27 moments later, and the archived file kept `usd: null` for good, because
nothing captures an archived run again.

So: the closeout says which sessions it could not price yet, and `fr usage
backfill` refreshes an archived file once their dollars exist — never trading
a reading for an absence. The fixture transcript's `cost-state` lines are
stripped to stage "still open" and restored to stage "exited".
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.cli import app
from fr.usage.file import archived_usage_path, dump_usage, load_usage, usage_path
from typer.testing import CliRunner

from tests.unit.test_usage_capture import (  # noqa: F401 — `transcripts` is a fixture
    CC_SESSION,
    RUN,
    _setup,
    _step,
    transcripts,
)


def _transcript(root: Path) -> Path:
    return root / "-work-example" / f"{CC_SESSION}.jsonl"


@pytest.fixture
def still_open(transcripts: Path) -> tuple[Path, str]:  # noqa: F811 — the imported fixture
    """The session's transcript without its exit-time `cost-state` records;
    returns `(transcript, the full text to restore on exit)`."""
    path = _transcript(transcripts)
    full = path.read_text()
    kept = (line for line in full.splitlines(True) if '"cost-state"' not in line)
    path.write_text("".join(kept))
    return path, full


def _entry(repo: Path):
    usage = load_usage(archived_usage_path(repo, RUN))
    assert usage is not None
    (capture,) = usage.captures
    return capture, next(s for s in capture.sessions if s.session == CC_SESSION)


def _delivered_and_archived(tmp_path: Path) -> Path:
    from fr.archive import _archive_run

    repo, shipped = _setup(tmp_path)
    for step in ("brainstorm", "plan", "review", "deliver"):
        assert _step(repo, shipped, step).exit_code == 0
    # The run was delivered from a devcontainer workspace whose record gc has
    # since reaped: the closeout must not relabel the capture.
    live = load_usage(usage_path(repo, RUN))
    assert live is not None
    relabelled = live.model_copy(
        update={
            "captures": tuple(c.model_copy(update={"mode": "devcontainer"}) for c in live.captures)
        }
    )
    usage_path(repo, RUN).write_text(dump_usage(relabelled))
    _archive_run(repo, Path("docs/superpowers/plans/2026-09-30-fixture"))
    return repo


def _backfill(repo: Path):
    return CliRunner().invoke(app, ["usage", "backfill", "--repo", str(repo)])


@pytest.mark.usefixtures("complete_live_pr")
def test_the_closeout_names_a_session_it_could_not_price_yet(
    tmp_path: Path, still_open: tuple[Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _delivered_and_archived(tmp_path)

    capture, entry = _entry(repo)
    assert "closeout" in capture.at
    assert all(m.usd is None for m in entry.models.values()), "the race, reproduced"
    err = capsys.readouterr().err
    assert CC_SESSION in err
    assert "fr usage backfill" in err


@pytest.mark.usefixtures("complete_live_pr")
def test_the_closeout_keeps_the_recorded_mode_when_the_workspace_is_gone(
    tmp_path: Path, still_open: tuple[Path, str]
) -> None:
    repo = _delivered_and_archived(tmp_path)
    capture, _ = _entry(repo)
    assert capture.mode == "devcontainer"


@pytest.mark.usefixtures("complete_live_pr")
def test_backfill_prices_an_archived_session_once_it_has_exited(
    tmp_path: Path, still_open: tuple[Path, str]
) -> None:
    repo = _delivered_and_archived(tmp_path)
    transcript, full = still_open
    transcript.write_text(full)  # the session exits

    result = _backfill(repo)

    assert result.exit_code == 0, result.output
    assert "1 refreshed" in result.output
    capture, entry = _entry(repo)
    assert entry.models and all(m.usd_source == "exact" for m in entry.models.values())
    assert capture.at[-2:] == ("closeout", "backfill")
    assert capture.mode == "devcontainer"


@pytest.mark.usefixtures("complete_live_pr")
def test_backfill_leaves_an_archived_file_alone_while_the_session_is_still_open(
    tmp_path: Path, still_open: tuple[Path, str]
) -> None:
    repo = _delivered_and_archived(tmp_path)
    before = archived_usage_path(repo, RUN).read_bytes()

    result = _backfill(repo)

    assert result.exit_code == 0, result.output
    assert archived_usage_path(repo, RUN).read_bytes() == before


@pytest.mark.usefixtures("complete_live_pr")
def test_a_second_backfill_after_the_refresh_is_a_no_op(
    tmp_path: Path, still_open: tuple[Path, str]
) -> None:
    repo = _delivered_and_archived(tmp_path)
    transcript, full = still_open
    transcript.write_text(full)
    assert _backfill(repo).exit_code == 0
    after = archived_usage_path(repo, RUN).read_bytes()

    result = _backfill(repo)

    assert "0 refreshed" in result.output
    assert archived_usage_path(repo, RUN).read_bytes() == after


@pytest.mark.usefixtures("complete_live_pr")
def test_backfill_never_trades_a_reading_for_an_absence(
    tmp_path: Path, still_open: tuple[Path, str]
) -> None:
    """The transcript pruned after the closeout: the recorded tokens stay."""
    repo = _delivered_and_archived(tmp_path)
    transcript, _ = still_open
    _, before = _entry(repo)
    transcript.unlink()

    assert _backfill(repo).exit_code == 0

    _, after = _entry(repo)
    assert after == before
