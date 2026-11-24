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
    "or force-push) and a red check by an ordinary commit, otherwise do what the printed "
    "line says, push with `fr push` and run it again; on exit 75 run it again; on exit 2 "
    "fix what it names (open the PR, correct the override) and run it again, which is not "
    "a fix round; after three fix rounds stop and report"
)
"""The fix rules every settle loop follows (R9)."""

DELIVER_LINE: Final = (
    f"After the PR body is on the PR and before resolving `deliver`, run "
    f"`fr pr settle --wait {DEFAULT_WAIT}`: {FIX_RULES}. `deliver` stays refused until the "
    "PR settles or a `settle.<key>: <mode> — <reason>` line in the spec's `## Verification` "
    "relaxes the key; CI cannot run on a conflicting PR, so a relaxed `settle.conflicts` "
    "leaves `settle.ci` `unrunnable` until it is relaxed too or the conflict is resolved. "
    "After the `deliver` resolve's push, run it once more under the same "
    "loop (a fix then is a commit after `deliver`) and report the result."
)
"""The `settle` line of the deliver brief (R9, R10)."""

CLOSEOUT_LINE: Final = (
    f"  fr pr settle --wait {DEFAULT_WAIT}   # after the housekeeping PR is opened: "
    f"{FIX_RULES} (no override; a driver-managed head exits 0 `managed`: nothing to do)"
)
"""The close-out brief's settle step (R10)."""
