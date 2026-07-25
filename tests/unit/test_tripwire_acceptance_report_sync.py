"""CI tripwire: the committed report SET must stay in sync with matrix.yaml.

`docs/acceptance/matrix.yaml` is the source; the committed set —
`report_local.html` (local HTML), `report_linked.html` (github HTML) and
`report_linked.md` (github Markdown) — is its deterministic rendering. Any matrix
change (a `fr acceptance add` row or a hand-edited status flip) must be
accompanied by regenerated reports. This test fails loud on drift instead of
shipping a stale artifact, the same posture as
`test_tripwire_opencode_skills_sync.py`.

The comparison uses `render_committed_set` — the exact function the
`fr acceptance report --check` CLI and the `fr acceptance check` gate use — so
they can never disagree about what "in sync" means. It is a pure function of
`matrix.yaml` (matrix-derived stamp, no git date/hash, no filesystem
twin-probing), so this only fires on a genuine matrix change. (`report.html` is
the ad-hoc, uncommitted render and is deliberately NOT covered here.)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.model import load_matrix
from fr.acceptance.report import REPORT_SET, render_committed_set

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX = REPO_ROOT / "docs" / "acceptance" / "matrix.yaml"


@pytest.mark.parametrize("rel", list(REPORT_SET))
def test_report_is_committed_and_tracked(rel: str) -> None:
    assert (REPO_ROOT / rel).exists(), (
        f"{rel} must be committed (the report SET is tracked now, not gitignored) — "
        "run `fr acceptance report --deterministic` and commit the report set."
    )


def test_committed_report_set_matches_matrix() -> None:
    expected = render_committed_set(load_matrix(MATRIX), REPO_ROOT)
    for rel, want in expected.items():
        assert (REPO_ROOT / rel).read_text() == want, (
            f"{rel} is stale (drifted from docs/acceptance/matrix.yaml).\n"
            "Run `fr acceptance report --deterministic` and commit the report set."
        )
