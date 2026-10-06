"""The acceptance matrix's shape BEFORE version 4 — frozen.

Matrix versions 1 through 3 only ever ADDED an optional, defaulted field
(`verify`, then `visual`), so one closed-world model reads all three. The
3 -> 4 migration (spec `2026-10-06-verification-strategies-design.md` §B)
rewrites `verify: post-merge` to `verify: live`, and the live `Row` no longer
accepts the old spelling. Validated against the live model, a v2 matrix
carrying `verify: post-merge` would be refused at its first hop — so EVERY
matrix hop reads through `MatrixV3`, and the live `Matrix` is v4 only. The
standing rule is `.claude/rules/artifact-versioning.md`.

**It must never be edited again.** A v3 matrix on an unmerged branch is
already written; editing the reader changes what fr believes those bytes
mean. A later removal freezes a `…V4` beside it. `FROZEN_CLASS_SHA256` pins
each class's source (`tests/unit/test_acceptance_legacy.py`).

Two deliberate divergences from a literal copy of the v3 `fr.acceptance.model`:

1. **The vocabularies are INLINED** (`StatusV3`, `LEVELS_V3`, the `verify`
   literal, `VisualV3`) rather than imported: a frozen reader that followed a
   live vocabulary would stop reading v3 the day that vocabulary moved.
2. **`VisualV3` does not check its state and interaction names.** The live
   `Visual` does, through a live rule. This reader's job is to READ what fr
   wrote; the live model re-checks on the way out.
"""

from __future__ import annotations

from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError, field_validator

LEVELS_V3: tuple[str, ...] = ("unit", "api", "int", "ui")
StatusV3 = Literal["ci", "scheduled", "skipped", "not-implemented", "failing"]


class MatrixV3Error(Exception):
    """A file that does not read as an acceptance matrix of version 1 to 3."""


class VisualV3(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    states: tuple[StrictStr, ...] = ()
    interactions: tuple[StrictStr, ...] = ()


class RowV3(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: StrictStr
    capability: StrictStr
    acceptance: StrictStr
    origin: tuple[StrictStr, ...] = ()
    levels: dict[str, tuple[StrictStr, ...]] = Field(default={}, validate_default=True)
    status: StatusV3
    notes: StrictStr = ""
    verify: Literal["post-merge"] | None = None
    visual: VisualV3 | None = None

    @field_validator("levels")
    @classmethod
    def _known_keys_only(cls, v: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
        unknown = set(v) - set(LEVELS_V3)
        if unknown:
            raise ValueError(f"unknown level keys {sorted(unknown)} (allowed: {list(LEVELS_V3)})")
        return {lv: v.get(lv, ()) for lv in LEVELS_V3}


class MatrixV3(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal[1, 2, 3] = 3
    org: StrictStr | None = None
    repo: StrictStr | None = None
    rows: tuple[RowV3, ...] = ()

    @field_validator("rows", mode="before")
    @classmethod
    def _none_is_empty(cls, v: object) -> object:
        return () if v is None else v


FROZEN_CLASS_SHA256: dict[str, str] = {
    "VisualV3": "ff854fb82cfc7ff5afdf906df9ac308e82d81bb68b12555852557317d9acc726",
    "RowV3": "a555d6072c2dcc1d90f7ddf368bed943e5eabeb6050cd9afdc4a7dddedd9fe05",
    "MatrixV3": "f9cfc0d94ac4683a446eac5fbc015eb8a5ec913d34482a8cc92afadc130724ff",
}
"""SHA-256 of each frozen class's own source, as `inspect.getsource` returns it.
Recorded, not computed at import: a hash the module derives from itself always
matches itself and proves nothing."""


def parse_matrix_v3(text: str) -> MatrixV3:
    """Parse + validate `text` as a matrix of version 1 to 3, or raise
    `MatrixV3Error` naming why — never a raw YAML or pydantic error."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise MatrixV3Error(f"not valid YAML: {e}") from e
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise MatrixV3Error(f"top level must be a mapping, got {type(data).__name__}")
    return matrix_v3_from_data(data)


def matrix_v3_from_data(data: dict[str, Any]) -> MatrixV3:
    """Validate an already-loaded mapping as a matrix of version 1 to 3 (an
    unstamped one is version 1), or raise `MatrixV3Error`. Duplicate row ids
    are refused, as the live reader refuses them."""
    try:
        matrix = MatrixV3.model_validate({"schema_version": 1, **data})
    except ValidationError as e:
        raise MatrixV3Error(str(e)) from e
    ids = [r.id for r in matrix.rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise MatrixV3Error(f"duplicate row ids: {dupes}")
    return matrix
