"""The step record's shapes BEFORE version 8 — frozen.

`RecordV6` reads versions 1 to 6; `RecordV7` (at the bottom) reads version 7,
frozen when 7 -> 8 widened `AcceptanceItem.verify` (spec
`2026-10-06-verification-strategies-design.md` §B).

Record versions 1 through 6 only ever ADDED an optional, defaulted field, so
one closed-world model reads all six. The 6 -> 7 migration (spec
`2026-09-29-spec-is-the-contract-design.md` §C) REMOVES `JournalItem.delegated`
and the `unconfirmed` member of `ResolutionState` from an `extra="forbid"`
model. Validated against the live model, a v5 record carrying `delegated` would
stop parsing and the chain would refuse it at its first hop — so every record
hop reads through `RecordV6`, and the live `StepRecord` is v7 only. The
standing rule is `.claude/rules/artifact-versioning.md`.

**It must never be edited again.** A v6 record on an unmerged branch is already
written; editing the reader changes what fr believes those bytes mean. A later
removal freezes a `…V7` beside it. `FROZEN_CLASS_SHA256` pins each class's
source (`tests/unit/test_migration_record_contract.py`).

Two deliberate divergences from a literal copy of the v6 `fr.record.model`:

1. **The vocabularies are INLINED** (`JournalKindV6` and friends) rather than
   imported from `fr.journal.model`, `fr.run.model` and `fr.acceptance.model`:
   a frozen reader that followed a live vocabulary would stop reading v6 the
   day that vocabulary moved.
2. **`VisualV6` does not check its state and interaction names.** The live
   `Visual` does, through `check_visual_names`, a live rule. This reader's job
   is to READ what fr wrote; the live model re-checks on the way out.
"""

from __future__ import annotations

import re
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError, model_validator

JournalKindV6 = Literal[
    "decision",
    "review",
    "discovery",
    "finding",
    "repro",
    "hypothesis",
    "ruled-out",
    "root-cause",
]
FindingStateV6 = Literal["fixed", "refuted", "open"]
ReviewScopeV6 = Literal["in", "out"]
AnsweredByV6 = Literal["operator", "agent"]
OutcomeV6 = Literal["done", "failed", "blocked"]
ResolutionStateV6 = Literal["fixed", "refuted", "deferred", "out-of-scope", "unconfirmed"]
TICK_ID_RE_V6 = re.compile(r"^P\d+\.T\d+\.S\d+$")
TASK_ID_RE_V6 = re.compile(r"^P\d+\.T\d+$")


class RecordV6Error(Exception):
    """A file that does not read as a record of version 1 to 6."""


class _StrictV6(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class TickItemV6(_StrictV6):
    id: StrictStr
    state: Literal["x", "-"] = "x"
    note: StrictStr | None = None

    @model_validator(mode="after")
    def _skip_needs_a_note(self) -> TickItemV6:
        if not TICK_ID_RE_V6.match(self.id):
            raise ValueError(f"tick id must look like P<n>.T<m>.S<k>, got {self.id!r}")
        if self.state == "-" and not self.note:
            raise ValueError(f"{self.id}: a skipped step (state '-') needs a note")
        return self


class CompleteItemV6(_StrictV6):
    phase: int
    note: StrictStr | None = None


class JournalItemV6(_StrictV6):
    kind: JournalKindV6
    id: StrictStr | None = None
    title: StrictStr
    body: StrictStr = ""
    state: FindingStateV6 | None = None
    phase: int | None = None
    is_global: bool = Field(False, alias="global")
    review_scope: ReviewScopeV6 | None = None
    resolves: StrictStr | None = None
    answered_by: AnsweredByV6 | None = None
    tracked_by: StrictStr | None = None
    out_of_scope: bool = False
    input: bool = False
    delegated: bool = False


class ResolutionV6(_StrictV6):
    id: StrictStr
    state: ResolutionStateV6
    body: StrictStr = Field(min_length=1)
    phase: int | None = None
    tracked_by: StrictStr | None = None
    answered_by: AnsweredByV6 | None = None

    @model_validator(mode="after")
    def _deferral_names_its_issue(self) -> ResolutionV6:
        if self.state == "deferred" and not self.tracked_by:
            raise ValueError(f"{self.id}: state deferred needs tracked_by (#N or a URL)")
        if self.tracked_by is not None and self.state != "deferred":
            raise ValueError(f"{self.id}: tracked_by is only for state deferred")
        return self


class VisualV6(_StrictV6):
    states: tuple[StrictStr, ...] = ()
    interactions: tuple[StrictStr, ...] = ()


class AcceptanceItemV6(_StrictV6):
    id: StrictStr
    capability: StrictStr | None = None
    acceptance: StrictStr | None = None
    origin: tuple[StrictStr, ...] = ()
    levels: dict[str, tuple[StrictStr, ...]] = {}
    status: StrictStr
    notes: StrictStr | None = None
    verify: Literal["post-merge"] | None = None
    visual: VisualV6 | None = None


class VisualShotV6(_StrictV6):
    path: StrictStr
    shows: tuple[StrictStr, ...] = Field(min_length=1)


class VisualEvidenceV6(_StrictV6):
    row: StrictStr
    script: StrictStr | None = None
    shots: tuple[VisualShotV6, ...] = Field(min_length=1)


class QuestionRoundsV6(_StrictV6):
    rounds: Literal[1, 2] = 1
    trigger: Literal["design-risk", "operator-request"] | None = None
    reason: StrictStr | None = None

    @model_validator(mode="after")
    def _round_two_explains_itself(self) -> QuestionRoundsV6:
        if self.rounds == 2:
            if self.trigger is None:
                raise ValueError("questions.trigger is required when rounds: 2")
            if not (self.reason or "").strip():
                raise ValueError("questions.reason is required when rounds: 2")
        else:
            if self.trigger is not None:
                raise ValueError("questions.trigger is only for rounds: 2")
            if self.reason is not None:
                raise ValueError("questions.reason is only for rounds: 2")
        return self


class RecordV6(_StrictV6):
    schema_version: Literal[1, 2, 3, 4, 5, 6] = 6
    run: StrictStr | None = None
    step: StrictStr | None = None
    item: StrictStr | None = None
    outcome: OutcomeV6 | None = None
    shape: StrictStr | None = None
    no_questions: bool = False
    reason: StrictStr | None = None
    questions: QuestionRoundsV6 | None = None
    ticks: tuple[StrictStr | TickItemV6, ...] = ()
    complete: CompleteItemV6 | None = None
    refactor: dict[StrictStr, StrictStr] = {}
    journal: tuple[JournalItemV6, ...] = ()
    resolves: tuple[ResolutionV6, ...] = ()
    acceptance: tuple[AcceptanceItemV6, ...] = ()
    visual: tuple[VisualEvidenceV6, ...] = ()
    emitted: dict[StrictStr, StrictStr] = {}
    evidence: dict[StrictStr, StrictStr] = {}

    @model_validator(mode="after")
    def _ids_are_shaped(self) -> RecordV6:
        if self.questions is not None and self.no_questions:
            raise ValueError("questions and no_questions are mutually exclusive")
        for tick in self.ticks:
            if isinstance(tick, str) and not TICK_ID_RE_V6.match(tick):
                raise ValueError(f"tick id must look like P<n>.T<m>.S<k>, got {tick!r}")
        for task in self.refactor:
            if not TASK_ID_RE_V6.match(task):
                raise ValueError(f"refactor key must be a task id P<n>.T<m>, got {task!r}")
            if not self.refactor[task].strip():
                raise ValueError(f"refactor reason for {task} is empty")
        return self


FROZEN_CLASS_SHA256: dict[str, str] = {
    "_StrictV6": "3a7269617b79e472658eca3c9cfbdc4df6448d02ea763829ae38b83cd7f8f9c3",
    "TickItemV6": "b3cf6db74580af478631468765f1c877153050588ac0d56ec0264ea7b75e07bb",
    "CompleteItemV6": "56da9253ca3cd53b97e24185fab7f306ed6a17f2a6ef8d85291263255d81ce35",
    "JournalItemV6": "49b5f7090b4681d8f10caf35062b2c79b9a91aecffc9fdfcdbe1c566f58222fa",
    "ResolutionV6": "9dd94967de29c8b78773efba9d05693b5a9e100fc9e0989dd4d5b902316a15f9",
    "VisualV6": "3cb9cdef824ad6016e6046a62dffc77fee1d98aae6e037ebb30c7bc86ae127cb",
    "AcceptanceItemV6": "62f52f2d46de870a6c8ec66cd8f20af184ba6e53130ea29ba215c2ddc0cc22da",
    "VisualShotV6": "e94368151f66285696406c88789ea7ab741bde664a93a9561096dce62c0fb43a",
    "VisualEvidenceV6": "8573e15b239b2f36590a908feb91db11aebe732812ab6dfbfb073a5a8f197152",
    "QuestionRoundsV6": "2fedbb65cc9f83a9509fdfba33a913e121796414c92a84bc7ced9335eaf00fa7",
    "RecordV6": "b76ed7d10c90799a883a2c6a9047f80fd338ec8a31a38382a6dfe2bec1c0d76b",
}
"""SHA-256 of each frozen class's own source, as `inspect.getsource` returns it.
Recorded, not computed at import: a hash the module derives from itself always
matches itself and proves nothing."""


def parse_record_v6(text: str) -> RecordV6:
    """Parse + validate `text` as a record of version 1 to 6, or raise
    `RecordV6Error` naming why — never a raw YAML or pydantic error."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise RecordV6Error(f"not valid YAML: {e}") from e
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise RecordV6Error(f"top level must be a mapping, got {type(data).__name__}")
    return record_v6_from_data(data)


def record_v6_from_data(data: dict[str, Any]) -> RecordV6:
    """Validate an already-loaded mapping as a record of version 1 to 6 (an
    unstamped one is version 1), or raise `RecordV6Error`."""
    try:
        return RecordV6.model_validate({"schema_version": 1, **data})
    except ValidationError as e:
        raise RecordV6Error(str(e)) from e


# --- version 7 ----------------------------------------------------------------
#
# The 7 -> 8 migration (spec `2026-10-06-verification-strategies-design.md` §B)
# widens `AcceptanceItem.verify` from `Literal["post-merge"]` to a strategy name
# and refuses the old spelling, so the live model no longer reads a v7 record
# carrying it. `RecordV7` is version 7 exactly, frozen the same way and pinned by
# `FROZEN_V7_CLASS_SHA256` (`tests/unit/test_record_acceptance_v8.py`). It reuses
# the v6 classes whose v7 shape did not change — they are frozen already — and
# freezes only what 6 -> 7 changed.

ResolutionStateV7 = Literal["fixed", "refuted", "deferred", "out-of-scope"]


class RecordV7Error(Exception):
    """A file that does not read as a record of version 7."""


class JournalItemV7(_StrictV6):
    kind: JournalKindV6
    id: StrictStr | None = None
    title: StrictStr
    body: StrictStr = ""
    state: FindingStateV6 | None = None
    phase: int | None = None
    is_global: bool = Field(False, alias="global")
    review_scope: ReviewScopeV6 | None = None
    resolves: StrictStr | None = None
    answered_by: AnsweredByV6 | None = None
    tracked_by: StrictStr | None = None
    out_of_scope: bool = False
    input: bool = False


class ResolutionV7(_StrictV6):
    id: StrictStr
    state: ResolutionStateV7
    body: StrictStr = Field(min_length=1)
    phase: int | None = None
    tracked_by: StrictStr | None = None
    answered_by: AnsweredByV6 | None = None

    @model_validator(mode="after")
    def _deferral_names_its_issue(self) -> ResolutionV7:
        if self.state == "deferred" and not self.tracked_by:
            raise ValueError(f"{self.id}: state deferred needs tracked_by (#N or a URL)")
        if self.tracked_by is not None and self.state != "deferred":
            raise ValueError(f"{self.id}: tracked_by is only for state deferred")
        return self


class RecordV7(_StrictV6):
    schema_version: Literal[7] = 7
    run: StrictStr | None = None
    step: StrictStr | None = None
    item: StrictStr | None = None
    outcome: OutcomeV6 | None = None
    shape: StrictStr | None = None
    no_questions: bool = False
    reason: StrictStr | None = None
    questions: QuestionRoundsV6 | None = None
    ticks: tuple[StrictStr | TickItemV6, ...] = ()
    complete: CompleteItemV6 | None = None
    refactor: dict[StrictStr, StrictStr] = {}
    journal: tuple[JournalItemV7, ...] = ()
    resolves: tuple[ResolutionV7, ...] = ()
    acceptance: tuple[AcceptanceItemV6, ...] = ()
    visual: tuple[VisualEvidenceV6, ...] = ()
    emitted: dict[StrictStr, StrictStr] = {}
    evidence: dict[StrictStr, StrictStr] = {}

    @model_validator(mode="after")
    def _ids_are_shaped(self) -> RecordV7:
        if self.questions is not None and self.no_questions:
            raise ValueError("questions and no_questions are mutually exclusive")
        for tick in self.ticks:
            if isinstance(tick, str) and not TICK_ID_RE_V6.match(tick):
                raise ValueError(f"tick id must look like P<n>.T<m>.S<k>, got {tick!r}")
        for task in self.refactor:
            if not TASK_ID_RE_V6.match(task):
                raise ValueError(f"refactor key must be a task id P<n>.T<m>, got {task!r}")
            if not self.refactor[task].strip():
                raise ValueError(f"refactor reason for {task} is empty")
        return self


FROZEN_V7_CLASS_SHA256: dict[str, str] = {
    "JournalItemV7": "da99c22cb7bb1f66deda38584c62e70674cd191d0df509a686159bba38c5ebae",
    "ResolutionV7": "c3652b24292aa764a7308fe5d1d8e013a97e6a9019c07041f881389ec1904b2c",
    "RecordV7": "2b419526080813782feff466a37e2eafd73df4401a9e532dbe5995df92066904",
}
"""As `FROZEN_CLASS_SHA256`, for the classes version 7 froze."""


def parse_record_v7(text: str) -> RecordV7:
    """Parse + validate `text` as a record of version 7, or raise
    `RecordV7Error` naming why — never a raw YAML or pydantic error."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise RecordV7Error(f"not valid YAML: {e}") from e
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise RecordV7Error(f"top level must be a mapping, got {type(data).__name__}")
    return record_v7_from_data(data)


def record_v7_from_data(data: dict[str, Any]) -> RecordV7:
    """Validate an already-loaded mapping as a record of version 7, or raise
    `RecordV7Error`."""
    try:
        return RecordV7.model_validate(data)
    except ValidationError as e:
        raise RecordV7Error(str(e)) from e
