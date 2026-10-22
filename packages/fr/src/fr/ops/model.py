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

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

OpPhase = Literal["pre-merge", "post-merge"]
PHASES: tuple[OpPhase, ...] = ("pre-merge", "post-merge")

PROOF = "proof"
"""The reserved `check:` value: DONE only once a recorded `result: proof` says so (R7)."""

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


class LegacyOp(_OpFields):
    """A frank-shaped block (R2): `layer`/`app`/`plan`/`when`/`why_manual`/`status`
    beside any R1 field. `summary` defaults to `why_manual`, `phase` to
    `post-merge`, and `status: done` reads as DONE (legacy)."""

    summary: StrictStr | None = None
    phase: OpPhase | None = None
    layer: StrictStr | None = None
    app: StrictStr | None = None
    plan: StrictStr | None = None
    when: StrictStr | None = None
    why_manual: StrictStr | None = None
    status: StrictStr | None = None

    @model_validator(mode="after")
    def _has_a_summary(self) -> LegacyOp:
        if not (self.summary or self.why_manual):
            raise ValueError(f"{self.id}: a legacy op needs `summary` or `why_manual`")
        return self

    def to_op(self) -> tuple[Op, bool]:
        """`(Op, legacy_done)`: the R1 op this block stands for, and whether it
        was marked `status: done`."""
        data = {name: getattr(self, name) for name in _OpFields.model_fields}
        op = Op(
            **data,
            summary=self.summary or self.why_manual or "",
            phase=self.phase or "post-merge",
        )
        return op, self.status == "done"
