"""The journal kind's 2 -> 3 hop: the `op` entry kind (spec 2026-10-22-fr-ops §D,
R17).

Stamp-only. A version-2 journal cannot hold an `op` entry — no fr that wrote
version 2 knew the kind — so one that does was spliced by hand or re-stamped
backwards, and the hop REFUSES it rather than certify it, leaving it
byte-identical. The structure validator reports the same journal
(`fr.artifacts.structure.validate_journal`).
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.runner import MIGRATIONS, SchemaMigration

KIND = "journal"


def op_entry_ids(text: str) -> list[str]:
    """Ids of the `op` entries in a journal's text; a journal that does not parse
    has none this hop can name (the validator reports the parse)."""
    from fr.journal.model import JournalParseError, parse_journal

    try:
        return [e.id for e in parse_journal(text) if e.kind == "op"]
    except JournalParseError:
        return []


def _stamp_only(path: Path) -> None:
    ops = op_entry_ids(path.read_text())
    if ops:
        raise ValueError(
            f"{path.name}: stamped journal schema 2 but carries `op` entr(ies) "
            f"{', '.join(ops)} — an fr at schema 2 could not have written them; "
            "left as it is (fix the journal by hand)"
        )


MIGRATIONS.register(
    SchemaMigration(
        kind=KIND,
        from_version=2,
        to_version=3,
        fn=_stamp_only,
        description="journal 2 -> 3: the `op` entry kind (stamp only)",
    )
)
