"""The journal kind's 1 -> 2 hop: the `owed` entry kind (spec
2026-10-11-debt-engine §E, R20).

Stamp-only. A version-1 journal cannot hold an `owed` entry — no fr that wrote
version 1 knew the kind — so one that does was spliced by hand or re-stamped
backwards, and the hop REFUSES it rather than certify it, leaving it
byte-identical. The structure validator reports the same journal
(`fr.artifacts.structure.validate_journal`).
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.runner import MIGRATIONS, SchemaMigration

KIND = "journal"


def owed_entry_ids(text: str) -> list[str]:
    """Ids of the `owed` entries in a journal's text; a journal that does not
    parse has none this hop can name (the validator reports the parse)."""
    from fr.journal.model import JournalParseError, parse_journal

    try:
        return [e.id for e in parse_journal(text) if e.kind == "owed"]
    except JournalParseError:
        return []


def _stamp_only(path: Path) -> None:
    owed = owed_entry_ids(path.read_text())
    if owed:
        raise ValueError(
            f"{path.name}: stamped journal schema 1 but carries `owed` entr(ies) "
            f"{', '.join(owed)} — an fr at schema 1 could not have written them; "
            "left as it is (fix the journal by hand)"
        )


MIGRATIONS.register(
    SchemaMigration(
        kind=KIND,
        from_version=1,
        to_version=2,
        fn=_stamp_only,
        description="journal 1 -> 2: the `owed` entry kind (stamp only)",
    )
)
