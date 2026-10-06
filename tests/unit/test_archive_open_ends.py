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


# --- T2: listing and selection (R8, R9) ---


def _journal(
    repo: Path, scope: str, slug: str, entries: list[JournalEntry], *, archived: bool = False
) -> Path:
    from fr.journal.model import archived_journal_path

    path = (archived_journal_path if archived else journal_path)(repo, scope, slug)  # type: ignore[arg-type]
    for e in entries:
        append_journal_entry(path, slug, e)
    return path


def _entry(
    scope: str,
    fid: str,
    title: str = "t",
    *,
    state: str = "open",
    resolves: str | None = None,
    tracked_by: str | None = None,
    out_of_scope: bool = False,
) -> JournalEntry:
    return JournalEntry(
        kind="finding",
        scope=scope,  # type: ignore[arg-type]
        id=fid,
        created="2026-10-06T00:00:00+00:00",
        state=state,  # type: ignore[arg-type]
        title=title,
        body=f"body of {fid}",
        resolves=resolves,
        tracked_by=tracked_by,
        out_of_scope=out_of_scope,
    )


def test_open_ends_keeps_open_and_out_of_scope_and_drops_the_rest(tmp_path: Path) -> None:
    from fr.archive_followups import open_ends

    _journal(
        tmp_path,
        "plan",
        "p1",
        [
            _entry("plan", "a", "still open"),
            _entry("plan", "b", "scoped out"),
            _entry("plan", "b-resolved", resolves="b", out_of_scope=True),
            _entry("plan", "c", "fixed", state="fixed"),
            _entry("plan", "d", "deferred"),
            _entry("plan", "d-resolved", resolves="d", tracked_by="https://x.example/i/1"),
            _entry("plan", "e", "refuted", state="refuted"),
        ],
        archived=True,
    )
    ends = open_ends(tmp_path, [("plan", "p1")])
    assert [(e.qid, e.state, e.title) for e in ends] == [
        ("plan/p1/a", "open", "still open"),
        ("plan/p1/b", "out-of-scope", "scoped out"),
    ]
    assert ends[0].body == "body of a"
    assert ends[0].path.name == "p1.md"


def test_open_ends_reads_a_missing_or_unparseable_journal_as_empty(tmp_path: Path) -> None:
    from fr.archive_followups import open_ends

    from fr.journal.model import archived_journal_path

    path = archived_journal_path(tmp_path, "spec", "bad")
    path.parent.mkdir(parents=True)
    path.write_text("<!-- fr:journal kind=finding scope=spec id=x created=NOPE -->\n")
    assert open_ends(tmp_path, [("spec", "bad"), ("plan", "missing")]) == []


def test_journals_from_log_names_the_archived_journals(tmp_path: Path) -> None:
    from fr.archive_followups import journals_from_log

    base = Path("docs/superpowers")
    moves = [
        (base / "plans/p1", base / "implemented/plans/p1"),
        (base / "journals/plans/p1.md", base / "implemented/journals/plans/p1.md"),
        (base / "journals/specs/s1.md", base / "implemented/journals/specs/s1.md"),
        (base / "journals/debug/d1.md", base / "implemented/journals/debug/d1.md"),
        (base / "journals/weird/z.md", base / "implemented/journals/weird/z.md"),
    ]
    assert journals_from_log(moves) == [("plan", "p1"), ("spec", "s1"), ("debug", "d1")]


def _two_journals(repo: Path) -> list:
    from fr.archive_followups import open_ends

    _journal(
        repo,
        "plan",
        "p1",
        [_entry("plan", "f1", "plan one"), _entry("plan", "u", "u")],
        archived=True,
    )
    _journal(
        repo,
        "spec",
        "s1",
        [_entry("spec", "f1", "spec one"), _entry("spec", "x", "x")],
        archived=True,
    )
    return open_ends(repo, [("plan", "p1"), ("spec", "s1")])


def test_select_all_returns_every_listed_end(tmp_path: Path) -> None:
    from fr.archive_followups import select

    listed = _two_journals(tmp_path)
    chosen, refused = select(listed, "all", tmp_path)
    assert chosen == listed and refused == []


def test_select_a_bare_id_must_be_unique_among_the_listed(tmp_path: Path) -> None:
    from fr.archive_followups import select

    listed = _two_journals(tmp_path)
    chosen, refused = select(listed, "u,x", tmp_path)
    assert [e.qid for e in chosen] == ["plan/p1/u", "spec/s1/x"] and refused == []
    chosen, refused = select(listed, "f1", tmp_path)
    assert refused and "ambiguous" in refused[0] and "plan/p1/f1" in refused[0]
    chosen, refused = select(listed, "nope", tmp_path)
    assert refused and "nope" in refused[0]


def test_select_a_qid_resolves_against_its_journal_live_or_archived(tmp_path: Path) -> None:
    from fr.archive_followups import select

    _journal(tmp_path, "plan", "live", [_entry("plan", "q1", "live one")])
    _journal(tmp_path, "spec", "old", [_entry("spec", "q2", "old one")], archived=True)
    chosen, refused = select([], "plan/live/q1, spec/old/q2", tmp_path)
    assert refused == []
    assert [(e.qid, e.title) for e in chosen] == [
        ("plan/live/q1", "live one"),
        ("spec/old/q2", "old one"),
    ]


def test_select_refuses_a_qid_that_is_not_an_open_end(tmp_path: Path) -> None:
    from fr.archive_followups import select

    _journal(tmp_path, "plan", "p", [_entry("plan", "done", state="fixed")])
    for bad in ("plan/p/done", "plan/p/ghost", "plan/nojournal/x", "weird/p/x", "a/b/c/d"):
        chosen, refused = select([], bad, tmp_path)
        assert chosen == [] and len(refused) == 1, bad
