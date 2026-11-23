"""The settle loop as the briefs state it (spec 2026-11-23-pr-readiness-wait R9, R10, §E).

`deliver`'s brief carries `DELIVER_LINE` (fr-goal's SKILL.md points at it), and the
hand-run close-out brief carries `CLOSEOUT_LINE` after its housekeeping PR. Both share
`FIX_RULES`, which fr-debugging's SKILL.md restates. The three-round limit is skill and
brief text: fr does not count rounds (R9).
"""

from __future__ import annotations

from typing import Final

from fr.settle.poll import DEFAULT_WAIT

__all__ = ["CLOSEOUT_LINE", "DELIVER_LINE", "FIX_RULES"]

FIX_RULES: Final = (
    "on exit 4 fix it, a conflict by merging `origin/<base>` into the branch (never rebase "
    "or force-push) and a red check by an ordinary commit, push with `fr push` and run it "
    "again; on exit 75 run it again; after three fix rounds stop and report"
)
"""The fix rules every settle loop follows (R9)."""

DELIVER_LINE: Final = (
    f"After the PR body is on the PR and before resolving `deliver`, run "
    f"`fr pr settle --wait {DEFAULT_WAIT}`: {FIX_RULES}. `deliver` stays refused until the "
    "PR settles or a `settle.<key>: <mode> — <reason>` line in the spec's `## Verification` "
    "relaxes the key. After the `deliver` resolve's push, run it once more and report the "
    "result."
)
"""The `settle` line of the deliver brief (R9, R10)."""

CLOSEOUT_LINE: Final = (
    f"  fr pr settle --wait {DEFAULT_WAIT}   # after the housekeeping PR is opened: "
    f"{FIX_RULES} (no override)"
)
"""The close-out brief's settle step (R10)."""
