"""The sanctioned override for the shared one-phase fixture plan.

`tests/unit/fixtures/v2_plan_minimal` is ONE agentic phase marked
`skeleton: true`. Since 2026-09-21 (debug journal C2) that shape is a
self-review ERROR — a skeleton with no work after it is the whole plan wearing
the marker. The fixture is shared by ~40 test files that count its phases, so
it keeps its shape; tests that push it through `plan-review` as plumbing record
the same operator override a real tiny-change plan would, rather than the rule
being weakened for them.
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
