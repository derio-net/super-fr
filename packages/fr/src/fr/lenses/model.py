"""Lens manifest and `.fr/lenses.yaml` models (spec 2026-11-12-review-lenses R1-R2).

Closed-world, like `fr.verification.model`: every structural failure is one
`LensError`, so callers never catch `yaml.YAMLError` or pydantic's
`ValidationError`. A lens id is safe as a journal header token and inside an
entry or finding id, hence `LENS_ID_RE`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from fr.artifacts.structure import _StrictLoader

LENS_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class LensError(ValueError):
    """Any structural failure of a lens manifest or of `.fr/lenses.yaml`."""


def _require_id(value: str) -> str:
    """The one id rule (R1/R2): lower-case letters, digits and hyphens, a letter first."""
    if not isinstance(value, str) or not LENS_ID_RE.match(value):
        raise ValueError(f"lens id {value!r} must match {LENS_ID_RE.pattern}")
    return value


def _non_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value


class Lens(BaseModel):
    """One effective lens. `source` says where it comes from (a path or a label)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    brief: str
    source: str = ""

    _id = field_validator("id")(_require_id)
    _title = field_validator("title")(_non_empty)
    _brief = field_validator("brief")(_non_empty)


class LensDef(BaseModel):
    """A repo-defined lens or a replacement: the id is the mapping key."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    brief: str

    _title = field_validator("title")(_non_empty)
    _brief = field_validator("brief")(_non_empty)


class PathRule(BaseModel):
    """Files matching any of `paths` require every lens in `lenses` (R6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    paths: tuple[str, ...]
    lenses: tuple[str, ...]

    @field_validator("paths", "lenses")
    @classmethod
    def _not_empty(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("paths")
    @classmethod
    def _globs(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for item in v:
            _non_empty(item)
        return v

    @field_validator("lenses")
    @classmethod
    def _ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for item in v:
            _require_id(item)
        return v


class LensConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    disable: tuple[str, ...] = ()
    lenses: dict[str, LensDef] = {}
    require: tuple[PathRule, ...] = ()

    @field_validator("disable")
    @classmethod
    def _disable_ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for item in v:
            _require_id(item)
        return v

    @field_validator("lenses")
    @classmethod
    def _lens_ids(cls, v: dict[str, LensDef]) -> dict[str, LensDef]:
        for key in v:
            _require_id(key)
        return v


def read_text(path: Path, source: str) -> str:
    """A lens file's text; an unreadable or undecodable file is a `LensError` too."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise LensError(f"{source}: cannot read: {e}") from e


def _load(text: str, source: str) -> Any:
    try:
        return yaml.load(text, Loader=_StrictLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as e:
        raise LensError(f"{source}: invalid YAML: {e}") from e


def _problems(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors())


def parse_lens(text: str, source: str = "<lens>") -> Lens:
    """Parse a shipped manifest `{lens, title, brief}` (spec R1)."""
    raw = _load(text, source)
    if not isinstance(raw, dict):
        raise LensError(f"{source}: lens manifest must be a YAML mapping")
    unknown = sorted(set(raw) - {"lens", "title", "brief"})
    if unknown:
        raise LensError(f"{source}: unknown key(s) {unknown}")
    try:
        return Lens.model_validate(
            {
                "id": raw.get("lens"),
                "title": raw.get("title"),
                "brief": raw.get("brief"),
                "source": source,
            }
        )
    except ValidationError as e:
        raise LensError(f"{source}: invalid lens manifest — {_problems(e)}") from e


def parse_config(text: str, source: str = ".fr/lenses.yaml") -> LensConfig:
    """Parse `.fr/lenses.yaml` (spec R2). An empty file is an empty config."""
    raw = _load(text, source)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise LensError(f"{source}: lens config must be a YAML mapping")
    try:
        return LensConfig.model_validate(raw)
    except ValidationError as e:
        raise LensError(f"{source}: invalid lens config — {_problems(e)}") from e
