"""`fr journal file` — file a leftover as an issue at `deliver` (spec 2026-10-14
exit-gates R10, §C).

Three kinds of journal entry can be left over when a run delivers, and each is
filed through the archive's existing filers in `fr.archive_followups` — never a
second copy of them — so filing moves from close-out to `deliver` without
changing what an issue looks like:

- an out-of-scope (or still open) finding: `file_open_ends`, label `follow-up`,
  then a `deferred --tracked-by <issue>` resolution record;
- a narrowing decision (R12, a `decision` carrying `narrows=`): the same filer,
  then a decision carrying the same `narrows=` and `tracked_by=<issue>`;
- an `owed` entry: `file_owed_ends`, label `fr:owed`, then an `open` record
  carrying `filed_as=<issue>`.

`plan_filing` is pure: it resolves ids to what they are, refusing every id it
cannot file, so a caller refuses before any forge call. `filing_record` turns
the forge's answers into ONE step record for the record engine — the journal
resolve engine — so the journal writes land in one commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr.journal.model import (
    JournalEntry,
    effective_finding_states,
    open_owed_ids,
    owed_filed_as,
    resolution_record_id,
)

if TYPE_CHECKING:
    from fr.archive_followups import OpenEnd, OwedEnd
    from fr.record.model import StepRecord

__all__ = [
    "Filing",
    "Plan",
    "filing_record",
    "narrowing_accounted",
    "narrowing_decisions",
    "plan_filing",
]

_FILEABLE_FINDING = ("open", "out-of-scope")


def narrowing_decisions(entries: list[JournalEntry]) -> list[JournalEntry]:
    """The narrowing decisions of a journal (R12): a `decision` carrying
    `narrows=` that is not itself a filing (one carrying `tracked_by=`)."""
    return [e for e in entries if e.kind == "decision" and e.narrows and e.tracked_by is None]


def narrowing_accounted(entries: list[JournalEntry], decision: JournalEntry) -> str | None:
    """Where `decision`'s remainder went (R9): the `tracked_by` of the LAST later
    decision filing the same `narrows=` set, else `None`."""
    seen = False
    found: str | None = None
    for e in entries:
        if e is decision:
            seen = True
            continue
        if (
            seen
            and e.kind == "decision"
            and e.tracked_by is not None
            and set(e.narrows) == set(decision.narrows)
        ):
            found = e.tracked_by
    return found


@dataclass(frozen=True)
class Plan:
    """What `fr journal file` will file, by kind, and every id it refuses."""

    findings: tuple[JournalEntry, ...] = ()
    narrowings: tuple[JournalEntry, ...] = ()
    owed: tuple[JournalEntry, ...] = ()
    refusals: tuple[str, ...] = ()


def plan_filing(entries: list[JournalEntry], ids: list[str]) -> Plan:
    """Resolve `ids` against a journal's entries. An id is fileable when it names
    a finding whose effective state is open or out-of-scope, an `owed` entry still
    owed and not yet filed, or a narrowing decision not yet filed; anything else
    is refused with the reason."""
    states = effective_finding_states(entries)
    owed_open = set(open_owed_ids(entries))
    filed = owed_filed_as(entries)
    findings: list[JournalEntry] = []
    narrowings: list[JournalEntry] = []
    owed: list[JournalEntry] = []
    refusals: list[str] = []
    for eid in dict.fromkeys(ids):
        entry = next((e for e in entries if e.id == eid), None)
        if entry is None:
            refusals.append(f"{eid}: no entry with that id in this journal")
        elif entry.kind == "finding" and entry.resolves is None:
            state = states.get(eid, entry.state or "open")
            if state in _FILEABLE_FINDING:
                findings.append(entry)
            else:
                refusals.append(f"{eid}: the finding is {state}, so there is nothing to file")
        elif entry.kind == "owed":
            if eid in filed:
                refusals.append(f"{eid}: already filed as {filed[eid]}")
            elif eid not in owed_open:
                refusals.append(f"{eid}: the owed action is discharged")
            else:
                owed.append(entry)
        elif entry in narrowing_decisions(entries):
            where = narrowing_accounted(entries, entry)
            if where is not None:
                refusals.append(f"{eid}: already filed as {where}")
            else:
                narrowings.append(entry)
        else:
            refusals.append(
                f"{eid}: a {entry.kind} — only a finding, an owed action or a narrowing "
                "decision (`narrows=`) is filed"
            )
    return Plan(tuple(findings), tuple(narrowings), tuple(owed), tuple(refusals))


@dataclass(frozen=True)
class Filing:
    """One filed (or reused) item: the entry and the issue it now names."""

    entry: JournalEntry
    ref: str


def open_end(scope: str, slug: str, path: Path, entry: JournalEntry) -> OpenEnd:
    """A finding or a narrowing decision as the archive filer's `OpenEnd`."""
    from fr.archive_followups import OpenEnd

    return OpenEnd(scope, slug, entry.id, entry.title, entry.body, "open", path)


def owed_end(scope: str, slug: str, path: Path, entry: JournalEntry) -> OwedEnd:
    """An `owed` entry as the archive filer's `OwedEnd`."""
    from fr.archive_followups import OwedEnd
    from fr.journal.model import owed_fields, owed_key

    fields = owed_fields(entry)
    key = owed_key(entry)
    assert key is not None  # the engine refuses an owed entry without its key
    return OwedEnd(
        scope,
        slug,
        entry.id,
        entry.title,
        key,
        fields.get("what", ""),
        fields.get("how", ""),
        path,
    )


def filing_record(
    entries: list[JournalEntry],
    *,
    findings: list[Filing],
    narrowings: list[Filing],
    owed: list[Filing],
) -> StepRecord:
    """The one-entry-per-filing record the engine applies: a `deferred`
    resolution per finding, a filing decision per narrowing, a `filed_as`
    record per owed action."""
    from fr.record.model import JournalItem, Resolution, StepRecord

    taken = {e.id for e in entries}
    items: list[JournalItem] = []
    for f in narrowings:
        fid = _filed_id(f.entry.id, taken)
        items.append(
            JournalItem.model_validate(
                {
                    "kind": "decision",
                    "id": fid,
                    "title": f"files {f.entry.id}: {f.entry.title}",
                    "body": f"Filed the rest of `{f.entry.id}` at deliver as {f.ref}.",
                    "phase": f.entry.phase,
                    "global": f.entry.phase is None and f.entry.scope == "plan",
                    "gate": f.entry.gate,
                    "narrows": list(f.entry.narrows),
                    "tracked_by": f.ref,
                }
            )
        )
    for f in owed:
        rid = resolution_record_id(f.entry.id, taken)
        taken.add(rid)
        items.append(
            JournalItem.model_validate(
                {
                    "kind": "finding",
                    "id": rid,
                    "title": f"resolves {f.entry.id}: {f.entry.title}",
                    "body": f"Filed at deliver as {f.ref}; still owed until discharged.",
                    "state": "open",
                    "phase": f.entry.phase,
                    "global": f.entry.phase is None and f.entry.scope == "plan",
                    "resolves": f.entry.id,
                    "filed_as": f.ref,
                }
            )
        )
    resolves = tuple(
        Resolution(
            id=f.entry.id,
            state="deferred",
            body=f"Filed at deliver as {f.ref}.",
            phase=f.entry.phase,
            tracked_by=f.ref,
        )
        for f in findings
    )
    return StepRecord(journal=tuple(items), resolves=resolves)


def _filed_id(decision_id: str, taken: set[str]) -> str:
    """`<decision>-filed`, then `-2`, `-3`… — never a duplicate id."""
    base = f"{decision_id}-filed"
    rid, n = base, 2
    while rid in taken:
        rid, n = f"{base}-{n}", n + 1
    taken.add(rid)
    return rid
