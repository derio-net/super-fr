"""The evidence an independent spec review resolves `spec-review` with.

Since 2026-09-24 spec §E the shipped `fr-goal` shape's `spec-review` declares
`evidence: [review, reviewer, findings]`, verified against the run's spec
journal. A test that walks the SHIPPED shape past `spec-review` has to record
what a real run records: a `kind=review` spec-journal entry created after the
step opened, and the reviewer's dispatch id. Written through the one journal
writer, so the fixture is a capture of the real serializer's output.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fr.journal.model import JournalEntry, append_journal_entry, journal_path, spec_journal_slug

REVIEWER_ID = "spec-reviewer-1"


def spec_review_evidence(repo: Path, spec_rel: str, *, entry_id: str = "spec-review") -> list[str]:
    """Record the review in `spec_rel`'s spec journal and return the
    `--evidence` arguments. Call it AFTER `fr run advance` opened the step."""
    slug = spec_journal_slug(Path(spec_rel).stem)
    append_journal_entry(
        journal_path(repo, "spec", slug),
        slug,
        JournalEntry(
            kind="review",
            scope="spec",
            id=entry_id,
            created=datetime.now().replace(microsecond=0).isoformat(),
            title="independent spec review",
            body="no findings",
        ),
    )
    return ["--evidence", f"review={entry_id}", "--evidence", f"reviewer={REVIEWER_ID}"]
