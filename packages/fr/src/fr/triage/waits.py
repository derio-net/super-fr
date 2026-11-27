"""Who a Batches card waits for (spec 2026-11-27-board-session-state §A, R1, R2).

`wait_of` is pure and decided AFTER the column: `lanes.lane_of` and `kanban.column_of`
stay the only decision of where a card sits, and the first matching row of the table
below names the one party it waits for. The board hands it what `kanban._card` already
computed; nothing here reads a clock, a forge or a runner.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Literal

from fr.triage.batch import DependencyState
from fr.triage.lanes import LaneVerdict

Party = Literal["you", "agent", "background", "ci", "queue", "dependency"]
Role = Literal["developer", "reviewer", "tester", "devops"]

PARTIES: tuple[Party, ...] = ("you", "agent", "background", "ci", "queue", "dependency")
"""The closed set (R1), in the order the page lists them."""

_ROLE_OF_LANE: Mapping[str, Role] = {
    "needs-developer": "developer",
    "needs-reviewer": "reviewer",
    "needs-tester": "tester",
    "needs-devops": "devops",
}
_DEAD: frozenset[DependencyState] = frozenset({"unsatisfiable", "unknown"})


@dataclass(frozen=True)
class Wait:
    party: Party
    role: Role | None = None  # set for `you` when the card is in a Needs-you lane


def wait_of(
    *,
    column: str,
    stage: str,
    lane: LaneVerdict | None,
    needs_you: bool,
    front_status: str | None,
    front_background: bool,
    checks: Mapping[str, int] | None,
    has_action: bool,
    queued: bool,
    ready: bool,
    awaiting: bool,
    selected: bool,
    deps: Collection[DependencyState],
) -> Wait | None:
    """The party a card waits for; first match wins. *front_status* is the status of the
    session the card's pill speaks for (`Card.front`) and *front_background* whether THAT
    session's item id is in the runner's background set. *checks* is the batch PR's check
    counts while the PR is open, else None."""
    if column == "done":  # 1
        return None
    if needs_you or front_status == "blocked":  # 2: a blocked session is always needs_you
        return Wait("you", _ROLE_OF_LANE[lane.lane] if lane is not None else None)
    if stage == "obsolete":  # 3: it waits for `batch cancel`
        return Wait("you")
    if awaiting:  # 4: green, held for the operator's `approved-fr`
        return Wait("you", "reviewer")
    if any(d in _DEAD for d in deps):  # 5: re-plan or cancel
        return Wait("you")
    if any(d != "satisfied" for d in deps):  # 6
        return Wait("dependency")
    if column == "proposed" and not selected:  # 7: the driver never takes it
        return Wait("you")
    if front_status == "working":  # 8
        return Wait("agent")
    if front_status in ("idle", "done") and front_background:  # 9
        return Wait("background")
    if (checks or {}).get("pending", 0) > 0:  # 10
        return Wait("ci")
    if has_action or queued or ready or column in ("proposed", "waiting"):  # 11
        return Wait("queue")
    if front_status in ("idle", "done"):  # 12: still its turn, below the idle threshold
        return Wait("agent")
    return Wait("queue")  # 13: the driver re-dispatches, replaces or flags a lost session
