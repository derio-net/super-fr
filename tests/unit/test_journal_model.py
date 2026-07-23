"""Unit tests for the `fr journal` primitive model (Phase 1).

Spec: docs/superpowers/specs/2026-07-22-fr-goal-subagent-execution-design.md §A.
The journal is a scope-keyed (spec|plan|debug), append-only, CLI-only durable
log. This module pins the entry schema, the scope→path resolution, and the
serialize/parse round-trip that keeps the file both human-readable and
machine-parseable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError


class TestJournalEntry:
    def test_accepts_every_defined_kind(self) -> None:
        from fr.journal.model import JournalEntry

        for kind in (
            "decision",
            "review",
            "discovery",
            "finding",
            "repro",
            "hypothesis",
            "ruled-out",
            "root-cause",
        ):
            state = "open" if kind == "finding" else None
            e = JournalEntry(
                kind=kind,
                scope="plan",
                id="e1",
                created="2026-07-22T10:00:00",
                phase=1,
                title="t",
                body="b",
                state=state,
            )
            assert e.kind == kind

    def test_rejects_unknown_kind(self) -> None:
        from fr.journal.model import JournalEntry

        with pytest.raises(ValidationError):
            JournalEntry(
                kind="bogus",
                scope="plan",
                id="e1",
                created="2026-07-22T10:00:00",
                phase=None,
                title="t",
                body="b",
            )

    def test_accepts_every_scope(self) -> None:
        from fr.journal.model import JournalEntry

        for scope in ("spec", "plan", "debug"):
            e = JournalEntry(
                kind="decision",
                scope=scope,
                id="e1",
                created="2026-07-22T10:00:00",
                phase=None,
                title="t",
                body="b",
            )
            assert e.scope == scope

    def test_rejects_unknown_scope(self) -> None:
        from fr.journal.model import JournalEntry

        with pytest.raises(ValidationError):
            JournalEntry(
                kind="decision",
                scope="galaxy",
                id="e1",
                created="2026-07-22T10:00:00",
                phase=None,
                title="t",
                body="b",
            )

    def test_finding_requires_state(self) -> None:
        from fr.journal.model import JournalEntry

        with pytest.raises(ValidationError):
            JournalEntry(
                kind="finding",
                scope="plan",
                id="f1",
                created="2026-07-22T10:00:00",
                phase=2,
                title="t",
                body="b",
                state=None,
            )

    def test_finding_state_must_be_valid(self) -> None:
        from fr.journal.model import JournalEntry

        with pytest.raises(ValidationError):
            JournalEntry(
                kind="finding",
                scope="plan",
                id="f1",
                created="2026-07-22T10:00:00",
                phase=2,
                title="t",
                body="b",
                state="maybe",
            )

    def test_non_finding_forbids_state(self) -> None:
        from fr.journal.model import JournalEntry

        with pytest.raises(ValidationError):
            JournalEntry(
                kind="discovery",
                scope="plan",
                id="d1",
                created="2026-07-22T10:00:00",
                phase=2,
                title="t",
                body="b",
                state="open",
            )

    def test_is_frozen(self) -> None:
        from fr.journal.model import JournalEntry

        e = JournalEntry(
            kind="decision",
            scope="spec",
            id="e1",
            created="2026-07-22T10:00:00",
            phase=None,
            title="t",
            body="b",
        )
        with pytest.raises(ValidationError):
            e.title = "mutated"  # type: ignore[misc]

    def test_extra_forbidden(self) -> None:
        from fr.journal.model import JournalEntry

        with pytest.raises(ValidationError):
            JournalEntry(
                kind="decision",
                scope="spec",
                id="e1",
                created="2026-07-22T10:00:00",
                phase=None,
                title="t",
                body="b",
                bogus_field="x",
            )


class TestJournalPath:
    def test_active_path_every_scope(self) -> None:
        from fr.journal.model import journal_path

        root = Path("/repo")
        for scope in ("spec", "plan", "debug"):
            p = journal_path(root, scope, "2026-07-22-foo")  # type: ignore[arg-type]
            assert p == root / "docs/superpowers/journals/2026-07-22-foo.md"

    def test_archived_path(self) -> None:
        from fr.journal.model import archived_journal_path

        root = Path("/repo")
        p = archived_journal_path(root, "plan", "2026-07-22-foo")
        assert p == root / "docs/superpowers/implemented/journals/2026-07-22-foo.md"


def _entry(**kw: object):
    from fr.journal.model import JournalEntry

    base = dict(
        kind="discovery",
        scope="plan",
        id="e1",
        created="2026-07-22T10:00:00",
        phase=2,
        title="a title",
        body="line one\nline two",
        state=None,
    )
    base.update(kw)
    return JournalEntry(**base)  # type: ignore[arg-type]


class TestRoundTrip:
    def test_single_entry_round_trip(self) -> None:
        from fr.journal.model import parse_journal, serialize_entry

        e = _entry()
        parsed = parse_journal(serialize_entry(e))
        assert len(parsed) == 1
        assert parsed[0] == e

    def test_finding_round_trip_preserves_state(self) -> None:
        from fr.journal.model import parse_journal, serialize_entry

        e = _entry(kind="finding", id="f1", title="a bug", state="open")
        parsed = parse_journal(serialize_entry(e))
        assert parsed[0] == e
        assert parsed[0].state == "open"

    def test_phaseless_entry_round_trip(self) -> None:
        from fr.journal.model import parse_journal, serialize_entry

        e = _entry(kind="decision", id="d1", phase=None, title="a call")
        parsed = parse_journal(serialize_entry(e))
        assert parsed[0] == e
        assert parsed[0].phase is None

    def test_three_entries_preserve_order(self) -> None:
        from fr.journal.model import parse_journal, serialize_entry

        es = [
            _entry(id="e1", title="first"),
            _entry(kind="finding", id="e2", title="second", state="fixed"),
            _entry(kind="decision", id="e3", phase=None, title="third"),
        ]
        text = "# Journal: demo\n\n" + "\n".join(serialize_entry(e) for e in es)
        parsed = parse_journal(text)
        assert [p.id for p in parsed] == ["e1", "e2", "e3"]
        assert parsed == es

    def test_preamble_before_first_delimiter_ignored(self) -> None:
        from fr.journal.model import parse_journal

        assert parse_journal("# Just a human header\n\nsome prose\n") == []

    def test_malformed_header_raises(self) -> None:
        from fr.journal.model import JournalParseError, parse_journal

        bad = "<!-- fr:journal kind finding scope=plan id=x -->\n### x\n\nbody\n"
        with pytest.raises(JournalParseError):
            parse_journal(bad)
