"""CI tripwire: no acceptance report is committed (spec 2026-11-04-repo-feature-settings
R19, R20).

The committed report SET (`report_local.html`, `report_linked.html`,
`report_linked.md`) used to be the deterministic rendering of
`docs/acceptance/matrix.yaml`, kept in sync by this test. The matrix is retired: its
rows live in per-feature fragments (`docs/acceptance/features/`), the effective matrix
is a fold over them, and reports are derived on demand (`fr acceptance report`). The
migration to fragments deleted the set, and this test keeps it deleted — a report
committed again would be a second, drifting copy of the fold.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.acceptance.report import REPORT_PATHS

REPO_ROOT = Path(__file__).resolve().parents[2]


def _tracked(rel: str) -> bool:
    done = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", "--", rel],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode == 0


@pytest.mark.parametrize("rel", list(REPORT_PATHS))
def test_no_report_is_committed(rel: str) -> None:
    assert not _tracked(rel), (
        f"{rel} is tracked, but reports are derived, never committed (R20) — "
        f"`git rm {rel}`; render one locally with `fr acceptance report`."
    )


def test_the_retired_matrix_is_not_committed() -> None:
    assert not _tracked("docs/acceptance/matrix.yaml"), (
        "docs/acceptance/matrix.yaml is retired (R19): run `fr migrate artifacts --yes`"
    )
