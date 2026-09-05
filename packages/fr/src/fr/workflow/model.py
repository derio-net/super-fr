"""Workflow shape manifest schema + parser — spec §4.A, Phase 6.

A shape is a YAML manifest declaring the decomposition **unit**
(`run`/`phase`/`spec`, §4.E), the runner **capabilities** it `requires`
(§4.F — validated against the closed set in `fr.workflow.check`, NOT here;
see that module's docstring for why), and an ordered list of **steps**.

Mirrors `fr/types.py` conventions: pydantic `BaseModel`, `frozen=True`,
`extra="forbid"` — a closed-world schema where an unrecognised key is a bug
report, not silently dropped data.

`parse_manifest` is the single entry point every caller (resolution, `fr
workflow check`, later phases' `fr run`) goes through, and it raises exactly
one exception type — `WorkflowError` — for every kind of structural failure
(malformed YAML, non-mapping top level, an unsupported `schema:`, an unknown
top-level or step key, a wrong-typed field). Callers never need to catch
`yaml.YAMLError` or pydantic's `ValidationError` directly.
"""

from __future__ import annotations

from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

SUPPORTED_SCHEMA = 1
"""The only `schema:` value `parse_manifest` accepts today (spec §4.A: "an
unknown version is rejected with a message naming the supported one")."""


class WorkflowError(Exception):
    """Raised for any structurally invalid workflow manifest."""


class Step(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: Literal["cli", "agent"]
    run: str | None = None
    skill: str | None = None
    agent: str | None = None
    needs: tuple[str, ...] = ()
    emits: tuple[str, ...] = ()
    gate: Literal["operator"] | None = None
    tier: str | None = None
    # Legal for `unit: run` (spec example: `implement`'s `for_each: phase`);
    # an error for `unit: phase` (items are already per-phase) — that
    # unit-dependent conflict is a SEMANTIC check, enforced by
    # `fr.workflow.check.check_workflow`, not here (a Step alone doesn't
    # know its manifest's `unit`).
    for_each: Literal["phase"] | None = None


class WorkflowManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow: str
    # Wire key is `schema:` (spec §4.A). Named `schema_version` on the
    # Python side — `BaseModel.schema` is a deprecated pydantic v1 method
    # name and shadowing it emits a warning, the same reason `types.py`'s
    # `PlanMeta` uses `schema_version` for `NN.yaml`'s `schema_version:` key.
    schema_version: Literal[1] = Field(alias="schema")
    description: str = ""
    unit: Literal["run", "phase", "spec"]
    requires: tuple[str, ...] = ()
    steps: tuple[Step, ...] = ()


def parse_manifest(text: str) -> WorkflowManifest:
    """Parse + validate YAML `text` into a `WorkflowManifest`.

    Raises `WorkflowError` — never a raw `yaml.YAMLError` or pydantic
    `ValidationError` — for: invalid YAML, a non-mapping top level, a
    `schema:` other than `SUPPORTED_SCHEMA` (message names the supported
    version explicitly, ahead of generic pydantic validation so the message
    reads as "wrong version" rather than "wrong literal value"), or any
    other schema violation (unknown top-level/step key, missing required
    field, wrong type).
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise WorkflowError(f"invalid YAML: {e}") from e

    if not isinstance(raw, dict):
        raise WorkflowError("workflow manifest must be a YAML mapping at the top level")

    schema = raw.get("schema")
    if schema != SUPPORTED_SCHEMA:
        raise WorkflowError(
            f"unsupported workflow schema: {schema!r} (fr supports schema: {SUPPORTED_SCHEMA})"
        )

    try:
        return WorkflowManifest.model_validate(raw)
    except ValidationError as e:
        raise WorkflowError(f"invalid workflow manifest: {e}") from e
