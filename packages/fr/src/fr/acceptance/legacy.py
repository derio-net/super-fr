"""The acceptance matrix's shapes BEFORE version 5 — frozen.

`MatrixV3` reads versions 1 to 3; `MatrixV4` (at the bottom) reads versions 1
to 4, frozen when 4 -> 5 split the status `skipped` (spec
`2026-10-11-debt-engine-design.md` §D).

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


# --- version 4 ----------------------------------------------------------------
#
# The 4 -> 5 migration (spec `2026-10-11-debt-engine-design.md` §D, R6) REMOVES
# the status `skipped`, splitting it into `unwired` / `walk-owed` / `walked` /
# `manual`. The live `Row` refuses `skipped` by name, so the live model is no
# longer a superset of the bodies the older hops read: EVERY matrix hop reads
# through `MatrixV4` from 4 -> 5 on, and the live `Matrix` is v5 only.
#
# `MatrixV4` is a closed SUPERSET of versions 1 to 4: `verify` takes any string
# (the v1-v3 `post-merge` and a v4 strategy name alike) and a row may carry the
# v4 fields. "Is this body v4?" is therefore `is_v4_body`: it reads as
# `MatrixV4` and no row still says `post-merge`. Frozen the same way as
# `MatrixV3` and pinned by `FROZEN_V4_CLASS_SHA256`
# (`tests/unit/test_migration_matrix_status_split.py`). It must never be edited
# again; a later removal freezes a `…V5` beside it.

StatusV4 = Literal["ci", "scheduled", "skipped", "not-implemented", "failing"]
WalkOutcomeV4 = Literal["pass", "fail"]


class MatrixV4Error(Exception):
    """A file that does not read as an acceptance matrix of version 1 to 4."""


class VisualV4(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    states: tuple[StrictStr, ...] = ()
    interactions: tuple[StrictStr, ...] = ()


class WalkV4(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    strategy: StrictStr
    harness: StrictStr
    model: StrictStr
    outcome: WalkOutcomeV4
    at: StrictStr
    evidence: StrictStr


class RowV4(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: StrictStr
    capability: StrictStr
    acceptance: StrictStr
    origin: tuple[StrictStr, ...] = ()
    levels: dict[str, tuple[StrictStr, ...]] = Field(default={}, validate_default=True)
    status: StatusV4
    notes: StrictStr = ""
    verify: StrictStr | None = None
    visual: VisualV4 | None = None
    scenario: StrictStr | None = None
    issues: tuple[StrictStr, ...] = ()
    harnesses: tuple[StrictStr, ...] = ()
    walks: tuple[WalkV4, ...] = ()

    @field_validator("levels")
    @classmethod
    def _known_keys_only(cls, v: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
        unknown = set(v) - set(LEVELS_V3)
        if unknown:
            raise ValueError(f"unknown level keys {sorted(unknown)} (allowed: {list(LEVELS_V3)})")
        return {lv: v.get(lv, ()) for lv in LEVELS_V3}


class MatrixV4(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal[1, 2, 3, 4] = 4
    org: StrictStr | None = None
    repo: StrictStr | None = None
    rows: tuple[RowV4, ...] = ()

    @field_validator("rows", mode="before")
    @classmethod
    def _none_is_empty(cls, v: object) -> object:
        return () if v is None else v


FROZEN_V4_CLASS_SHA256: dict[str, str] = {
    "VisualV4": "1bd94debfb50f0ffac913a5d574a6b60ab3c3f43afc5881c9968b97acf0e950a",
    "WalkV4": "6609426cf6c5d457b058d29e46eb74de56472c8494bb9bcda3b3db02f4b7f72d",
    "RowV4": "4a3a4e212c4a31069927b49264003a3b14c5b24c7609db369521d375b08148de",
    "MatrixV4": "80c72f844ba10aa95638b991baeff8f6726cb68e401d061ea43802152d5d7a24",
}
"""As `FROZEN_CLASS_SHA256`, for the classes version 4 froze."""


def parse_matrix_v4(text: str) -> MatrixV4:
    """Parse + validate `text` as a matrix of version 1 to 4, or raise
    `MatrixV4Error` naming why — never a raw YAML or pydantic error."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise MatrixV4Error(f"not valid YAML: {e}") from e
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise MatrixV4Error(f"top level must be a mapping, got {type(data).__name__}")
    try:
        matrix = MatrixV4.model_validate({"schema_version": 1, **data})
    except ValidationError as e:
        raise MatrixV4Error(str(e)) from e
    ids = [r.id for r in matrix.rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise MatrixV4Error(f"duplicate row ids: {dupes}")
    return matrix


def is_v4_body(text: str) -> bool:
    """Whether `text` already reads as a version-4 body: a `MatrixV4` with no
    row still carrying the v3 `verify: post-merge`."""
    try:
        matrix = parse_matrix_v4(text)
    except MatrixV4Error:
        return False
    return not any(r.verify == "post-merge" for r in matrix.rows)
