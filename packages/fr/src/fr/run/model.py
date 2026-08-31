"""Run state schema, path resolution, and serialize/parse — spec §4.B, Phase 7.

A run's step cursor is git-tracked, a sibling of `journals/`:

    docs/superpowers/runs/<run-id>.yaml

It is the *control* log — which step, what it emitted, whether it
succeeded — while `fr.journal` stays the *content* log (decisions,
findings, discoveries). The two are deliberately separate (spec §4.B):
one is what happened, the other is where we are.

Design mirrors `fr.journal.model` / `fr.workflow.model`:
  - pydantic `BaseModel`, `frozen=True`, `extra="forbid"` — closed-world
    schema, an unrecognised key (or step `state`) is a bug report, not
    silently dropped/coerced data.
  - `parse_run_state` is the ONE entry point every caller goes through,
    raising exactly one exception type — `RunStateError` — for every kind
    of structural failure. Callers never catch `yaml.YAMLError` or
    pydantic's `ValidationError` directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

StepState = Literal["pending", "running", "done", "failed", "blocked"]
"""A step's lifecycle in run state — distinct from `fr.item_state.ItemState`
(the dispatch-queue vocabulary for a `WorkItem`); this is per-STEP progress
inside one run's cursor, not a tracker projection."""

RUNS_REL = Path("docs") / "superpowers" / "runs"
IMPLEMENTED_RUNS_REL = Path("docs") / "superpowers" / "implemented" / "runs"


class RunStateError(Exception):
    """Raised for any structurally invalid run-state file."""


class StepRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    state: StepState
    at: str | None = None
    gate: Literal["cleared"] | None = None
    """An operator gate the operator has answered (`fr run resolve`).

    Separate from `state` on purpose: a gate is an *authorization*, not a
    lifecycle position, and the two are independent — a `cli` step whose gate
    was cleared goes back to `pending` so `advance` still executes it and its
    exit code is still the verdict. Sticky for the life of the run (carried
    across `_complete_step`), so a retry after a failure does not silently
    re-block on a question already answered. Absent (`None`) on every step of
    every pre-existing run file, which is exactly "not answered"."""

    emitted: dict[str, str] | None = None
    exit: int | None = None
    stdout: str | None = None

    items: dict[str, str] | None = None
    """Per-item state for a step that fans out (`for_each: phase`).

    Spec §4.B's own illustration of run state carries it —
    `implement: {state: running, items: {".../phase/1": done, ...}}` — and
    `fr run adopt` (2026-08-30 §3.E) is the first writer: adopting a plan
    that is half-implemented has to record WHICH phases are done, or the
    cursor says `implement` and loses everything that makes the adoption
    worth having.

    Keys are the plan-relative tail of the §4.D identity grammar
    (`phase/<n>`), not a full work-item id: composing the full
    `<repo>/<spec>/<plan>/phase/<n>` is `fr_dispatch.work_item`'s job and
    `fr` may not import it (`tests/unit/test_import_direction.py`). The run
    file already records which plan it is about, in `emitted.plan`, so the
    tail identifies the item unambiguously within the run.

    Additive and optional, so every run file written without it still
    parses; no artifact-version bump follows, because the run kind is new in
    4.0.0 (`fr.artifacts.registry`, `current_version=1`) and no released fr
    has ever read a run file.
    """


class RunState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run: str
    workflow: str  # "<shape-name>@<schema-version>" e.g. "fr-goal@1"
    branch: str
    started: str  # ISO 8601; kept as a string for round-trip stability
    cursor: str  # the step id currently active (running/blocked) or next-up
    steps: dict[str, StepRecord]


def run_path(repo_root: Path, run_id: str) -> Path:
    """Active run-state path: ``docs/superpowers/runs/<run-id>.yaml``."""
    return repo_root / RUNS_REL / f"{run_id}.yaml"


def archived_run_path(repo_root: Path, run_id: str) -> Path:
    """Archived run-state path (mirrors ``implemented/plans`` / ``implemented/journals``)."""
    return repo_root / IMPLEMENTED_RUNS_REL / f"{run_id}.yaml"


def dump_run_state(state: RunState) -> str:
    """Canonical run-state YAML.

    `exclude_none` drops unset optional step fields (`at`/`emitted`/`exit`/
    `stdout`) rather than padding them as `null:` — a freshly started run
    (all steps `pending`) stays readable, and round-tripping the result
    through `parse_run_state` reproduces this exact text (unset fields
    default back to `None`).
    """
    data = state.model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)


def parse_run_state(text: str) -> RunState:
    """Parse + validate YAML `text` into a `RunState`.

    Raises `RunStateError` — never a raw `yaml.YAMLError` or pydantic
    `ValidationError` — for: invalid YAML, a non-mapping top level, or any
    schema violation (unknown top-level/step key, missing required field,
    an unrecognised step `state`).
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise RunStateError(f"invalid YAML: {e}") from e

    if not isinstance(raw, dict):
        raise RunStateError("run state must be a YAML mapping at the top level")

    try:
        return RunState.model_validate(raw)
    except ValidationError as e:
        raise RunStateError(f"invalid run state: {e}") from e


def save_run_state(repo_root: Path, state: RunState) -> Path:
    """Write `state` to its canonical path, creating parent dirs as needed."""
    path = run_path(repo_root, state.run)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_run_state(state))
    return path


def load_run_state(repo_root: Path, run_id: str) -> RunState:
    """Read + parse the run state for `run_id`. Raises `RunStateError` if absent."""
    path = run_path(repo_root, run_id)
    if not path.is_file():
        raise RunStateError(f"no run state at {path}")
    return parse_run_state(path.read_text())
