"""The board's pure model (spec 2026-10-05-triage-batch-board §C).

No `fr_dispatch` import: `BoardStatus` is fr's own copy of
`fr_dispatch.protocols.SessionStatus`, the way `batch_item_id` is a copy of
`run_item_id`, and `tests/unit/test_import_direction.py` pins the two equal.
"""

from __future__ import annotations

from typing import Literal

BoardStatus = Literal["working", "blocked", "idle", "done", "unknown", "absent"]
"""One session's live state as the board shows it; `absent` when the runner holds none."""
