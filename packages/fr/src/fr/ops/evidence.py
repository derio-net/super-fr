"""Op evidence: the `op` journal entries (spec 2026-10-22-fr-ops R7, §D).

Every apply result, recorded check outcome, proof and attestation is a
plan-journal entry of kind `op`, whose body is `key: value` lines
(`fr.journal.model.OP_BODY_KEYS`) and never secret material. `fold` keeps the
latest entry per op; `JournalEvidence` is the journal port `fr ops status`
reads (a plan op from its own plan's journal, a runbook op from every live and
archived plan journal); `record_op` is the writer `apply`/`attest` use, through
the journal's one writer.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from fr.journal.model import (
    IMPLEMENTED_JOURNALS_REL,
    JOURNALS_REL,
    SCOPE_DIRS,
    JournalEntry,
    JournalParseError,
    append_journal_entry,
    journal_now,
    journal_path,
    journal_stamp_as_utc,
    op_body,
    op_fields,
    parse_journal,
    resolve_journal_read_path,
)

PLANS_REL = Path("docs/superpowers/plans")


@dataclass(frozen=True)
class OpEvidence:
    """One op's latest recorded outcome."""

    result: str
    created: str
    identity: str | None = None
    reason: str | None = None
    phase: str | None = None
    attested_by: str | None = None
    entry_id: str | None = None


def _evidence(entry: JournalEntry) -> tuple[str, OpEvidence] | None:
    fields = op_fields(entry)
    op = fields.get("op")
    result = fields.get("result")
    if entry.kind != "op" or not op or not result:
        return None
    return op, OpEvidence(
        result=result,
        created=entry.created,
        identity=fields.get("identity"),
        reason=fields.get("reason"),
        phase=fields.get("phase"),
        attested_by=fields.get("attested_by"),
        entry_id=entry.id,
    )


def fold(entries: Iterable[JournalEntry]) -> dict[str, OpEvidence]:
    """Op id -> its latest entry. Ordered by `created` (in UTC), ties kept in
    the order given, so one journal folds in file order and several journals
    interleave by time."""
    found = [e for e in (_evidence(entry) for entry in entries) if e is not None]
    found.sort(key=lambda pair: journal_stamp_as_utc(pair[1].created))
    return dict(found)


def _entries(path: Path) -> list[JournalEntry]:
    if not path.is_file():
        return []
    try:
        return parse_journal(path.read_text())
    except JournalParseError:
        return []  # `fr validate artifacts` reports the journal; evidence is absent


def _all_plan_journals(repo_root: Path) -> list[Path]:
    sub = SCOPE_DIRS["plan"]
    dirs = (repo_root / JOURNALS_REL / sub, repo_root / IMPLEMENTED_JOURNALS_REL / sub)
    return [p for d in dirs if d.is_dir() for p in sorted(d.glob("*.md"))]


class JournalEvidence:
    """The journal port over a checkout. Folds lazily, once per source."""

    def __init__(self, repo_root: Path, plan_slug: str) -> None:
        self.repo_root = repo_root
        self.plan_slug = plan_slug
        self._plan: dict[str, OpEvidence] | None = None
        self._every: dict[str, OpEvidence] | None = None

    def latest(self, op_id: str, *, runbook: bool) -> OpEvidence | None:
        if runbook:
            if self._every is None:
                self._every = fold(
                    e for p in _all_plan_journals(self.repo_root) for e in _entries(p)
                )
            return self._every.get(op_id)
        if self._plan is None:
            path = resolve_journal_read_path(self.repo_root, "plan", self.plan_slug)
            self._plan = fold(_entries(path))
        return self._plan.get(op_id)


def record_op(
    repo_root: Path,
    plan_slug: str,
    *,
    op: str,
    result: str,
    phase: str | None = None,
    identity: str | None = None,
    reason: str | None = None,
    attested_by: str | None = None,
    created: str | None = None,
) -> JournalEntry:
    """Append one `op` entry to the plan's journal and return it. Refuses a plan
    that does not exist (R7: a runbook op's evidence needs a named plan)."""
    if not (repo_root / PLANS_REL / plan_slug).is_dir():
        raise ValueError(f"no plan {plan_slug!r} to record op {op!r} against")
    path = journal_path(repo_root, "plan", plan_slug)
    taken = {e.id for e in _entries(path)}
    n = 1
    while f"op-{op}-{n}" in taken:
        n += 1
    entry = JournalEntry(
        kind="op",
        scope="plan",
        id=f"op-{op}-{n}",
        created=created or journal_now(),
        title=f"op {op}: {result}",
        body=op_body(
            op=op,
            result=result,
            identity=identity,
            reason=reason,
            phase=phase,
            attested_by=attested_by,
        ),
    )
    append_journal_entry(path, plan_slug, entry)
    return entry
