"""Driver-managed PRs (spec 2026-11-23-pr-readiness-wait R5).

A PR whose branch only the wave driver produces belongs to the driver's queue and
hand-backs, so `fr pr settle` reads nothing for it. Every prefix comes from its owner;
this module writes no branch name of its own (`tests/unit/test_settle_managed.py`).
The owners are imported inside `driver_managed`, because the driver's brief modules
import `MANAGED_SENTENCE` from here.
"""

from __future__ import annotations

from typing import Final

MANAGED_SENTENCE: Final = (
    "The wave driver owns this PR's mergeability and CI: run no `fr pr settle` loop."
)
"""The one sentence every driver brief carries (R5)."""


def driver_managed(branch: str) -> bool:
    """True for a head only the wave driver produces: a batch branch, a collected
    close-out, a legacy per-batch archive head, a state export and a DevOps
    housekeeping PR. A hand-run close-out's archive head (a plan or run id) is not."""
    from fr.triage.batch import BRANCH_PREFIX, FIX_BRANCH_PREFIX
    from fr.triage.batch_drive import (
        COLLECTED_PREFIX,
        HOUSEKEEPING_PREFIX,
        collected_name,
    )
    from fr.triage.batch_drive_export import EXPORT_PREFIX

    batch = (BRANCH_PREFIX, FIX_BRANCH_PREFIX)
    legacy_archive = tuple(COLLECTED_PREFIX + p.replace("/", "-") for p in batch)
    if branch.startswith((*batch, *legacy_archive, EXPORT_PREFIX, HOUSEKEEPING_PREFIX)):
        return True
    return collected_name(branch) is not None
