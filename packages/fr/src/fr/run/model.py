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


class ContextEstimate(BaseModel):
    """What fr assembled for ONE attempt — `PhaseAccounting`'s V1 half, on its
    own (spec `2026-09-20-unit-record-unification-design.md` §4.A).

    Sizes, not tokens: no harness offers a token API at dispatch time, so this
    measures the context fr itself built (journal, composed handoff, spec +
    plan bytes) and every renderer labels the derived token figure an
    ESTIMATE. The `at` timestamp `PhaseAccounting` carried is NOT here — in
    the v5 shape the estimate hangs off an `Attempt`, whose `dispatched` is
    that same moment recorded once instead of twice.

    Every field defaults to `0` on purpose, and that is the opposite stance
    from `MeasuredTokens` below: a size fr failed to read is genuinely zero
    bytes of assembled context, while a measurement fr failed to take is not a
    zero, it is an absence — which is why one is defaulted and the other is
    required.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    journal_entries: int = 0
    journal_lines: int = 0
    handoff_chars: int = 0
    spec_bytes: int = 0
    plan_bytes: int = 0


class MeasuredTokens(BaseModel):
    """What ONE attempt actually burned, read from the harness's own
    transcript — `PhaseAccounting`'s V2 half, with gh#514's invariant made
    STRUCTURAL (spec §4.A).

    All four fields are REQUIRED. A measurement is atomic — all four or none
    — and `PhaseAccounting` could only say so in prose plus a validator
    (`fr.artifacts.structure.validate_run`'s partial-measurement check), which
    meant the unrepresentable state was representable everywhere except at the
    one place that looked. Here a partial measurement cannot be constructed at
    all, so "no measurement" is expressed the only honest way: no
    `MeasuredTokens` at all, rather than a `MeasuredTokens` of zeros. A unit
    that genuinely spent nothing stays distinguishable from one nobody could
    read.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int

    @property
    def total(self) -> int:
        """The four figures summed — never a partial sum, because a partial
        `MeasuredTokens` does not exist."""
        return (
            self.input_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
            + self.output_tokens
        )


class Attempt(BaseModel):
    """One attempt to hold a unit, carrying its own identity AND its own cost
    (spec §4.A) — `DispatchRecord` plus `session`, `estimate` and `measured`.

    A unit's attempts (`UnitRecord.attempts`) are kept oldest first and never
    overwritten: a failed unit that is retried, or one `--redispatch`ed over a
    lost agent, keeps every prior attempt — the forensic trail gh-503 asked
    for. Which side of the dispatch-holder spec's §3 line each field sits on:

    - **fr knows it** — `dispatched`, fr's own timestamp of the act of
      dispatching. Stamped BEFORE the brief is built, because it doubles as
      the start edge of the measurement window (`fr.run.units.estimated_at`):
      one moment, recorded once.
    - **fr derives it** — `agent_type`, `model`, `session`, `estimate`.
    - **reported, unverifiable** — `agent`, `harness`, `returned`, `outcome`.
      An unreported `agent` is recorded as absent, never guessed.

    The three new fields are each the repair of a defect the split shape had:

    - `session` — the harness session that dispatched it. gh#514's
      `measure_unit` reads the transcript out of the CURRENT process
      environment, so without this a cursor picked up in another session (or
      on another host: §4.D.1) either finds nothing or, worse, measures a
      stranger's transcript that happens to fall in the same time window.
    - `estimate` / `measured` — per ATTEMPT, not per unit. The old top-level
      `accounting` map held one snapshot per unit, so a redispatched unit's
      second attempt overwrote the first one's cost and the abandoned agent's
      spend — exactly the spend worth seeing — disappeared.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dispatched: str
    agent: str | None = None
    agent_type: str | None = None
    harness: str | None = None
    model: str | None = None

    session: str | None = None
    """The harness session id fr derived when it OPENED this attempt (§4.D.1).

    Recorded so a transcript is looked up by `(session, agent)` in the
    *recorded* session's directory rather than the current one. Absent on
    every attempt written before this field existed, and on any harness with
    no session concept — which reads as "not observable from here", never as
    zero. No hostname is recorded: a missing session directory already says
    "elsewhere", and a hostname in a public repo's committed cursor is
    identity nobody needs."""

    returned: str | None = None
    outcome: DispatchOutcome | None = None

    estimate: ContextEstimate | None = None
    """What fr assembled for THIS attempt, written by `advance`."""

    measured: MeasuredTokens | None = None
    """What THIS attempt burned, written by `resolve` (and by `claim
    --abandoned`, whose spend is exactly the spend worth seeing)."""

    synthesized: Literal[True] | None = None
    """`True` on the ONE kind of attempt fr did not record when it happened:
    the attempt the 4 -> 5 migration creates for a unit that had a cost
    snapshot and no dispatch record (spec §4.F — every cursor that predates
    the dispatch record, which is most of them). Absent everywhere else.

    **A synthesized attempt carries COST, never a HOLD.** It exists so the
    unit's estimate and measurement have an attempt to hang off, with
    `dispatched` = the moment fr briefed it, which is the only fact fr has.
    It has no `returned`, and that must NOT read as "still held": the unit may
    be `done`, or `failed` and waiting to be retried, and treating it as held
    made `advance` refuse to retry a failed unit of an in-flight run the
    moment the run was migrated, and made `fr run check` report every finished
    unit of every older cursor as open. It has no `agent_type`, and that must
    NOT read as "the orchestrator ran it" — which is what an absent
    `agent_type` means on an attempt fr DID record. Nothing else on the
    record can tell the two apart, so the record says it.

    The witness (`fr.run.units.open_attempt`) skips it, so a migrated unit
    behaves exactly as it did while its cost lived in the v4 `accounting` map,
    which no witness ever read. Stated, not invented: closing it instead would
    have needed a `returned` timestamp fr never had.
    """

    @field_validator("harness")
    @classmethod
    def _check_harness(cls, value: str | None) -> str | None:
        """Validated against `fr.harness.model.HARNESSES`, imported rather
        than re-listed — `DispatchRecord`'s rule, kept."""
        from fr.harness.model import HARNESSES

        if value is not None and value not in HARNESSES:
            raise ValueError(f"harness {value!r} must be one of {HARNESSES}")
        return value

    @model_validator(mode="after")
    def _returned_and_outcome_are_one_fact(self) -> Attempt:
        """`outcome` is set exactly when `returned` is — `DispatchRecord`'s
        invariant, kept verbatim. A half-closed record reads as still-held or
        as held-forever depending on which half a reader happens to look at,
        which is the double-dispatch hazard wearing a disguise."""
        if (self.returned is None) != (self.outcome is None):
            raise ValueError(
                "`returned` and `outcome` are set together or not at all "
                f"(returned={self.returned!r}, outcome={self.outcome!r}); a record with "
                "exactly one of them is neither open nor closed"
            )
        return self

    @model_validator(mode="after")
    def _a_synthesized_attempt_claims_nothing_fr_did_not_know(self) -> Attempt:
        """A synthesized attempt is `dispatched` + cost and NOTHING else.

        Identity or a close on one would be a claim nobody made — and it would
        also make the record ambiguous again: is this a hold, or not? The
        marker only means something while the answer stays "never"."""
        if self.synthesized:
            claimed = [
                name
                for name in (
                    "agent",
                    "agent_type",
                    "harness",
                    "model",
                    "session",
                    "returned",
                    "outcome",
                )
                if getattr(self, name) is not None
            ]
            if claimed:
                raise ValueError(
                    f"a synthesized attempt carries only `dispatched` and its cost, but this "
                    f"one also sets {', '.join(claimed)}"
                )
        return self


UnitState = Literal["pending", "running", "done", "failed", "manual"]
"""A unit's state — the values the v4 `StepRecord.items` map carried as bare
strings, named (spec §4.B).

`manual` is gh#496's marker for a `tag: manual` phase the fan-out will never
dispatch; it is a state a unit can be IN, not an outcome, which is why it sits
here rather than in `DispatchOutcome`. There is no `blocked`: a gate blocks a
STEP, never one of its units."""


class UnitRecord(BaseModel):
    """One unit of one step — its state, every attempt to hold it, and the
    evidence it produced (spec §4.A) — the value type of `StepRecord.units`.

    This is the whole point of the unit-record spec: `items`, `dispatch` and
    the top-level `accounting` map were three key spaces over ONE identity,
    kept in step by call sites that each re-derived the join. Collapsing them
    means a unit's state cannot drift from its history, and a write that
    forgets one half stops being expressible.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: UnitState | None = None
    """`None` exactly for a `step/<step-id>` unit — a flat `kind: agent`
    step, whose `StepRecord.state` is that fact's ONE home (§4.B). A fact with
    two homes is what this spec exists to stop."""

    attempts: tuple[Attempt, ...] = ()
    """Oldest first; the OPEN attempt is the last one whose `returned` is
    `None` (a `synthesized` one never counts), and there is at most one.
    Empty is a real, honest state: a phase `fr run adopt` found already
    complete was never dispatched by fr, and inventing an attempt to look
    uniform would be fabrication."""

    evidence: dict[str, str] | None = None
    """Obligation name -> journal entry id, verified when the unit resolved
    (§4.E). `None` on every unit resolved before the evidence gate existed —
    visible debt reported as `done, unevidenced`, never a retroactive
    failure."""


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

    members: list[str] | None = None
    """Member-step ids of a grouped `for_each` step, recorded at build.

    Lets `_check_step_drift` tell a member added/removed after `fr run
    start` from the ordinary case — without it a shape edit inside the nest
    would advance silently against a step list the cursor was never computed
    for. Absent (`None`) on grouped steps of pre-existing run files, where
    the member check is skipped rather than guessed.
    """

    units: dict[str, UnitRecord] | None = None
    """Every unit of this step — its state, every attempt to hold it, and its
    cost — under ONE key (spec `2026-09-20-unit-record-unification-design.md`
    §4.A). Replaces `items` (state), `dispatch` (attempts) and the top-level
    `RunState.accounting` (cost): three key spaces over one identity, kept in
    step by call sites that each re-derived the join, which is how a unit's
    state came to drift from its history.

    Three key forms, each with a rule `fr.artifacts.structure.validate_run`
    enforces (§4.B):

    - `phase/<n>/<member-id>` — a grouped `for_each` member. Carries `state`.
    - `step/<step-id>` — a flat `kind: agent` step. Carries **no** `state`:
      `StepRecord.state` above is that fact's one home. The `step/` prefix is
      load-bearing, not cosmetic — a repo-authored step id may itself contain
      a `/` (`fr.workflow.check.check_workflow` constrains no characters), so
      without a namespace the key spaces are not provably disjoint.
    - `phase/<n>` — a phase fr never dispatches AS a phase: gh#496's
      `state: manual` marker, or a unit of a flat `for_each` step that
      `fr run adopt` recorded. Carries `state`; never any attempts.

    Keys are the plan-relative tail of the work-item identity grammar, not a
    full work-item id: composing `<repo>/<spec>/<plan>/phase/<n>` is
    `fr_dispatch.work_item`'s job and `fr` may not import it
    (`tests/unit/test_import_direction.py`). The run file already records
    which plan it is about, in `emitted.plan`.

    Only `fr.run.units` reads or writes this map; everything else speaks of
    units, states, attempts and cost through that module. **A shape change**
    (`current_version=5`, migration `fr.artifacts.run_unit_record`): this is a
    field REMOVAL on an `extra="forbid"` model, so the prior shape is frozen
    in `fr.run.legacy` and every migration reads with that, never with this.
    """


UNIT_RECORD_SCHEMA_VERSION = 5
"""The `run` artifact version `StepRecord.units` FIRST appears in.

Not a second declaration of the kind's `current_version` — that lives in
`fr.artifacts.registry` and only there, and may move past this. This says
which version a cursor must declare before it is allowed to carry `units`, so
`validate_run` can report the one state that would otherwise go unnoticed: a
v5 body under an older stamp (the 4 -> 5 migration's crash window, or a bad
merge), which raises in any fr that believes the stamp."""


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


class _CursorDumper(yaml.SafeDumper):
    """`SafeDumper`, except a multi-line string asks for a block literal."""


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    # A cursor is git-tracked and read in diffs. The default renders a string
    # ending in a newline as a quoted scalar folded over three lines — valid
    # YAML that looks broken — and a failed step's output as one blob of `\n`
    # escapes. `|` is a HINT: the emitter still falls back to a quoted scalar
    # for what a block literal cannot carry (a leading space, a space before a
    # newline, a control character), so the round trip stays exact either way.
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_CursorDumper.add_representer(str, _represent_str)


def dump_cursor_yaml(data: dict) -> str:
    """The ONE way a run cursor's mapping becomes text.

    Both writers call it — `dump_run_state` and the 4 -> 5 body rewrite
    (`fr.artifacts.run_unit_record`). A second spelling of these options is how
    a migrated cursor would restyle itself on its first native save: a diff
    nobody wrote. A block literal is never folded, whatever the line length —
    folding is what `>` is for — so `width` stays at the default and no
    single-line scalar already on disk is re-wrapped by this.
    """
    return yaml.dump(
        data,
        Dumper=_CursorDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def dump_run_state(state: RunState) -> str:
    """Canonical run-state YAML.

    `exclude_none` drops unset optional step fields (`at`/`emitted`/`exit`/
    `stdout`) rather than padding them as `null:` — a freshly started run
    (all steps `pending`) stays readable, and round-tripping the result
    through `parse_run_state` reproduces this exact text (unset fields
    default back to `None`).
    """
    data = state.model_dump(mode="json", exclude_none=True)
    # A unit fr never dispatched — an adopted `done` phase, a `manual` marker,
    # a still-`pending` member — dumps as `{state: …}` and nothing else.
    # `exclude_none` cannot do it (an empty tuple is not `None`), and padding
    # every such unit with `attempts: []` would both bury the units that DO
    # have a history and make a native dump differ from what the 4 -> 5
    # rewrite writes for the same unit.
    for record in data["steps"].values():
        for unit in (record.get("units") or {}).values():
            if not unit.get("attempts"):
                unit.pop("attempts", None)
    return dump_cursor_yaml(data)


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
