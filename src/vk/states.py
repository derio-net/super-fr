"""Dataclasses for the projection chain.

Three families of state:

1. **Observed** — what GitHub actually says right now.
   - `GhState`, `PhaseObservation`, `PrObservation`
   - Produced by `vk.observe.observe(plan, gh)`.

2. **Rendered** — what GitHub *should* say, computed from
   `(plan, observed)`.
   - `RenderedState`, `RenderedIssue`, `Warning`
   - Produced by `vk.render.render(plan, observed)`.

3. **Diff / Apply** — the mutations needed to bring observed → rendered.
   - Lives in `vk.diff` (next module).

**Frozen-vs-not asymmetry.** Leaf dataclasses with only hashable fields
(`PrObservation`, `PhaseObservation`, `RenderedIssue`, `Warning`) are
`frozen=True` — they hash and compare cleanly. Container dataclasses
that hold a `dict` (`GhState`, `RenderedState`) are NOT frozen because
`dict` is unhashable; instead we treat them as by-convention immutable
(don't mutate after construction). If we ever need to put one in a
set, switch the `dict` to `tuple[tuple[...], ...]` first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class PrObservation:
    url: str
    state: Literal["OPEN", "CLOSED"]
    merged: bool
    draft: bool
    ci: Literal["PASS", "FAIL", "PENDING", "NONE"]


@dataclass(frozen=True)
class PhaseObservation:
    issue_state: Literal["OPEN", "CLOSED"] | None  # None = not yet dispatched
    issue_labels: frozenset[str]
    issue_assignees: tuple[str, ...]
    linked_prs: tuple[PrObservation, ...]
    body: str = ""  # current Issue body — used by diff() to detect body drift


@dataclass
class GhState:
    # Not frozen: holds a dict. By-convention immutable post-construction.
    phases: dict[int, PhaseObservation] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderedIssue:
    body: str
    labels: frozenset[str]
    state: Literal["OPEN", "CLOSED"]


@dataclass(frozen=True)
class Warning:
    """A drift signal surfaced by the renderer.

    Severity drives presentation in `vk apply --dry-run` output and
    in the GHA spec-status comment, ordering more-actionable signals
    first.
    """

    severity: Literal["info", "warn", "error"]
    message: str

    def __str__(self) -> str:  # makes legacy 'in warning' substring tests still pass
        return self.message


@dataclass
class RenderedState:
    # Not frozen: holds a dict. By-convention immutable post-construction.
    issue_per_phase: dict[int, RenderedIssue]
    archive_decision: bool
    warnings: tuple[Warning, ...] = ()
