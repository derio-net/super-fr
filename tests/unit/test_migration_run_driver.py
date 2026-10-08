"""The `run` kind's 7 -> 8 migration: `RunState.driver` (gh#761).

Stamp-only: a v7 cursor's body is unchanged and reads with the live model
(an absent `driver` means the pipeline drives the run); a cursor that does
not read as v7 is refused and left byte-identical.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts import MIGRATIONS, run_migrations
from fr.artifacts.registry import read_version
from fr.run.model import parse_run_state

V7 = (
    "schema_version: 7\nrun: r1\nworkflow: fr-goal@1\nbranch: b\n"
    "started: '2026-10-02T00:00:00Z'\ncursor: brainstorm\n"
    "steps:\n  brainstorm:\n    state: pending\n"
)


def _seed(root: Path, text: str) -> Path:
    path = root / "docs" / "superpowers" / "runs" / "r1.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_hop_is_registered_and_moves_seven_to_eight() -> None:
    chain = MIGRATIONS.chain("run", 7)
    assert [(m.from_version, m.to_version) for m in chain] == [(7, 8), (8, 9), (9, 10)]


def test_a_v7_cursor_is_stamped_eight_and_its_body_is_untouched(tmp_path: Path) -> None:
    cursor = _seed(tmp_path, V7)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.failed == (), report.failed
    # The chain carries on through 8 -> 9 (`run_bound_model`) and 9 -> 10
    # (`run_fr_version`), stamp-only too.
    assert read_version("run", cursor) == 10
    assert cursor.read_text() == V7.replace("schema_version: 7", "schema_version: 10")
    assert parse_run_state(cursor.read_text()).driver is None


def test_a_standalone_cursor_round_trips_its_driver(tmp_path: Path) -> None:
    text = V7.replace("schema_version: 7", "schema_version: 8") + "driver: standalone\n"
    assert parse_run_state(text).driver == "standalone"


def test_a_cursor_that_does_not_read_as_v7_is_refused_unchanged(tmp_path: Path) -> None:
    broken = V7 + "nonsense_key: 1\n"
    cursor = _seed(tmp_path, broken)

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [cursor]
    assert "version-7" in report.failed[0].error
    assert cursor.read_text() == broken
