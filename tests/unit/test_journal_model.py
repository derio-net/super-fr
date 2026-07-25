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
    def test_active_path_per_scope_subdir(self) -> None:
        from fr.journal.model import journal_path

        root = Path("/repo")
        expected = {"spec": "specs", "plan": "plans", "debug": "debug"}
        for scope, sub in expected.items():
            p = journal_path(root, scope, "2026-07-22-foo")  # type: ignore[arg-type]
            assert p == root / f"docs/superpowers/journals/{sub}/2026-07-22-foo.md"

    def test_archived_path_per_scope_subdir(self) -> None:
        from fr.journal.model import archived_journal_path

        root = Path("/repo")
        p = archived_journal_path(root, "plan", "2026-07-22-foo")
        assert p == root / "docs/superpowers/implemented/journals/plans/2026-07-22-foo.md"
        d = archived_journal_path(root, "debug", "2026-07-24-bug")
        assert d == root / "docs/superpowers/implemented/journals/debug/2026-07-24-bug.md"


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

    def test_body_starting_with_heading_round_trips(self) -> None:
        """F2: a body whose first line is a `### ...` markdown heading survives."""
        from fr.journal.model import parse_journal, serialize_entry

        e = _entry(id="e1", body="### Not the auto-heading\nmore body")
        parsed = parse_journal(serialize_entry(e))
        assert parsed[0].body == "### Not the auto-heading\nmore body"


class TestIdInvariant:
    def test_id_rejects_whitespace(self) -> None:
        """F3: the space-delimited header can't survive a space in the id."""
        from fr.journal.model import JournalEntry

        with pytest.raises(ValidationError):
            JournalEntry(
                kind="decision",
                scope="spec",
                id="has space",
                created="2026-07-22T10:00:00",
                phase=None,
                title="t",
                body="b",
            )


class TestSpecJournalSlug:
    """A spec file is `<slug>-design.md`; its spec-scope journal is keyed by the
    bare `<slug>` (2026-07-22 spec §A). The slug helper bridges the two."""

    def test_strips_design_suffix(self) -> None:
        from fr.journal.model import spec_journal_slug

        assert spec_journal_slug("2026-07-24-isolation-host-modes-design") == (
            "2026-07-24-isolation-host-modes"
        )

    def test_passes_through_stem_without_design_suffix(self) -> None:
        from fr.journal.model import spec_journal_slug

        # An older / hand-named spec with no `-design` suffix maps to itself.
        assert spec_journal_slug("2026-05-10-solo") == "2026-05-10-solo"

    def test_only_strips_a_trailing_design(self) -> None:
        from fr.journal.model import spec_journal_slug

        # `-design` mid-slug is not a suffix and must survive.
        assert spec_journal_slug("2026-01-01-design-system-design") == ("2026-01-01-design-system")


class TestResolveJournalReadPath:
    """Reads (render/check) resolve the active path if present, else the
    archived one — so a journal stays readable after its spec/plan archives."""

    def _write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Journal\n")

    def test_prefers_active_when_present(self, tmp_path: Path) -> None:
        from fr.journal.model import journal_path, resolve_journal_read_path

        active = journal_path(tmp_path, "spec", "s")
        self._write(active)
        assert resolve_journal_read_path(tmp_path, "spec", "s") == active

    def test_falls_back_to_archived(self, tmp_path: Path) -> None:
        from fr.journal.model import archived_journal_path, resolve_journal_read_path

        archived = archived_journal_path(tmp_path, "spec", "s")
        self._write(archived)
        assert resolve_journal_read_path(tmp_path, "spec", "s") == archived

    def test_active_wins_over_archived_when_both_exist(self, tmp_path: Path) -> None:
        from fr.journal.model import (
            archived_journal_path,
            journal_path,
            resolve_journal_read_path,
        )

        active = journal_path(tmp_path, "plan", "p")
        self._write(active)
        self._write(archived_journal_path(tmp_path, "plan", "p"))
        assert resolve_journal_read_path(tmp_path, "plan", "p") == active

    def test_returns_active_path_when_neither_exists(self, tmp_path: Path) -> None:
        from fr.journal.model import journal_path, resolve_journal_read_path

        resolved = resolve_journal_read_path(tmp_path, "spec", "missing")
        assert resolved == journal_path(tmp_path, "spec", "missing")
        assert not resolved.exists()
