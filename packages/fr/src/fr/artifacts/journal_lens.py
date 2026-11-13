"""The journal kind's 3 -> 4 hop: the `lens` entry kind (spec
2026-11-12-review-lenses §3.B, R4, R5).

Stamp-only. A version-3 journal cannot hold a `lens` entry — no fr that wrote
version 3 knew the kind — so one that does was spliced by hand or re-stamped
backwards, and the hop REFUSES it rather than certify it, leaving it
byte-identical. The structure validator reports the same journal
(`fr.artifacts.structure.validate_journal`).
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.runner import MIGRATIONS, SchemaMigration

KIND = "journal"


def lens_entry_ids(text: str) -> list[str]:
    """Ids of the `lens` entries in a journal's text; a journal that does not parse
    has none this hop can name (the validator reports the parse)."""
    from fr.journal.model import JournalParseError, parse_journal

    try:
        return [e.id for e in parse_journal(text) if e.kind == "lens"]
    except JournalParseError:
        return []


def _stamp_only(path: Path) -> None:
    lenses = lens_entry_ids(path.read_text())
    if lenses:
        raise ValueError(
            f"{path.name}: stamped journal schema 3 but carries `lens` entr(ies) "
            f"{', '.join(lenses)} — an fr at schema 3 could not have written them; "
            "left as it is (fix the journal by hand)"
        )


MIGRATIONS.register(
    SchemaMigration(
        kind=KIND,
        from_version=3,
        to_version=4,
        fn=_stamp_only,
        description="journal 3 -> 4: the `lens` entry kind (stamp only)",
    )
)
