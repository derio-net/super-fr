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
