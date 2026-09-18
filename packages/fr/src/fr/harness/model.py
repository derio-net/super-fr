"""Harness-parity schema and parser — 2026-09-18 harness-parity-matrix spec
§3.A, Phase 1.

Design mirrors `fr.run.model` / `fr.workflow.model`: pydantic `BaseModel`,
`frozen=True`, `extra="forbid"` — closed-world schema, an unrecognised key
(or state) is a bug report, not silently dropped/coerced data.
`parse_matrix` is the ONE entry point every caller goes through, raising
exactly one exception type — `HarnessError`, naming the offending surface
id and (where relevant) the harness key — for every kind of structural
failure. Callers never catch pydantic's `ValidationError` directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

HARNESSES: tuple[str, ...] = ("claude-code", "opencode", "hermes", "codex", "copilot-cli")
"""The closed, ordered harness set (spec §3.A). Closed for the same reason
`fr.capabilities.CAPABILITIES` is closed — a typo in a row becomes a
validation error rather than a silently-missing column. `codex` and
`copilot-cli` are present from day one, every row `unsupported`, so adding
support later is a state change on existing rows, not a schema migration."""

STATES: frozenset[str] = frozenset({"enforced", "partial", "advisory", "absent", "unsupported"})
"""The closed, five-state vocabulary (spec §3.A table). `partial` is the
fifth state #436 did not name; `scope_note` is required alongside it and
alongside `advisory` — see `Surface._check_harnesses` below."""

_StateLiteral = Literal["enforced", "partial", "advisory", "absent", "unsupported"]
_KindLiteral = Literal["hook", "interaction"]

_NOTE_REQUIRED_STATES = ("partial", "advisory")


class HarnessError(ValueError):
    """Raised for any structurally invalid `parity.yaml` / Matrix payload.

    Every message names the offending surface id, and — when the failure is
    about one harness's state rather than the surface as a whole — the
    harness key too (P1.T4 refactor)."""


class HarnessState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    state: _StateLiteral
    scope_note: str | None = None
    """Required when `state` is `partial` or `advisory` (enforced by
    `Surface._check_harnesses`, not here — the check needs the harness key
    to name in the error, which a lone `HarnessState` doesn't carry)."""


class Surface(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: _KindLiteral
    script: str | None = None
    """Required iff `kind == "hook"` — the shipped script this row declares
    states for (must exist under `plugins/super-fr/hooks/`, checked by
    Phase 2's derived check, not here)."""
    summary: str
    harnesses: dict[str, HarnessState]

    @model_validator(mode="after")
    def _check_surface(self) -> Surface:
        """Every structural rule a single `Surface` must satisfy, folded into
        one validator (P1.T4 refactor) rather than one `model_validator` per
        rule: harness-key closure, `scope_note` presence, and `script`
        required iff `kind == "hook"`. `parse_matrix` wraps whatever this
        raises with the surface id; this method names the harness key too,
        wherever the failure is about one harness rather than the surface as
        a whole."""
        keys = set(self.harnesses)
        expected = set(HARNESSES)
        missing = sorted(expected - keys)
        extra = sorted(keys - expected)
        if missing:
            raise ValueError(f"missing harness(es) {missing}")
        if extra:
            raise ValueError(f"unknown harness key(s) {extra}")
        for harness, hstate in self.harnesses.items():
            if hstate.state in _NOTE_REQUIRED_STATES and not hstate.scope_note:
                raise ValueError(
                    f"harness {harness!r} state {hstate.state!r} requires a scope_note"
                )

        if self.kind == "hook" and not self.script:
            raise ValueError("kind 'hook' requires 'script'")
        if self.kind == "interaction" and self.script is not None:
            raise ValueError("kind 'interaction' must not set 'script'")
        return self


class Matrix(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Wire key is `schema:` (matches `parity.yaml`'s top level). Named
    # `schema_version` on the Python side — `BaseModel.schema` is a
    # deprecated pydantic v1 method name and shadowing it emits a warning,
    # the same reason `fr.workflow.model.WorkflowManifest` and
    # `fr.types.PlanMeta` do the same rename.
    schema_version: Literal[1] = Field(alias="schema")
    surfaces: tuple[Surface, ...]


def _first_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return str(exc)
    msg = errors[0]["msg"]
    prefix = "Value error, "
    return msg[len(prefix) :] if msg.startswith(prefix) else msg


def _load_mapping(source: str | Mapping[str, object]) -> Mapping[str, object]:
    if isinstance(source, str):
        try:
            data = yaml.safe_load(source)
        except yaml.YAMLError as exc:
            raise HarnessError(f"parity data is not valid YAML: {exc}") from exc
    else:
        data = source
    if not isinstance(data, Mapping):
        raise HarnessError("parity data must be a mapping with a 'surfaces' key")
    return data


def parse_matrix(source: str | Mapping[str, object]) -> Matrix:
    """Parse `source` (YAML text or an already-loaded mapping) into a `Matrix`.

    The ONE entry point — raises `HarnessError` for every failure, always
    naming the offending surface id (looked up from the raw payload BEFORE
    validation, so even a pydantic-native failure like an unknown `state`
    literal, raised while parsing a nested `HarnessState`, still gets the
    id it belongs to)."""
    data = _load_mapping(source)
    raw_surfaces = data.get("surfaces")
    if not isinstance(raw_surfaces, list):
        raise HarnessError("parity data must have a 'surfaces' list")

    surfaces: list[Surface] = []
    for raw in raw_surfaces:
        surface_id = raw.get("id", "<unknown>") if isinstance(raw, Mapping) else "<unknown>"
        try:
            surfaces.append(Surface.model_validate(raw))
        except ValidationError as exc:
            raise HarnessError(f"surface {surface_id!r}: {_first_message(exc)}") from exc

    try:
        return Matrix.model_validate({**data, "surfaces": surfaces})
    except ValidationError as exc:
        raise HarnessError(_first_message(exc)) from exc
