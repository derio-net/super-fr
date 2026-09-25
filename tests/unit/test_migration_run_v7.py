"""The `run` kind's 6 -> 7 migration: usage moves out of the cursor (spec
`2026-09-25-lean-cost-aware-process-design.md` §5.B.4).

`Attempt.estimate`, `Attempt.measured` and `StepRecord.main_session` are
REMOVED. A removal freezes the prior shape (`fr.run.legacy.RunStateV6`), the
figures are MOVED into the run's `usage/` file (`at: migrated`, `usd_source:
none`) rather than dropped, an unconvertible cursor stays byte-identical, and a
body already wholly v7 under a v6 stamp (the crash window) is completed.
Exercised against a cursor fr really wrote (`tests/fixtures/run_cursors/v6/`).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fr.artifacts import MIGRATIONS, run_migrations
from fr.artifacts.registry import read_version
from fr.run.model import parse_run_state
from fr.usage.file import MIGRATED_HOST, host_label, load_usage, usage_path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "run_cursors"
V6 = FIXTURES / "v6" / "2026-09-24-feat-597-593.yaml"
RUN = "2026-09-24-feat-597-593"


def _seed(root: Path, text: str | None = None) -> Path:
    path = root / "docs" / "superpowers" / "runs" / f"{RUN}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    if text is None:
        shutil.copy(V6, path)
    else:
        path.write_text(text)
    return path


def test_the_hop_is_registered_and_moves_six_to_seven() -> None:
    chain = MIGRATIONS.chain("run", 6)
    assert [(m.from_version, m.to_version) for m in chain] == [(6, 7)]


def test_a_v6_cursor_migrates_with_its_figures_moved_into_usage(tmp_path: Path) -> None:
    cursor = _seed(tmp_path)
    report = run_migrations(tmp_path, dry_run=False)
    assert report.failed == (), report.failed

    text = cursor.read_text()
    assert read_version("run", cursor) == 7
    parse_run_state(text)  # the LIVE model reads it
    for gone in ("estimate:", "measured:", "main_session:"):
        assert gone not in text

    usage = load_usage(usage_path(tmp_path, RUN))
    assert usage is not None
    (capture,) = usage.captures
    assert capture.at == ("migrated",)
    assert capture.host == host_label(RUN, MIGRATED_HOST)
    by_session = {s.session: s for s in capture.sessions}

    main = by_session["(main)"]
    assert main.role == "main"
    assert main.steps["implement"].turns == 49
    assert main.steps["deliver"].turns == 38
    assert all(m.usd_source == "none" and m.usd is None for m in main.models.values())

    subagents = [s for s in capture.sessions if (s.role or "").startswith("subagent")]
    assert subagents
    executor = next(s for s in subagents if s.briefs.get("phase/1/implement-phase") == 347)
    assert executor.role == "subagent:super-fr:fr-phase-executor"
    figures = executor.models["claude-opus-5-5"]
    assert figures.cache_read == 17753981 and figures.cache_write == 468702
    assert figures.usd is None and figures.usd_source == "none"

    # p2-r23: a dispatched attempt (it names an `agent`) is a subagent even
    # when v6 recorded no `agent_type` — only the `(main)` entry is `main`
    assert [s.session for s in capture.sessions if s.role == "main"] == ["(main)"]
    assert by_session["a1ea2343c237b8a52"].role == "subagent"

    # the usage file is committed with the cursor: it is a changed path
    assert usage_path(tmp_path, RUN) in report.changed_paths


def test_an_unconvertible_cursor_stays_byte_identical_and_is_reported(tmp_path: Path) -> None:
    broken = V6.read_text().replace("      turns: 49\n", "", 1)  # a partial main_session
    cursor = _seed(tmp_path, broken)
    before = cursor.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [cursor]
    assert cursor.read_bytes() == before
    assert not usage_path(tmp_path, RUN).exists()


def test_a_wholly_v7_body_under_a_v6_stamp_is_completed(tmp_path: Path) -> None:
    cursor = _seed(tmp_path)
    run_migrations(tmp_path, dry_run=False)
    migrated = cursor.read_text()
    usage_before = usage_path(tmp_path, RUN).read_bytes()
    # the crash window: body written, stamp not yet
    cursor.write_text(migrated.replace("schema_version: 7", "schema_version: 6", 1))

    report = run_migrations(tmp_path, dry_run=False)

    assert report.failed == ()
    assert cursor.read_text() == migrated
    assert usage_path(tmp_path, RUN).read_bytes() == usage_before


def test_a_crash_after_the_usage_write_is_idempotent(tmp_path: Path) -> None:
    """Usage first, cursor second: a crash between the two leaves a v6 cursor
    that still carries its figures, and re-running rebuilds the SAME capture."""
    cursor = _seed(tmp_path)
    original = cursor.read_bytes()
    run_migrations(tmp_path, dry_run=False)
    usage_once = load_usage(usage_path(tmp_path, RUN))
    cursor.write_bytes(original)

    run_migrations(tmp_path, dry_run=False)

    again = load_usage(usage_path(tmp_path, RUN))
    assert again is not None and usage_once is not None
    assert [c.sessions for c in again.captures] == [c.sessions for c in usage_once.captures]
