"""The stale ops workspace (spec 2026-11-27-ops-gate-truth R1–R6, §A).

Stage 3 of `fr ops gate` is the only place the ops workspace used to move onto the default
branch. A later stage that failed and was rerun applied the ops as stage 3 saw them, even
after a fix to an op landed on the default branch (gh#1617). So before stages 4, 5, 6 and 7
act, `refresh` compares the workspace with `origin/<default>`:

- `drift` loads the run's ops on both sides (`fr.ops.load.load_ops`, compared op by op on
  the whole frozen definition) and the run's Test Plan steps (`fr.spec.test_plan_steps`).
  A side that cannot be read is a refusal, never "equal". Rows are left out on purpose:
  the ops branch writes row walks the default branch does not hold yet.
- `refresh` asks the operator (always, `--yes` or not), commits the workspace's records,
  merges `origin/<default>` with a merge commit (never a rebase: the pushed ops branch
  moves forward only), pushes it leased, reopens the changed and added ops in the host
  state and re-checks trust. A refresh after stage 4 that reopened anything sends the run
  back to stage 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr.ops.gate import StageFailed

if TYPE_CHECKING:
    from collections.abc import Callable

    from fr.ops.gate import GateState
    from fr.ops.model import Op
    from fr.spec import Step


@dataclass(frozen=True)
class Drift:
    """What differs between the ops workspace and the default branch: op ids added on the
    default branch, removed from it, or changed, and whether the Test Plan changed."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]
    test_plan: bool

    @property
    def differs(self) -> bool:
        return bool(self.added or self.removed or self.changed or self.test_plan)


def _ops_of(root: Path, plan_rel: str, side: str) -> dict[str, Op]:
    """The run's ops on one side, by id (runbook ops the plan needs included); a carrier
    that does not load is a refusal, never an empty set."""
    from fr.ops.load import OpsLoadError, load_ops

    try:
        return {lo.op.id: lo.op for lo in load_ops(root / plan_rel, root).ops}
    except (OpsLoadError, OSError) as exc:
        raise StageFailed(f"the ops on {side} cannot be read: {exc}", code=2) from exc


def _steps_of(root: Path, spec_rel: str | None, side: str) -> list[Step] | None:
    """The run's Test Plan steps on one side; None when the spec is not there."""
    from fr.spec import TestPlanHeadingError, test_plan_steps

    if spec_rel is None:
        return []
    path = root / spec_rel
    try:
        if not path.is_file():
            return None
        return test_plan_steps(path.read_text(), source=f"{spec_rel} on {side}")
    except (OSError, UnicodeDecodeError, TestPlanHeadingError) as exc:
        raise StageFailed(f"the Test Plan on {side} cannot be read: {exc}", code=2) from exc


def drift(
    workspace_root: Path, default_root: Path, plan_rel: str, spec_rel: str | None
) -> Drift:
    """The ops and the Test Plan of the ops workspace against the default branch (R1). A
    plan directory the default branch lacks is a refusal (R5), as is a side that cannot be
    read: unknown is never "equal"."""
    if not (default_root / plan_rel).is_dir():
        raise StageFailed(
            f"the run's plan directory {plan_rel} is not on the default branch; the ops "
            "workspace cannot be brought up to date",
            code=2,
        )
    mine = _ops_of(workspace_root, plan_rel, "the ops workspace")
    tip = _ops_of(default_root, plan_rel, "the default branch")
    return Drift(
        added=tuple(i for i in tip if i not in mine),
        removed=tuple(i for i in mine if i not in tip),
        changed=tuple(i for i in mine if i in tip and mine[i] != tip[i]),
        test_plan=_steps_of(workspace_root, spec_rel, "the ops workspace")
        != _steps_of(default_root, spec_rel, "the default branch"),
    )


def closure_exclusions(state: GateState, at_head: set[str]) -> Callable[[str], set[str]]:
    """Per op id, the plan-journal entries that do not close it: the PR head's own
    (*at_head*), and for an op a refresh reopened, also every entry present at that refresh.
    Only its live status, or evidence recorded after the refresh, closes it (R6)."""
    reopened, before = state.reopened()
    return lambda op_id: at_head | before if op_id in reopened else at_head
