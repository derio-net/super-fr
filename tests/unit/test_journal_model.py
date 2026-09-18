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


class TestHandoff:
    """`compose_handoff` — the curated executor brief (methodology
    restoration): open findings and dependency-relevant entries in full,
    unrelated fixed history collapsed to one line each, raw pointer always
    present."""

    def _entries(self):
        return [
            _entry(
                id="o1",
                kind="finding",
                state="open",
                phase=9,
                title="Open elsewhere",
                body="actionable anywhere",
            ),
            _entry(
                id="f-dep",
                kind="finding",
                state="fixed",
                phase=1,
                title="Fixed on dep",
                body="relevant history",
            ),
            _entry(
                id="f-old",
                kind="finding",
                state="fixed",
                phase=5,
                title="Fixed elsewhere",
                body="ancient detail " * 20,
            ),
            _entry(
                id="d-dep", kind="decision", phase=1, title="Dep decision", body="why we did it"
            ),
            _entry(
                id="d-far",
                kind="decision",
                phase=5,
                title="Far decision",
                body="unrelated rationale",
            ),
            _entry(
                id="d-any",
                kind="decision",
                phase=None,
                title="Global decision",
                body="applies to all",
            ),
            _entry(
                id="v-dep", kind="discovery", phase=2, title="Dep discovery", body="trap to avoid"
            ),
            _entry(
                id="v-far", kind="discovery", phase=5, title="Far discovery", body="unrelated note"
            ),
        ]

    def test_open_findings_render_in_full(self) -> None:
        from fr.journal.model import compose_handoff

        out = compose_handoff(self._entries(), phase=2, depends_on=(1,), scope="plan", slug="s")

        assert "actionable anywhere" in out

    def test_dependency_scoped_entries_render_in_full(self) -> None:
        from fr.journal.model import compose_handoff

        out = compose_handoff(self._entries(), phase=2, depends_on=(1,), scope="plan", slug="s")

        assert "relevant history" in out
        assert "why we did it" in out
        assert "trap to avoid" in out
        assert "applies to all" in out

    def test_unrelated_fixed_history_collapses_to_one_line_each(self) -> None:
        from fr.journal.model import compose_handoff

        out = compose_handoff(self._entries(), phase=2, depends_on=(1,), scope="plan", slug="s")

        assert "Far decision" in out
        assert "unrelated rationale" not in out
        assert "Far discovery" in out
        assert "unrelated note" not in out
        assert "Fixed elsewhere" in out
        assert "ancient detail" not in out

    def test_collapsed_lines_carry_state_and_phase(self) -> None:
        from fr.journal.model import compose_handoff

        out = compose_handoff(self._entries(), phase=2, depends_on=(1,), scope="plan", slug="s")

        assert "f-old" in out and "fixed" in out and "phase 5" in out

    def test_raw_pointer_is_always_present(self) -> None:
        from fr.journal.model import compose_handoff

        out = compose_handoff(self._entries(), phase=2, depends_on=(1,), scope="plan", slug="s")

        assert "fr journal render --scope plan --slug s" in out

    def test_empty_journal_composes_to_pointer_only(self) -> None:
        from fr.journal.model import compose_handoff

        out = compose_handoff([], phase=1, scope="plan", slug="s")

        assert "fr journal render --scope plan --slug s" in out
        assert "Open" not in out


class TestEffectiveFindingStates:
    """Phase 7 (spec §3.G.1): a finding's state is a FOLD over records in file
    order, not a field read off its own entry.

    The journal is an audit log, so `fr journal resolve` appends a *resolution
    record* naming the finding rather than rewriting it — a finding mutated in
    place would erase that it was ever open. The last record for an id wins.
    """

    def test_a_journal_with_no_resolution_records_folds_to_each_findings_own_state(
        self,
    ) -> None:
        """Back-compat: every journal written before phase 7 has no resolution
        record at all, so the fold must agree with the old per-entry read."""
        from fr.journal.model import effective_finding_states, open_finding_ids

        entries = [
            _entry(kind="finding", id="f1", state="open"),
            _entry(kind="finding", id="f2", state="fixed"),
            _entry(kind="finding", id="f3", state="refuted"),
            _entry(kind="decision", id="d1", phase=None),
        ]
        assert effective_finding_states(entries) == {"f1": "open", "f2": "fixed", "f3": "refuted"}
        assert open_finding_ids(entries) == ["f1"]

    def test_an_older_journal_file_on_disk_still_folds(self) -> None:
        """The same property through the real parser, on text in the exact
        pre-phase-7 shape (no `resolves=` token anywhere)."""
        from fr.journal.model import effective_finding_states, parse_journal

        text = (
            "# Journal: legacy\n\n"
            "<!-- fr:journal kind=finding scope=plan id=old1 created=2026-07-22T10:00:00 "
            "state=open -->\n### old1 · finding [open] · an old bug\n\nbody\n\n"
            "<!-- fr:journal kind=discovery scope=plan id=old2 created=2026-07-22T10:01:00 "
            "-->\n### old2 · discovery · a note\n\nbody\n"
        )
        assert effective_finding_states(parse_journal(text)) == {"old1": "open"}

    def test_a_resolution_record_supersedes_the_original_state(self) -> None:
        from fr.journal.model import effective_finding_states, open_finding_ids

        entries = [
            _entry(kind="finding", id="f1", state="open", title="a bug"),
            _entry(
                kind="finding",
                id="f1-resolved",
                state="fixed",
                resolves="f1",
                title="resolves f1: superseded by phase 2",
            ),
        ]
        assert effective_finding_states(entries)["f1"] == "fixed"
        assert open_finding_ids(entries) == []
        # The original entry is untouched — that it was ever open is the record.
        assert entries[0].state == "open"

    def test_a_resolution_record_does_not_register_as_a_finding_of_its_own(self) -> None:
        """A record carrying `resolves` speaks about the target finding, not
        about itself, or resolving would open a new finding every time."""
        from fr.journal.model import effective_finding_states

        entries = [
            _entry(kind="finding", id="f1", state="open"),
            _entry(kind="finding", id="f1-resolved", state="fixed", resolves="f1"),
        ]
        assert set(effective_finding_states(entries)) == {"f1"}

    def test_the_last_record_wins_so_a_resolved_finding_can_be_reopened(self) -> None:
        from fr.journal.model import effective_finding_states, open_finding_ids

        entries = [
            _entry(kind="finding", id="f1", state="open"),
            _entry(kind="finding", id="f1-resolved", state="fixed", resolves="f1"),
            _entry(kind="finding", id="f1-again", state="open", resolves="f1"),
        ]
        assert effective_finding_states(entries)["f1"] == "open"
        assert open_finding_ids(entries) == ["f1"]

    def test_a_resolution_record_for_an_unknown_finding_still_folds(self) -> None:
        """A record can only be written by `resolve`, which refuses an unknown
        id — but a journal spliced by hand must not make the fold crash."""
        from fr.journal.model import effective_finding_states

        entries = [_entry(kind="finding", id="x-resolved", state="fixed", resolves="ghost")]
        assert effective_finding_states(entries) == {"ghost": "fixed"}

    def test_open_finding_ids_are_in_first_appearance_order(self) -> None:
        from fr.journal.model import open_finding_ids

        entries = [
            _entry(kind="finding", id="b", state="open"),
            _entry(kind="finding", id="a", state="open"),
            _entry(kind="finding", id="b-resolved", state="fixed", resolves="b"),
            _entry(kind="finding", id="b-again", state="open", resolves="b"),
        ]
        assert open_finding_ids(entries) == ["b", "a"]


class TestResolvesRoundTrip:
    def test_resolves_survives_serialize_parse(self) -> None:
        from fr.journal.model import parse_journal, serialize_entry

        e = _entry(kind="finding", id="f1-resolved", state="fixed", resolves="f1", title="r")
        parsed = parse_journal(serialize_entry(e))
        assert parsed[0] == e
        assert parsed[0].resolves == "f1"

    def test_resolves_requires_a_finding_entry(self) -> None:
        from fr.journal.model import JournalEntry

        with pytest.raises(ValidationError):
            JournalEntry(
                kind="decision",
                scope="plan",
                id="d1",
                created="2026-09-18T10:00:00",
                title="t",
                resolves="f1",
            )

    def test_a_record_cannot_resolve_itself(self) -> None:
        from fr.journal.model import JournalEntry

        with pytest.raises(ValidationError):
            JournalEntry(
                kind="finding",
                scope="plan",
                id="f1",
                created="2026-09-18T10:00:00",
                title="t",
                state="fixed",
                resolves="f1",
            )


class TestHandoffReadsEffectiveState:
    def test_a_resolved_finding_leaves_the_open_findings_section(self) -> None:
        """A handoff that keeps showing a resolved finding as open is the noise
        the fold exists to remove; what became of it stays visible."""
        from fr.journal.model import compose_handoff

        entries = [
            _entry(kind="finding", id="f1", state="open", phase=9, title="Open elsewhere"),
            _entry(
                kind="finding",
                id="f1-resolved",
                state="fixed",
                phase=9,
                resolves="f1",
                title="resolves f1: fixed in phase 9",
            ),
        ]
        out = compose_handoff(entries, phase=2, depends_on=(1,), scope="plan", slug="s")
        assert "## Open findings" not in out
        assert "resolves f1" in out  # the resolution is still on the record

    def test_a_reopened_finding_returns_to_the_open_findings_section(self) -> None:
        from fr.journal.model import compose_handoff

        entries = [
            _entry(kind="finding", id="f1", state="open", phase=9, title="Open elsewhere"),
            _entry(kind="finding", id="f1-resolved", state="fixed", phase=9, resolves="f1"),
            _entry(kind="finding", id="f1-again", state="open", phase=9, resolves="f1"),
        ]
        out = compose_handoff(entries, phase=2, depends_on=(1,), scope="plan", slug="s")
        assert "## Open findings" in out
        assert "Open elsewhere" in out


# --- Forward compatibility: an OLDER fr must keep reading a NEWER journal. ---


def test_a_header_token_this_fr_does_not_know_is_ignored_not_fatal() -> None:
    """The property that let phase 7 add `resolves=` with no stamp bump and no
    migration — and it is load-bearing rather than incidental, which is why it
    is pinned here.

    `JournalEntry` is `extra="forbid"`, exactly like `RunState`. What keeps an
    older fr able to read a newer journal is that `parse_journal` constructs the
    entry from EXPLICITLY NAMED keys rather than splatting `**fields`, so an
    unknown token stays in the dict and never reaches the model. Verified
    against a real release rather than by reading: `fr` 4.4.0 renders this
    repo's phase-7 journal — nine `resolves=` records — at exit 0, while the
    same test against the `run` kind fails loudly (`schema_version — Extra
    inputs are not permitted`), because `RunState` is built by parsing the whole
    mapping. Same closed-world model, opposite outcome, purely construction
    style.

    Nothing guarded that difference until this test. Refactoring the parser to
    `JournalEntry(**fields)` is an obvious tidy-up and would silently turn every
    future optional header field into a breaking change, the first symptom being
    an older fr raising on a journal it used to read. Under `extra="forbid"`
    that refactor fails this test immediately, which is the whole point.
    """
    from fr.journal.model import parse_journal

    text = (
        "<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-18T00:00:00 "
        "state=open some_future_field=whatever -->\n"
        "### f1 · finding [open] · A finding from a newer fr\n"
        "\n"
        "Body.\n"
    )
    entries = parse_journal(text)
    assert [e.id for e in entries] == ["f1"]
    assert entries[0].state == "open"
    assert entries[0].title == "A finding from a newer fr"


def test_an_unknown_token_does_not_disturb_the_effective_state_fold() -> None:
    """The fold is what `fr journal check` and fr-goal §7's delivery gate read,
    so an unreadable-to-us token must not make a finding look resolved (or a
    resolved one look open)."""
    from fr.journal.model import open_finding_ids, parse_journal

    text = (
        "<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-18T00:00:00 "
        "state=open future=1 -->\n"
        "### f1 · finding [open] · Still open\n"
        "\n"
        "Body.\n"
    )
    assert open_finding_ids(parse_journal(text)) == ["f1"]
