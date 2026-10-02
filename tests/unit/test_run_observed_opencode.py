"""The OpenCode backend of `fr.run.observed` (spec 2026-10-02-opencode-observe-2
§A, §B, §H; Test Plan 1), over the committed run-tree fixture
`tests/fixtures/usage/opencode/opencode.db` (built by its `build.py`; shapes
follow a live OpenCode 1.18.33 capture, every identity fictional — see
`tests/fixtures/usage/NOTE.md`)."""

from __future__ import annotations

from pathlib import Path

from fr.run import observed

DB = Path(__file__).parents[1] / "fixtures" / "usage" / "opencode" / "opencode.db"


def _env(session: str | None = "ses_run", db: Path = DB) -> dict[str, str]:
    env = {"FR_HARNESS": "opencode", "FR_OPENCODE_DB": str(db)}
    if session is not None:
        env["FR_OPENCODE_SESSION_ID"] = session
    return env


def test_fixture_opens() -> None:
    view = observed.observed_session(_env())
    assert view is not None
    assert view.session == "ses_run"
