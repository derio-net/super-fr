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

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

StepState = Literal["pending", "running", "done", "failed", "blocked"]
"""A step's lifecycle in run state — distinct from `fr.item_state.ItemState`
(the dispatch-queue vocabulary for a `WorkItem`); this is per-STEP progress
inside one run's cursor, not a tracker projection."""

AnsweredBy = Literal["operator", "agent"]
"""Who cleared an operator gate (spec `2026-09-18-harness-parity-matrix` §3.D.2).

Two values, not three, and neither is provable: this records a *claim*. No
mechanism here can show that a human answered (that spec's §2 non-goals say so
outright), which is why `fr run resolve --answered-by` defaults to `agent` —
the weaker claim is what an unmodified caller records, so nothing is silently
upgraded to "a human answered"."""

RUNS_REL = Path("docs") / "superpowers" / "runs"
IMPLEMENTED_RUNS_REL = Path("docs") / "superpowers" / "implemented" / "runs"


class RunStateError(Exception):
    """Raised for any structurally invalid run-state file."""


DispatchOutcome = Literal["done", "failed", "abandoned"]
"""How a dispatch ended, reported at `fr run resolve`/`claim --abandoned` time
(spec `2026-09-20-dispatch-holder-identity-design.md` §4.A).

`abandoned` is not a lifecycle state `StepState` also has — it describes the
DISPATCH, not the step: §1.C found there is no way to retire a non-returning
agent from the outside, so `abandoned` is the honest terminal state for "this
dispatch is never coming back", recorded while the step itself goes back to
`running` for a fresh attempt."""


class DispatchRecord(BaseModel):
    """One attempt to hold a unit — a phase member or a flat `kind: agent`
    step — spanning from `advance`'s own dispatch act to `resolve`'s close.

    Spec §3 draws the line this model exists to keep visible, and every field
    below sits on one side of it:

    - **fr knows it** — `dispatched`, fr's own timestamp of the act of
      writing the brief. Nothing here can be wrong about this one, because fr
      performed it.
    - **fr derives it** — `agent_type` and `model`, computed from the step
      definition and `fr models resolve` at the moment `advance` opens the
      record.
    - **reported, unverifiable** — `agent`, `harness`, `returned`, `outcome`.
      The orchestrator claims what it dispatched and how it ended, the same
      documented terms `AnsweredBy` above already uses for a gate: this is
      visibility, not enforcement. An unreported `agent` is recorded as
      absent, never guessed — the same reason `--answered-by` defaults to the
      weaker claim rather than silently upgrading one nobody made.

    A unit's list of these (`StepRecord.dispatch`, §4.B) is kept oldest
    first and never overwritten: a failed unit that is retried, or
    `--redispatch`ed over a lost agent, keeps every prior attempt, which is
    the forensic trail #503 asks for."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dispatched: str
    """ISO 8601 — fr's own act of writing the brief (`advance`). Never absent
    on a record that exists: this is the one field fr always knows."""

    agent: str | None = None
    """The harness-reported agent/task id (`fr run claim --agent`). Absent
    until claimed — an unclaimed dispatch is visible debt (`fr run check`),
    not a guess at who is holding it."""

    agent_type: str | None = None
    """E.g. `super-fr:fr-phase-executor` — derived from the step's `agent:`
    at dispatch time. `None` for an orchestrator-run `kind: agent` step
    (`agent: null` in the manifest, spec §4.B.1): that is not a missing
    value, it is `held by the orchestrator`."""

    harness: str | None = None
    """The harness the orchestrator reported dispatching on, one of
    `fr.harness.model.HARNESSES`. Detected via
    `fr.harness.detect.detect_harness` when `--harness` is not given — a
    guess about the environment, not a claim about the agent — and left
    absent rather than guessed when detection itself returns `None`. There is
    no `"unknown"` member: inventing a fifth harness name to mean "we don't
    know" would put a value here no parity row can ever match."""

    model: str | None = None
    """The resolved tier binding actually dispatched (`fr models resolve`),
    derived at `advance` time like `agent_type`."""

    returned: str | None = None
    """ISO 8601, set at `fr run resolve` (or `claim --abandoned`) — the other
    half of the dispatched/returned pair spec §1.D says `StepRecord.at` alone
    cannot give."""

    outcome: DispatchOutcome | None = None
    """Set alongside `returned`. `None` exactly when `returned` is `None` —
    the record is still open, and at most one such record may exist per unit
    (`advance` refuses to open a second, spec §4.C)."""

    @field_validator("harness")
    @classmethod
    def _check_harness(cls, value: str | None) -> str | None:
        """Validated against `fr.harness.model.HARNESSES`, imported rather
        than re-listed — the same discipline `fr.types.phase_tiers` documents
        for a closed vocabulary owned by another module."""
        from fr.harness.model import HARNESSES

        if value is not None and value not in HARNESSES:
            raise ValueError(f"harness {value!r} must be one of {HARNESSES}")
        return value

    @model_validator(mode="after")
    def _returned_and_outcome_are_one_fact(self) -> DispatchRecord:
        """`outcome` is set exactly when `returned` is.

        Enforced rather than merely documented, because "is this dispatch
        open?" is the question every reader asks — `fr run status` to name the
        holder, `fr run advance` to refuse a second one, `fr run check` to
        count the debt. A half-closed record answers it differently depending
        on which half a reader happens to look at: `returned` without
        `outcome` reads as still-held while carrying a return timestamp, and
        `outcome` without `returned` reads as held forever by an agent that
        has already finished. Both are the double-dispatch hazard wearing a
        disguise, so the model refuses them instead of leaving one invariant
        to be re-derived at every call site."""
        if (self.returned is None) != (self.outcome is None):
            raise ValueError(
                "`returned` and `outcome` are set together or not at all "
                f"(returned={self.returned!r}, outcome={self.outcome!r}); a record with "
                "exactly one of them is neither open nor closed"
            )
        return self


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

    answered_by: AnsweredBy | None = None
    """Who answered that gate — set only when a gate is CLEARED.

    The same shape as `gate` above and for the same reason: it is an
    authorization, not a lifecycle position. So it is `None` on every step
    that has no gate, on a gate that was *declined* (a declined gate was not
    cleared), and on every step of every run file written before this field
    existed — which is exactly "no gate was cleared here".

    It is the only durable trace of the failure this field was added for
    (spec §1): a `gate: operator` step self-resolving on a harness with no
    operator-question tool. Carried across `_complete_step` like `gate`, or
    the record would go quiet the moment a cleared `cli` gate's step actually
    ran — and `fr run check` reads it, so quiet means unreported."""

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
    (`phase/<n>` for a flat fan-out, `phase/<n>/<member-id>` for a grouped
    `for_each` with member steps), not a full work-item id: composing the
    full `<repo>/<spec>/<plan>/phase/<n>` is `fr_dispatch.work_item`'s job
    and `fr` may not import it (`tests/unit/test_import_direction.py`). The
    run file already records which plan it is about, in `emitted.plan`, so
    the tail identifies the item unambiguously within the run.

    Additive and optional, so every run file written without it still
    parses; no artifact-version bump follows, because the run kind is new in
    4.0.0 (`fr.artifacts.registry`, `current_version=1`) and no released fr
    has ever read a run file.
    """

    members: list[str] | None = None
    """Member-step ids of a grouped `for_each` step, recorded at build.

    Lets `_check_step_drift` tell a member added/removed after `fr run
    start` from the ordinary case — without it a shape edit inside the nest
    would advance silently against a step list the cursor was never computed
    for. Absent (`None`) on grouped steps of pre-existing run files, where
    the member check is skipped rather than guessed. Additive and optional,
    same versioning argument as `items` above.
    """

    dispatch: dict[str, list[DispatchRecord]] | None = None
    """Every attempt to hold a unit of this step, oldest first (spec §4.B).

    Keyed by the unit key — a grouped `for_each` member's key matches its
    `items` entry (`phase/<n>/<member-id>`); a flat `kind: agent` step has no
    `items` entry at all, so it is keyed `step/<step-id>` instead. The prefix
    is not cosmetic: a repo-authored step id may itself contain a `/`
    (`fr.workflow.check.check_workflow` does not forbid it), so without a
    namespace the two key spaces are not provably disjoint.

    The OPEN dispatch for a key, wherever this docstring or the CLI says it,
    means the last element of that list when its `returned is None` — there
    is at most one, because `advance` refuses to open a second (spec §4.C).

    This is a **shape change** (`current_version=3` in
    `fr.artifacts.registry`, spec §4.D): `StepRecord`/`RunState` are
    `extra="forbid"`, so a released fr predating this field raises on a
    cursor that carries it. Additive and optional regardless — absent means
    exactly "no dispatch recorded for this step", true of every run file
    written before this field existed.
    """


MEASURED_TOKEN_FIELDS: tuple[str, ...] = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)
"""The four V2 figures `fr.run.telemetry` writes into `PhaseAccounting`.

Named once, here, so the model, the structure validator and the renderer agree
on what "a measurement" consists of. A measurement is ATOMIC — all four or
none — which is why the validator can call a partially-filled snapshot a
structural problem rather than quietly summing three."""

MEASURED_TOKENS_SCHEMA_VERSION = 3
"""The `run` artifact version these fields FIRST appear in.

Not a second declaration of the kind's `current_version` — that lives in
`fr.artifacts.registry` and only there, and may move past this. This says
which version a cursor must declare before it is allowed to carry measured
tokens, so `validate_run` can report the one state that would otherwise go
unnoticed: v3 content under a v2 stamp, which no migration would ever revisit
and which raises in any fr that believes the stamp."""


class PhaseAccounting(BaseModel):
    """Context accounting for one dispatched `(phase, member)` unit — what it
    is about to re-read (V1), and what it actually cost (V2).

    **V1 — sizes, not tokens.** No harness offers a token API, so V1 measures
    the context fr itself assembles (journal, composed handoff, spec + plan
    bytes) and `fr run status` renders token figures explicitly labeled as
    estimates. Keyed like `items` (`phase/<n>` flat, `phase/<n>/<member>`
    grouped). Additive and optional: pre-accounting runs parse with
    `accounting=None`, same versioning argument as `items`/`members`.

    **V2 — measured tokens** (spec §5.C). The four fields below are read from
    the harness's own transcript by `fr.run.telemetry` when the unit resolves.
    Unlike the V1 sizes they default to `None`, not `0`, and that distinction
    is the point: `None` means *no measurement was possible* (no transcript,
    an unreadable one, an unattributable unit) while `0` is a real, measured
    zero. `fr run status` never renders the two the same way.

    Adding them is a SHAPE change under `.claude/rules/artifact-versioning.md`
    — this model is `extra="forbid"`, so an fr that predates the fields raises
    on a cursor carrying them rather than ignoring them. Hence the `run`
    kind's stamp bump to 3 and `fr.artifacts.run_telemetry`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    at: str | None = None
    journal_entries: int = 0
    journal_lines: int = 0
    handoff_chars: int = 0
    spec_bytes: int = 0
    plan_bytes: int = 0

    input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    output_tokens: int | None = None

    def measured_fields(self) -> dict[str, int | None]:
        """The four measured figures, by name — `None` where unmeasured."""
        return {name: getattr(self, name) for name in MEASURED_TOKEN_FIELDS}

    @property
    def measured_tokens(self) -> int | None:
        """The four measured figures summed, or `None` for no measurement.

        A measurement is atomic — all four or none — so this never returns a
        partial sum that would read as a small honest number. A cursor that
        carries some of the four and not others is a structural problem, and
        `fr.artifacts.structure.validate_run` reports it as one.
        """
        values = list(self.measured_fields().values())
        if any(value is None for value in values):
            return None
        return sum(value for value in values if value is not None)


def current_run_schema_version() -> int:
    """The `run` artifact version this `fr` writes.

    Read from `fr.artifacts.registry` rather than restated here:
    `.claude/rules/artifact-versioning.md` makes the registry the ONE place a
    kind's `current_version` may be declared, so a future bump moves one
    number and every run fr creates is still born stamped with it. A run that
    is stale from birth would make the first `fr` command in any
    non-interactive context (CI, a pod, an agent's Bash tool) refuse.

    Imported inside the function, like `fr.artifacts.structure` does in the
    other direction: the registry is imported at CLI entry before every
    command and must not drag the run models in with it.
    """
    from fr.artifacts.registry import artifact_kind

    return artifact_kind("run").current_version


class RunState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    """The artifact version this cursor was written for (spec §3.A of the
    migration framework).

    Defaulted to the pre-framework version, NOT to the current one: a run file
    with no `schema_version` key is a pre-framework file, and saying so is what
    lets the migration runner find it. fr's own writers (`fr run start`,
    `fr run adopt`) pass `current_run_schema_version()` explicitly.

    Optional and defaulted because it must be: `extra="forbid"` means an fr
    that does not know this key *raises* rather than ignoring it, so the stamp
    the migration writes would otherwise make a file unreadable by the very fr
    that wrote it (`.claude/rules/artifact-versioning.md`)."""

    run: str
    workflow: str  # "<shape-name>@<schema-version>" e.g. "fr-goal@1"
    branch: str
    started: str  # ISO 8601; kept as a string for round-trip stability
    cursor: str  # the step id currently active (running/blocked) or next-up
    steps: dict[str, StepRecord]
    accounting: dict[str, PhaseAccounting] | None = None


RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
"""What a run id may contain. Deliberately narrow (review r5-e1).

A run id becomes THREE things: a file stem (`runs/<id>.yaml`), a segment of a
`WorkItem` id (`<repo>/run/<id>`, §4.D) and a token in copy-pasted shell
(`fr run advance <id>`). The intersection of what all three tolerate is
alphanumerics, dot, dash and underscore — and a first character that is
alphanumeric, so an id can never be read as a CLI option or a git pathspec.
"""

RUN_ID_MAX_LENGTH = 128
"""Long enough for `<date>-<flattened-branch>` with a very long branch; short
enough to stay under every filesystem's 255-byte name limit once `.yaml` and
any suffix are added."""


def validate_run_id(run_id: str) -> str:
    """`run_id` unchanged, or `RunStateError` if it is not a safe single segment.

    A run id becomes a **path segment** (`docs/superpowers/runs/<id>.yaml`)
    and an **item id segment** (`<repo>/run/<id>`, §4.D). Neither `fr run
    start --run-id` nor `fr run adopt --run-id` checked it, so (verified
    live, review r5-b1):

    - `--run-id ../../../escaped` exited 0 and wrote the run file OUTSIDE
      `runs/` — a caller-controlled path traversal, with the escape hidden
      because the success line prints the id, not the path;
    - `--run-id weird/id` wrote `runs/weird/id.yaml`, which
      `find_run_for_plan`'s non-recursive `glob("*.yaml")` cannot see (so
      `fr archive` would strand it) and which `fr_dispatch.work_item.
      run_item_id` rejects outright (so the run can never be dispatched).

    The rule is an ALLOWLIST, not a list of the characters that happened to
    break something (review r5-e1). A denylist of `/` and `..` still admits a
    leading `-` (git reads it as a pathspec and argparse as an option), a
    backslash (a separator on the other platform, and an escape in most
    shells), a NUL or control character (unrepresentable in a filename and
    invisible in a terminal), and whitespace (a token that silently becomes
    two). `RUN_ID_RE` admits none of them.

    Mirrors `run_item_id`'s constraint and is strictly stricter; duplicated
    rather than imported because `fr` may not import `fr_dispatch`
    (`tests/unit/test_import_direction.py`). `derive_run_id` is written to
    satisfy it, so this only ever fires on an operator-supplied override.
    """
    if not run_id:
        raise RunStateError("run id must not be empty")
    if len(run_id) > RUN_ID_MAX_LENGTH:
        raise RunStateError(
            f"run id is {len(run_id)} characters; the limit is {RUN_ID_MAX_LENGTH} "
            "(it becomes a filename)"
        )
    if not RUN_ID_RE.match(run_id):
        raise RunStateError(
            f"run id {run_id!r} must match {RUN_ID_RE.pattern} — it names a file in "
            "docs/superpowers/runs/ and a segment of the work-item id, so it may "
            "contain only letters, digits, '.', '-' and '_' and must start with a "
            "letter or digit"
        )
    if run_id in (".", ".."):  # pragma: no cover — RUN_ID_RE already rejects both
        raise RunStateError(f"run id {run_id!r} is a directory reference, not a name")
    return run_id


def existing_run_id_colliding_with(repo_root: Path, run_id: str) -> str | None:
    """An existing run whose id differs from `run_id` only by CASE, if any.

    macOS (APFS, case-insensitive by default) and Windows treat `Run-1.yaml`
    and `run-1.yaml` as ONE file, so `fr run start --run-id Run-1` would
    silently overwrite an existing `run-1` — while the `path.exists()` guard
    passed on Linux and the two runs then diverged per platform (review
    r5-e1). Detecting the collision explicitly makes the behaviour the same
    everywhere, and the same as the operator's intuition: two runs whose ids
    differ only by case are one run with a typo.
    """
    runs_dir = repo_root / RUNS_REL
    if not runs_dir.is_dir():
        return None
    wanted = run_id.casefold()
    for path in sorted(runs_dir.glob("*.yaml")):
        if path.stem != run_id and path.stem.casefold() == wanted:
            return path.stem
    return None


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
