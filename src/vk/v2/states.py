"""Frozen dataclasses for the projection chain.

Three families of state:

1. **Observed** — what GitHub actually says right now.
   - `GhState`, `PhaseObservation`, `PrObservation`
   - Produced by `vk.v2.observe.observe(plan, gh)`.

2. **Rendered** — what GitHub *should* say, computed from
   `(plan, observed)`.
   - `RenderedState`, `RenderedIssue`
   - Produced by `vk.v2.render.render(plan, observed)`.

3. **Diff / Apply** — the mutations needed to bring observed → rendered.
   - Lives in `vk.v2.diff` (next module).

All dataclasses are `frozen=True` so the renderer can be a pure
function and consumers can compare states with `==` for idempotency
checks.
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


@dataclass(frozen=True)
class GhState:
    phases: dict[int, PhaseObservation] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderedIssue:
    body: str
    labels: frozenset[str]
    state: Literal["OPEN", "CLOSED"]


@dataclass(frozen=True)
class RenderedState:
    issue_per_phase: dict[int, RenderedIssue]
    archive_decision: bool
    warnings: tuple[str, ...] = ()
