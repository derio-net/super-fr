"""Verification strategy manifest schema + parser — spec
2026-10-06-verification-strategies §A (R1, R2).

A strategy is a YAML manifest naming one way to exercise a PR's behaviour:
when it runs (`pre-merge | post-merge`), who drives it (`agent | operator`),
and the argv templates that install the candidate and run one scenario.

Mirrors `fr.workflow.model`: pydantic, `frozen=True`, `extra="forbid"`, wire
key `schema:` aliased to `schema_version`, and one exception type —
`StrategyError` — for every structural failure, so callers never catch
`yaml.YAMLError` or pydantic's `ValidationError`.

Placeholders in an argv template are a CLOSED set (`PLACEHOLDERS`): an unknown
`{name}` is refused at parse time, not discovered when the walk runs it.
"""

from __future__ import annotations

import re
import shlex
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

SUPPORTED_SCHEMA = 1

PLACEHOLDERS = frozenset(
    {"repo", "worktree", "prefix", "bin", "fixture", "client", "scenario", "source"}
)
"""What an `install` / `scenario` template may interpolate (spec §A)."""

RESERVED = "none"
"""Not a strategy: a row's `verify: none` / a spec line's `none` means "no
strategy applies". No manifest may take the name."""

_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")


class StrategyError(ValueError):
    """Any structural failure of a strategy manifest."""


def _placeholders(argv: tuple[str, ...]) -> set[str]:
    return {m for arg in argv for m in _PLACEHOLDER.findall(arg)}


def _argv(value: Any) -> tuple[str, ...] | None:
    """A template is a string (shell-split) or a list of strings, or null."""
    if value is None:
        return None
    if isinstance(value, str):
        return tuple(shlex.split(value))
    if isinstance(value, list | tuple) and all(isinstance(v, str) for v in value):
        return tuple(value)
    raise ValueError("must be a string, a list of strings, or null")


class StrategyManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    verification: str
    # Wire key `schema:`; see `fr.workflow.model.WorkflowManifest` for why the
    # Python name differs.
    schema_version: Literal[1] = Field(alias="schema")
    description: str = ""
    when: Literal["pre-merge", "post-merge"]
    driver: Literal["agent", "operator"]
    install: tuple[str, ...] | None = None
    scenario: tuple[str, ...] | None = None
    source: Literal["worktree", "prerelease", "none"] = "none"
    notes: str = ""

    def used_placeholders(self) -> set[str]:
        """Every `{name}` the install and scenario templates interpolate."""
        return _placeholders((self.install or ()) + (self.scenario or ()))

    @field_validator("install", "scenario", mode="before")
    @classmethod
    def _split(cls, v: Any) -> tuple[str, ...] | None:
        return _argv(v)

    @field_validator("install", "scenario")
    @classmethod
    def _known_placeholders(cls, v: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if v is not None:
            unknown = _placeholders(v) - PLACEHOLDERS
            if unknown:
                raise ValueError(
                    f"unknown placeholder(s) {sorted(unknown)} (known: {sorted(PLACEHOLDERS)})"
                )
        return v

    @field_validator("verification")
    @classmethod
    def _not_reserved(cls, v: str) -> str:
        if v == RESERVED:
            raise ValueError(f"{RESERVED!r} is reserved and cannot name a strategy")
        return v


def parse_strategy(text: str, source: str) -> StrategyManifest:
    """Parse + validate YAML `text` into a `StrategyManifest`.

    `source` (a path or label) prefixes every error, so a failure names the
    file and the field.
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise StrategyError(f"{source}: invalid YAML: {e}") from e

    if not isinstance(raw, dict):
        raise StrategyError(f"{source}: strategy manifest must be a YAML mapping")

    schema = raw.get("schema")
    if schema != SUPPORTED_SCHEMA:
        raise StrategyError(
            f"{source}: unsupported schema: {schema!r} (fr supports schema: {SUPPORTED_SCHEMA})"
        )

    try:
        return StrategyManifest.model_validate(raw)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        raise StrategyError(f"{source}: invalid strategy manifest — {problems}") from e
