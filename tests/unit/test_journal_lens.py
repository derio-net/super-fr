"""The `lens` journal entry kind and journal version 4 (spec 2026-11-12-review-lenses
R4, R5, §3.B).

A `lens` entry records that a step added a review lens to the feature: its header
carries `lens=<id>` and, when it came through a step record, `step=<step-id>`. Both
tokens are valid on a `lens` entry only. A journal stamped below 4 cannot hold one,
so appending one stamps the journal in the same write.
"""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest
from fr.artifacts import ARTIFACT_KINDS, MIGRATIONS, run_migrations
from fr.artifacts.structure import validate_journal
from fr.journal.model import (
    JournalEntry,
    JournalKind,
    JournalParseError,
    append_journal_entry,
    journal_path,
    parse_journal,
    serialize_entry,
)
from pydantic import ValidationError

CREATED = "2026-11-12T00:00:00+00:00"


def _lens(**over: object) -> JournalEntry:
    fields: dict[str, object] = {
        "kind": "lens",
        "scope": "plan",
        "id": "lens-security-1",
        "created": CREATED,
        "title": "parses untrusted input",
        "lens": "security",
        "step": "implement-phase",
        "phase": 2,
    }
    fields.update(over)
    return JournalEntry.model_validate(fields)


def test_journal_kind_contains_lens() -> None:
    assert "lens" in get_args(JournalKind)


def test_a_lens_entry_round_trips_with_its_header_tokens() -> None:
    entry = _lens()
    text = serialize_entry(entry)
    header = text.splitlines()[0]
    assert header.endswith("lens=security step=implement-phase -->"), header
    (back,) = parse_journal("# Journal: p\n\n" + text)
    assert back == entry


def test_a_lens_entry_without_a_step_serializes_no_step_token() -> None:
    entry = _lens(step=None, phase=None, scope="spec")
    header = serialize_entry(entry).splitlines()[0]
    assert "lens=security" in header
    assert "step=" not in header
    (back,) = parse_journal("# Journal: s\n\n" + serialize_entry(entry))
    assert back.step is None and back.lens == "security"


@pytest.mark.parametrize("token", [{"lens": "security"}, {"step": "implement-phase"}])
def test_lens_and_step_are_refused_on_any_other_kind(token: dict[str, str]) -> None:
    with pytest.raises(ValidationError, match="only valid on a `lens` entry"):
        JournalEntry.model_validate(
            {
                "kind": "discovery",
                "scope": "plan",
                "id": "d1",
                "created": CREATED,
                "title": "t",
                "phase": 1,
                **token,
            }
        )


@pytest.mark.parametrize(
    ("over", "needle"),
    [
        ({"lens": None}, "names its lens"),
        ({"title": "  "}, "reason"),
        ({"title": ""}, "reason"),
        ({"state": "open"}, "state"),
        ({"resolves": "f1"}, "resolves"),
        ({"lens": "Not_A_Lens"}, "lens id"),
        ({"step": "two words"}, "step"),
    ],
)
def test_an_ill_formed_lens_entry_is_refused(over: dict[str, object], needle: str) -> None:
    with pytest.raises(ValidationError, match=needle):
        _lens(**over)


def test_a_hand_edited_lens_token_on_a_discovery_fails_to_parse() -> None:
    text = (
        "# Journal: p\n\n"
        f"<!-- fr:journal kind=discovery scope=plan id=d1 created={CREATED} phase=1 "
        "lens=security -->\n### d1 · discovery · t (phase 1)\n"
    )
    with pytest.raises(JournalParseError, match="d1"):
        parse_journal(text)


def test_a_journal_stamped_three_is_stamped_four_by_a_lens_write(tmp_path: Path) -> None:
    path = journal_path(tmp_path, "plan", "p")
    path.parent.mkdir(parents=True)
    path.write_text("<!-- fr:journal-schema=3 -->\n# Journal: p\n")
    append_journal_entry(path, "p", _lens())
    assert ARTIFACT_KINDS["journal"].read_version(path) == 4
    assert validate_journal(path) == []


def test_a_journal_stamped_three_holding_a_lens_entry_is_reported(tmp_path: Path) -> None:
    path = journal_path(tmp_path, "plan", "p")
    path.parent.mkdir(parents=True)
    path.write_text("<!-- fr:journal-schema=3 -->\n# Journal: p\n\n" + serialize_entry(_lens()))
    problems = validate_journal(path)
    assert any("lens" in p and "schema 3" in p for p in problems), problems


def test_a_journal_stamped_four_accepts_a_lens_entry(tmp_path: Path) -> None:
    path = journal_path(tmp_path, "plan", "p")
    path.parent.mkdir(parents=True)
    path.write_text("<!-- fr:journal-schema=4 -->\n# Journal: p\n\n" + serialize_entry(_lens()))
    assert validate_journal(path) == []


# --- the journal kind 3 -> 4 ----------------------------------------------------


def test_the_journal_kind_is_at_version_four() -> None:
    assert ARTIFACT_KINDS["journal"].current_version == 4


def test_the_journal_chain_from_one_reaches_four_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("journal", 1)
    assert [(m.from_version, m.to_version) for m in chain] == [(1, 2), (2, 3), (3, 4)]
    hop = MIGRATIONS.chain("journal", 3)[0]
    assert hop.fn.__module__ == "fr.artifacts.journal_lens"


_BODY = (
    "# Journal: p\n\n"
    "<!-- fr:journal kind=discovery scope=plan id=d1 created=2026-01-01T00:00:00 -->\n"
    "### d1 · discovery · t\n\nbody\n"
)


def test_a_v3_journal_migrates_byte_identically_apart_from_its_stamp(tmp_path: Path) -> None:
    path = tmp_path / "docs/superpowers/journals/plans/p.md"
    path.parent.mkdir(parents=True)
    path.write_text("<!-- fr:journal-schema=3 -->\n" + _BODY)
    report = run_migrations(tmp_path, dry_run=False)
    assert report.ok, report.failed
    assert path.read_text() == "<!-- fr:journal-schema=4 -->\n" + _BODY


def test_a_v3_journal_already_holding_a_lens_entry_is_refused_and_left_alone(
    tmp_path: Path,
) -> None:
    path = tmp_path / "docs/superpowers/journals/plans/p.md"
    path.parent.mkdir(parents=True)
    path.write_text("<!-- fr:journal-schema=3 -->\n# Journal: p\n\n" + serialize_entry(_lens()))
    before = path.read_bytes()
    report = run_migrations(tmp_path, dry_run=False)
    assert not report.ok
    assert path.read_bytes() == before
