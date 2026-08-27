"""Pydantic schemas for the v2 plan-as-folder format.

Models are organised plan-level → phase-level:
  - PlanMeta, OriginItem        (in `_meta.yaml`)
  - PhaseDoc, PhaseHeader, Task, Step, PhaseStateBlock, StepState,
    Completion                  (in `NN.yaml`)

Design rules baked into every model:
  - `frozen=True`                -- instances are immutable; the renderer
                                    in Phase 2 relies on this for purity.
  - `extra="forbid"`             -- closed-world schema. Adding any field
                                    in v2.x is intentionally a "must update
                                    your vk_version" event because new
                                    fields typically come with new logic
                                    (the renderer treats them as inputs).
                                    Operators bump the constraint when they
                                    adopt new fields. v2.0.0 plans loaded
                                    by v2.1.0 tooling work fine; v2.1.0
                                    plans loaded by v2.0.0 tooling fail
                                    loud at parse time, which is the right
                                    behaviour given the "don't silently
                                    drop unknown data" stance.
"""

from __future__ import annotations

import datetime as _dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OriginItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: int
    item: str
    source: str
    # Free-form per the spec: canonical tokens are `development` /
    # `operations` / `decision`, but transitions like
    # `decision → development` and compounds like
    # `development (future-triggered)` are accepted unchanged.
    track: str


class PlanMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal[2]
    plan: str
    spec: str | None = None
    target_repo: str
    # Legacy constraint for the retired `vk` tool — parsed but NEVER
    # enforced (inert metadata; plans in the wild keep it). The enforced
    # constraint is `fr_version` (super-fr split, v3).
    vk_version: str | None = None
    fr_version: str | None = None
    created: str  # YYYY-MM-DD; not parsed to date for round-trip stability
    parent_plan: str | None = None
    prior_rework: str | None = None
    origin_items: list[OriginItem] = Field(default_factory=list)
    # The workflow SHAPE this plan dispatches at (2026-08-14 workflow-shapes
    # spec §4.A.1, Phase 12) — resolved through
    # `fr.workflow.resolve.workflow_for_plan`, repo > shipped. Optional, and
    # **absence means exactly today's behaviour**: no key resolves
    # `FR_GOAL_PHASE_DISPATCH`, which is what lets the live bridge keep
    # ticking every existing plan through the upgrade. A name that does NOT
    # resolve is an error, never a fallback to the default.
    #
    # Declared LAST so a plan written before the field existed keeps its byte
    # order when rewritten. Because this model is extra="forbid", a plan
    # carrying the key is a hard parse failure on fr < 4.0.0 (not a warning) —
    # hence `fr plan create --workflow` floors `fr_version` at >=4.0.0.
    workflow: str | None = None

    @field_validator("created", mode="before")
    @classmethod
    def _coerce_date_to_iso(cls, v: object) -> object:
        # PyYAML parses bare `2026-05-09` as datetime.date; coerce back to
        # ISO string so the canonical representation is always a string.
        if isinstance(v, _dt.date):
            return v.isoformat()
        return v


class Step(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(pattern=r"^P\d+\.T\d+\.S\d+$")
    text: str


class Task(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    number: int
    title: str
    steps: tuple[Step, ...]


class PhaseHeader(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    # Phase numbering starts at 1 — a `00.yaml` phase fails parse loud.
    # (Frank's pre-fix `safe-update-automation` plan has a phase 0; the
    # bridge skips unparseable plans gracefully until it's remediated.)
    number: int = Field(ge=1)
    title: str
    tag: Literal["agentic", "manual"]
    depends_on: tuple[int, ...] = ()
    tracking_issue: str | None = None
    # Acceptance-matrix row ids this phase advances (2026-07-04 spec,
    # decision 2). Optional and omitted when empty, so pre-acceptance plans
    # stay byte-stable; `fr plan self-review` validates the ids against
    # docs/acceptance/matrix.yaml.
    acceptance: tuple[str, ...] = ()
    # Harness-neutral complexity hint used by fr-goal to pick a subagent model
    # at dispatch (2026-07-22 fr-goal-subagent-execution spec §B.2). The plan
    # never names a concrete model — the tier→model binding is resolved per
    # harness via `fr models`. Optional + None default keeps pre-tier plans
    # byte-stable; adding it is a deliberate extra=forbid schema bump (see the
    # module docstring's "must update your fr_version" note).
    tier: Literal["mechanical", "standard", "hard"] | None = None


class StepState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    state: Literal[" ", "x", "-"]
    ticked_at: str | None = None
    note: str | None = None


class Completion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    at: str | None = None
    note: str | None = None
    observed_prs: tuple[str, ...] = ()


class PhaseStateBlock(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    steps: dict[str, StepState]
    completion: Completion


class PhaseDoc(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal[2]
    phase: PhaseHeader
    tasks: tuple[Task, ...]
    state: PhaseStateBlock

    @model_validator(mode="after")
    def _state_keys_match_steps(self) -> PhaseDoc:
        step_ids = {s.id for t in self.tasks for s in t.steps}
        state_keys = set(self.state.steps.keys())
        if step_ids != state_keys:
            missing = step_ids - state_keys
            extra = state_keys - step_ids
            raise ValueError(
                f"state.steps keys must match task step ids exactly. "
                f"missing={sorted(missing)} extra={sorted(extra)}"
            )
        return self
