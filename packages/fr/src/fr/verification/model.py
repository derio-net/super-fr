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
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SUPPORTED_SCHEMAS = (1, 2)
"""Schema 2 adds `gate:` (spec 2026-10-14 exit-gates R3); schema 1 stays valid."""

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
    schema_version: Literal[1, 2] = Field(alias="schema")
    description: str = ""
    when: Literal["pre-merge", "post-merge"]
    driver: Literal["agent", "operator"]
    install: tuple[str, ...] | None = None
    scenario: tuple[str, ...] | None = None
    source: Literal["worktree", "prerelease", "none"] = "none"
    notes: str = ""
    # The strategy's default gate (spec 2026-10-14 R3) — schema 2 only.
    gate: Literal["none", "tester", "devops"] = "none"

    @model_validator(mode="after")
    def _gate_needs_schema_2(self) -> StrategyManifest:
        # The ONE schema rule: `gate:` exists only from schema 2 on.
        if "gate" in self.model_fields_set and self.schema_version < 2:
            raise ValueError("`gate:` needs `schema: 2` (schema 1 manifests carry no gate)")
        return self

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
    if schema not in SUPPORTED_SCHEMAS:
        raise StrategyError(
            f"{source}: unsupported schema: {schema!r} "
            f"(fr supports schema: {' or '.join(map(str, SUPPORTED_SCHEMAS))})"
        )

    try:
        return StrategyManifest.model_validate(raw)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        raise StrategyError(f"{source}: invalid strategy manifest — {problems}") from e
