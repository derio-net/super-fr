"""Catalogue parser and snapshot store (spec 2026-10-06-model-binding-churn §A, R3).

The fixture is a CAPTURE of `opencode models github-copilot --verbose`
(tests/fixtures/bindings/README.md), never composed."""

from __future__ import annotations

from pathlib import Path

from fr.bindings.catalogue import CatalogueEntry, SnapshotStore, parse_catalogue

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bindings" / "opencode-models-verbose.txt"


def test_every_captured_block_parses() -> None:
    entries, skipped = parse_catalogue(FIXTURE.read_text())
    assert skipped == 0
    by_id = {e.id: e for e in entries}
    assert set(by_id) == {
        "github-copilot/claude-haiku-4.5",
        "github-copilot/claude-sonnet-5.5",
        "github-copilot/gpt-6-luna",
        "github-copilot/gpt-6.1-sol",
    }
    sol = by_id["github-copilot/gpt-6.1-sol"]
    assert sol == CatalogueEntry(
        id="github-copilot/gpt-6.1-sol",
        provider="github-copilot",
        family="gpt-sol",
        release_date="2026-09-29",
        price=12.0,
        toolcall=True,
    )
    assert by_id["github-copilot/gpt-6-luna"].price == 0.6


def test_a_malformed_block_is_skipped_and_counted_never_raised() -> None:
    text = FIXTURE.read_text() + "github-copilot/broken\n{ not json\n"
    entries, skipped = parse_catalogue(text)
    assert skipped == 1
    assert len(entries) == 4


def test_a_block_with_no_cost_has_no_price() -> None:
    text = 'p/m\n{"id": "m", "family": "f", "release_date": "2026-01-01", "capabilities": {"toolcall": true}}\n'
    (entry,), skipped = parse_catalogue(text)
    assert skipped == 0
    assert entry.price is None
    assert entry.provider == "p"


def test_snapshots_round_trip_and_keep_the_last_known_entry(tmp_path: Path) -> None:
    entries, _ = parse_catalogue(FIXTURE.read_text())
    store = SnapshotStore(tmp_path / "snapshots.json")
    store.remember(entries)
    assert SnapshotStore(tmp_path / "snapshots.json").get("github-copilot/gpt-6-luna") == next(
        e for e in entries if e.id.endswith("gpt-6-luna")
    )
    # A later catalogue that omits the model does not forget it.
    store.remember([e for e in entries if not e.id.endswith("gpt-6-luna")])
    assert store.get("github-copilot/gpt-6-luna") is not None
    assert store.get("github-copilot/never-seen") is None


def test_a_corrupt_snapshot_file_reads_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "snapshots.json"
    path.write_text("{ nope")
    assert SnapshotStore(path).get("x/y") is None
