"""The op model (spec 2026-10-22-fr-ops R1, §A) and its legacy reader (R2).

`Op` is closed-world: an unknown key is refused by name, and the loader adds
the file and line. `LegacyOp` reads frank's `# manual-operation` blocks and the
repo runbook: frank's own keys plus every R1 key, with R2's defaults applied by
`to_op()`. Both share one field set (`_OpFields`), so the two readers cannot
drift on what an R1 field means.

Probes (`check`, `na_if`, `ready`, `escalate`) and `apply`/`undo` are shell
strings; the engine runs them, this module only holds them.
"""

from __future__ import annotations

import re
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

OpPhase = Literal["pre-merge", "post-merge"]
PHASES: tuple[OpPhase, ...] = ("pre-merge", "post-merge")

PROOF = "proof"
"""The reserved `check:` value: DONE only once a recorded `result: proof` says so (R7)."""

TODO_CHECK = "TODO"
"""The stub sentinel `check:` (spec 2026-11-01-ops-gate-probes R11): an op `fr ops stub`
wrote and nobody has given a real probe yet. `fr plan self-review` refuses it (R7)."""

OP_ID_PATTERN = r"^[A-Za-z0-9][\w.-]*$"


class UndoNone(BaseModel):
    """`undo: {none: <reason>}` — an op that cannot be undone says why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    none: StrictStr = Field(min_length=1)


class _OpFields(BaseModel):
    """R1's optional fields, shared by `Op` and `LegacyOp`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: StrictStr = Field(pattern=OP_ID_PATTERN)
    needs: tuple[StrictStr, ...] = ()
    check: StrictStr | None = None
    na_if: StrictStr | None = None
    apply: StrictStr | None = None
    undo: StrictStr | UndoNone | None = None
    mutating: bool = False
    interactive: bool = False
    side_effects: tuple[StrictStr, ...] = ()
    identities: tuple[StrictStr, ...] = ()
    ready: StrictStr | None = None
    disables: StrictStr | None = None
    escalate: StrictStr | None = None
    vacuous_if: StrictStr | None = None
    commands: tuple[StrictStr, ...] | StrictStr | None = None
    verify: tuple[StrictStr, ...] | StrictStr | None = None


R1_KEYS: frozenset[str] = frozenset(_OpFields.model_fields) | {"summary", "phase"}
"""Every key an `Op` accepts."""


class Op(_OpFields):
    """One manual operation (R1)."""

    summary: StrictStr = Field(min_length=1)
    phase: OpPhase

    @property
    def is_proof(self) -> bool:
        return self.check == PROOF


LegacyState = Literal["done", "n/a"]
"""What a legacy `status:` closes an op as (R2): DONE (legacy) or N/A (legacy)."""

_FRANK_PROSE = ("layer", "app", "plan", "when", "why_manual", "status", "summary")
_DONE_RE = re.compile(r"^done\b", re.IGNORECASE)
_NA_STATUSES = frozenset({"decommissioned", "n/a"})


def _as_prose(value: object) -> str:
    """A non-string YAML value as one line of prose (a mapping in flow style)."""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return yaml.safe_dump(value, default_flow_style=True, sort_keys=False).strip()
    return str(value)


class LegacyOp(_OpFields):
    """A frank-shaped block (R2): `layer`/`app`/`plan`/`when`/`why_manual`/`status`
    beside any R1 field. `summary` defaults to `why_manual`, `phase` to
    `post-merge`; a `done`/`done …` status reads as DONE (legacy) and
    `decommissioned`/`n/a` as N/A (legacy).

    Tolerant where `Op` is strict, because the legacy carrier is a convention fr
    does not own: a key that is neither R1's nor frank's is kept as prose
    (`prose_keys`, which the loader warns about), non-string `commands`/`verify`
    items and frank's scalar fields are kept as prose. The R1 fields fr acts on
    (`check`, `apply`, …) stay typed."""

    model_config = ConfigDict(frozen=True, extra="allow")

    summary: StrictStr | None = None
    phase: OpPhase | None = None
    layer: StrictStr | None = None
    app: StrictStr | None = None
    plan: StrictStr | None = None
    when: StrictStr | None = None
    why_manual: StrictStr | None = None
    status: StrictStr | None = None

    @field_validator(*_FRANK_PROSE, mode="before")
    @classmethod
    def _scalar_prose(cls, value: object) -> object:
        return value if value is None else _as_prose(value)

    @field_validator("commands", "verify", mode="before")
    @classmethod
    def _items_prose(cls, value: object) -> object:
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, list):
            return [_as_prose(item) for item in value]
        return _as_prose(value)

    @model_validator(mode="after")
    def _has_a_summary(self) -> LegacyOp:
        if not (self.summary or self.why_manual):
            raise ValueError(f"{self.id}: a legacy op needs `summary` or `why_manual`")
        return self

    @property
    def prose_keys(self) -> tuple[str, ...]:
        """Keys neither R1 nor frank defines, kept as prose."""
        return tuple(sorted(self.model_extra or {}))

    @property
    def legacy_state(self) -> LegacyState | None:
        status = (self.status or "").strip()
        if _DONE_RE.match(status):
            return "done"
        return "n/a" if status.lower() in _NA_STATUSES else None

    def to_op(self) -> tuple[Op, LegacyState | None]:
        """`(Op, legacy state)`: the R1 op this block stands for, and what its
        `status:` closes it as (`None`: not closed)."""
        data = {name: getattr(self, name) for name in _OpFields.model_fields}
        op = Op(
            **data,
            summary=self.summary or self.why_manual or "",
            phase=self.phase or "post-merge",
        )
        return op, self.legacy_state


class OpsFile(BaseModel):
    """`ops.yaml` in a plan folder: the `ops` artifact kind (R17)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    ops: tuple[Op, ...] = ()
    none: StrictStr | None = Field(default=None, min_length=1)
    """`none: <reason>`: no ops on purpose (spec 2026-11-01-ops-gate-probes R4)."""

    @model_validator(mode="after")
    def _none_or_ops(self) -> OpsFile:
        if self.none is not None and self.ops:
            raise ValueError("`none:` says the plan has no ops, but `ops:` declares some")
        return self
