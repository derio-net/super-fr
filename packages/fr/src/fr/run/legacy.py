"""The run cursor's shape BEFORE version 5 — frozen, and the 4 -> 5 rewrite.

## The rule this module exists to state (spec §4.F)

**It is a superset of run-cursor versions 1 through 4, and it can be that
precisely BECAUSE every change so far was additive.** Version 1 had no stamp at
all; 1 -> 2, 2 -> 3 and 3 -> 4 each only ADDED an optional, defaulted field, so
one closed-world model reads all four. **It must never be edited again.**

Every earlier run migration "parsed first" with the LIVE `fr.run.model`, and
that was sound only while the live model stayed a superset of every old shape.
The 4 -> 5 rewrite REMOVES `items`, `dispatch` and `accounting` from an
`extra="forbid"` model. Had the chain kept validating against the live model, a
v2 cursor carrying `items` would stop parsing and `2 -> 3 -> 4 -> 5` would
refuse every old cursor **at its first hop** — stranding exactly the files the
framework exists to carry. So every hop up to and including `4 -> 5` reads with
the models below, and the live `RunState` is v5 only.

The general rule, now in `.claude/rules/artifact-versioning.md`: *the first
migration that removes or moves a field freezes the prior shape as a legacy
model, and no migration may validate an old file against the live one.*

**A future removal freezes a `…V5` beside this, it does not edit this.** A v4
cursor sitting on an unmerged branch is already written; editing the reader
changes what fr believes those bytes mean, silently and retroactively.
`tests/unit/test_run_legacy.py` pins each class's source by SHA-256 so that an
edit fails loudly and has to be argued for in a diff to `FROZEN_CLASS_SHA256`.

## Two deliberate divergences from a literal copy

1. **The vocabularies are INLINED** (`STEP_STATES_V4` and friends) instead of
   imported from `fr.run.model`. A frozen reader that followed a live
   vocabulary would stop being a reader of v4 the moment the vocabulary grew.
2. **`DispatchRecordV4` does not validate `harness` against
   `fr.harness.model.HARNESSES`.** The live model does, and should — but that
   list is a live vocabulary too, and a harness retired from it would make
   every cursor that recorded it unreadable and therefore unmigratable. This
   reader's job is to READ what fr wrote, not to re-litigate a vocabulary; the
   live `parse_run_state` and `fr validate artifacts` still check it on the way
   out. Refusing to read a file you are about to repair is the failure mode
   §4.F names.
"""

from __future__ import annotations

import copy
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from fr.run.model import RunStateError

STEP_STATES_V4: tuple[str, ...] = ("pending", "running", "done", "failed", "blocked")
"""A v4 step's lifecycle vocabulary, inlined and frozen."""

DISPATCH_OUTCOMES_V4: tuple[str, ...] = ("done", "failed", "abandoned")
"""How a v4 dispatch ended, inlined and frozen."""

ANSWERED_BY_V4: tuple[str, ...] = ("operator", "agent")
"""Who cleared a v4 operator gate, inlined and frozen."""

MEASURED_TOKEN_FIELDS_V4: tuple[str, ...] = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)
"""The four V2 telemetry figures a v3/v4 `accounting` entry can carry. A
measurement is ATOMIC — all four or none — which is what makes a partial one a
structural problem the rewrite below refuses rather than silently completes."""

StepStateV4 = Literal["pending", "running", "done", "failed", "blocked"]
AnsweredByV4 = Literal["operator", "agent"]
DispatchOutcomeV4 = Literal["done", "failed", "abandoned"]


class DispatchRecordV4(BaseModel):
    """One v4 attempt to hold a unit (`StepRecord.dispatch`'s element type).

    FROZEN. See the module docstring.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dispatched: str
    agent: str | None = None
    agent_type: str | None = None
    harness: str | None = None
    model: str | None = None
    returned: str | None = None
    outcome: DispatchOutcomeV4 | None = None

    @model_validator(mode="after")
    def _returned_and_outcome_are_one_fact(self) -> DispatchRecordV4:
        if (self.returned is None) != (self.outcome is None):
            raise ValueError(
                "`returned` and `outcome` are set together or not at all "
                f"(returned={self.returned!r}, outcome={self.outcome!r}); a record with "
                "exactly one of them is neither open nor closed"
            )
        return self


class StepRecordV4(BaseModel):
    """One step of a v1-v4 cursor: its lifecycle, what it emitted, and the
    three per-unit maps version 5 collapses.

    FROZEN. See the module docstring.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: StepStateV4
    at: str | None = None
    gate: Literal["cleared"] | None = None
    answered_by: AnsweredByV4 | None = None
    emitted: dict[str, str] | None = None
    exit: int | None = None
    stdout: str | None = None
    items: dict[str, str] | None = None
    members: list[str] | None = None
    dispatch: dict[str, list[DispatchRecordV4]] | None = None


class PhaseAccountingV4(BaseModel):
    """One entry of a v1-v4 cursor's top-level `accounting` map: the V1 sizes
    fr assembled for a unit, plus the V2 measured figures where a transcript
    was read.

    FROZEN. See the module docstring.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    at: str | None = None
    journal_entries: int = 0
    journal_lines: int = 0
    handoff_chars: int = 0
    spec_bytes: int = 0
    plan_bytes: int = 0

    input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    output_tokens: int | None = None


class RunStateV4(BaseModel):
    """A run cursor as versions 1 through 4 wrote it.

    FROZEN. See the module docstring.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    run: str
    workflow: str
    branch: str
    started: str
    cursor: str
    steps: dict[str, StepRecordV4]
    accounting: dict[str, PhaseAccountingV4] | None = None


FROZEN_CLASS_SHA256: dict[str, str] = {
    "DispatchRecordV4": "6c454584292c57030550d4d42f227a77b168ebcd84a47386267c6b9be21eb411",
    "StepRecordV4": "c21f3e37706ad67b94268a78fd0754a87ca0ce38c4682f2a4aea4c067382bb50",
    "PhaseAccountingV4": "ee6f64286a0d7b4ffe787090798db6611dc1a2e66b5c126d2e8a8ea45494de64",
    "RunStateV4": "2a9bf23560d5b223d5617e6bf8bc4524b47078b207ceefb640bd3ead95e949c9",
    # the v5/v6 shape, frozen by run 6 -> 7 (bottom of this module)
    "ContextEstimateV6": "99e2c4859590c997d23342839f547f160e39bbf01aa1e91a994d6cf612d71e54",
    "MeasuredTokensV6": "f6b968da0eb527cc5b063ecfd6bdb4031e275b2a893a4e5f3167817ee469e8f4",
    "MainSessionUsageV6": "180916a5470eb04b2dad1a2f5c23f40d37e2bd234b2e41be9da76f34de0f00cb",
    "AttemptV6": "81d96c71e60c737fcb763f5d30f4ebf977c8ab0670ba36e940779394bf033cda",
    "UnitRecordV6": "46c2c06e2eeae7fb249cebca58bf88e3787dd558b87e1935b839f4b2906dfdcc",
    "StepRecordV6": "774a1f3c402e88dcb3725ddc1610ed3fda3db896ca61bfbf139848a136d691da",
    "RunStateV6": "eda937dfba50c7e8831fe98668a87af9c6d6f7b10d41a6a0858244817d0cbba6",
}
"""SHA-256 of each frozen class's own source, as `inspect.getsource` returns it.

The tripwire (`tests/unit/test_run_legacy.py`) compares against these. They are
recorded rather than computed at import time on purpose: a hash the module
derives from itself always matches itself and proves nothing.
"""


def parse_run_state_v4(text: str) -> RunStateV4:
    """Parse + validate `text` as a run cursor of version 1, 2, 3 or 4.

    Raises `RunStateError` — never a raw `yaml.YAMLError` or pydantic
    `ValidationError` — exactly like the live `parse_run_state`, so a caller
    that swaps one for the other catches the same thing.
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise RunStateError(f"invalid YAML: {e}") from e

    if not isinstance(raw, dict):
        raise RunStateError("run state must be a YAML mapping at the top level")

    try:
        return RunStateV4.model_validate(raw)
    except ValidationError as e:
        raise RunStateError(f"invalid run state: {e}") from e


class RunMigrationError(RunStateError):
    """A v4 cursor the 4 -> 5 rewrite will not convert.

    Named separately from `RunStateError` because it means something different:
    the file was READ fine, and fr is refusing to write a v5 body it would have
    had to invent. Spec §4.F — "a cursor the migration cannot fully convert is
    left byte-identical".
    """


def v4_to_v5(data: dict[str, Any]) -> dict[str, Any]:
    """The `run` 4 -> 5 body rewrite, as a pure function. No I/O, no clock.

    `data` is a parsed v4 cursor (plain YAML data, not a model); the return
    value is the same cursor in the v5 shape. The input is never mutated.

    What it does, per spec §4.F:

    1. `items[k] = s` becomes `units[k].state = s`. gh#496's `phase/<n>:
       manual` markers keep `state: manual` and acquire no attempts — the whole
       point of the marker is that nothing was ever dispatched.
    2. `dispatch[k] = [...]` becomes `units[k].attempts`, unchanged and in
       order. A flat `kind: agent` step's `step/<step-id>` unit therefore
       arrives with attempts and **no `state`**: §4.B gives that fact one home,
       `StepRecord.state`, and this rewrite must not give it a second.
    3. `accounting[k]` splits into `estimate` (the five V1 sizes) and
       `measured` (the four V2 figures, when all four are there) and attaches
       to the **last** attempt of `units[k]` — the attempt the cost belongs to.
    4. A unit with accounting but NO attempt (every pre-#508 cursor, which is
       most of them) gets **one synthesized attempt** with
       `dispatched = accounting.at` and no identity at all. Stated, not
       invented: that is when fr briefed the unit, and it is the only fact fr
       has. No agent, no agent_type, no harness, no model, no outcome — and
       `synthesized: true`, so that the missing `returned` never reads as a
       hold and the missing `agent_type` never reads as "the orchestrator"
       (phase 3 found both, end to end, on a migrated in-flight cursor).
    5. The top-level `accounting` map is dropped.

    `schema_version` is NOT touched: the migration runner writes the stamp, and
    a body rewrite that also stamped would be two facts in one function.

    **Idempotent.** A cursor already in the v5 shape has no `items`, `dispatch`
    or `accounting` to convert and comes back equal to itself.

    Raises `RunMigrationError`, naming the field or key, rather than converting
    partially:

    - a **partial measurement** (some of the four token figures). It is already
      invalid under gh#514's validator, and completing it with zeros would
      manufacture a measurement nobody took.
    - an accounting entry for a unit **no step records**, which has nowhere to
      attach and whose figures would otherwise vanish.
    - an accounting entry with **no `at`** on a unit with no attempt, where
      there is neither an attempt to hang the cost on nor a timestamp to
      synthesize one from.
    """
    out = copy.deepcopy(data)
    steps = out.get("steps")
    if not isinstance(steps, dict):
        return out

    accounting = out.get("accounting") or {}

    # Which step owns each unit key. Built before anything is written, so the
    # refusals below fire on a still-unmodified `out`.
    owner_of: dict[str, str] = {}
    for step_id, record in steps.items():
        if not isinstance(record, dict):
            continue
        for key in record.get("items") or {}:
            owner_of.setdefault(key, step_id)
        for key in record.get("dispatch") or {}:
            owner_of.setdefault(key, step_id)

    for key in accounting:
        if key not in owner_of:
            raise RunMigrationError(
                f"`accounting.{key}` names a unit no step records, so its cost has "
                "nowhere to go in the v5 shape. fr will not drop a figure to make a "
                "cursor convertible — repair the file by hand; it is left unchanged."
            )

    for step_id, record in steps.items():
        if not isinstance(record, dict):
            continue
        units: dict[str, dict[str, Any]] = {}
        for key, state in (record.get("items") or {}).items():
            units.setdefault(key, {})["state"] = state
        for key, attempts in (record.get("dispatch") or {}).items():
            units.setdefault(key, {})["attempts"] = list(attempts)

        for key in units:
            snapshot = accounting.get(key)
            if snapshot is None or owner_of.get(key) != step_id:
                continue
            _attach_cost(units[key], key, snapshot)

        record.pop("items", None)
        record.pop("dispatch", None)
        if units:
            record["units"] = units

    out.pop("accounting", None)
    return out


def _attach_cost(unit: dict[str, Any], key: str, snapshot: dict[str, Any]) -> None:
    """Fold one v4 `accounting` entry onto `unit`'s LAST attempt, in place.

    Synthesizes the one attempt §4.F sanctions when there is none — and only
    that one. `dispatched` is the snapshot's `at`, which is when fr assembled
    the context, i.e. when it briefed the unit; every identity field stays
    absent, because fr genuinely does not know them.
    """
    estimate = {
        name: snapshot.get(name, 0)
        for name in (
            "journal_entries",
            "journal_lines",
            "handoff_chars",
            "spec_bytes",
            "plan_bytes",
        )
    }
    measured = _measured_or_none(key, snapshot)

    attempts = unit.get("attempts")
    if not attempts:
        at = snapshot.get("at")
        if at is None:
            raise RunMigrationError(
                f"`accounting.{key}` has no `at` and its unit has no dispatch record, so "
                "there is nothing to attach its cost to and no moment to synthesize an "
                "attempt from. fr will not invent one — the cursor is left unchanged."
            )
        # `synthesized` is what keeps this attempt from reading as a HOLD (it
        # has no `returned`, and never will) or as orchestrator-run (it has no
        # `agent_type`): see `fr.run.model.Attempt.synthesized`.
        attempts = [{"dispatched": at, "synthesized": True}]
        unit["attempts"] = attempts

    last = attempts[-1]
    last["estimate"] = estimate
    if measured is not None:
        last["measured"] = measured
    if "synthesized" in last:
        # Key order is part of what lands on disk. The live model declares
        # `synthesized` after the cost fields, so a rewrite that leaves it
        # ahead of them is reordered by the cursor's first native save — a
        # diff nobody wrote, on every migrated cursor.
        last["synthesized"] = last.pop("synthesized")


def _measured_or_none(key: str, snapshot: dict[str, Any]) -> dict[str, int] | None:
    """The four V2 figures, or `None` when none were recorded — and a refusal
    when only some were. A measurement is all four or it is not one."""
    present = {
        name: snapshot[name] for name in MEASURED_TOKEN_FIELDS_V4 if snapshot.get(name) is not None
    }
    if not present:
        return None
    missing = [name for name in MEASURED_TOKEN_FIELDS_V4 if name not in present]
    if missing:
        raise RunMigrationError(
            f"`accounting.{key}` records a PARTIAL measurement: {', '.join(missing)} "
            "missing. A measurement is all four fields or none — three of four sums to "
            "a number that reads like a whole one — so fr will not complete it with "
            "zeros. The cursor is left unchanged."
        )
    return present


# --- the v5/v6 shape, frozen by run 6 -> 7 ----------------------------------
#
# Spec `2026-09-25-lean-cost-aware-process-design.md` §5.B.4: `Attempt.estimate`,
# `Attempt.measured` and `StepRecord.main_session` left the live model, so the
# shape that carried them is frozen here — a superset of versions 5 and 6 (6
# only ADDED `main_session`). Every hop from 4 -> 5 onward reads with it.
#
# Same two divergences as the v4 freeze, for the same reasons: vocabularies are
# INLINED, and `harness` is not validated against the live `HARNESSES`. And one
# more: the live model's cross-field validators (returned/outcome together, a
# synthesized attempt claims nothing) are not copied. This reader's job is to
# READ what fr wrote; the live model and `fr validate artifacts` check the
# result on the way out.

UNIT_STATES_V6: tuple[str, ...] = ("pending", "running", "done", "failed", "manual")
"""A v5/v6 unit's state vocabulary, inlined and frozen."""

UnitStateV6 = Literal["pending", "running", "done", "failed", "manual"]


class ContextEstimateV6(BaseModel):
    """FROZEN. `Attempt.estimate` as versions 5 and 6 wrote it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    journal_entries: int = 0
    journal_lines: int = 0
    handoff_chars: int = 0
    spec_bytes: int = 0
    plan_bytes: int = 0


class MeasuredTokensV6(BaseModel):
    """FROZEN. `Attempt.measured`: all four figures, or no record at all."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int


class MainSessionUsageV6(BaseModel):
    """FROZEN. `StepRecord.main_session` as version 6 wrote it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int
    turns: int
    sessions: int
    cost_usd: float | None = None


class AttemptV6(BaseModel):
    """FROZEN. One attempt to hold a unit, as versions 5 and 6 wrote it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dispatched: str
    agent: str | None = None
    agent_type: str | None = None
    harness: str | None = None
    model: str | None = None
    session: str | None = None
    returned: str | None = None
    outcome: DispatchOutcomeV4 | None = None
    estimate: ContextEstimateV6 | None = None
    measured: MeasuredTokensV6 | None = None
    synthesized: Literal[True] | None = None


class UnitRecordV6(BaseModel):
    """FROZEN. One unit of one step (`StepRecord.units`' value type)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: UnitStateV6 | None = None
    attempts: tuple[AttemptV6, ...] = ()
    evidence: dict[str, str] | None = None


class StepRecordV6(BaseModel):
    """FROZEN. One step of a v5/v6 cursor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: StepStateV4
    at: str | None = None
    gate: Literal["cleared"] | None = None
    answered_by: AnsweredByV4 | None = None
    emitted: dict[str, str] | None = None
    exit: int | None = None
    stdout: str | None = None
    main_session: MainSessionUsageV6 | None = None
    members: list[str] | None = None
    units: dict[str, UnitRecordV6] | None = None


class RunStateV6(BaseModel):
    """FROZEN. A run cursor as versions 5 and 6 wrote it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    run: str
    workflow: str
    branch: str
    started: str
    cursor: str
    steps: dict[str, StepRecordV6]


def parse_run_state_v6(text: str) -> RunStateV6:
    """Parse + validate `text` as a run cursor of version 5 or 6.

    Raises `RunStateError`, exactly like `parse_run_state_v4`."""
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise RunStateError(f"invalid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise RunStateError("run state must be a YAML mapping at the top level")
    try:
        return RunStateV6.model_validate(raw)
    except ValidationError as e:
        raise RunStateError(f"invalid run state: {e}") from e
