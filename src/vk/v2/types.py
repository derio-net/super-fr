from __future__ import annotations

import datetime as _dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OriginItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: int
    item: str
    source: str
    track: Literal["development", "operations", "decision"]


class PlanMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal[2]
    plan: str
    spec: str | None = None
    target_repo: str
    vk_version: str
    created: str  # YYYY-MM-DD; not parsed to date for round-trip stability
    parent_plan: str | None = None
    prior_rework: str | None = None
    origin_items: list[OriginItem] = Field(default_factory=list)

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
    number: int
    title: str
    tag: Literal["agentic", "manual"]
    depends_on: tuple[int, ...] = ()
    tracking_issue: str | None = None


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
