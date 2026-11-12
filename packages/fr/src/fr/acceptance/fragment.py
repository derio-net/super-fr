"""Acceptance fragments: one feature's rows and amendments (spec 2026-11-04 R16).

A fragment lives at `docs/acceptance/features/<spec-slug>.yaml` (§3.D). Where each
field comes from:

- `schema_version` — the `acceptance-fragment` artifact stamp (R19, `fr.artifacts.registry`).
- `feature` — the owning feature's spec slug, equal to the file stem (R16: each row is
  owned by the feature that created it); `legacy` for `legacy.yaml`, the fragment R19's
  migration sends rows without exactly one origin spec to.
- `repo` — `<org>/<repo>`, the identity the retired matrix carried as `org`/`repo`,
  agreed across fragments (spec journal decision `fragment-repo-identity`), so code refs
  keep their own-repo check without a remote.
- `rows` — the rows this feature created, each the matrix's one `Row` model
  (`fr.acceptance.model.Row`), never a copy of its fields.
- `amendments` — R16's five ops on rows another feature (or an earlier plan of this one)
  owns, each naming the row revision it is `base`d on (R17) and `why` it was made.

The effective matrix is never stored; `fr.acceptance.fold` derives it (R17).
"""

from __future__ import annotations

import functools
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from fr.acceptance.model import (
    LEVELS,
    AcceptanceError,
    Row,
    Status,
    Walk,
    check_issue_refs,
    check_status,
    check_verify,
)

FRAGMENTS_DIR = Path("docs/acceptance/features")
"""Where fragments live under `repo` (§3.D); the kind's locator is `<this>/*.yaml`."""

LEGACY_FEATURE = "legacy"
"""The fragment of rows with no single origin spec (R19)."""

AMENDMENT_OPS: tuple[str, ...] = ("reword", "set-status", "add-level", "drop-level", "retire")
"""R16's amendment ops, the one vocabulary."""

REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")

LevelName = Literal["unit", "api", "int", "ui"]
"""`fr.acceptance.model.LEVELS` as a type (pinned equal by the assert below)."""

assert set(LevelName.__args__) == set(LEVELS)  # type: ignore[attr-defined]


class _AmendmentBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    row: StrictStr
    base: StrictInt = Field(ge=0)
    """The row's revision (count of amendments applied to it) this was written against."""
    why: StrictStr = Field(min_length=1)


class Reword(_AmendmentBase):
    op: Literal["reword"]
    acceptance: StrictStr | None = None
    capability: StrictStr | None = None

    @model_validator(mode="after")
    def _changes_something(self) -> Reword:
        if self.acceptance is None and self.capability is None:
            raise ValueError("reword needs `acceptance` and/or `capability`")
        return self


class SetStatus(_AmendmentBase):
    op: Literal["set-status"]
    status: Status
    notes: StrictStr
    walk: Walk | None = None
    issues: tuple[StrictStr, ...] = ()
    verify: StrictStr | None = None
    """The row's verification strategy, replaced when given (plan journal
    `amend-set-status-verify-scenario`: `set-status --verify` on a merged row)."""
    scenario: StrictStr | None = None
    """The row's walk scenario, replaced when given (as `verify`)."""

    @field_validator("status", mode="before")
    @classmethod
    def _not_the_v4_status(cls, v: object) -> object:
        check_status(v)
        return v

    @field_validator("issues")
    @classmethod
    def _issues_are_qualified(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        check_issue_refs(v)
        return v

    @field_validator("verify")
    @classmethod
    def _verify_spelling(cls, v: str | None) -> str | None:
        check_verify(v)
        return v


class AddLevel(_AmendmentBase):
    op: Literal["add-level"]
    level: LevelName
    ref: StrictStr


class DropLevel(_AmendmentBase):
    op: Literal["drop-level"]
    level: LevelName
    ref: StrictStr


class Retire(_AmendmentBase):
    op: Literal["retire"]
    notes: StrictStr


Amendment = Annotated[Reword | SetStatus | AddLevel | DropLevel | Retire, Field(discriminator="op")]
"""One amendment, discriminated on `op` (each variant closed, so an op carrying
another op's field is refused)."""


class Fragment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: int = 1
    feature: StrictStr
    repo: StrictStr
    rows: tuple[Row, ...] = ()
    amendments: tuple[Amendment, ...] = ()

    @field_validator("rows", "amendments", mode="before")
    @classmethod
    def _none_is_empty(cls, v: object) -> object:
        return () if v is None else v

    @field_validator("repo")
    @classmethod
    def _repo_is_qualified(cls, v: str) -> str:
        if not REPO_RE.match(v):
            raise ValueError(f"repo {v!r} must be <org>/<repo>")
        return v


def fragment_slug_for_spec(path: str | Path) -> str:
    """A spec's fragment slug: its file stem minus a trailing `-design`.

    Identical for a live spec and its archived twin, so a fragment's name survives
    `fr archive`."""
    return PurePosixPath(str(path)).stem.removesuffix("-design")


def _loc(parts: tuple[object, ...]) -> str:
    out = ""
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out or "<root>"


def parse_fragment(text: str, *, source: str | Path) -> Fragment:
    """Parse + validate one fragment; every failure is an `AcceptanceError` naming
    *source* and the offending key.

    Identical text is parsed once per source (the `parse_matrix` pattern); every call
    returns its own deep copy, so no caller can change another's result. Errors are
    raised by the cached function and never cached."""
    return _parse_fragment_cached(text, str(source)).model_copy(deep=True)


@functools.lru_cache(maxsize=256)
def _parse_fragment_cached(text: str, source: str) -> Fragment:
    import yaml

    from fr import yamlio

    try:
        data = yamlio.safe_load(text)
    except yaml.YAMLError as e:
        raise AcceptanceError(f"{source}: not valid YAML: {e}") from e
    if not isinstance(data, dict):
        raise AcceptanceError(f"{source}: top level must be a mapping, got {type(data).__name__}")
    try:
        frag = Fragment.model_validate(data)
    except ValidationError as e:
        problems = "; ".join(f"`{_loc(tuple(err['loc']))}`: {err['msg']}" for err in e.errors())
        raise AcceptanceError(f"{source}: fragment schema: {problems}") from e
    stem = PurePosixPath(source).stem
    if frag.feature != stem:
        raise AcceptanceError(
            f"{source}: `feature: {frag.feature}` must match the file name (`feature: {stem}`)"
        )
    counts = Counter(r.id for r in frag.rows)
    dupes = sorted(i for i, n in counts.items() if n > 1)
    if dupes:
        raise AcceptanceError(f"{source}: duplicate row ids in `rows`: {dupes}")
    return frag
