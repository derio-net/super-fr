"""The `owed` journal kind and its fold (spec 2026-10-11-debt-engine §E, R20).

An `owed` entry records an action the operator owes. It folds apart from
findings: an open owed entry never fails `fr journal check`, and a resolution
record naming an owed entry never reads as an open finding.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.artifacts import ARTIFACT_KINDS, MIGRATIONS, run_migrations
from fr.artifacts.structure import validate_journal
from fr.cli import app
from fr.journal.model import (
    JournalEntry,
    JournalParseError,
    append_journal_entry,
    journal_path,
    open_finding_ids,
    open_owed_ids,
    owed_body,
    owed_fields,
    owed_filed_as,
    parse_journal,
    resolution_entry,
    serialize_entry,
)
from typer.testing import CliRunner

runner = CliRunner()
KEY = "spec:2026-10-11-x#step1"


def _owed(eid: str = "test-plan-step-1", key: str = KEY) -> JournalEntry:
    return JournalEntry(
        kind="owed",
        scope="spec",
        id=eid,
        created="2026-10-11T10:00:00+00:00",
        title="Test Plan step 1 owed",
        body=owed_body(
            what="dispatch the workflow",
            why="needs main",
            how="fr journal resolve --scope spec --slug 2026-10-11-x --id test-plan-step-1 "
            '--state fixed --note "<evidence>"',
            key=key,
        ),
    )


def _record(target: JournalEntry, taken: set[str], **kw: object) -> JournalEntry:
    return resolution_entry(
        target=target,
        scope="spec",
        taken=taken,
        created="2026-10-11T11:00:00+00:00",
        body=str(kw.pop("body", "note")),
        **kw,  # type: ignore[arg-type]
    )


def _roundtrip(entries: list[JournalEntry]) -> list[JournalEntry]:
    return parse_journal("# Journal: x\n\n" + "\n".join(serialize_entry(e) for e in entries))


def test_an_owed_entry_parses_and_carries_its_fields() -> None:
    (entry,) = _roundtrip([_owed()])
    assert entry.kind == "owed"
    assert entry.state is None
    fields = owed_fields(entry)
    assert fields["owed_key"] == KEY
    assert fields["what"] == "dispatch the workflow"
    assert fields["why"] == "needs main"
    assert fields["how"].startswith("fr journal resolve")


def test_an_owed_entry_carries_no_state() -> None:
    with pytest.raises(ValueError):
        JournalEntry(
            kind="owed", scope="spec", id="o", created="c", title="t", state="open", body=""
        )


def test_owed_body_refuses_a_key_of_the_wrong_shape() -> None:
    for bad in ("nope", "spec:x", "spec:x#step1 -->", "-x", "plan:x#step1"):
        with pytest.raises(ValueError):
            owed_body(what="w", why="y", how="h", key=bad)


def test_open_finding_ids_ignores_records_naming_an_owed_entry() -> None:
    owed = _owed()
    filed = _record(owed, {owed.id}, state="open", filed_as="derio-net/super-fr#12")
    entries = _roundtrip([owed, filed])
    assert open_finding_ids(entries) == []
    assert open_owed_ids(entries) == ["test-plan-step-1"]


def test_filed_as_is_still_owed_and_names_its_issue() -> None:
    owed = _owed()
    filed = _record(owed, {owed.id}, state="open", filed_as="derio-net/super-fr#12")
    entries = _roundtrip([owed, filed])
    assert entries[1].filed_as == "derio-net/super-fr#12"
    assert owed_filed_as(entries) == {"test-plan-step-1": "derio-net/super-fr#12"}
    assert open_owed_ids(entries) == ["test-plan-step-1"]


def test_filed_as_is_validated_by_tracked_by_re() -> None:
    owed = _owed()
    for bad in ("not a ref", "-x", "derio-net/super-fr#12 extra"):
        with pytest.raises(ValueError):
            _record(owed, {owed.id}, state="open", filed_as=bad)


def test_filed_as_only_on_an_open_record() -> None:
    owed = _owed()
    with pytest.raises(ValueError):
        _record(owed, {owed.id}, state="fixed", filed_as="#3")


def test_a_fixed_record_closes_the_owed_entry() -> None:
    owed = _owed()
    filed = _record(owed, {owed.id}, state="open", filed_as="#12")
    fixed = _record(owed, {owed.id, filed.id}, state="fixed", body="ran it: green")
    entries = _roundtrip([owed, filed, fixed])
    assert open_owed_ids(entries) == []
    assert open_finding_ids(entries) == []


def test_a_finding_still_folds_beside_an_owed_entry() -> None:
    owed = _owed()
    finding = JournalEntry(
        kind="finding", scope="spec", id="f1", created="c", title="bug", state="open"
    )
    assert open_finding_ids(_roundtrip([owed, finding])) == ["f1"]


# --- fr journal check / render --------------------------------------------


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _write(root: Path, entries: list[JournalEntry], slug: str = "2026-10-11-x") -> Path:
    path = journal_path(root, "spec", slug)
    for e in entries:
        append_journal_entry(path, slug, e)
    return path


def test_journal_check_passes_with_an_open_owed_entry_and_lists_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    _write(root, [_owed()])
    monkeypatch.chdir(root)
    res = runner.invoke(app, ["journal", "check", "--scope", "spec", "--slug", "2026-10-11-x"])
    assert res.exit_code == 0, res.output
    assert "1 owed action(s) open: test-plan-step-1" in res.output


def test_journal_render_shows_owed_entries_in_their_own_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    finding = JournalEntry(kind="decision", scope="spec", id="d1", created="c", title="a decision")
    _write(root, [finding, _owed()])
    monkeypatch.chdir(root)
    res = runner.invoke(app, ["journal", "render", "--scope", "spec", "--slug", "2026-10-11-x"])
    assert res.exit_code == 0, res.output
    head, sep, owed_block = res.output.partition("## Owed actions")
    assert sep, res.output
    assert "d1" in head and "test-plan-step-1" not in head
    assert "test-plan-step-1" in owed_block


# --- the journal kind 1 -> 2 ----------------------------------------------


def test_the_journal_kind_moved_to_version_two() -> None:
    assert ARTIFACT_KINDS["journal"].current_version == 2


def test_the_journal_kind_is_reachable_from_version_one() -> None:
    chain = MIGRATIONS.chain("journal", 1)
    assert [m.from_version for m in chain] == [1]
    assert [m.to_version for m in chain] == [2]


def test_the_journal_migration_is_stamp_only(tmp_path: Path) -> None:
    path = tmp_path / "docs/superpowers/journals/plans/p.md"
    path.parent.mkdir(parents=True)
    body = (
        "# Journal: p\n\n"
        "<!-- fr:journal kind=discovery scope=plan id=d1 created=2026-01-01T00:00:00 -->\n"
        "### d1 · discovery · t\n\nbody\n"
    )
    path.write_text(body)
    report = run_migrations(tmp_path, dry_run=False)
    assert report.ok, report.failed
    assert ARTIFACT_KINDS["journal"].read_version(path) == 2
    text = path.read_text()
    assert text == "<!-- fr:journal-schema=2 -->\n" + body
    # The stamp stays readable: the journal still parses to the same entries.
    assert [e.id for e in parse_journal(text)] == ["d1"]


def test_an_old_stamp_journal_with_an_owed_entry_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "docs/superpowers/journals/specs/2026-10-11-x.md"
    path.parent.mkdir(parents=True)
    path.write_text("<!-- fr:journal-schema=1 -->\n# Journal: x\n\n" + serialize_entry(_owed()))
    before = path.read_bytes()
    problems = validate_journal(path)
    assert any("owed" in p and "schema 1" in p for p in problems), problems
    report = run_migrations(tmp_path, dry_run=False)
    assert not report.ok
    assert path.read_bytes() == before, "a refused journal is left byte-identical"


def test_a_new_journal_is_written_at_the_current_stamp(tmp_path: Path) -> None:
    path = journal_path(tmp_path, "spec", "2026-10-11-x")
    append_journal_entry(path, "2026-10-11-x", _owed())
    assert ARTIFACT_KINDS["journal"].read_version(path) == 2
    assert validate_journal(path) == []
    assert [e.id for e in parse_journal(path.read_text())] == ["test-plan-step-1"]


def test_an_owed_entry_without_its_key_fails_the_validator(tmp_path: Path) -> None:
    path = journal_path(tmp_path, "spec", "x")
    bare = JournalEntry(kind="owed", scope="spec", id="o1", created="c", title="t", body="x")
    append_journal_entry(path, "x", bare)
    problems = validate_journal(path)
    assert any("owed_key" in p for p in problems), problems


def test_a_hand_written_owed_state_is_a_parse_error() -> None:
    text = (
        "<!-- fr:journal kind=owed scope=spec id=o1 created=c state=open -->\n### o1 · owed · t\n"
    )
    with pytest.raises(JournalParseError):
        parse_journal(text)


# --- the record engine (record kind 9 carries the live JournalKind) --------


def _add(root: Path, *args: str):  # noqa: ANN202
    from fr.commands import journal_cmd

    return runner.invoke(
        app,
        ["journal", "add", "--scope", "spec", "--slug", "2026-10-11-x", "--kind", "owed", *args],
    ), journal_cmd


def test_journal_add_writes_an_owed_entry_through_the_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import journal_cmd

    monkeypatch.setattr(journal_cmd, "_orphan_refusal", lambda *a, **k: None)
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    body = owed_body(what="w", why="y", how="h", key=KEY)
    res, _ = _add(root, "--id", "o1", "--title", "owed", "--body", body)
    assert res.exit_code == 0, res.output
    entries = parse_journal(journal_path(root, "spec", "2026-10-11-x").read_text())
    assert [(e.id, e.kind) for e in entries] == [("o1", "owed")]


def test_journal_add_refuses_an_owed_entry_without_a_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import journal_cmd

    monkeypatch.setattr(journal_cmd, "_orphan_refusal", lambda *a, **k: None)
    root = _repo(tmp_path)
    monkeypatch.chdir(root)
    res, _ = _add(root, "--id", "o1", "--title", "owed", "--body", "no key here")
    assert res.exit_code == 2, res.output
    assert "owed_key" in res.output
    assert not journal_path(root, "spec", "2026-10-11-x").exists()


# --- review p3-r5 / p3-r7 -------------------------------------------------


@pytest.mark.parametrize("bad", ["https://x.example/\x1b[2J", "https://x.example/é"])
def test_filed_as_must_be_printable_ascii(bad: str) -> None:
    owed = _owed()
    with pytest.raises(ValueError):
        _record(owed, {owed.id}, state="open", filed_as=bad)


def test_appending_an_owed_entry_to_an_archived_unstamped_journal_stamps_it(
    tmp_path: Path,
) -> None:
    from fr.journal.model import archived_journal_path

    path = archived_journal_path(tmp_path, "spec", "2026-10-11-x")
    path.parent.mkdir(parents=True)
    path.write_text("<!-- fr:journal-schema=1 -->\n# Journal: x\n")
    append_journal_entry(path, "2026-10-11-x", _owed())
    assert ARTIFACT_KINDS["journal"].read_version(path) == 2
    assert path.read_text().count("fr:journal-schema=") == 1
    assert validate_journal(path) == []
