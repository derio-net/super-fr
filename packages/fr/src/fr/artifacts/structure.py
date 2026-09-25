"""Per-kind structure validators — what `fr validate artifacts` checks (spec §3.F).

One function per artifact kind, each `(path) -> list[str]` of human-readable
problems ("" is never a problem; an empty list means valid). They are attached
to their kind in `fr.artifacts.registry`, so the registry stays the ONE place
that enumerates kinds and a new kind cannot appear here without appearing there.

Three rules the functions obey:

1. **Name the field.** "invalid" without a field name is a validator nobody
   uses. Every message either names the missing/invalid field or quotes the
   offending line with its number.
2. **Reuse the canonical schema.** The closed-world kinds already have a
   pydantic model (`PlanMeta`, `RunState`, `Matrix`) and the open ones a
   parser (`parse_journal`, `fr.parser.parse`); validation goes through those
   rather than growing a second definition of "valid" that can drift.
3. **Read only.** These run against files an operator has open. Nothing here
   writes, and nothing re-serialises.

The YAML kinds are parsed with `_StrictLoader`, not `yaml.safe_load`: a
duplicate key is the one corruption a schema check cannot see, because PyYAML
resolves it before the model ever runs (see the class docstring).

Imports of the heavier `fr` modules are deliberately *inside* the functions:
`fr.artifacts.registry` is imported at CLI entry by the migration trigger,
before every command, and must not drag the plan parser and pydantic models in
with it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:  # pragma: no cover — typing only, keeps the runtime
    # import of `fr.run.model` inside the function that needs it (see the
    # module docstring's note on CLI-entry import cost).
    from fr.run.model import RunState

# --- shared helpers ------------------------------------------------------


class _StrictLoader(yaml.SafeLoader):
    """`SafeLoader` that refuses a mapping with a repeated key.

    PyYAML keeps the LAST occurrence and says nothing, which makes a duplicate
    key a *silent drop* — the shape still validates, and everything the earlier
    block declared is simply gone. This repo shipped exactly that: a row of
    `docs/acceptance/matrix.yaml` carried `levels:` twice, so one of its two
    test refs disappeared from the matrix, from the generated reports and from
    `fr acceptance check`, with nothing anywhere reporting a problem.

    Structure validation is the layer that can see it, because it is the only
    one that reads the artifact as *text* rather than as whatever the parser
    already decided it meant.
    """

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            # PyYAML ships no stubs for its constructor API, hence the cast.
            key: Any = self.construct_object(key_node, deep=deep)  # type: ignore[no-untyped-call]
            try:
                duplicate = key in seen
            except TypeError:  # pragma: no cover — an unhashable YAML key
                continue
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _load_mapping(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """`(mapping, problems)` — a non-mapping, unparseable, or duplicate-keyed
    file is a problem."""
    try:
        data: Any = yaml.load(path.read_text(), Loader=_StrictLoader)  # noqa: S506
    except yaml.YAMLError as e:
        return None, [f"not valid YAML: {e}"]
    if data is None:
        return None, ["file is empty"]
    if not isinstance(data, dict):
        return None, [f"top level must be a mapping, got {type(data).__name__}"]
    return data, []


def _loc(parts: tuple[Any, ...]) -> str:
    """A pydantic error location as a field path: `rows[3].status`."""
    out = ""
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out or "<root>"


def _model_problems(model: Any, data: dict[str, Any]) -> list[str]:
    """Validate `data` against a pydantic model, one message per error."""
    from pydantic import ValidationError

    try:
        model.model_validate(data)
    except ValidationError as e:
        problems = []
        for err in e.errors():
            field = _loc(tuple(err["loc"]))
            if err["type"] == "missing":
                problems.append(f"missing required field `{field}`")
            else:
                problems.append(f"invalid field `{field}`: {err['msg']}")
        return problems
    return []


# --- plan ----------------------------------------------------------------


_PHASE_FILE_RE = re.compile(r"^\d{2}\.yaml$")


def validate_plan(path: Path) -> list[str]:
    """`_meta.yaml` against `PlanMeta`, every `NN.yaml` strict-loaded, then the
    whole folder through the parser.

    The folder parse is what catches a malformed `NN.yaml`, and it passes
    `enforce_fr_version=False`: a ceiling that excludes this fr is a *migration*
    question (the stamp check and `fr migrate artifacts` own it), not a
    structural one, and reporting it twice in different words helps nobody.

    **Every YAML file in the folder gets the strict loader, not just
    `_meta.yaml`** (review r5-c4). A plan is a FOLDER of YAML carriers and the
    interesting one is `NN.yaml`: tick state lives there, so a `01.yaml`
    declaring `state:` twice loses whichever block PyYAML drops — silently
    un-ticking steps an agent had completed — and `parse()` uses
    `yaml.safe_load`, which keeps the last occurrence and says nothing. Before
    this, `.claude/rules/artifact-versioning.md`'s "a duplicate YAML key in any
    of the three YAML-carried kinds fails `fr validate artifacts`" was true of
    a plan's `_meta.yaml` and false of the file that actually carries its state.
    """
    from fr.parser import PlanSchemaError, parse
    from fr.types import PlanMeta

    data, problems = _load_mapping(path)
    if problems or data is None:
        return problems
    problems = _model_problems(PlanMeta, data)
    if problems:
        return problems
    for phase_file in sorted(path.parent.iterdir()):
        if not phase_file.is_file() or not _PHASE_FILE_RE.match(phase_file.name):
            continue
        _, phase_problems = _load_mapping(phase_file)
        problems.extend(f"{phase_file.name}: {p}" for p in phase_problems)
    if problems:
        return problems
    try:
        parse(path.parent, enforce_fr_version=False)
    except PlanSchemaError as e:
        return [f"plan folder does not parse: {e}"]
    return []


# --- journal -------------------------------------------------------------


def validate_journal(path: Path) -> list[str]:
    """Every entry parses, and no entry id appears twice.

    `fr journal add` refuses duplicate `--id` values, so two entries sharing one id can
    only come from a hand edit or a bad splice — and `fr journal render
    --entry` would then silently show the first.
    """
    from fr.journal.model import JournalParseError, parse_journal

    try:
        entries = parse_journal(path.read_text())
    except JournalParseError as e:
        return [str(e)]

    problems: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.id in seen:
            problems.append(f"duplicate journal entry id `{entry.id}` — the entry appears twice")
        seen.add(entry.id)
    return problems


# --- run -----------------------------------------------------------------


def validate_run(path: Path) -> list[str]:
    """`RunState`, plus the cross-references the model does not encode.

    Each is a relationship between fields rather than a field, so the schema
    cannot see it:

    1. the cursor must name a step the run actually records;
    2. a cursor carrying `units` must DECLARE at least the version that map
       appeared in. A v5 body under an older stamp is the one state nothing
       else would catch — it is what the 4 -> 5 migration's crash window
       leaves behind, and any fr that believed the stamp would raise on the
       key;
    3. the unit-key grammar and the state rule of spec
       `2026-09-20-unit-record-unification-design.md` §4.B
       (`_run_unit_problems`).

    What is NOT here any more, on purpose: the partial-measurement check. A
    measurement is `MeasuredTokens`, whose four figures are all required, so a
    partial one cannot be represented and `RunState` itself refuses it — the
    invariant became structural (§4.A) and the check disappeared rather than
    moving. A v4 file carrying one never reaches this function in the v5
    shape: the migration refuses it and leaves it byte-identical.
    """
    from fr.run.model import UNIT_RECORD_SCHEMA_VERSION, RunState

    data, problems = _load_mapping(path)
    if problems or data is None:
        return problems
    problems = _model_problems(RunState, data)
    if problems:
        return problems

    state = RunState.model_validate(data)
    if state.cursor not in state.steps:
        known = ", ".join(state.steps) or "none"
        problems.append(
            f"`cursor` names `{state.cursor}`, which is not a recorded step (recorded: {known})"
        )
    carries_units = any(record.units for record in state.steps.values())
    if carries_units and state.schema_version < UNIT_RECORD_SCHEMA_VERSION:
        problems.append(
            f"a step carries `units` but `schema_version` is {state.schema_version}; that "
            f"map appeared in version {UNIT_RECORD_SCHEMA_VERSION}, so this file declares a "
            "shape it does not have — `fr migrate artifacts --yes` finishes the job"
        )
    problems.extend(_run_unit_problems(state))
    return problems


_GROUPED_UNIT_KEY_RE = re.compile(r"^phase/\d+/.+$")
_PHASE_UNIT_KEY_RE = re.compile(r"^phase/\d+$")
_STEP_UNIT_KEY_RE = re.compile(r"^step/.+$")
"""The three unit-key forms of spec §4.B: `phase/<n>/<member-id>` for a grouped
`for_each` member, `phase/<n>` for a phase fr never dispatches as such, and
`step/<step-id>` for a flat `kind: agent` step.

The `step/` namespace is load-bearing rather than decorative: a repo-authored
step id may itself contain a `/` — `fr.workflow.check.check_workflow` checks
duplicate ids, dangling `needs`, cycles and unknown capabilities, and
constrains no characters at all — so without the prefix the key spaces are
not provably disjoint."""


def _run_unit_problems(state: RunState) -> list[str]:
    """The invariants `StepRecord.units` states but pydantic cannot (§4.B).

    These live here rather than on the model deliberately. `advance`, `claim`,
    `resolve` and `adopt` build every key and record themselves, so a
    violation only reaches a file by hand-edit or a bad merge — the threat
    model `.claude/rules/artifact-versioning.md` names for a git-tracked,
    hand-editable artifact. Refusing them in `parse_run_state` would make a
    damaged cursor unreadable by the very commands an operator needs in order
    to repair it; reporting them from `fr validate artifacts` is what makes
    the damage visible without making it unrecoverable.

    **`phase/<n>` is broader than the spec's first wording.** §4.B called it
    "gh#496's manual-phase marker — `state: manual`, always". A captured
    cursor refutes the "always": a flat `for_each: phase` step (no member
    steps) records its phases under the same key with an ordinary state
    (`tests/fixtures/run_cursors/v1/2026-09-09-feat-issue-464.yaml`,
    `phase/1: pending`), and `fr run adopt` still writes that. Enforcing
    `manual` would have made every such cursor fail validation the moment it
    migrated. What the marker and the flat unit share — and what IS enforced —
    is that fr never dispatches a phase as a phase, so neither ever has
    attempts.
    """
    problems: list[str] = []
    for step_id, record in state.steps.items():
        for key, unit in (record.units or {}).items():
            where = f"step `{step_id}` unit `{key}`"
            attempts = unit.attempts
            if _STEP_UNIT_KEY_RE.match(key):
                if unit.state is not None:
                    problems.append(
                        f"{where} carries `state: {unit.state}`; a flat step's unit has no "
                        "state of its own — the step's `state` is that fact's one home, and "
                        "a fact with two homes drifts"
                    )
                if not attempts and not unit.evidence:
                    problems.append(
                        f"{where} records nothing — no attempts and no evidence; a unit key "
                        "with no history means nothing"
                    )
            elif _GROUPED_UNIT_KEY_RE.match(key):
                if unit.state is None:
                    problems.append(
                        f"{where} carries no `state`; a grouped member's state has no other "
                        "home, so `advance` can neither dispatch nor skip it"
                    )
            elif _PHASE_UNIT_KEY_RE.match(key):
                if unit.state is None:
                    problems.append(f"{where} carries no `state`")
                if attempts:
                    problems.append(
                        f"{where} records {len(attempts)} attempts; fr dispatches a phase's "
                        "MEMBERS (`phase/<n>/<member-id>`), never the phase, so a "
                        "`phase/<n>` unit — a `manual` marker, or a flat fan-out's adopted "
                        "phase — never has any"
                    )
            else:
                problems.append(
                    f"{where} is not a unit key — expected `step/<step-id>` for a flat "
                    "agent step, `phase/<n>/<member-id>` for a grouped one, or `phase/<n>`"
                )
            synthesized_at = [i for i, a in enumerate(attempts) if a.synthesized]
            if synthesized_at and synthesized_at != [0]:
                problems.append(
                    f"{where} has a synthesized attempt at position "
                    f"{', '.join(str(i + 1) for i in synthesized_at)}; the 4 -> 5 migration "
                    "writes at most one, and FIRST — nothing precedes a dispatch that predates "
                    "the dispatch record"
                )
            # A synthesized attempt carries a migrated cost, never a hold, so it
            # is not "open" however long it goes without a `returned`.
            open_at = [
                i for i, a in enumerate(attempts) if a.returned is None and not a.synthesized
            ]
            if len(open_at) > 1:
                problems.append(
                    f"{where} has {len(open_at)} open attempts; at most one unit may be "
                    "held at a time, or two writers share one worktree"
                )
            elif open_at and open_at[0] != len(attempts) - 1:
                problems.append(
                    f"{where} leaves attempt {open_at[0] + 1} of {len(attempts)} open while a "
                    "later one is closed; the open attempt is the LAST one, and every "
                    "reader takes it from the end"
                )
    return problems


# --- matrix --------------------------------------------------------------


def validate_matrix(path: Path) -> list[str]:
    """The acceptance matrix against `Matrix`.

    Ref resolution and staleness are `fr acceptance check`'s job and stay
    there; this is the shape only, so the two gates cannot disagree.
    """
    from fr.acceptance.model import Matrix

    data, problems = _load_mapping(path)
    if problems or data is None:
        return problems
    return _model_problems(Matrix, data)


# --- usage ---------------------------------------------------------------


def validate_usage(path: Path) -> list[str]:
    """A usage file (spec `2026-09-25-lean-cost-aware-process-design.md` §5.B)
    against `UsageFile` — which also refuses two captures from one host and a
    host that is a name rather than a label."""
    from fr.usage.file import UsageFile

    data, problems = _load_mapping(path)
    if problems or data is None:
        return problems
    return _model_problems(UsageFile, data)


def validate_record(path: Path) -> list[str]:
    """A step record (spec `2026-09-25-lean-cost-aware-process-design.md`
    §5.C.1) against `StepRecord`. Which sections its step may carry needs the
    manifest, so that is `fr run resolve --record`'s check, not this one."""
    from fr.record.model import StepRecord

    data, problems = _load_mapping(path)
    if problems or data is None:
        return problems
    return _model_problems(StepRecord, data)


# --- spec ----------------------------------------------------------------
#
# Specs are hand-written Markdown with no schema, so the checks target the
# corruption this repo has actually produced: commit 7ece5a9 spliced a spec
# with `end = text.index("## Implementation Plans")`, matched an inline mention
# of that heading sitting BEFORE the replaced section, and re-appended the tail
# — ~640 duplicated lines and one heading fused mid-sentence. Nothing caught
# it. Both signals are checked below; measured against every spec in this repo,
# both are silent on all of them and both fire on the damaged file.

_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(\S.*?)\s*$")

_SECTION_LEVEL = 3
"""Headings at this level or shallower name a *section*; deeper ones (`####`
notes, per-item headings) legitimately repeat and are not compared."""


def validate_spec(path: Path) -> list[str]:
    problems: list[str] = []
    seen: dict[tuple[int, str], int] = {}
    in_fence = False
    has_title = False

    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
        if m is None:
            continue
        level, text = len(m.group(1)), m.group(2)
        if level == 1:
            has_title = True

        # An inline-code span that never closes on a heading line: the heading
        # ran on into prose it was spliced into. A legitimate heading quoting
        # code (`### The `--yes` flag`) balances its backticks.
        if line.count("`") % 2:
            problems.append(
                f"line {number}: heading has an unclosed `` ` `` — a heading fused "
                f"mid-sentence? {line.strip()[:90]!r}"
            )

        if level <= _SECTION_LEVEL:
            key = (level, text)
            first = seen.get(key)
            if first is not None:
                problems.append(
                    f"line {number}: duplicated section heading {line.strip()[:90]!r} "
                    f"(already at line {first}) — a section block appears twice"
                )
            else:
                seen[key] = number

    if not has_title:
        problems.append("missing required `# ` title heading on the first heading level")
    return problems
