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

    def test_duplicate_entry_id_raises(self) -> None:
        from fr.journal.model import JournalParseError, parse_journal, serialize_entry

        text = "\n".join((serialize_entry(_entry(id="same")), serialize_entry(_entry(id="same"))))

        with pytest.raises(JournalParseError, match="duplicate journal entry id"):
            parse_journal(text)

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
    closed findings and unrelated context collapsed to one line each, raw pointer always
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
        """Dependency scoping survives the state-first collapse — for the two
        kinds it was ever right for. A decision is never "closed" (it still
        constrains the phase depending on it), a discovery is a trap paid for
        once, and an untagged entry is global; all three still render in full.
        """
        from fr.journal.model import compose_handoff

        out = compose_handoff(self._entries(), phase=2, depends_on=(1,), scope="plan", slug="s")

        assert "why we did it" in out
        assert "trap to avoid" in out
        assert "applies to all" in out

    def test_a_closed_finding_on_a_dependency_phase_collapses(self) -> None:
        """CHANGED CONTRACT (bounded-executor-handoff P2.T1, spec §5.A1).

        This assertion used to read `assert "relevant history" in out` and sat
        in `test_dependency_scoped_entries_render_in_full` above: `f-dep` is
        `fixed`, tagged to phase 1, which phase 2 depends on, so it rendered in
        full. That test was pinning the defect — measured at ~30k of a real
        83k handoff — and its failure on this change is the expected result,
        not a regression. State now decides before phase does: the title stays
        on the record, the body does not come along.
        """
        from fr.journal.model import compose_handoff

        out = compose_handoff(self._entries(), phase=2, depends_on=(1,), scope="plan", slug="s")

        assert "relevant history" not in out
        assert "- f-dep · finding [fixed] · Fixed on dep (phase 1)" in out

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


class TestReviewedPhases:
    """`reviewed_phases` — the pure fold `fr journal check --require-reviews`
    (phase 2) uses to decide which owed phases already have a recorded
    review. A phase "names" its review by carrying `phase=N` on a `kind=review`
    entry; an unphased review (the 5 unphased plan-scope review entries
    already in this repo's journals, spec §B) does not blanket-satisfy every
    phase, or the gate would be trivially defeated by one undated review."""

    def test_a_phased_review_entry_contributes_its_phase(self) -> None:
        from fr.journal.model import reviewed_phases

        entries = [_entry(kind="review", phase=3, title="phase 3 review")]
        assert reviewed_phases(entries) == {3}

    def test_an_unphased_review_entry_contributes_nothing(self) -> None:
        from fr.journal.model import reviewed_phases

        entries = [_entry(kind="review", phase=None, title="a general review")]
        assert reviewed_phases(entries) == set()

    def test_a_finding_with_a_phase_contributes_nothing(self) -> None:
        from fr.journal.model import reviewed_phases

        entries = [_entry(kind="finding", phase=3, state="open", title="a bug")]
        assert reviewed_phases(entries) == set()

    def test_empty_entries_gives_empty_set(self) -> None:
        from fr.journal.model import reviewed_phases

        assert reviewed_phases([]) == set()

    def test_two_reviews_of_the_same_phase_give_one_element(self) -> None:
        from fr.journal.model import reviewed_phases

        entries = [
            _entry(kind="review", id="r1", phase=2, title="first pass"),
            _entry(kind="review", id="r2", phase=2, title="second pass"),
        ]
        assert reviewed_phases(entries) == {2}


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


def test_a_deferred_finding_is_neither_open_nor_closed_in_the_fold() -> None:
    from fr.journal.model import (
        effective_finding_states,
        open_finding_ids,
        parse_journal,
        phase_finding_states,
    )

    text = (
        "<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-22T00:00:00 "
        "phase=2 state=open -->\n### f1 · finding [open] · real but later (phase 2)\n\nbody\n\n"
        "<!-- fr:journal kind=finding scope=plan id=f1-resolved created=2026-09-22T00:01:00 "
        "state=open resolves=f1 tracked_by=#535 -->\n"
        "### f1-resolved · finding [deferred → #535] · resolves f1: real but later\n\nwhy\n"
    )
    entries = parse_journal(text)
    assert effective_finding_states(entries) == {"f1": "deferred"}
    assert open_finding_ids(entries) == []
    # `fr run resolve`'s findings obligation reads this map: deferred != open.
    assert phase_finding_states(entries, 2) == {"f1": "deferred"}


def test_tracked_by_is_only_valid_on_an_open_resolution_record() -> None:
    from fr.journal.model import JournalEntry

    base = dict(kind="finding", scope="plan", id="r", created="t", title="x", body="")
    with pytest.raises(ValueError, match="tracked_by"):
        JournalEntry(**base, state="open", tracked_by="#1")  # no `resolves`
    with pytest.raises(ValueError, match="tracked_by"):
        JournalEntry(**base, state="fixed", resolves="f1", tracked_by="#1")
    ok = JournalEntry(**base, state="open", resolves="f1", tracked_by="#1")
    assert ok.tracked_by == "#1"


# --- out-of-scope (spec 2026-09-24 §A) ------------------------------------

_OOS_TEXT = (
    "<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-24T00:00:00 "
    "phase=2 state=open -->\n### f1 · finding [open] · true, not ours (phase 2)\n\nbody\n\n"
    "<!-- fr:journal kind=finding scope=plan id=f1-resolved created=2026-09-24T00:01:00 "
    "state=open resolves=f1 out_of_scope=true -->\n"
    "### f1-resolved · finding [out-of-scope] · resolves f1: true, not ours\n\nwhy\n"
)


class TestOutOfScope:
    """A finding that is TRUE but not caused by this change. Written the way
    `deferred` is — `state=open` plus a token — so an fr that predates the
    token reads the finding as still open (fail closed), never as closed and
    never as a parse error."""

    def test_the_fold_reads_it_as_out_of_scope_and_the_gates_stop_counting_it(self) -> None:
        from fr.journal.model import (
            effective_finding_states,
            open_finding_ids,
            parse_journal,
            phase_finding_states,
        )

        entries = parse_journal(_OOS_TEXT)
        record = entries[1]
        assert record.state == "open" and record.out_of_scope is True
        assert effective_finding_states(entries) == {"f1": "out-of-scope"}
        assert open_finding_ids(entries) == []
        assert phase_finding_states(entries, 2) == {"f1": "out-of-scope"}

    def test_a_reader_that_ignores_the_token_reads_it_open(self) -> None:
        """Simulates an older fr: the token is stripped before parsing, which is
        exactly what a named-key projection that does not know it amounts to."""
        from fr.journal.model import open_finding_ids, parse_journal

        older = _OOS_TEXT.replace(" out_of_scope=true", "")
        assert open_finding_ids(parse_journal(older)) == ["f1"]

    def test_a_later_deferral_supersedes_it(self) -> None:
        from fr.journal.model import effective_finding_states, parse_journal

        text = _OOS_TEXT + (
            "\n<!-- fr:journal kind=finding scope=plan id=f1-resolved-2 "
            "created=2026-09-24T00:02:00 state=open resolves=f1 tracked_by=#9 -->\n"
            "### f1-resolved-2 · finding [deferred → #9] · resolves f1: filed\n\nfiled\n"
        )
        assert effective_finding_states(parse_journal(text)) == {"f1": "deferred"}

    def test_it_round_trips_and_is_serialized_only_when_true(self) -> None:
        from fr.journal.model import parse_journal, serialize_entry

        record = _entry(kind="finding", id="r1", state="open", resolves="f1", out_of_scope=True)
        text = serialize_entry(record)
        assert "out_of_scope=true" in text.splitlines()[0]
        assert "[out-of-scope]" in text.splitlines()[1]
        assert parse_journal(text)[0].out_of_scope is True
        plain = serialize_entry(_entry(kind="finding", id="f2", state="open"))
        assert "out_of_scope" not in plain

    def test_only_an_open_resolution_record_may_carry_it(self) -> None:
        from fr.journal.model import JournalEntry

        base = dict(kind="finding", scope="plan", id="r", created="t", title="x", body="")
        with pytest.raises(ValueError, match="out_of_scope"):
            JournalEntry(**base, state="open", out_of_scope=True)  # no `resolves`
        with pytest.raises(ValueError, match="out_of_scope"):
            JournalEntry(**base, state="fixed", resolves="f1", out_of_scope=True)
        with pytest.raises(ValueError, match="out_of_scope"):
            JournalEntry(**base, state="open", resolves="f1", tracked_by="#1", out_of_scope=True)


def test_a_review_scope_value_this_fr_does_not_know_is_dropped_not_fatal() -> None:
    """The tag is display-only: one bad value must not make the journal — and
    every gate reading it — unparseable."""
    from fr.journal.model import open_finding_ids, parse_journal

    text = (
        "<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-24T00:00:00 "
        "state=open review_scope=partly -->\n### f1 · finding [open] · x\n"
    )
    entries = parse_journal(text)
    assert entries[0].review_scope is None
    assert open_finding_ids(entries) == ["f1"]


# --- the operator guard (spec 2026-09-24 §A) -------------------------------


def _oos_then(*records: dict) -> list:
    """f1, resolved out-of-scope, then `records` (each a resolution of f1)."""
    entries = [
        _entry(kind="finding", id="f1", state="open"),
        _entry(kind="finding", id="f1-r1", state="open", resolves="f1", out_of_scope=True),
    ]
    for n, extra in enumerate(records, start=2):
        entries.append(_entry(kind="finding", id=f"f1-r{n}", resolves="f1", **extra))
    return entries


class TestUnauthorizedFixes:
    """Moving a finding from out-of-scope to fixed puts work the orchestrator
    judged not this change's back INTO the change — the scope ratchet the state
    exists to stop. Only the operator may do that, so the `fixed` record must
    carry `answered_by=operator`. Enforced in the fold, where every write path
    (`resolve`, `add --resolves`) meets."""

    def test_a_fix_after_out_of_scope_without_the_operator_is_unauthorized(self) -> None:
        from fr.journal.model import unauthorized_fixes

        assert unauthorized_fixes(_oos_then({"state": "fixed"})) == ["f1"]
        assert unauthorized_fixes(_oos_then({"state": "fixed", "answered_by": "agent"})) == ["f1"]

    def test_the_operator_authorizes_it(self) -> None:
        from fr.journal.model import unauthorized_fixes

        assert unauthorized_fixes(_oos_then({"state": "fixed", "answered_by": "operator"})) == []

    def test_a_later_operator_record_ratifies_an_unauthorized_fix(self) -> None:
        """The journal is append-only, so the cure is a new record, not an edit."""
        from fr.journal.model import unauthorized_fixes

        entries = _oos_then({"state": "fixed"}, {"state": "fixed", "answered_by": "operator"})
        assert unauthorized_fixes(entries) == []

    def test_a_fix_that_never_passed_through_out_of_scope_needs_nobody(self) -> None:
        from fr.journal.model import unauthorized_fixes

        entries = [
            _entry(kind="finding", id="f1", state="open"),
            _entry(kind="finding", id="f1-r", state="fixed", resolves="f1"),
            _entry(kind="finding", id="f2", state="fixed"),
        ]
        assert unauthorized_fixes(entries) == []

    def test_moving_away_from_fixed_clears_it(self) -> None:
        from fr.journal.model import unauthorized_fixes

        entries = _oos_then({"state": "fixed"}, {"state": "refuted"})
        assert unauthorized_fixes(entries) == []

    def test_a_deferral_in_between_hands_the_finding_back_to_the_change(self) -> None:
        """The guard reads the IMMEDIATELY preceding state: once a deferral names
        the issue that carries the work, out-of-scope is no longer the finding's
        state, so a later fix is an ordinary one and needs no operator."""
        from fr.journal.model import effective_finding_states, unauthorized_fixes

        entries = _oos_then({"state": "open", "tracked_by": "#1"}, {"state": "fixed"})
        assert effective_finding_states(entries)["f1"] == "fixed"
        assert unauthorized_fixes(entries) == []

    def test_answered_by_round_trips_and_is_only_for_a_resolution_record(self) -> None:
        from fr.journal.model import JournalEntry, parse_journal, serialize_entry

        record = _entry(
            kind="finding", id="r", state="fixed", resolves="f1", answered_by="operator"
        )
        assert "answered_by=operator" in serialize_entry(record).splitlines()[0]
        assert parse_journal(serialize_entry(record))[0].answered_by == "operator"
        base = dict(kind="finding", scope="plan", id="x", created="t", title="x", body="")
        with pytest.raises(ValueError, match="answered_by"):
            JournalEntry(**base, state="fixed", answered_by="operator")

    def test_an_unknown_answered_by_value_reads_as_absent(self) -> None:
        """Fail closed: a value this fr does not know is not `operator`."""
        from fr.journal.model import parse_journal, unauthorized_fixes

        text = (
            "<!-- fr:journal kind=finding scope=plan id=f1 created=2026-09-24T00:00:00 "
            "state=open -->\n### f1 · finding [open] · x\n\n"
            "<!-- fr:journal kind=finding scope=plan id=r1 created=2026-09-24T00:01:00 "
            "state=open resolves=f1 out_of_scope=true -->\n### r1 · finding · y\n\n"
            "<!-- fr:journal kind=finding scope=plan id=r2 created=2026-09-24T00:02:00 "
            "state=fixed resolves=f1 answered_by=committee -->\n### r2 · finding · z\n"
        )
        assert unauthorized_fixes(parse_journal(text)) == ["f1"]


def test_a_journal_stamp_reads_as_local_time(monkeypatch) -> None:
    """`fr journal` stamps LOCAL wall-clock time with no offset, while the
    transcript reader treats a naive stamp as UTC. Handed over raw, a record
    written at 21:00 in Athens (18:00Z) would open the question window three
    hours late and refuse an operator who answered in between."""
    import time

    from fr.journal.model import journal_stamp_as_utc

    monkeypatch.setenv("TZ", "Europe/Athens")
    time.tzset()
    try:
        assert journal_stamp_as_utc("2026-09-24T21:00:00") == "2026-09-24T18:00:00+00:00"
        assert journal_stamp_as_utc("2026-09-24T21:00:00+00:00") == "2026-09-24T21:00:00+00:00"
    finally:
        monkeypatch.undo()
        time.tzset()
