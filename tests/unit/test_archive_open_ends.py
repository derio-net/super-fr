"""`fr archive` open ends → issues (spec 2026-10-06-archive-followups-design §C)."""

from __future__ import annotations

from pathlib import Path

from fr.journal.model import (
    JournalEntry,
    append_journal_entry,
    effective_finding_states,
    journal_path,
    parse_journal,
    resolution_entry,
    resolution_record_id,
)


def _finding(fid: str = "f1", title: str = "a finding") -> JournalEntry:
    return JournalEntry(
        kind="finding",
        scope="plan",
        id=fid,
        created="2026-10-06T00:00:00+00:00",
        state="open",
        title=title,
        body="why it matters",
    )


# --- T1: the shared deferral builder (R12) ---


def test_resolution_entry_builds_the_deferral_the_record_engine_builds(tmp_path: Path) -> None:
    f = _finding()
    entry = resolution_entry(
        target=f,
        taken={"f1"},
        created="2026-10-06T01:00:00+00:00",
        state="deferred",
        body="Filed at archive as https://x.example/issues/1.",
        phase=None,
        tracked_by="https://x.example/issues/1",
    )
    assert entry.id == resolution_record_id("f1", {"f1"}) == "f1-resolved"
    assert entry.title == "resolves f1: a finding"
    assert entry.state == "open"
    assert entry.resolves == "f1"
    assert entry.tracked_by == "https://x.example/issues/1"
    assert entry.scope == "plan"
    assert entry.kind == "finding"
    assert entry.out_of_scope is False
    assert effective_finding_states([f, entry]) == {"f1": "deferred"}
