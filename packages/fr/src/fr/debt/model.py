"""`DebtReport` — one structured answer to "what does this repo owe?" (R1).

Every surface that shows acceptance or plan debt renders this, or the one
status set it counts with (`fr.acceptance.model.DEBT_STATUSES`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from fr.acceptance.model import DEBT_STATUSES

OwedSource = Literal["journal", "row", "plan", "issue"]
"""Where an owed item came from. When several sources share a key the
precedence is journal, row, plan, issue (`engine.OWED_PRECEDENCE`)."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceStatus(_Frozen):
    """One input of the report: read, or unavailable and why (R4)."""

    state: Literal["read", "unavailable"]
    why: str = ""


class DebtRow(_Frozen):
    id: str
    status: str
    acceptance: str
    notes: str = ""
    walked_at: str | None = None
    """The latest passing walk of a `walked` row; None renders as undated."""


class AcceptanceDebt(_Frozen):
    by_status: dict[str, int] = Field(default_factory=dict)
    rows: tuple[DebtRow, ...] = ()
    """Debt rows plus the `walked` and `manual` rows (listed, never debt)."""
    available: bool = True
    """False when the matrix could not be read: unavailable, never zero."""

    def debt_count(self) -> int:
        return sum(n for s, n in self.by_status.items() if s in DEBT_STATUSES)


class ArchivablePlan(_Frozen):
    name: str
    command: str
    merged_at: str | None = None
    age_days: int | None = None


class StalePlan(_Frozen):
    name: str
    last_activity: str | None = None
    idle_days: int | None = None
    basis: str = "git"
    """`git` or `git+forge`: what the last-activity time was taken from."""


class ManualOpenPlan(_Frozen):
    name: str
    phases: tuple[int, ...] = ()


class PlanDebt(_Frozen):
    archivable: tuple[ArchivablePlan, ...] = ()
    stale: tuple[StalePlan, ...] = ()
    manual_open: tuple[ManualOpenPlan, ...] = ()


class OwedItem(_Frozen):
    key: str
    source: OwedSource
    title: str
    how: str = ""
    ref: str = ""


class DebtReport(_Frozen):
    schema_version: int = 1
    acceptance: AcceptanceDebt = AcceptanceDebt()
    plans: PlanDebt = PlanDebt()
    owed: tuple[OwedItem, ...] = ()
    stale_days: int = 14
    sources: dict[str, SourceStatus] = Field(default_factory=dict)
    generated_at: str = ""

    def owed_counted(self) -> int:
        """Owed items counted here: a `row:` item is already acceptance debt."""
        return sum(1 for o in self.owed if not o.key.startswith("row:"))

    def debt_total(self) -> int:
        """The one definition of zero debt (spec §A)."""
        return (
            self.acceptance.debt_count()
            + len(self.plans.archivable)
            + len(self.plans.stale)
            + self.owed_counted()
        )
