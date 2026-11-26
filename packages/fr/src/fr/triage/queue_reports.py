"""The merge queue's report actions as the drive pass's own (wave-merge-queue R28, R31).

Split out of `fr.triage.batch_drive`, which holds its module budget.
"""

from __future__ import annotations

from fr.triage.batch_drive import Action
from fr.triage.wave_queue import QueuePlan

QUEUE_REPORT_KEY = "queue"
"""The `key` of an `Action` the merge queue reported (R28): `needs_you` reads it as a
`queue-need`, not as a blocked batch."""


def queue_reports(plan: QueuePlan) -> list[Action]:
    """The queue's report actions, as the pass's own: a held repo is `held` (R31), a Need is
    `blocked` (the operator's, R28, R30), a report said once is a `warn` keyed in `warned`."""
    out: list[Action] = []
    for a in plan.actions:
        if a.kind == "queue-held":
            out.append(Action("held", plan.repo, a.detail, key=QUEUE_REPORT_KEY))
        elif a.kind == "queue-need":
            out.append(Action("blocked", a.batch or plan.repo, a.detail, key=QUEUE_REPORT_KEY))
        elif a.kind == "queue-warn":
            out.append(Action("warn", plan.repo, a.detail, head=a.key))
    return out
