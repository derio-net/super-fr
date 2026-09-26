"""The sanctioned override for the shared one-phase fixture plan.

`tests/unit/fixtures/v2_plan_minimal` is ONE agentic phase marked
`skeleton: true`. Since 2026-09-26 (one-phase-plans) that shape is first-class
and self-review raises nothing for it, so the override is no longer required;
the helper is kept because callers still write it and it is harmless (it
silences the two-or-more-phase unmarked error, which this fixture cannot
raise).
"""

from __future__ import annotations

from pathlib import Path

FIXTURE_PLAN_SLUG = "2026-05-09-fixture-minimal"
FIXTURE_SPEC_JOURNAL_SLUG = "fixture-spec"


def write_skeleton_override(repo: Path, plan_slug: str = FIXTURE_PLAN_SLUG) -> Path:
    """Log `skeleton-override-<plan_slug>` on the fixture spec's journal."""
    from fr.journal.model import journal_path

    path = journal_path(repo, "spec", FIXTURE_SPEC_JOURNAL_SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Journal: {FIXTURE_SPEC_JOURNAL_SLUG}\n\n"
        "<!-- fr:journal kind=decision scope=spec "
        f"id=skeleton-override-{plan_slug} created=2026-09-21T00:00:00 -->\n"
        f"### skeleton-override-{plan_slug} · decision · Fixture plan\n\n"
        "Shared one-phase test fixture; it exists to be the smallest valid plan.\n"
    )
    return path
