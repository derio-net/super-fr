"""The `record` artifact: one step's bookkeeping, as data (spec
`2026-09-25-lean-cost-aware-process-design.md` §5.C.1).

A record lives at `docs/superpowers/runs/<run-id>.records/<step>[__<item>].yaml`
while its step is in progress. It is committed with the agent's normal commits
(so a stale session can be resumed from it) and deleted by the `fr run resolve
--record` that applies it, in that resolve's one commit.

Which sections a record may carry is read from the step's `emits:` — never from
a table in code about fr-goal's step names — so a repo-overridden manifest gets
the same rules without a line of code (§5.C.2.1, `fr.workflow.artifacts`).

The one-entry records the verbs build (`fr journal add`, `fr plan edit --tick`,
`fr acceptance set-status`, …) use the same model with `run: null`: they carry
every field the verb's own flags can express, which is why a few entry fields
here are richer than the §5.C.1 example shows.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError, model_validator

from fr.journal.model import FindingState, JournalKind, ReviewScope
from fr.run.model import AnsweredBy
from fr.workflow.artifacts import ALWAYS_RECORD_SECTIONS, record_sections

__all__ = [
    "RECORD_SCHEMA_VERSION",
    "RECORDS_SUFFIX",
    "AcceptanceItem",
    "CompleteItem",
    "JournalItem",
    "QuestionRounds",
    "RecordError",
    "Resolution",
    "StepRecord",
    "TickItem",
    "allowed_sections",
    "load_record",
    "parse_record",
    "present_sections",
    "record_path",
    "records_dir",
]

RECORD_SCHEMA_VERSION = 2
"""Bumped 1 -> 2 for `questions` (spec
`2026-09-26-dynamic-brainstorm-question-rounds-design.md` §3.B) — a shape
change under `.claude/rules/artifact-versioning.md`. Migration:
`fr.artifacts.record_questions`."""
RECORDS_SUFFIX = ".records"
RUNS_REL = Path("docs") / "superpowers" / "runs"

Outcome = Literal["done", "failed", "blocked"]
ResolutionState = Literal["fixed", "refuted", "deferred", "out-of-scope"]

_TICK_ID_RE = re.compile(r"^P\d+\.T\d+\.S\d+$")
_TASK_ID_RE = re.compile(r"^P\d+\.T\d+$")


class RecordError(Exception):
    """A record that does not parse, does not validate, or is not allowed."""


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class TickItem(_Strict):
    """A tick with a state other than the default `x`, or with a note — the
    long form the `fr plan edit --tick --state - --note` verb needs."""

    id: StrictStr
    state: Literal["x", "-"] = "x"
    note: StrictStr | None = None

    @model_validator(mode="after")
    def _skip_needs_a_note(self) -> TickItem:
        if not _TICK_ID_RE.match(self.id):
            raise ValueError(f"tick id must look like P<n>.T<m>.S<k>, got {self.id!r}")
        if self.state == "-" and not self.note:
            raise ValueError(f"{self.id}: a skipped step (state '-') needs a note")
        return self


class CompleteItem(_Strict):
    """`fr plan edit --complete-phase N [--note]` as a record entry."""

    phase: int
    note: StrictStr | None = None


class JournalItem(_Strict):
    """One journal entry. `id` is optional (fr derives one, as `fr journal add`
    does); a `finding` with no `state` is `open`; `phase` defaults to the
    record's item for a plan-scope journal."""

    kind: JournalKind
    id: StrictStr | None = None
    title: StrictStr
    body: StrictStr = ""
    state: FindingState | None = None
    phase: int | None = None
    is_global: bool = Field(False, alias="global")
    review_scope: ReviewScope | None = None
    resolves: StrictStr | None = None
    answered_by: AnsweredBy | None = None
    tracked_by: StrictStr | None = None
    out_of_scope: bool = False


class Resolution(_Strict):
    """Closing one finding — `fr journal resolve` as a record entry."""

    id: StrictStr
    state: ResolutionState
    body: StrictStr = Field(min_length=1)
    phase: int | None = None
    tracked_by: StrictStr | None = None
    answered_by: AnsweredBy | None = None

    @model_validator(mode="after")
    def _deferral_names_its_issue(self) -> Resolution:
        if self.state == "deferred" and not self.tracked_by:
            raise ValueError(f"{self.id}: state deferred needs tracked_by (#N or a URL)")
        if self.tracked_by is not None and self.state != "deferred":
            raise ValueError(f"{self.id}: tracked_by is only for state deferred")
        return self


class AcceptanceItem(_Strict):
    """One acceptance row. An id the matrix does not carry is CREATED (needs
    `capability` and `acceptance`); an id it does carry has its status moved
    in place (needs `notes`, the reason) and `levels` added to its evidence."""

    id: StrictStr
    capability: StrictStr | None = None
    acceptance: StrictStr | None = None
    origin: tuple[StrictStr, ...] = ()
    levels: dict[str, tuple[StrictStr, ...]] = {}
    status: StrictStr
    notes: StrictStr | None = None


class QuestionRounds(_Strict):
    """How many operator question rounds a cleared gate took (spec
    `2026-09-26-dynamic-brainstorm-question-rounds-design.md` §3.B).

    `rounds` is `Literal[1, 2]`, so a round 3 is unrepresentable by design —
    there is no value this field can hold that means "three rounds happened".
    `trigger`/`reason` are required when `rounds: 2` (the second round must
    explain itself) and forbidden when `rounds: 1` (the default needs no
    justification)."""

    rounds: Literal[1, 2] = 1
    trigger: Literal["design-risk", "operator-request"] | None = None
    reason: StrictStr | None = None

    @model_validator(mode="after")
    def _round_two_explains_itself(self) -> QuestionRounds:
        if self.rounds == 2:
            if self.trigger is None:
                raise ValueError("questions.trigger is required when rounds: 2")
            if not self.reason:
                raise ValueError("questions.reason is required when rounds: 2")
        else:
            if self.trigger is not None:
                raise ValueError("questions.trigger is only for rounds: 2")
            if self.reason is not None:
                raise ValueError("questions.reason is only for rounds: 2")
        return self


class StepRecord(_Strict):
    """The §5.C.1 record. Every section is optional; which ones a step may
    carry is `allowed_sections`' business, not the model's."""

    schema_version: int = RECORD_SCHEMA_VERSION
    run: StrictStr | None = None
    step: StrictStr | None = None
    item: StrictStr | None = None
    outcome: Outcome | None = None
    no_questions: bool = False
    """`fr run resolve --no-questions`: clear the step's operator gate WITHOUT
    having asked the operator — the explicit, recorded bypass (needs `reason`)."""
    reason: StrictStr | None = None
    """`--reason`: why no operator decision was needed (with `no_questions`)."""
    questions: QuestionRounds | None = None
    """`questions: {rounds, trigger, reason}` (spec
    `2026-09-26-dynamic-brainstorm-question-rounds-design.md` §3.B): how many
    operator question rounds this gate's resolve took. Absent means one round.
    Mutually exclusive with `no_questions` — a gate is either cleared by
    asking, or explicitly cleared without asking."""
    ticks: tuple[StrictStr | TickItem, ...] = ()
    complete: CompleteItem | None = None
    refactor: dict[StrictStr, StrictStr] = {}
    journal: tuple[JournalItem, ...] = ()
    resolves: tuple[Resolution, ...] = ()
    acceptance: tuple[AcceptanceItem, ...] = ()
    emitted: dict[StrictStr, StrictStr] = {}
    evidence: dict[StrictStr, StrictStr] = {}

    @model_validator(mode="after")
    def _ids_are_shaped(self) -> StepRecord:
        if self.schema_version != RECORD_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version {self.schema_version} — this fr reads record "
                f"version {RECORD_SCHEMA_VERSION}"
            )
        if self.questions is not None and self.no_questions:
            raise ValueError("questions and no_questions are mutually exclusive")
        for tick in self.ticks:
            if isinstance(tick, str) and not _TICK_ID_RE.match(tick):
                raise ValueError(f"tick id must look like P<n>.T<m>.S<k>, got {tick!r}")
        for task in self.refactor:
            if not _TASK_ID_RE.match(task):
                raise ValueError(f"refactor key must be a task id P<n>.T<m>, got {task!r}")
            if not self.refactor[task].strip():
                raise ValueError(f"refactor reason for {task} is empty")
        return self

    def tick_items(self) -> list[TickItem]:
        return [TickItem(id=t) if isinstance(t, str) else t for t in self.ticks]


# `ticks` and `complete` are one section for the manifest's purposes: both are
# plan state, both need `plan:ticks`.
_SECTION_FIELDS: dict[str, tuple[str, ...]] = {
    "ticks": ("ticks", "complete"),
    "refactor": ("refactor",),
    "journal": ("journal",),
    "resolves": ("resolves",),
    "acceptance": ("acceptance",),
    "outcome": ("outcome", "no_questions", "reason", "questions"),
    "evidence": ("evidence", "emitted"),
}


def present_sections(record: StepRecord) -> set[str]:
    """The sections this record actually fills — what `allowed_sections` is
    checked against. An empty section is not present."""
    out: set[str] = set()
    for section, fields in _SECTION_FIELDS.items():
        if any(getattr(record, f) not in (None, (), {}) for f in fields):
            out.add(section)
    return out


def allowed_sections(step: Any, group: Any = None) -> frozenset[str]:
    """The sections a record for `step` may carry (§5.C.2.1): read from the
    step's own `emits:`, falling back to its group's when it declares none —
    the same fallback `fr run resolve --emitted` uses."""
    emits = tuple(step.emits) or (tuple(group.emits) if group is not None else ())
    return frozenset(record_sections(emits)) | ALWAYS_RECORD_SECTIONS


def records_dir(repo_root: Path, run_id: str) -> Path:
    return repo_root / RUNS_REL / f"{run_id}{RECORDS_SUFFIX}"


def record_path(repo_root: Path, run_id: str, step: str, item: str | None = None) -> Path:
    """`<run>.records/<step>[__<item>].yaml`, `/` in an item spelled `-`."""
    name = step if item is None else f"{step}__{item.replace('/', '-')}"
    return records_dir(repo_root, run_id) / f"{name}.yaml"


def _problems(e: ValidationError) -> str:
    parts = []
    for err in e.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "record"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)


def parse_record(text: str, where: str = "record") -> StepRecord:
    """Parse and validate a record, or raise `RecordError` naming every problem."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise RecordError(f"{where}: not valid YAML: {e}") from e
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise RecordError(f"{where}: top level must be a mapping, got {type(data).__name__}")
    try:
        return StepRecord.model_validate(data)
    except ValidationError as e:
        raise RecordError(f"{where}: {_problems(e)}") from e


def load_record(path: Path) -> StepRecord:
    try:
        text = path.read_text()
    except OSError as e:
        raise RecordError(f"{path}: cannot read: {e}") from e
    return parse_record(text, str(path))
