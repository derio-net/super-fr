"""`fr run start / status / advance / resolve / check` — spec §4.B, Phase 7.

`fr run advance` is the one place this package could be tempted to shell
out to a model, and it structurally cannot: a `kind: cli` step is executed
directly (`subprocess.run`, exit code + stdout captured into the step
record); a `kind: agent` step is NEVER executed here — it produces a brief
(the shape a harness dispatches, e.g. the `fr-phase-executor` agent) and
marks itself `running`. This is the structural half of the
`no-claude-p-batch` rule, not merely compliance with it — there is nothing
in this module that could invoke an LLM even by mistake.

`fr run resolve` is the other half of that split (spec §4.B, added in the
Phase 7 review — the original four-command CLI was a dead end: nothing
could ever move an `agent` step past `running`, so a real run wedges on its
first one). The harness calls `resolve` when a dispatched agent returns;
it shares `_complete_step` with `advance`'s `cli` branch rather than
forking the done/failed cursor asymmetry a second time.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shlex
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, NoReturn

import typer
from rich.console import Console

from fr.commands.common import resolve_repo_root
from fr.harness import HARNESSES, load_matrix
from fr.harness.detect import detect_harness
from fr.harness.model import HarnessError
from fr.journal.model import (
    JournalEntry,
    JournalParseError,
    compose_handoff,
    parse_journal,
    resolve_journal_read_path,
)
from fr.run.adopt import AdoptError, adopt_run, plan_phase_numbers
from fr.run.model import (
    RUN_ID_MAX_LENGTH,
    RUNS_REL,
    AnsweredBy,
    DispatchOutcome,
    DispatchRecord,
    PhaseAccounting,
    RunState,
    RunStateError,
    StepRecord,
    current_run_schema_version,
    existing_run_id_colliding_with,
    load_run_state,
    parse_run_state,
    run_path,
    save_run_state,
    validate_run_id,
)
from fr.run.provenance import agent_cleared_gates, gates
from fr.run.workspace import RunWorkspaceError, ensure_run_workspace
from fr.workflow.artifacts import REPO_TRACKED_ARTIFACTS
from fr.workflow.check import check_workflow
from fr.workflow.model import Step, WorkflowError, WorkflowManifest
from fr.workflow.resolve import resolve_workflow

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

run_app = typer.Typer(
    help="Durable workflow-run cursor: start / status / advance / resolve / check.",
    no_args_is_help=True,
)

_TEMPLATE_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}")


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat()


_UNSAFE_IN_RUN_ID = re.compile(r"[^A-Za-z0-9._-]+")


def derive_run_id(branch: str, *, today: _dt.date | None = None) -> str:
    """Derive a run id from `branch` when `--run-id` is not given.

    Must satisfy `validate_run_id` — and therefore
    `fr_dispatch.work_item.run_item_id` — because it FEEDS them: a single
    segment of `[A-Za-z0-9._-]`, starting with an alphanumeric. `branch`
    routinely contains `/` (e.g. `feat/ticket-polling`), so it is flattened;
    the date prefix mirrors the plan-slug shape spec §4.B's own example
    (`2026-08-14-ticket-polling`) uses, keeping a run id visually consistent
    with the plan slug a `unit: run` shape will go on to create.

    **Every unsafe run collapses, not just `/`** (review r5-e1). Git branch
    names admit far more than this: `feat/../x`, `-weird`, `wip #3`, a
    non-ASCII word. Replacing only `/` produced ids that `validate_run_id`
    then rejected — turning a legal branch into a `fr run start` that could
    not run at all — or, worse, an id starting with `-`. The date prefix
    guarantees the leading character, so only the tail needs sanitising, and
    a branch that sanitises to nothing still yields the bare date.
    """
    day = today or _dt.date.today()
    sanitized = _UNSAFE_IN_RUN_ID.sub("-", branch.strip("/")).strip("-.")
    derived = f"{day.isoformat()}-{sanitized}" if sanitized else day.isoformat()
    return derived[:RUN_ID_MAX_LENGTH].rstrip("-.") or day.isoformat()


def _step_by_id(manifest: WorkflowManifest, step_id: str) -> Step:
    step, _parent = _find_step(manifest, step_id)
    return step


def _find_step(manifest: WorkflowManifest, step_id: str) -> tuple[Step, Step | None]:
    """`(step, parent-group)` for a top-level OR member id — members share the
    flattened id space `check_workflow` validates, so resolving one must find
    them too. Parent is `None` for a top-level step."""
    for step in manifest.steps:
        if step.id == step_id:
            return step, None
        for member in step.steps:
            if member.id == step_id:
                return member, step
    raise RunStateError(f"step {step_id!r} not found in workflow {manifest.workflow!r}")


def _unit_key(
    repo_root: Path,
    state: RunState,
    step: Step,
    parent: Step | None,
    item: str | None,
) -> str:
    """The `StepRecord.dispatch`/`items` key a `(--step, --item)` pair names —
    spec §4.B's two key spaces (`phase/<n>/<member-id>` for a grouped member,
    `step/<step-id>` for a flat one) computed in exactly ONE place, so
    `claim`, `_resolve_member` and `advance`'s own flat-step key can never
    drift apart (P3.T1.S3). `step`/`parent` are `_find_step`'s own return
    shape — `parent` is `None` for a top-level step, the group for a member.

    Exits 2 (printing to `err_console`) for every input shape that cannot
    name a unit: a member given no `--item`, a non-member given one, or an
    `--item` naming a phase this run's recorded plan does not have.
    """
    if parent is not None:
        if item is None:
            err_console.print(
                f"[red]{step.id}: a member outcome must address a phase item — "
                "pass --item phase/<n>[/red]"
            )
            raise typer.Exit(2)
        try:
            phases = _group_phases(repo_root, state)
        except (RunStateError, AdoptError) as e:
            err_console.print(f"[red]{parent.id}: {e}[/red]", soft_wrap=True)
            raise typer.Exit(2) from e
        expected = _expected_group_items(parent, phases)
        key = f"{item}/{step.id}"
        if key not in expected:
            err_console.print(
                f"[red]{key}: not a phase member of {parent.id!r} — expected "
                f"phase/<n> for phases {phases} (from the recorded plan)[/red]"
            )
            raise typer.Exit(2)
        return key
    if item is not None:
        if step.steps:
            members = ", ".join(m.id for m in step.steps)
            err_console.print(
                f"[red]{step.id}: a group outcome must address a member step "
                f"({members}) — pass --step <member> --item phase/<n>[/red]"
            )
        else:
            err_console.print(
                f"[red]{step.id}: --item is only for members of a grouped "
                f"`for_each` step — {step.id!r} has no members[/red]"
            )
        raise typer.Exit(2)
    return f"step/{step.id}"


def _emitted_plan(state: RunState) -> str | None:
    """The recorded repo-relative plan path, wherever the shape put it."""
    for record in state.steps.values():
        if record.emitted and "plan" in record.emitted:
            return record.emitted["plan"]
    return None


def _group_phases(repo_root: Path, state: RunState) -> list[int]:
    """Phase numbers the grouped fan-out iterates over — from the plan on
    disk, the one source of which phases exist. Fail-closed: a group advanced
    before its plan is recorded (or against an unparseable plan) names what
    is missing instead of dispatching against a guessed phase list."""
    plan_rel = _emitted_plan(state)
    if plan_rel is None:
        raise RunStateError(
            "cannot dispatch per-phase members — no plan recorded yet "
            "(resolve the step that emits `plan` first)"
        )
    return plan_phase_numbers(repo_root, plan_rel)


def _expected_group_items(group: Step, phases: list[int]) -> list[str]:
    """Every `phase/<n>/<member>` key of a grouped fan-out, in dispatch
    order: phase-major, then member order — implement before review, per
    phase, never the reverse."""
    return [f"phase/{n}/{m.id}" for n in phases for m in group.steps]


def _accounting_snapshot(
    repo_root: Path, state: RunState, phase_n: int, depends_on: tuple[int, ...] = ()
) -> PhaseAccounting:
    """What the dispatched unit is about to re-read (V1 context accounting).

    Measured, not metered: journal entries/lines, the composed handoff's
    chars, spec + plan bytes — the context fr itself assembles. Never a gate:
    anything unreadable here degrades to zeros rather than refusing the
    dispatch (observability must not break execution).
    """
    from fr.parser import PlanSchemaError, parse

    plan_rel = _emitted_plan(state)
    spec_rel: str | None = None
    for record in state.steps.values():
        if record.emitted and "spec" in record.emitted:
            spec_rel = record.emitted["spec"]
    spec_bytes = 0
    if spec_rel is not None:
        try:
            candidate = repo_root / spec_rel
            spec_bytes = candidate.stat().st_size if candidate.is_file() else 0
        except OSError:
            spec_bytes = 0
    plan_bytes = 0
    slug = ""
    if plan_rel is not None:
        slug = plan_rel.rstrip("/").rsplit("/", 1)[-1]
        try:
            plan_bytes = sum(
                f.stat().st_size for f in (repo_root / plan_rel).rglob("*") if f.is_file()
            )
        except OSError:
            plan_bytes = 0
        try:
            plan = parse(repo_root / plan_rel)
            depends_on = next(
                (p.phase.depends_on for p in plan.phases if p.phase.number == phase_n),
                depends_on,
            )
        except (PlanSchemaError, OSError):
            pass
    entries: list[JournalEntry] = []
    journal_lines = 0
    if slug:
        jpath = resolve_journal_read_path(repo_root, "plan", slug)
        if jpath.is_file():
            try:
                text = jpath.read_text()
            except OSError:
                text = ""
            if text:
                journal_lines = len(text.splitlines())
                try:
                    entries = parse_journal(text)
                except JournalParseError:
                    entries = []
    handoff_chars = len(
        compose_handoff(entries, phase=phase_n, scope="plan", slug=slug, depends_on=depends_on)
    )
    return PhaseAccounting(
        at=_now(),
        journal_entries=len(entries),
        journal_lines=journal_lines,
        handoff_chars=handoff_chars,
        spec_bytes=spec_bytes,
        plan_bytes=plan_bytes,
    )


def _next_step_id(manifest: WorkflowManifest, step_id: str) -> str | None:
    ids = [s.id for s in manifest.steps]
    idx = ids.index(step_id)
    return ids[idx + 1] if idx + 1 < len(ids) else None


def _resolve_manifest_for_state(repo_root: Path, state: RunState) -> WorkflowManifest:
    """The manifest this run was started against — name AND schema version.

    `state.workflow` is `"<name>@<schema>"`. The suffix used to be sliced off
    and thrown away (review r5-e3), so a run started against `fr-goal@1` would
    happily keep advancing after the shape was rewritten as `schema: 2` — with
    a step graph the cursor was never computed for. The suffix is a version
    stamp; a version stamp nobody checks is decoration.
    """
    name, _, recorded_schema = state.workflow.partition("@")
    manifest = resolve_workflow(name, repo_root)
    if recorded_schema and str(manifest.schema_version) != recorded_schema:
        raise RunStateError(
            f"run {state.run!r} was started against {state.workflow!r}, but "
            f"{name!r} now declares schema {manifest.schema_version}. A shape's "
            "schema version changes its step grammar; start a new run rather than "
            "advancing this one against a different one."
        )
    _check_step_drift(state, manifest)
    return manifest


def _check_step_drift(state: RunState, manifest: WorkflowManifest) -> None:
    """Refuse when the shape's STEPS have changed since `fr run start`.

    A step added, removed or renamed makes every recorded position suspect:
    the cursor may name a step that no longer exists, a new step silently
    never runs, and `_next_step_id` moves the run somewhere the operator never
    reviewed. Each of those used to surface as a `KeyError` or a `ValueError`
    from `list.index` deep inside `advance` (review r5-e3) — or, for an added
    step, as nothing at all.

    Reported as a DIFF, because "the workflow changed" is not actionable and
    "added: verify; removed: spec-review" is.
    """
    recorded = set(state.steps)
    current = {s.id for s in manifest.steps}
    if recorded != current:
        added = sorted(current - recorded)
        removed = sorted(recorded - current)
        parts = []
        if added:
            parts.append(f"added: {', '.join(added)}")
        if removed:
            parts.append(f"removed: {', '.join(removed)}")
        raise RunStateError(
            f"run {state.run!r} was started against a different version of "
            f"{state.workflow!r} ({'; '.join(parts)}). A run's cursor is a position in "
            "a step list; start a new run rather than advancing this one against a "
            "list it was never computed for."
        )
    for step in manifest.steps:
        if not step.steps:
            continue
        record = state.steps.get(step.id)
        recorded_members = record.members if record is not None else None
        if recorded_members is None:
            continue  # pre-nesting run file: top-level ids match, members unknowable
        current_members = [m.id for m in step.steps]
        if recorded_members != current_members:
            added = sorted(set(current_members) - set(recorded_members))
            removed = sorted(set(recorded_members) - set(current_members))
            parts = []
            if added:
                parts.append(f"added: {', '.join(added)}")
            if removed:
                parts.append(f"removed: {', '.join(removed)}")
            raise RunStateError(
                f"run {state.run!r} was started against a different version of "
                f"{state.workflow!r} (step {step.id!r} members changed: {'; '.join(parts)}). "
                "A run's cursor is a position in a step list; start a new run rather "
                "than advancing this one against a list it was never computed for."
            )


def _with_step(state: RunState, step_id: str, record: StepRecord) -> RunState:
    new_steps = dict(state.steps)
    new_steps[step_id] = record
    return state.model_copy(update={"steps": new_steps})


def _complete_step(
    state: RunState,
    manifest: WorkflowManifest,
    step_id: str,
    outcome: Literal["done", "failed"],
    *,
    exit_code: int | None = None,
    stdout: str | None = None,
    emitted: Mapping[str, str] | None = None,
    answered_by: AnsweredBy | None = None,
) -> RunState:
    """Record `step_id`'s outcome and move the cursor — the ONE place that
    implements the done/failed cursor asymmetry, shared by `advance`'s
    `cli` branch and `resolve` (an `agent` step's outcome) rather than
    forked between them: the cursor advances to the next step on `done`,
    and stays exactly where it is on `failed` — a stalled step must stay
    the loudest thing `status`/`check` report, never slide past silently.

    **The cursor moves off the CURSOR, never relative to `step_id`** (review
    fix r2-f8). Assigning `_next_step_id(manifest, step_id)` unconditionally
    meant completing any step *behind* the cursor rewound the run to just
    after that step — a silent state corruption. Only a step that IS the
    cursor can move it; anything else records its outcome and leaves the
    cursor alone. That is correct however many steps are `running` at once,
    so it stays correct if a shape ever dispatches steps concurrently —
    which enforcing "one running step" as an invariant would have foreclosed.

    The prior record's `gate` is carried forward on `done`, and on `failed`
    it is deliberately not — which is narrower than "an operator authorizes a
    step once" (corrected in review r5-b6). `StepRecord.gate` is only ever set
    to `"cleared"` by `resolve`'s **cli** branch, which returns the step to
    `pending`; the `agent` branch below records `done`/`failed` and writes no
    `gate` at all. So a *failed* gated agent step keeps `gate: None` and
    `_gate_pending` re-asks on the next `advance`. That re-ask is correct — a
    step that failed after its gate was answered is a new question, not a
    resumption — but the claim that the gate is answered once for the life of
    the run was not true of it.

    `answered_by` is the gated **agent** branch's half of that story: those
    steps never acquire `gate: cleared` at all, so provenance is the only
    record that a gate was cleared there, and it is passed in by `resolve`.
    Absent an explicit value the prior record's is carried forward — exactly
    like `gate`, so a cleared `cli` gate's provenance survives the `advance`
    that finally executes the step.
    """
    prior = state.steps.get(step_id)
    new_record = StepRecord(
        state=outcome,
        at=_now(),
        gate=prior.gate if prior is not None else None,
        answered_by=answered_by or (prior.answered_by if prior is not None else None),
        exit=exit_code,
        stdout=stdout,
        emitted=dict(emitted) if emitted else None,
        # A completed grouped step keeps its item history and member list:
        # `status` still shows what ran, and drift still sees member edits
        # after the group is done. (Previously items were dropped here, which
        # is also why an adopted flat fan-out went blind once it completed —
        # `_fan_out_items` scans every record for exactly this.)
        items=dict(prior.items) if prior is not None and prior.items else None,
        members=list(prior.members) if prior is not None and prior.members else None,
        # …and its dispatch history, for the same reason plus one more: the
        # trail gh-503 asked for ("who was holding this phase, and when")
        # would otherwise be deleted by the very act of FINISHING. A group's
        # `dispatch` map holds EVERY phase's attempts, so the moment its last
        # member resolved, the whole run's holder history vanished — silently,
        # because the map is only ever read by `status`/`check`, which would
        # then have had nothing left to read (P4.T3.S1).
        dispatch=dict(prior.dispatch) if prior is not None and prior.dispatch else None,
    )
    new_state = _with_step(state, step_id, new_record)
    if outcome == "done" and step_id == state.cursor:
        next_id = _next_step_id(manifest, step_id)
        if next_id is not None:
            new_state = new_state.model_copy(update={"cursor": next_id})
    return new_state


def _gate_pending(step: Step, record: StepRecord) -> bool:
    """Is this step still waiting on its operator gate?

    A gate is answered by `fr run resolve` (which records `gate: cleared`),
    not by the step's lifecycle state — spec §4.A: "a pause. The step ends
    the turn and the run does not advance until the operator answers."
    """
    return step.gate == "operator" and record.gate != "cleared" and record.state != "done"


def _gate_degradation_notice() -> str | None:
    """The loud degradation notice for a blocked `gate: operator` step (spec
    §3.D.1), or `None` when the detected harness genuinely enforces it.

    Reads `os.environ` through `detect_harness` (never a hardcoded harness
    name) and the shipped matrix's `operator-gate` row through `load_matrix`
    — the notice text is built from that row's `scope_note`, so a stale or
    hand-typed string here can never drift from what `fr harness parity`
    itself declares. An UNRECOGNISED environment (`detect_harness` returns
    `None`) is treated as degraded too — fail loud, the same posture as the
    isolation gate: a wrong notice costs a confusing paragraph, a missing one
    costs a silently skipped gate.

    Raises `HarnessError` when `FR_HARNESS` is set to something outside
    `fr.harness.HARNESSES` — a typo must not silently become an inference,
    so the caller surfaces it as a command error rather than guessing.
    """
    harness = detect_harness(os.environ)
    matrix = load_matrix()
    surface = next(s for s in matrix.surfaces if s.id == "operator-gate")
    if harness is not None:
        hstate = surface.harnesses[harness]
        if hstate.state == "enforced":
            return None
        detail = f"your harness ({harness}) does not enforce this gate (state: {hstate.state})"
        if hstate.scope_note:
            detail += f" — {hstate.scope_note}"
    else:
        detail = (
            "your harness could not be detected (set FR_HARNESS to one of "
            f"{', '.join(HARNESSES)}) — treating this gate as advisory to be safe"
        )
    return (
        f"gate: {detail}.\n"
        "      Put the questions to the operator in your reply and STOP. Clearing this "
        "gate without\n"
        "      asking is recorded as `answered_by: agent` and reported in the delivered PR."
    )


def _clears_gate(step: Step, record: StepRecord, outcome: str) -> bool:
    """Does this `resolve` CLEAR an operator gate (rather than decline it, or
    resolve a step that never had one)?

    The condition provenance is recorded under, and deliberately narrow:
    `answered_by` must not claim an authorization for a step nobody gated, and
    a *declined* gate (`--state failed`) was not cleared. It reads the
    record's own state rather than `_gate_pending`, because by the time this
    runs the step is `blocked` — which is what "waiting on its gate" looks
    like once `advance` has seen it.
    """
    return step.gate == "operator" and record.state == "blocked" and outcome == "done"


def _parse_emitted(pairs: list[str], repo_root: Path, step: Step | None = None) -> dict[str, str]:
    """`--emitted name=path` pairs, validated and made repo-relative.

    **The normalization is the point** (review r5-b2). `emitted.plan` is the
    key `archive.find_run_for_plan` and `run.adopt.adoptable_plans` match a
    run to its plan by, and both compare against a repo-relative posix path.
    A stored ABSOLUTE path matches neither — verified live: it made `fr run
    adopt` create a SECOND run for a plan that already had one, and would
    have left the first behind at `fr archive`. Both are silent no-ops, which
    spec §4.B calls out as worse than failing. And an absolute path is what
    an agent following SKILL.md's `--emitted plan=<path>` produces routinely.

    Only `REPO_TRACKED_ARTIFACTS` (`spec`, `plan`) are path-normalised: `pr`
    is a URL, `report` and `journal:*` have no repo path, and rewriting those
    would be nonsense.

    Five further rules, each closing a way to record a wrong thing quietly
    (review r5-e2):

    1. **Split on the FIRST `=` only.** A path may contain `=`; splitting on
       the last, or on all, silently truncates it.
    2. **Neither half may be empty.** `plan=` records the repo root as the
       plan; `=x` records an artifact with no name.
    3. **The name must be one the step declares it `emits`.** An artifact the
       manifest never mentions is a shape/agent mismatch — the agent emitted
       something the workflow does not know about, or misspelled the name it
       does — and storing it means the run carries a key nothing will ever
       read. The refusal names the step's declared emits.
    4. **No duplicate names in one call.** `--emitted plan=a --emitted plan=b`
       silently kept `b`.
    5. **A repo-tracked artifact must EXIST.** An agent reporting a spec that
       is not on disk is precisely the silent-wrong-state case the run cursor
       exists to prevent.
    """
    result: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")  # partition splits on the FIRST `=`
        if not sep:
            raise RunStateError(f"--emitted must be 'name=path', got {pair!r}")
        name = name.strip()
        if not name:
            raise RunStateError(f"--emitted has an empty artifact name: {pair!r}")
        if not value.strip():
            raise RunStateError(f"--emitted {name}= has an empty value")
        if name in result:
            raise RunStateError(
                f"--emitted {name}= given twice ({result[name]!r} then {value!r}) — "
                "one artifact, one value"
            )
        if step is not None and name not in step.emits:
            emits = ", ".join(sorted(step.emits)) or "(nothing)"
            raise RunStateError(
                f"step {step.id!r} does not emit {name!r}; it declares: {emits}. "
                "Either the workflow shape is missing an `emits:` entry or the "
                "artifact name is misspelled."
            )
        result[name] = _repo_relative_artifact(name, value.strip(), repo_root)
    return result


def _repo_relative_artifact(name: str, value: str, repo_root: Path) -> str:
    if name not in REPO_TRACKED_ARTIFACTS:
        return value
    raw = Path(value)
    target = raw if raw.is_absolute() else repo_root / raw
    # `resolve()` on BOTH sides (review r5-e2): an fr worktree lives under
    # `~/.cache`, which on macOS is reached through `/private/var/...` — so a
    # resolved artifact path and an unresolved repo root have no common
    # prefix and `relative_to` raises on a file that is plainly inside.
    resolved_root = repo_root.resolve()
    try:
        rel = target.resolve().relative_to(resolved_root)
    except ValueError as e:
        raise RunStateError(
            f"--emitted {name}={value!r} is outside the repo ({resolved_root}) — "
            "a run records repo-relative artifact paths"
        ) from e
    if not (resolved_root / rel).exists():
        raise RunStateError(
            f"--emitted {name}={value!r} does not exist ({resolved_root / rel}). "
            "A run records artifacts that were actually written; recording one "
            "that is not there is the silent-wrong-state this cursor exists to "
            "prevent."
        )
    return rel.as_posix()


def _template_context(state: RunState) -> dict[str, str]:
    ctx = {"run.id": state.run, "run.branch": state.branch}
    for record in state.steps.values():
        if record.emitted:
            for name, value in record.emitted.items():
                ctx[f"artifacts.{name}"] = value
    return ctx


def _render_template(text: str, context: Mapping[str, str], *, quote: bool) -> str:
    """Substitute `{{ ... }}` from `context`.

    `quote=True` shell-quotes every substituted value and is mandatory for
    anything handed to a shell (review fix r2-f3). The manifest itself is
    operator-authored, but `{{ artifacts.* }}` values are not: they arrive via
    `fr run resolve --emitted name=path`, i.e. from whatever a dispatched
    agent reports. The shipped `plan-review` step is `fr plan self-review
    {{ artifacts.plan }}`, so an emitted path containing `;` or backticks was
    a command-injection seam straight through `shell=True`. Quoting at the
    substitution boundary keeps the manifest's own shell syntax (pipes,
    redirects, `&&`) working while making an interpolated value inert data.
    """

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in context:
            raise RunStateError(f"unresolved template variable: {{{{ {key} }}}}")
        value = context[key]
        return shlex.quote(value) if quote else value

    return _TEMPLATE_RE.sub(repl, text)


def _build_brief(step: Step, state: RunState) -> dict[str, Any]:
    """The dispatch brief for a `kind: agent` step — everything the harness
    needs to actually run it, and nothing fr itself executes.

    Phase 11 wires `fr-goal` onto `fr run`; it must produce/consume this
    same shape, so its keys are deliberately exhaustive of `Step`'s
    agent-relevant fields rather than a subset convenient for today's tests
    — pinned by deriving the expected key set from `Step.model_fields` in
    `test_run_cli.py`, so a future `Step` field cannot be silently omitted.

    Exhaustive means every `Step` field except two: `id` (emitted as `step`)
    and `run` (the one cli-only field — `advance` executes it; it is never
    dispatched). `kind` is carried even though a brief is only ever printed
    for an `agent` step, so the brief stays self-describing and the
    exclusion list stays at exactly the two fields that have a reason.
    `for_each` and `gate` were missing until review fix r2-f4, which made
    the brief unable to express `implement`'s whole purpose (one executor
    per phase) or the fact that a step is gated at all. `steps` carries the
    member ids of a grouped `for_each` (empty for a flat step) so the
    harness can see the per-phase loop without re-reading the manifest.
    """
    return {
        "run": state.run,
        "workflow": state.workflow,
        "step": step.id,
        "kind": step.kind,
        "skill": step.skill,
        "agent": step.agent,
        "needs": list(step.needs),
        "emits": list(step.emits),
        "gate": step.gate,
        "tier": step.tier,
        "for_each": step.for_each,
        "steps": [m.model_dump(exclude_none=True) for m in step.steps],
    }


def _effective_tier(step: Step, group: Step | None = None) -> str | None:
    """The tier a unit actually dispatches under: its own `tier:` when set,
    else its group's — `None` when neither has one. `_build_member_brief`
    and `_open_dispatch`'s `_advance_group` call site both read this ONE
    helper (P2.T1.S3) rather than each re-deriving the fallback, which is
    how the two came to duplicate it in the first place. `group=None` for a
    flat step, which has none to fall back to."""
    if step.tier is not None:
        return step.tier
    return group.tier if group is not None else None


PHASE_TIER_SENTINEL = "from_phase"
"""`Step.tier`'s one non-tier value — the shipped `fr-goal` shape's marker for
"this unit's tier is whatever the plan's phase header says".

`Step.tier` is a free `str`, not `PhaseHeader.tier`'s closed
mechanical/standard/hard Literal, precisely so a shape can say this. The
*brief* passes the sentinel through verbatim, because there it is an
instruction to the harness: look the phase up. A dispatch RECORD cannot do
that — it stores what was actually sent — so `_advance_group` resolves it
first (finding f4). Handing the sentinel straight to `fr models resolve` can
only ever miss, which is how every real fr-goal dispatch came to record
`model: null`."""


def _phase_header_tier(repo_root: Path, state: RunState, phase_n: int) -> str | None:
    """The `tier:` on plan phase `phase_n`'s header, or `None`.

    Reads the plan the same way `_accounting_snapshot` already does. Degrades
    to `None` on anything unreadable rather than raising: like accounting,
    this is observability riding along with a dispatch, and it must never be
    the reason a dispatch fails.
    """
    from fr.parser import PlanSchemaError, parse

    plan_rel = _emitted_plan(state)
    if plan_rel is None:
        return None
    try:
        plan = parse(repo_root / plan_rel)
    except (PlanSchemaError, OSError):
        return None
    return next((p.phase.tier for p in plan.phases if p.phase.number == phase_n), None)


def _dispatch_tier(repo_root: Path, state: RunState, tier: str | None, phase_n: int) -> str | None:
    """`tier` with `PHASE_TIER_SENTINEL` replaced by phase `phase_n`'s own
    tier — what a dispatch RECORD needs, as opposed to what the brief says.

    An unresolvable sentinel becomes `None`, which `_resolved_model` then
    records as an absent model: the spec §4.A rule that nothing is ever
    guessed applies to the sentinel exactly as it does to an unbound tier."""
    if tier != PHASE_TIER_SENTINEL:
        return tier
    return _phase_header_tier(repo_root, state, phase_n)


def _resolved_model(repo_root: Path, tier: str | None) -> str | None:
    """The model bound to `tier` for this machine's detected harness, via
    `fr.models.resolve` — repo config overriding user config, the same rule
    `fr models resolve` itself uses. `None` when there is no tier, no
    detected harness, or no binding for the pair: an unresolved tier leaves
    `model` absent rather than guessed (spec §4.A / P2.T1.S2).

    `PHASE_TIER_SENTINEL` is refused here as well as resolved upstream in
    `_dispatch_tier`. Callers with no phase in hand — a flat `kind: agent`
    step — have nothing to resolve it against, and without this guard a
    models.yaml that happened to carry a `from_phase:` key would bind it,
    turning a sentinel into a model name by coincidence."""
    if tier is None or tier == PHASE_TIER_SENTINEL:
        return None
    harness = detect_harness(os.environ)
    if harness is None:
        return None
    from fr.commands.models_cmd import REPO_MODELS_REL
    from fr.models import default_models_path, load_models
    from fr.models import resolve as resolve_model

    repo_cfg = load_models(repo_root / REPO_MODELS_REL)
    user_cfg = load_models(default_models_path())
    return resolve_model(harness, tier, repo_cfg=repo_cfg, user_cfg=user_cfg)


def _open_dispatch(
    state: RunState,
    step_id: str,
    key: str,
    *,
    agent_type: str | None,
    tier: str | None,
    repo_root: Path,
) -> RunState:
    """Append a new `DispatchRecord` opening `key`'s hold under `step_id`.

    Spec §4.B.1: called exactly when `advance` moves a unit to `running` —
    from BOTH `_advance_group`'s write-claim and the flat `kind: agent`
    branch, and only on the actual transition (both call sites already guard
    on that). Never called from `_gate_pending`: a gated step is marked
    `blocked`, not `running`, so nothing was dispatched and there is nothing
    to hold.
    """
    record = state.steps[step_id]
    dispatch = dict(record.dispatch or {})
    attempts = list(dispatch.get(key, []))
    attempts.append(
        DispatchRecord(
            dispatched=_now(),
            agent_type=agent_type,
            model=_resolved_model(repo_root, tier),
        )
    )
    dispatch[key] = attempts
    new_record = record.model_copy(update={"dispatch": dispatch})
    return _with_step(state, step_id, new_record)


def _dispatch_needs_open(record: StepRecord, key: str) -> bool:
    """Should `advance` append a fresh `DispatchRecord` for `key`?

    True when nothing has been recorded for it yet, or its last attempt is
    CLOSED (`returned` is not `None`) — an abandoned (`fr run claim
    --abandoned`) or failed-and-retried unit is not currently held, so
    re-dispatching it opens a NEW hold rather than silently leaving the old,
    closed one as the only record. False while the last attempt is still
    OPEN — the unit is currently HELD, which `advance` refuses to dispatch
    over (`_refuse_held`, spec §4.C / gh-499) unless `--redispatch` says so.

    This is the ONE notion of "is this unit currently held?" in the module:
    `advance`'s refusal, `--redispatch`'s abandon and `resolve`'s close all
    ask it here rather than each re-deriving "the last record is open".
    """
    attempts = (record.dispatch or {}).get(key)
    if not attempts:
        return True
    return attempts[-1].returned is not None


def _held_record(record: StepRecord, key: str) -> DispatchRecord | None:
    """`key`'s OPEN `DispatchRecord`, or `None` when the unit is free.

    The read half of `_dispatch_needs_open` — same predicate, but handing
    back the holder so a caller can name it. `validate_run` guarantees at
    most one open record per unit and that it is the LAST element, so the
    tail is the whole answer."""
    if _dispatch_needs_open(record, key):
        return None
    return (record.dispatch or {})[key][-1]


def _refuse_held(
    owner_id: str,
    key: str,
    held: DispatchRecord,
    *,
    run_id: str,
    step_flag: str,
    item_flag: str | None,
) -> NoReturn:
    """Refuse to re-brief a unit somebody is already holding — gh-499, exit 2.

    ONE function for both the flat and the grouped path, so the two cannot
    drift: the single thing gh-499 asks for is that fr stop handing out "a
    dispatch brief that looks like an instruction to act when the correct
    action is to wait", and a message that says so on one path only is the
    same defect with a smaller blast radius. Nothing of the brief is printed
    alongside it, for exactly that reason.

    Wording follows spec §4.C, which in turn follows gh-499's own "Expected"
    block — including its `anyway`, which carries the one thing a bare
    `--redispatch` label does not: that re-briefing over a live holder is a
    deliberate act, not the next step.

    The three ways forward are printed as complete, copy-pastable commands
    carrying THIS unit's own `--step`/`--item`, because an operator who is
    being refused is exactly the reader with no appetite for reconstructing
    a unit key by hand.
    """
    holder = f"agent {held.agent}" if held.agent else "an unclaimed agent"
    descriptors = [d for d in (held.agent_type, held.harness) if d]
    suffix = f" ({', '.join(descriptors)})" if descriptors else ""
    unit = f"--step {step_flag}" + (f" --item {item_flag}" if item_flag else "")
    err_console.print(
        f"[red]{owner_id}: {key} is ALREADY HELD\n"
        f"  by {holder}{suffix}\n"
        f"  dispatched {held.dispatched} — not yet returned.\n"
        "  Waiting on that agent — do NOT dispatch again.\n"
        f"  Resolve it:      fr run resolve {run_id} {unit} --state done|failed\n"
        f"  Lost agent:      fr run claim {run_id} {unit} --abandoned\n"
        f"  Re-brief anyway: fr run advance {run_id} --redispatch[/red]",
        soft_wrap=True,
    )
    raise typer.Exit(2)


def _replace_last_attempt(record: StepRecord, key: str, attempt: DispatchRecord) -> StepRecord:
    """`record` with `key`'s LAST dispatch attempt replaced by `attempt`.

    The one mutation shape every dispatch write shares — `claim`'s identity
    fill, `claim --abandoned`, `--redispatch`'s abandon and `resolve`'s close
    all rewrite exactly the tail element, because `validate_run` requires the
    open record to BE the tail. Copying the dicts/lists keeps the frozen
    models honest."""
    dispatch = dict(record.dispatch or {})
    attempts = list(dispatch[key])
    attempts[-1] = attempt
    dispatch[key] = attempts
    return record.model_copy(update={"dispatch": dispatch})


def _close_dispatch(record: StepRecord, key: str, outcome: DispatchOutcome) -> StepRecord:
    """Close `key`'s open dispatch: `returned` = now, `outcome` = `outcome`.

    `DispatchRecord` enforces that the two are one fact, so they are written
    in one `model_copy` and never separately. Callers must have established
    that the unit IS held (`_held_record` / `_open_dispatch_record`); this
    helper does not re-derive it, so there is still exactly one place that
    decides what "open" means."""
    return _replace_last_attempt(
        record,
        key,
        (record.dispatch or {})[key][-1].model_copy(
            update={"returned": _now(), "outcome": outcome}
        ),
    )


def _claimed_identity(
    open_record: DispatchRecord,
    key: str,
    *,
    agent: str,
    harness: str | None,
    model: str | None,
) -> DispatchRecord:
    """`open_record` carrying the orchestrator's reported identity, or refuse.

    Shared by `fr run claim` (the eager report) and `fr run resolve`'s late
    fallback (decision d2), so a *second* agent id can never be attached to a
    dispatch by taking the other route. Re-reporting the SAME id is
    idempotent and may refresh `harness`/`model`; a DIFFERENT one is refused
    naming both, because two ids on one hold is the two-writers hazard this
    whole feature exists to make visible."""
    if open_record.agent is not None and open_record.agent != agent:
        err_console.print(
            f"[red]{key}: already claimed by {open_record.agent!r} — refusing to "
            f"attribute it to {agent!r} as well. The worktree has exactly one "
            "writer; close the first claim (`fr run resolve ... --state "
            "done|failed`, or `fr run claim ... --abandoned`) before naming a "
            "second.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    return open_record.model_copy(
        update={
            "agent": agent,
            "harness": harness if harness is not None else open_record.harness,
            "model": model if model is not None else open_record.model,
        }
    )


def _close_on_resolve(
    state: RunState,
    owner_id: str,
    key: str,
    outcome: DispatchOutcome,
    *,
    agent: str | None,
    harness: str | None,
    model: str | None,
) -> RunState:
    """`resolve`'s half of the dispatch pair: close `key`'s open record with
    `outcome`, optionally attaching a late identity first (spec §4.C).

    **Silent when there is nothing open** — and that is the requirement, not
    a shortcut. A run `fr run adopt`ed from a plan on disk has no dispatch
    history at all, and a `gate: operator` step is marked `blocked` without
    ever being dispatched; neither may start failing to resolve because this
    feature landed. Nothing is invented for them either: an absent record
    stays absent rather than being back-filled with a dispatch fr never made.

    A record that is already CLOSED (`claim --abandoned`) is likewise left
    exactly as it is — `abandoned` is what happened to that attempt, and
    overwriting it with this resolve's outcome would erase the one fact the
    operator recorded by hand.
    """
    record = state.steps[owner_id]
    if _dispatch_needs_open(record, key):
        return state
    open_record = (record.dispatch or {})[key][-1]
    if agent is not None:
        open_record = _claimed_identity(open_record, key, agent=agent, harness=harness, model=model)
    elif harness is not None or model is not None:
        open_record = open_record.model_copy(
            update={
                "harness": harness if harness is not None else open_record.harness,
                "model": model if model is not None else open_record.model,
            }
        )
    record = _replace_last_attempt(record, key, open_record)
    return _with_step(state, owner_id, _close_dispatch(record, key, outcome))


def _build_member_brief(member: Step, group: Step, item: str, state: RunState) -> dict[str, Any]:
    """The dispatch brief for one `(phase, member)` unit of a grouped step.

    Same keys as the step brief (so a harness parses one shape) plus `group`
    (the fan-out step's id) and `item` (the `phase/<n>` unit). `tier` and
    `for_each` fall back to the group's when the member leaves them unset —
    the common case, where the group declares the dispatch policy once.
    """
    return {
        "run": state.run,
        "workflow": state.workflow,
        "step": member.id,
        "group": group.id,
        "item": item,
        "kind": member.kind,
        "skill": member.skill,
        "agent": member.agent,
        "needs": list(member.needs),
        "emits": list(member.emits),
        "gate": member.gate,
        "tier": _effective_tier(member, group),
        "for_each": group.for_each,
        "steps": [],
    }


def _advance_group(
    repo_root: Path,
    state: RunState,
    manifest: WorkflowManifest,
    step: Step,
    record: StepRecord,
    *,
    redispatch: bool = False,
) -> None:
    """Dispatch the next pending `(phase, member)` unit of a grouped step.

    The cursor stays on the group while any unit is outstanding; `resolve`
    records each unit, and the group completes (cursor advances) only when
    every expected `phase/<n>/<member>` key is done. A group with nothing
    pending but no `done` record (every unit resolved before this build
    learned members) completes here rather than dispatching thin air.
    """
    try:
        phases = _group_phases(repo_root, state)
    except (RunStateError, AdoptError) as e:
        err_console.print(f"[red]{step.id}: {e}[/red]", soft_wrap=True)
        raise typer.Exit(2) from e
    expected = _expected_group_items(step, phases)
    items = dict(record.items or {})
    pending = next((key for key in expected if items.get(key) != "done"), None)
    if pending is None:
        save_run_state(repo_root, _complete_step(state, manifest, step.id, "done"))
        console.print(f"{step.id}: done (all {len(expected)} phase members done)")
        return
    item, _, member_id = pending.rpartition("/")
    member = next(m for m in step.steps if m.id == member_id)
    phase_n = int(item.rsplit("/", 1)[-1])
    snaps = dict(state.accounting or {})
    snaps[pending] = _accounting_snapshot(repo_root, state, phase_n)
    items = dict(record.items or {})
    # The write-claim: this unit is now outstanding. A resolve for any OTHER
    # unit while it is running is a second writer — refused in `_resolve_member`.
    # Unconditional (not setdefault): a retried failed unit is running again,
    # not still failed.
    items[pending] = "running"
    # `dispatch` reopens independently of `items`/`state`: an `--abandoned`
    # unit leaves BOTH unchanged (still "running") so its hold looks
    # unchanged to this comparison, yet its last dispatch record is CLOSED —
    # exactly the case a fresh hold must open a new record for
    # (`_dispatch_needs_open`).
    held = _held_record(record, pending)
    if held is not None:
        if not redispatch:
            _refuse_held(
                step.id,
                pending,
                held,
                run_id=state.run,
                step_flag=member.id,
                item_flag=item,
            )
        record = _close_dispatch(record, pending, "abandoned")
        state = _with_step(state, step.id, record)
    needs_dispatch = _dispatch_needs_open(record, pending)
    if record.state != "running" or record.items != items:
        record = record.model_copy(update={"state": "running", "at": _now(), "items": items})
        state = _with_step(state, step.id, record)
    if needs_dispatch:
        state = _open_dispatch(
            state,
            step.id,
            pending,
            agent_type=member.agent,
            tier=_dispatch_tier(repo_root, state, _effective_tier(member, step), phase_n),
            repo_root=repo_root,
        )
    save_run_state(repo_root, state.model_copy(update={"accounting": snaps}))
    console.print(f"{step.id}: dispatch brief ({pending})", soft_wrap=True)
    console.print(json.dumps(_build_member_brief(member, step, item, state), sort_keys=True))


def _existing_run_for_workflow(repo_root: Path, workflow: str, branch: str) -> str | None:
    """The id of a run on `branch` already driving `workflow`, if any.

    Compares `state.branch` rather than trusting the workspace to stand in for
    it. The previous version scanned every run file in the workspace on the
    reasoning that "`fr run start` writes the run inside the isolation worktree
    for `--branch`, so every run file here belongs to that branch by
    construction" — true of runs CREATED here, false of runs INHERITED here. A
    workspace is a fresh checkout of `origin/main`, so it carries every cursor
    ever merged and not yet archived, and one merged `fr-goal` cursor therefore
    refused every subsequent `fr-goal` run in the repo: the shape worked exactly
    once between archives. The refusal even named the new branch as the one that
    "already has a run".

    Found by Test Plan item 1 of the 2026-09-18 harness-parity work, running
    `/fr-goal` on OpenCode against a clean branch — post-merge testing catching
    what CI structurally could not, since every unit fixture creates its runs in
    the workspace and so satisfies the false assumption by construction.
    """
    runs_dir = repo_root / RUNS_REL
    if not runs_dir.is_dir():
        return None
    for candidate in sorted(runs_dir.glob("*.yaml")):
        try:
            state = parse_run_state(candidate.read_text())
        except (RunStateError, OSError):
            continue  # a broken run file is a different problem
        if state.workflow.split("@", 1)[0] == workflow and state.branch == branch:
            return state.run
    return None


@run_app.command("start")
def start_cmd(
    workflow: str = typer.Argument(..., help="Workflow shape name (resolved repo > shipped)."),
    branch: str = typer.Option(..., "--branch", help="Branch this run operates on."),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Override the derived run id (default: date + sanitized branch)."
    ),
) -> None:
    """Start a run: resolve the shape, ensure isolation, write run state in it.

    Isolation is a PRECONDITION, not the run's first step (spec §4.B, review
    fix r2-f5): the run file is written inside the workspace for `--branch`,
    because that is where every later step runs and the only place the file
    is on the feature branch. See `fr.run.workspace`.

    The shape is resolved BEFORE isolation is ensured, so a typo'd shape name
    fails without provisioning a worktree or starting a container.
    """
    repo_root = resolve_repo_root()
    try:
        manifest = resolve_workflow(workflow, repo_root)
    except WorkflowError as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e
    if not manifest.steps:
        err_console.print(f"[red]workflow {workflow!r} has no steps[/red]")
        raise typer.Exit(2)
    # Validate the RESOLVED manifest before provisioning anything (review
    # r5-b6). `fr workflow check` was opt-in, so a repo-authored shape with a
    # dangling `needs`, a cycle, or a `kind: cli` step carrying no `run:`
    # started a run — and a `cli` step with no command exits 0, i.e. a green
    # step that did nothing. Cheap, and it runs before isolation is ensured,
    # so a bad shape costs no worktree and no container.
    shape_errors = check_workflow(manifest)
    if shape_errors:
        err_console.print(f"[red]workflow {workflow!r} is not valid:[/red]")
        for err in shape_errors:
            err_console.print(f"  {err}", soft_wrap=True)
        raise typer.Exit(2)

    try:
        workspace = ensure_run_workspace(repo_root, branch)
    except RunWorkspaceError as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    if workspace.resolve() != repo_root.resolve():
        # RE-RESOLVE inside the workspace (review r5-e3). The first resolution
        # is a cheap name check, done before anything is provisioned so a typo
        # costs no worktree; but `advance` runs in the WORKSPACE, and a repo
        # override lives at `docs/superpowers/workflows/<name>.yaml` — which is
        # a different file in the base clone and in the worktree. Starting
        # against one and advancing against the other is the "manifest changed
        # under the run" case, arranged by fr itself.
        try:
            manifest = resolve_workflow(workflow, workspace)
        except WorkflowError as e:
            err_console.print(f"[red]{e}[/red]")
            raise typer.Exit(2) from e
        shape_errors = check_workflow(manifest)
        if shape_errors:
            err_console.print(f"[red]workflow {workflow!r} is not valid in {workspace}:[/red]")
            for err in shape_errors:
                err_console.print(f"  {err}", soft_wrap=True)
            raise typer.Exit(2)

    try:
        # `--run-id` is operator input and becomes a path segment
        # (`runs/<id>.yaml`) plus a §4.D item-id segment. Unvalidated,
        # `--run-id ../../../escaped` exited 0 and wrote outside `runs/`
        # (review r5-b1). `derive_run_id` already flattens `/`, so this only
        # ever fires on an explicit override.
        rid = validate_run_id(run_id) if run_id else derive_run_id(branch)
    except RunStateError as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e
    path = run_path(workspace, rid)
    # The case check runs FIRST so its (more informative) message wins on both
    # kinds of filesystem: on macOS/APFS `path.exists()` is already true for a
    # case-variant, and "run 'Run-1' already exists" would leave the operator
    # hunting for a file that is spelled differently.
    collision = existing_run_id_colliding_with(workspace, rid)
    if collision is not None:
        # macOS/APFS and Windows are case-insensitive, so `Run-1` and `run-1`
        # are ONE file there and two on Linux (review r5-e1). Refusing makes
        # the behaviour identical everywhere, and matches the intuition that
        # two ids differing only by case are one id with a typo.
        err_console.print(
            f"[red]run {collision!r} already exists and differs from {rid!r} only by "
            "case; on a case-insensitive filesystem these are the same file[/red]"
        )
        raise typer.Exit(2)
    if path.exists():
        err_console.print(f"[red]run {rid!r} already exists at {path}[/red]")
        raise typer.Exit(2)
    existing = _existing_run_for_workflow(workspace, manifest.workflow, branch)
    if existing is not None:
        # A second `start` on the same branch and shape is nearly always a
        # mistake — a re-run after a wedge, or a forgotten in-flight run
        # (review r5-e5). Both have better answers than a duplicate cursor.
        err_console.print(
            f"[red]branch {branch!r} already has a {manifest.workflow!r} run: {existing}[/red]"
        )
        err_console.print(
            f"  inspect it:  fr run status {existing}\n"
            f"  resume it:   fr run advance {existing}\n"
            "  or start a differently-named shape, or delete that run file.",
            soft_wrap=True,
        )
        raise typer.Exit(2)

    steps = {
        s.id: StepRecord(state="pending", members=[m.id for m in s.steps] or None)
        for s in manifest.steps
    }
    state = RunState(
        schema_version=current_run_schema_version(),
        run=rid,
        workflow=f"{manifest.workflow}@{manifest.schema_version}",
        branch=branch,
        started=_now(),
        cursor=manifest.steps[0].id,
        steps=steps,
    )
    save_run_state(workspace, state)
    console.print(f"started run {rid} ({state.workflow}) — cursor: {state.cursor}")
    # soft_wrap: rich would fold a long worktree path across lines and break
    # the operator's copy-paste (same reason `commands/common.py` uses a plain
    # echo for its `fr migrate dirs` hint).
    console.print(
        f"workspace: {workspace} — run every later `fr run` command from there",
        soft_wrap=True,
    )


@run_app.command("adopt")
def adopt_cmd(
    target: Path = typer.Argument(
        ..., help="Plan folder to adopt (or the spec, when no plan exists yet)."
    ),
    branch: str | None = typer.Option(
        None, "--branch", help="Branch this run operates on (default: the checked-out one)."
    ),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Override the derived run id (default: date + sanitized branch)."
    ),
    workflow: str | None = typer.Option(
        None, "--workflow", help="Shape to adopt against (default: fr-goal)."
    ),
    pr: str | None = typer.Option(
        None, "--pr", help="URL of the PR delivering this work, if one is already open."
    ),
) -> None:
    """Give in-flight work a run cursor, inferred from artifacts that exist.

    The other half of the 2026-08-30 artifact-migration framework (§3.E): the
    installed fr changes under work already under way, and `fr run start` would
    put the cursor at step one with the spec and plan already written. Adoption
    reads what is on disk instead — spec only, plan with no phase complete, some
    phases complete, all complete, a PR already open — and lands the cursor on
    the step that state implies, recording the emitted spec and plan so
    archival keys on them afterwards.

    Explicit by design. `fr migrate artifacts` *reports* which plans could be
    adopted, and adopts only with `--adopt`; nothing creates a run as a side
    effect of an unrelated command.
    """
    repo_root = resolve_repo_root()
    notes: list[str] = []
    try:
        state = adopt_run(
            repo_root,
            target,
            branch=branch,
            run_id=run_id,
            workflow=workflow,
            pr_url=pr,
            notes=notes,
        )
    except AdoptError as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    console.print(f"adopted run {state.run} ({state.workflow}) \u2014 cursor: {state.cursor}")
    done = [sid for sid, rec in state.steps.items() if rec.state == "done"]
    if done:
        console.print(f"  already done: {', '.join(done)}")
    items = _fan_out_items(state)
    if items:
        complete = [k for k, v in items.items() if v == "done"]
        # Grouped fan-out keys (`phase/<n>/<member>`) count member outcomes,
        # not phases — label them honestly so "3/3" never reads as reviewed.
        unit = "phase members" if any(k.count("/") >= 2 for k in items) else "phases"
        console.print(f"  {len(complete)}/{len(items)} {unit} complete")
    for note in notes:
        console.print(f"  {note}", soft_wrap=True)
    console.print(f"  advance it with: fr run advance {state.run}", soft_wrap=True)


def _fan_out_items(state: RunState) -> dict[str, str]:
    """The per-phase items of the step that fans out — NOT of the cursor.

    `build_run_state` attaches `items` to the `for_each: phase` step
    (`implement` in the shipped fr-goal shape), and adoption deliberately moves
    the cursor PAST it when every phase is done. Reading the cursor's record
    therefore made "N/M phases complete" vanish for `review` and `deliver` —
    the two cases where the answer is most worth printing. At most one step
    fans out, so scanning for the record that carries items needs no knowledge
    of the workflow's step names.
    """
    for record in state.steps.values():
        if record.items:
            return dict(record.items)
    return {}


def _load_or_exit(repo_root: Path, run_id: str) -> RunState:
    """Load a run, or exit 2 naming the FILE (review r5-e3).

    Every `fr run` subcommand needs this and each did it slightly differently.
    A missing or unparseable run file is an ordinary operator situation — a
    typo'd id, a half-written file, a bad merge — and must never be a
    traceback; `RunStateError` already carries the path.
    """
    try:
        return load_run_state(repo_root, run_id)
    except RunStateError as e:
        err_console.print(f"[red]{e}[/red]", soft_wrap=True)
        raise typer.Exit(2) from e
    except OSError as e:  # pragma: no cover — unreadable file
        err_console.print(
            f"[red]cannot read {run_path(repo_root, run_id)}: {e}[/red]", soft_wrap=True
        )
        raise typer.Exit(2) from e


def _dispatch_holder_label(attempt: DispatchRecord) -> str:
    """Who to name for `attempt` — the priority spec §4.B.1/§4.C both rely on.

    `agent_type is None` means an orchestrator-run `kind: agent` step (the
    manifest's own `agent: null`): that is not a missing value, it is the
    orchestrator doing the work itself, and it never reports an `agent` id
    for itself. Only once a unit IS dispatched to an actual agent type does
    an absent `agent` read as `an unclaimed agent` — the same distinction
    `_refuse_held` already draws for the gh-499 refusal.
    """
    if attempt.agent_type is None:
        return "the orchestrator"
    if attempt.agent is not None:
        return f"agent {attempt.agent}"
    return "an unclaimed agent"


def _dispatch_descriptor_suffix(attempt: DispatchRecord) -> str:
    descriptors = [d for d in (attempt.harness, attempt.model) if d]
    return f" ({', '.join(descriptors)})" if descriptors else ""


def _render_dispatch_attempt(attempt: DispatchRecord) -> str:
    """One `DispatchRecord` as a line of `fr run status`/`fr run check`
    prose — spec §4.C's illustration, cases (a)-(d) of P5.T1.S1."""
    who = _dispatch_holder_label(attempt)
    suffix = _dispatch_descriptor_suffix(attempt)
    if attempt.returned is None:
        if attempt.agent_type is None:
            return f"held by the orchestrator{suffix} since {attempt.dispatched}"
        return f"HELD BY {who}{suffix} since {attempt.dispatched}"
    return f"{who}{suffix} {attempt.dispatched} -> {attempt.returned} {attempt.outcome}"


def _render_unit_dispatch(record: StepRecord, key: str, *, indent: str, console: Console) -> None:
    """Every attempt recorded for `key`, oldest first (case (e))."""
    for attempt in (record.dispatch or {}).get(key, []):
        console.print(f"{indent}{_render_dispatch_attempt(attempt)}", soft_wrap=True)


def _render_step_and_items(state: RunState, console: Console) -> None:
    """The step/items renderer — unchanged in shape from before this phase
    when a run carries no dispatch data (case (f)): the dispatch lines are
    additive, never a replacement for the existing `items` line."""
    for step_id, record in state.steps.items():
        console.print(f"  {step_id}: {record.state}")
        if record.items:
            for key in sorted(record.items):
                console.print(f"    {key}: {record.items[key]}")
                _render_unit_dispatch(record, key, indent="      ", console=console)
        if record.dispatch:
            for key in sorted(record.dispatch):
                if record.items and key in record.items:
                    continue  # already rendered nested under its `items` line
                console.print(f"    {key}:")
                _render_unit_dispatch(record, key, indent="      ", console=console)


def _render_accounting(state: RunState, console: Console) -> None:
    if not state.accounting:
        return
    console.print("  accounting (context sizes; ~tok figures use a 4 chars/token estimate):")
    total = 0
    for key in sorted(state.accounting):
        snap = state.accounting[key]
        chars = snap.handoff_chars + snap.spec_bytes + snap.plan_bytes
        total += chars
        console.print(
            f"    {key}: journal {snap.journal_entries} entries/"
            f"{snap.journal_lines} lines, handoff {snap.handoff_chars} chars, "
            f"spec+plan {snap.spec_bytes + snap.plan_bytes} chars "
            f"(~{chars // 4} tok est)"
        )
    console.print(f"    total: {total} chars (~{total // 4} tok est)")


@run_app.command("status")
def status_cmd(run_id: str = typer.Argument(..., help="Run id.")) -> None:
    """Print the cursor, every step's state, and — since phase 5 — who is
    holding each dispatched unit, since when, and whether it has returned
    (spec §4.C)."""
    repo_root = resolve_repo_root()
    state = _load_or_exit(repo_root, run_id)

    console.print(f"run: {state.run}")
    console.print(f"workflow: {state.workflow}")
    console.print(f"branch: {state.branch}")
    console.print(f"cursor: {state.cursor}")
    _render_step_and_items(state, console)
    _render_accounting(state, console)


@run_app.command("advance")
def advance_cmd(
    run_id: str = typer.Argument(..., help="Run id."),
    redispatch: bool = typer.Option(
        False,
        "--redispatch",
        help="Re-brief a unit that is ALREADY HELD: close its open dispatch "
        "`abandoned` and append a fresh one. The deliberate escape for a "
        "genuinely lost agent (gh-499) — the old holder stays in the unit's "
        "list, which is the forensic trail. On a unit nobody holds this "
        "changes nothing.",
    ),
) -> None:
    """Advance the cursor by one step.

    `kind: cli` executes directly (exit code + stdout captured; cursor
    moves only on success). `kind: agent` is NEVER executed — it emits a
    dispatch brief and marks itself `running`. A `gate: operator` step whose
    gate is unanswered marks `blocked` and executes nothing; an `agent` step
    still prints its brief there, since the gate stops the run, not the
    harness's view of what the step is. `fr run resolve` answers the gate.

    A unit somebody is ALREADY HOLDING is refused — exit 2, and no brief of
    any kind (gh-499, where an identical second brief read as an instruction
    to dispatch a second `fr-phase-executor` into the one worktree the first
    was already writing). `--redispatch` is the deliberate escape.
    """
    repo_root = resolve_repo_root()
    try:
        state = load_run_state(repo_root, run_id)
        manifest = _resolve_manifest_for_state(repo_root, state)
        step = _step_by_id(manifest, state.cursor)
    except (RunStateError, WorkflowError, AdoptError) as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    record = state.steps.get(state.cursor)
    if record is None:
        # Every other lookup in this module is guarded; this one was not, so a
        # manifest that gained a step after `fr run start` tracebacked instead
        # of reporting something an operator could act on (review fix r2-f7).
        err_console.print(
            f"[red]run {state.run!r} has no record for its cursor step "
            f"{state.cursor!r} — workflow {state.workflow!r} changed after "
            "`fr run start`; start a new run[/red]"
        )
        raise typer.Exit(2)

    if record.state == "done" and _next_step_id(manifest, state.cursor) is None:
        # The run is finished: the cursor sits on the LAST step and that step
        # is done. Without this, one more `advance` flipped the last step from
        # `done` back to `running` (verified live, review r5-b3) — and for a
        # `cli` last step it would have RE-EXECUTED the command, after
        # `fr run check` had already exited 0. Nothing is written here; a
        # finished run is read-only until something else moves it.
        console.print(f"run {state.run} complete — cursor {state.cursor!r} is done")
        return

    if _gate_pending(step, record):
        if record.state != "blocked":
            new_record = record.model_copy(update={"state": "blocked", "at": _now()})
            save_run_state(repo_root, _with_step(state, state.cursor, new_record))
        # soft_wrap on both: the gate line ends in a command the operator
        # copy-pastes, and the brief is JSON a harness parses off stdout —
        # rich's default folding would break a long token mid-string and
        # produce invalid JSON.
        console.print(
            f"{step.id}: blocked on operator gate — answer it, then "
            f"`fr run resolve {state.run} --step {step.id} --state done`",
            soft_wrap=True,
        )
        # spec §3.D.1: printed BEFORE the agent brief (below), not after — the
        # brief is a single JSON line a harness parses off stdout, and this
        # notice must not become the last line a naive `tail -1` reads.
        try:
            notice = _gate_degradation_notice()
        except HarnessError as e:
            err_console.print(f"[red]{e}[/red]", soft_wrap=True)
            raise typer.Exit(2) from e
        if notice is not None:
            console.print(notice, soft_wrap=True)
        # A gate stops the RUN, not the harness's view of the step: an `agent`
        # step still prints its brief here, because the skill/agent named in it
        # is how the operator's question gets asked in the first place. Nothing
        # is executed either way — a `cli` step's side effect is exactly what
        # the gate is guarding.
        if step.kind == "agent":
            console.print(json.dumps(_build_brief(step, state), sort_keys=True), soft_wrap=True)
        return

    if step.kind == "agent":
        if step.steps:
            _advance_group(repo_root, state, manifest, step, record, redispatch=redispatch)
            return
        brief = _build_brief(step, state)
        key = _unit_key(repo_root, state, step, None, None)
        held = _held_record(record, key)
        if held is not None:
            if not redispatch:
                _refuse_held(
                    step.id, key, held, run_id=state.run, step_flag=step.id, item_flag=None
                )
            record = _close_dispatch(record, key, "abandoned")
            state = _with_step(state, state.cursor, record)
        needs_dispatch = _dispatch_needs_open(record, key)
        if record.state != "running" or needs_dispatch:
            if record.state != "running":
                new_record = record.model_copy(update={"state": "running", "at": _now()})
                state = _with_step(state, state.cursor, new_record)
            if needs_dispatch:
                state = _open_dispatch(
                    state,
                    state.cursor,
                    key,
                    agent_type=step.agent,
                    tier=step.tier,
                    repo_root=repo_root,
                )
            save_run_state(repo_root, state)
        console.print(f"{step.id}: dispatch brief")
        console.print(json.dumps(brief, sort_keys=True), soft_wrap=True)
        return

    # kind == "cli"
    context = _template_context(state)
    try:
        command = _render_template(step.run or "", context, quote=True)
    except RunStateError as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    if not command.strip():
        # `subprocess.run("", shell=True)` exits 0, so an omitted `run:` used
        # to report a green step that did nothing (review fix r2-f2).
        # `check_workflow` rejects the authored form; this catches the
        # hand-built manifest and the template that renders to nothing.
        err_console.print(
            f"[red]{step.id}: kind: cli with no `run:` command — a cli step's "
            "exit code is its verdict, so there is nothing to be the verdict[/red]"
        )
        raise typer.Exit(2)

    proc = subprocess.run(  # noqa: S602 — manifest is operator-authored; values are shlex-quoted
        command, shell=True, cwd=repo_root, capture_output=True, text=True
    )
    if proc.returncode == 0:
        new_state = _complete_step(
            state, manifest, state.cursor, "done", exit_code=0, stdout=proc.stdout
        )
        save_run_state(repo_root, new_state)
        console.print(f"{step.id}: done (exit 0)")
    else:
        new_state = _complete_step(
            state, manifest, state.cursor, "failed", exit_code=proc.returncode, stdout=proc.stdout
        )
        save_run_state(repo_root, new_state)
        err_console.print(f"{step.id}: failed (exit {proc.returncode})")
        raise typer.Exit(1)


def _resolve_member(
    repo_root: Path,
    state: RunState,
    manifest: WorkflowManifest,
    *,
    member: Step,
    group: Step,
    item: str | None,
    state_value: Literal["done", "failed"],
    emitted_map: dict[str, str],
    agent: str | None = None,
    harness: str | None = None,
    model: str | None = None,
) -> None:
    """Record one `(phase, member)` outcome on its group's item map.

    The group completes — via the same `_complete_step` cursor asymmetry as
    every other step — only when every expected `phase/<n>/<member>` key is
    done; a `failed` unit fails the group at once and holds the cursor, same
    as a failed step. Whole-group completion (`resolve --step <group>`) stays
    available for harnesses that do not address members.
    """
    grec = state.steps.get(group.id)
    if grec is None:  # pragma: no cover — drift guarantees top-level records
        err_console.print(f"[red]{group.id}: no step record in run {state.run!r}[/red]")
        raise typer.Exit(2)
    if grec.state == "done":
        err_console.print(
            f"[red]{group.id}: already done — re-resolving it does nothing. "
            "Pass --emitted to amend the artifacts it recorded.[/red]"
        )
        raise typer.Exit(2)
    if grec.state not in ("running", "blocked"):
        err_console.print(
            f"[red]{group.id}: not running (state={grec.state!r}) — advance "
            "the group first, then resolve its members[/red]"
        )
        raise typer.Exit(2)
    key = _unit_key(repo_root, state, member, group, item)
    # `_unit_key` already validated `key` against the expected set; recomputed
    # here (cheap, and already proven readable) only to know when EVERY
    # expected key is done, which is a different question than "is this ONE
    # key valid".
    expected = _expected_group_items(group, _group_phases(repo_root, state))
    items = dict(grec.items or {})
    if items.get(key) == "done" and state_value == "done":
        err_console.print(f"[red]{key}: already recorded done[/red]")
        raise typer.Exit(2)
    # One writer at a time: any OTHER outstanding unit means a second writer
    # is active (a finished executor still writing, or the orchestrator
    # alongside it) — resolve the running unit first instead of interleaving.
    running = sorted(k for k, v in items.items() if v == "running" and k != key)
    if running:
        err_console.print(
            f"[red]{key}: refused — {running[0]} is still running. The worktree "
            "has exactly one writer; resolve the running unit first.[/red]"
        )
        raise typer.Exit(2)
    items[key] = state_value
    merged_emitted = {**(grec.emitted or {}), **emitted_map}
    updated = _with_step(
        state,
        group.id,
        grec.model_copy(update={"items": items, "emitted": merged_emitted or None}),
    )
    # The dispatch closes BEFORE `_complete_step` runs, so the closed record
    # is what that rebuild carries forward — and before the `failed` branch
    # too, because a failed unit's holder returned just as surely as a done
    # one's did.
    updated = _close_on_resolve(
        updated, group.id, key, state_value, agent=agent, harness=harness, model=model
    )
    if state_value == "failed":
        save_run_state(repo_root, _complete_step(updated, manifest, group.id, "failed"))
        console.print(f"{member.id} {item}: failed")
        return
    if all(items.get(k) == "done" for k in expected):
        save_run_state(
            repo_root, _complete_step(updated, manifest, group.id, "done", emitted=merged_emitted)
        )
        console.print(f"{group.id}: done (all {len(expected)} phase members done)")
        return
    save_run_state(repo_root, updated)
    console.print(f"{member.id} {item}: done")


@run_app.command("resolve")
def resolve_cmd(
    run_id: str = typer.Argument(..., help="Run id."),
    step_id: str = typer.Option(..., "--step", help="Step id to resolve (must be `running`)."),
    state_value: str = typer.Option(..., "--state", help="done | failed."),
    emitted: list[str] = typer.Option(
        [], "--emitted", help="'name=path' artifact this step emitted (repeatable)."
    ),
    item: str | None = typer.Option(
        None,
        "--item",
        help="Phase item (phase/<n>) this outcome is for — required when --step "
        "names a member of a grouped `for_each` step.",
    ),
    answered_by: str = typer.Option(
        "agent",
        "--answered-by",
        help="operator | agent — who answered this step's operator gate. "
        "Defaults to `agent`, the weaker claim; recorded only when a gate "
        "is cleared, and reported by `fr run check` and in the PR body.",
    ),
    agent: str | None = typer.Option(
        None,
        "--agent",
        help="The harness-reported agent/task id that held this unit — the "
        "LATE fallback for an orchestrator that never called `fr run claim`. "
        "Applied only to an unclaimed record; one that disagrees with an "
        "existing claim is refused, naming both.",
    ),
    harness: str | None = typer.Option(
        None, "--harness", help="One of fr.harness's HARNESSES, alongside --agent."
    ),
    model: str | None = typer.Option(
        None, "--model", help="The model actually dispatched, alongside --agent."
    ),
) -> None:
    """Record the outcome of an `agent` step, or answer a step's operator gate.

    The harness calls this when a dispatched agent returns. `advance`
    deliberately never executes an `agent` step, so this is the only way its
    cursor can move past `running`; `done` advances the cursor, `failed`
    leaves it put (same asymmetry `advance` already has for `cli` steps —
    see `_complete_step`).

    It is also the CLOSING half of the dispatch pair `advance` opened: the
    unit's open `DispatchRecord` gets `returned` = now and `outcome` =
    `--state`, which is what stops `advance` refusing the unit as held.
    `--agent/--harness/--model` attach a late identity to a record nobody
    claimed — the fallback for an orchestrator that never called
    `fr run claim`, refused if it disagrees with an existing claim.

    It also clears an operator gate (review fix r2-f1), which is what makes
    a `gate: operator` step something other than a permanent dead end — the
    shipped `fr-goal` `brainstorm` step is `kind: agent` + `gate: operator`,
    so before this the shipped shape wedged on its first step. A **blocked**
    step resolves like this:

    - `kind: agent` — exactly like a `running` one: `done`/`failed`, cursor
      asymmetry unchanged. The gate WAS the agent's question; answering it
      and reporting the outcome are the same act.
    - `kind: cli` — `done` clears the gate and returns the step to `pending`
      so the next `advance` executes it and its exit code is still the
      verdict; `failed` records a declined gate. `resolve` executes nothing,
      ever.
    """
    if state_value not in ("done", "failed"):
        err_console.print(f"[red]--state must be 'done' or 'failed', got {state_value!r}[/red]")
        raise typer.Exit(2)
    if answered_by not in ("operator", "agent"):
        # Refused rather than coerced: a typo recorded as a third provenance
        # would be read by nobody and would quietly weaken the one claim this
        # field exists to make.
        err_console.print(
            f"[red]--answered-by must be 'operator' or 'agent', got {answered_by!r}[/red]"
        )
        raise typer.Exit(2)
    if harness is not None and harness not in HARNESSES:
        err_console.print(f"[red]--harness must be one of {list(HARNESSES)}, got {harness!r}[/red]")
        raise typer.Exit(2)

    repo_root = resolve_repo_root()
    try:
        state = load_run_state(repo_root, run_id)
        manifest = _resolve_manifest_for_state(repo_root, state)
        step, parent = _find_step(manifest, step_id)
        # A member validates against its own declared emits, falling back to
        # the group's; a top-level step always validates against its own —
        # even when it declares none, so `--emitted` on a non-emitting step
        # stays refused (rule 3) rather than silently recorded.
        emits_owner = step if parent is None or step.emits else parent
        emitted_map = _parse_emitted(emitted, repo_root, emits_owner)
    except (RunStateError, WorkflowError, AdoptError) as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    if parent is not None:
        _resolve_member(
            repo_root,
            state,
            manifest,
            member=step,
            group=parent,
            item=item,
            state_value=state_value,  # type: ignore[arg-type]  # validated below
            emitted_map=emitted_map,
            agent=agent,
            harness=harness,
            model=model,
        )
        return
    if item is not None:
        if step.steps:
            members = ", ".join(m.id for m in step.steps)
            err_console.print(
                f"[red]{step_id}: a group outcome must address a member step "
                f"({members}) — pass --step <member> --item phase/<n>[/red]"
            )
        else:
            err_console.print(
                f"[red]{step_id}: --item is only for members of a grouped "
                "`for_each` step — {step_id!r} has no members[/red]"
            )
        raise typer.Exit(2)

    record = state.steps.get(step_id)
    if record is None:
        err_console.print(
            f"[red]{step_id}: no step record in run {run_id!r} — workflow "
            f"{state.workflow!r} changed after `fr run start`[/red]"
        )
        raise typer.Exit(2)

    cursor_record = state.steps.get(state.cursor)
    finished = (
        cursor_record is not None
        and cursor_record.state == "done"
        and _next_step_id(manifest, state.cursor) is None
    )
    if finished and not emitted_map:
        # Symmetric with `advance` (review r5-b3/e3): a finished run is
        # read-only. Amending `emitted` is still allowed — that is a
        # correction to the record, not a resumption of the run.
        err_console.print(
            f"[red]run {run_id!r} is complete (cursor {state.cursor!r} is done). "
            "Pass --emitted to amend what a step recorded; nothing else moves.[/red]"
        )
        raise typer.Exit(2)

    if step.kind == "cli":
        # A `cli` step is fr's to execute, so `resolve` may never declare one
        # done — that would let an operator report success for a command that
        # never ran. The ONE thing it can do is answer that step's operator
        # gate (review fix r2-f1), which is a decision, not an execution.
        if record.state != "blocked":
            err_console.print(
                f"[red]{step_id}: kind {step.kind!r} — resolved by `fr run advance`, "
                "not `fr run resolve` (resolve records an `agent` step's outcome, "
                "or clears a blocked step's operator gate)[/red]"
            )
            raise typer.Exit(2)
        if state_value == "done":
            new_record = record.model_copy(
                update={
                    "state": "pending",
                    "gate": "cleared",
                    # `_clears_gate`, not the inline `blocked and done` this
                    # branch already established (review r4-m1). The two are
                    # equivalent today — the only writer of `blocked` is
                    # `_gate_pending`, which requires `gate == "operator"` —
                    # but the helper exists so the condition lives in one
                    # place, and a future second writer of `blocked` would
                    # have made these diverge silently.
                    "answered_by": (
                        answered_by if _clears_gate(step, record, state_value) else None
                    ),
                    "at": _now(),
                    "emitted": dict(emitted_map) if emitted_map else record.emitted,
                }
            )
            save_run_state(repo_root, _with_step(state, step_id, new_record))
            console.print(
                f"{step_id}: operator gate cleared — `fr run advance {run_id}` now executes it",
                soft_wrap=True,
            )
            return
        # `failed` = the operator declined the gate. Same cursor asymmetry as
        # every other failure: recorded, and the run does not move past it.
        save_run_state(repo_root, _complete_step(state, manifest, step_id, "failed"))
        console.print(f"{step_id}: failed (operator gate declined)")
        return

    if record.state == "done" and state_value == "done":
        # AMEND, not a re-resolve (review r5-b6). A wrong `emitted` on a step
        # already `done` was unamendable: `resolve` refused ("not running or
        # blocked") and nothing else writes the field, so a run whose
        # `emitted.plan` pointed at the wrong path stayed that way — and that
        # is the key `fr archive` and `fr run adopt` match on. The cursor is
        # deliberately NOT moved: `_complete_step` only moves it when the
        # step IS the cursor, and re-running that for a step already done
        # would advance the run a second time.
        if not emitted_map:
            err_console.print(
                f"[red]{step_id}: already done — re-resolving it does nothing. "
                "Pass --emitted to amend the artifacts it recorded.[/red]"
            )
            raise typer.Exit(2)
        merged = {**(record.emitted or {}), **emitted_map}
        save_run_state(
            repo_root, _with_step(state, step_id, record.model_copy(update={"emitted": merged}))
        )
        console.print(f"{step_id}: amended emitted artifacts (still done; cursor unchanged)")
        return

    if record.state not in ("running", "blocked"):
        err_console.print(
            f"[red]{step_id}: not running or blocked (state={record.state!r}) — "
            "only a dispatched or gated step can be resolved[/red]"
        )
        raise typer.Exit(2)

    # The flat unit's dispatch closes here, keyed through the SAME `_unit_key`
    # `advance` opened it with and `claim` annotates it by — a `step/<id>` key
    # computed a second time by hand is the drift phase 3 removed.
    state = _close_on_resolve(
        state,
        step_id,
        _unit_key(repo_root, state, step, None, None),
        state_value,  # type: ignore[arg-type]  # validated above
        agent=agent,
        harness=harness,
        model=model,
    )
    new_state = _complete_step(
        state,
        manifest,
        step_id,
        state_value,  # type: ignore[arg-type]  # validated above
        emitted=emitted_map,
        # A gated `agent` step is the shape of the measured failure (spec §1):
        # it goes straight from `blocked` to `done` here and never acquires
        # `gate: cleared`, so provenance is the only trace that its gate was
        # cleared at all.
        answered_by=(
            answered_by  # type: ignore[arg-type]  # validated above
            if _clears_gate(step, record, state_value)
            else None
        ),
    )
    save_run_state(repo_root, new_state)
    console.print(f"{step_id}: {state_value}")


def _open_dispatch_record(record: StepRecord, key: str) -> DispatchRecord:
    """The OPEN (`returned is None`) `DispatchRecord` for `key`, or refuse.

    `fr run claim` annotates a dispatch `fr run advance` already made; it
    never invents one (spec §4.C) — a unit with no attempts at all, or whose
    last attempt is already closed, has nothing open to annotate."""
    attempts = (record.dispatch or {}).get(key) or []
    if not attempts or attempts[-1].returned is not None:
        err_console.print(
            f"[red]{key}: no open dispatch — nothing to claim. `fr run claim` "
            "annotates a dispatch `fr run advance` already made; it does not "
            "invent one. Advance the run first.[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    return attempts[-1]


def _claim_abandon(repo_root: Path, state: RunState, owner_id: str, key: str) -> None:
    """Close `key`'s open dispatch as `abandoned`, WITHOUT resolving the step
    it belongs to (spec §4.C, §1.C).

    The step's `items`/`state` are left exactly as they are — still
    `running` — so the next `fr run advance` sees the unit as still pending
    and briefs it again, appending a fresh `DispatchRecord` alongside this
    now-closed one (`_dispatch_needs_open`). This is the sanctioned recovery
    for an executor that is never coming back: nothing can retire it from the
    orchestrator side, so freeing the tree has to be a named operator act.
    """
    record = state.steps[owner_id]
    _open_dispatch_record(record, key)  # refuses when there is nothing to abandon
    new_record = _close_dispatch(record, key, "abandoned")
    save_run_state(repo_root, _with_step(state, owner_id, new_record))
    console.print(
        f"{key}: dispatch abandoned — `fr run advance` will brief it again", soft_wrap=True
    )


def _claim_identity(
    repo_root: Path,
    state: RunState,
    owner_id: str,
    key: str,
    *,
    agent: str,
    harness: str | None,
    model: str | None,
) -> None:
    """Fill `key`'s open dispatch record with the orchestrator's reported
    `agent`/`harness`/`model` (spec §3, §4.C).

    Idempotent for the SAME `agent` id (re-claiming just refreshes
    `harness`/`model` when given again); refuses a DIFFERENT one while the
    first is still open, naming both — the two-writers hazard this whole
    feature exists to make visible.
    """
    record = state.steps[owner_id]
    open_record = _open_dispatch_record(record, key)
    new_record = _replace_last_attempt(
        record,
        key,
        _claimed_identity(open_record, key, agent=agent, harness=harness, model=model),
    )
    save_run_state(repo_root, _with_step(state, owner_id, new_record))
    console.print(f"{key}: claimed by {agent}", soft_wrap=True)


@run_app.command("claim")
def claim_cmd(
    run_id: str = typer.Argument(..., help="Run id."),
    step_id: str = typer.Option(..., "--step", help="Step id (or member id) to claim."),
    item: str | None = typer.Option(
        None,
        "--item",
        help="Phase item (phase/<n>) this claim is for — required when --step "
        "names a member of a grouped `for_each` step.",
    ),
    agent: str | None = typer.Option(
        None, "--agent", help="The harness-reported agent/task id claiming this dispatch."
    ),
    harness: str | None = typer.Option(
        None,
        "--harness",
        help="One of fr.harness's HARNESSES; defaults to "
        "fr.harness.detect.detect_harness(), recording nothing when it cannot tell.",
    ),
    model: str | None = typer.Option(
        None, "--model", help="The model actually dispatched, if known."
    ),
    abandoned: bool = typer.Option(
        False,
        "--abandoned",
        help="Close this dispatch as abandoned WITHOUT resolving its step — the "
        "sanctioned recovery when an executor is never coming back (spec §1.C), since "
        "nothing can retire it from the orchestrator side; the step stays `running` so "
        "the next `fr run advance` briefs the unit again.",
    ),
) -> None:
    """Put the orchestrator's reported identity onto the dispatch `fr run
    advance` already opened for a unit (spec §3, §4.C) — the `agent`/
    `harness` half of `DispatchRecord` that only the orchestrator can report,
    fr itself can only derive `agent_type`/`model` and time its own act.

    Requires an OPEN dispatch record for the unit: a claim annotates a
    dispatch `fr run advance` made, it does not invent one. Re-claiming the
    SAME agent id is idempotent; a DIFFERENT one while the first is open is
    refused, naming both — the two-writers hazard this whole feature exists
    to make visible. `--abandoned` closes the record instead, for a dispatch
    that is never returning; see its own help text.
    """
    if abandoned and agent is not None:
        err_console.print(
            "[red]--abandoned closes a dispatch; it does not also claim one — "
            "pass --agent or --abandoned, not both[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    if not abandoned and agent is None:
        err_console.print(
            "[red]--agent is required (or pass --abandoned to close without one)[/red]"
        )
        raise typer.Exit(2)
    if harness is not None and harness not in HARNESSES:
        err_console.print(f"[red]--harness must be one of {list(HARNESSES)}, got {harness!r}[/red]")
        raise typer.Exit(2)

    repo_root = resolve_repo_root()
    try:
        state = load_run_state(repo_root, run_id)
        manifest = _resolve_manifest_for_state(repo_root, state)
        step, parent = _find_step(manifest, step_id)
        key = _unit_key(repo_root, state, step, parent, item)
    except (RunStateError, WorkflowError, AdoptError) as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    owner_id = parent.id if parent is not None else step.id
    if abandoned:
        _claim_abandon(repo_root, state, owner_id, key)
        return

    resolved_harness = harness
    if resolved_harness is None:
        try:
            resolved_harness = detect_harness(os.environ)
        except HarnessError as e:
            err_console.print(f"[red]{e}[/red]", soft_wrap=True)
            raise typer.Exit(2) from e
    assert agent is not None  # guarded above: not abandoned => agent is required
    _claim_identity(
        repo_root, state, owner_id, key, agent=agent, harness=resolved_harness, model=model
    )


def _open_dispatches(state: RunState) -> list[tuple[str, str, DispatchRecord]]:
    """Every currently-open `(step_id, key, DispatchRecord)` in `state`,
    steps in cursor order and keys sorted within a step.

    Reuses `_held_record` — the one notion of "is this unit held" in the
    module — rather than re-deriving "the last attempt is open" here."""
    open_dispatches: list[tuple[str, str, DispatchRecord]] = []
    for step_id, record in state.steps.items():
        for key in sorted(record.dispatch or {}):
            held = _held_record(record, key)
            if held is not None:
                open_dispatches.append((step_id, key, held))
    return open_dispatches


@run_app.command("check")
def check_cmd(run_id: str = typer.Argument(..., help="Run id.")) -> None:
    """Freshness gate: non-zero when the cursor sits on a failed step.

    It also REPORTS every operator gate the agent cleared itself (spec
    §3.D.3), every currently open dispatch, and how many of those are
    unclaimed (spec §4.C) — none of it changes the exit code. The exit code
    stays exactly what it was: `check` is a narrow freshness gate, and
    making an open or unclaimed dispatch non-zero would turn every ordinary
    in-flight run red, which is the same hard-refusal shape the operator
    already rejected for an agent-cleared gate. The enforcement is that the
    same list rides the delivered PR body, where a human reads it.
    """
    repo_root = resolve_repo_root()
    state = _load_or_exit(repo_root, run_id)

    record = state.steps.get(state.cursor)
    step_state = record.state if record is not None else "unknown"
    console.print(f"{state.run}: cursor={state.cursor} ({step_state})")
    for gate in agent_cleared_gates(state):
        # soft_wrap: this line is read for the step id it names, and rich
        # would fold a long id across a line break at a narrow width.
        console.print(
            f"{gate.step}: operator gate cleared by the agent (answered_by: agent) — "
            "no operator answered it",
            soft_wrap=True,
        )
    open_dispatches = _open_dispatches(state)
    for step_id, key, held in open_dispatches:
        console.print(
            f"{step_id}: {key} is open — {_render_dispatch_attempt(held)}",
            soft_wrap=True,
        )
    unclaimed = [
        held for _, _, held in open_dispatches if held.agent_type is not None and held.agent is None
    ]
    if unclaimed:
        console.print(
            f"{len(unclaimed)} unclaimed dispatch(es) — visible debt, not a failure",
            soft_wrap=True,
        )
    if record is not None and record.state == "failed":
        err_console.print(f"[red]{state.cursor}: failed[/red]")
        raise typer.Exit(1)


@run_app.command("gates")
def gates_cmd(run_id: str = typer.Argument(..., help="Run id.")) -> None:
    """Every `gate: operator` step this run's manifest declares, and who
    cleared it — the source `fr-goal`'s `deliver` step reads for the PR
    body's "Operator gates" section (spec §3.D.3, review r4-i2).

    NEVER prints nothing: a workflow with no operator gates says so
    explicitly, and a step whose cursor predates `answered_by` (this
    feature's own OpenCode run, or any `fr run adopt` cursor) says THAT
    explicitly too — both `cleared_gates()`-only readings would have
    rendered blank here, which on a delivered PR reads as "the feature
    never ran".
    """
    repo_root = resolve_repo_root()
    try:
        state = _load_or_exit(repo_root, run_id)
        manifest = _resolve_manifest_for_state(repo_root, state)
    except (RunStateError, WorkflowError, AdoptError) as e:
        err_console.print(f"[red]{e}[/red]", soft_wrap=True)
        raise typer.Exit(2) from e

    statuses = gates(state, manifest)
    if not statuses:
        console.print(f"{state.run}: no `gate: operator` steps recorded as cleared")
        return
    for status in statuses:
        if status.outcome == "recorded" and status.answered_by == "agent":
            # The same sentence `fr run check` prints (review r5-m3). This is
            # the surface that rides the delivered PR body, so the case a human
            # most needs to notice must not be the tersest line on the page —
            # "cleared by agent" alone reads as bookkeeping, not as a warning.
            console.print(
                f"{status.step}: operator gate cleared by the agent "
                "(answered_by: agent) — no operator answered it",
                soft_wrap=True,
            )
        elif status.outcome == "recorded":
            console.print(f"{status.step}: operator gate answered by the operator", soft_wrap=True)
        else:
            console.print(
                f"{status.step}: cleared, but provenance not recorded "
                "(this cursor predates `answered_by`)",
                soft_wrap=True,
            )
