"""Run lookup: which step, unit and artifact a cursor names (spec 2026-11-27-run-verdict R4).

The cluster `fr/commands/run_cmd.py` used to hold between its run-id derivation and
`complete_step`: finding a step in a manifest, naming a unit key, resolving the manifest a
cursor was started against, and recording a step's outcome. A refusal is a `RunRefusal` and
a warning goes to the caller's `warn`; the command prints both (`run_cmd._refusals`,
`run_cmd._say`).

Engine code: no `typer`, no `rich` beyond `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from rich.markup import escape

from fr.artifacts.paths import emitted_path
from fr.run.adopt import MANUAL_ITEM, AdoptError, plan_phase_tags
from fr.run.liveness import flat_unit_key, next_step_id
from fr.run.model import (
    RUN_ID_MAX_LENGTH,
    AnsweredBy,
    RunState,
    RunStateError,
    StepRecord,
)
from fr.run.reshape import diff_ids
from fr.run.verdict import RunRefusal, Say, Warn
from fr.run.writes import now
from fr.workflow.check import check_workflow
from fr.workflow.model import Step, WorkflowError, WorkflowManifest
from fr.workflow.resolve import resolve_workflow


def emitted_plan(state: RunState) -> str | None:
    """The recorded repo-relative plan path, wherever the shape put it."""
    for record in state.steps.values():
        if record.emitted and "plan" in record.emitted:
            return record.emitted["plan"]
    return None


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


def step_by_id(manifest: WorkflowManifest, step_id: str) -> Step:
    step, _parent = find_step(manifest, step_id)
    return step


def split_member_id(manifest: WorkflowManifest, step_id: str) -> tuple[str, str] | None:
    """`(item, member_id)` if `step_id` is a grouped fan-out's COMPOSITE key
    (`phase/1/implement-phase`), else `None`.

    The composite is the display id and the `items`-map key — what `fr run
    status` and `advance` both show — but it is deliberately NOT accepted in
    `--step` (spec §3.B, journal `d2`). Accepting it and splitting it
    internally was the issue's own option 2 and was declined: it would leave
    two spellings of one id, and it would hide the `--item` flag from the
    operator at the exact moment they need to learn it. So this function
    exists to *recognise* the composite in order to teach the two flags —
    never to resolve it.

    Recognition is manifest-driven, not shape-of-string: the tail after the
    last `/` must name a member of some `for_each` group. An id that merely
    contains a slash is an ordinary not-found id and gets the ordinary
    message.
    """
    if "/" not in step_id:
        return None
    item, _, tail = step_id.rpartition("/")
    for step in manifest.steps:
        if step.for_each and any(member.id == tail for member in step.steps):
            return item, tail
    return None


def find_step(manifest: WorkflowManifest, step_id: str) -> tuple[Step, Step | None]:
    """`(step, parent-group)` for a top-level OR member id — members share the
    flattened id space `check_workflow` validates, so resolving one must find
    them too. Parent is `None` for a top-level step."""
    for step in manifest.steps:
        if step.id == step_id:
            return step, None
        for member in step.steps:
            if member.id == step_id:
                return member, step
    not_found = f"step {step_id!r} not found in workflow {manifest.workflow!r}"
    split = split_member_id(manifest, step_id)
    if split is not None:
        item, member_id = split
        raise RunStateError(
            f"{not_found}.\n"
            "It is a grouped `for_each` member, which takes two flags:\n"
            f"  --step {member_id} --item {item}"
        )
    raise RunStateError(not_found)


def unit_key(
    repo_root: Path,
    state: RunState,
    step: Step,
    parent: Step | None,
    item: str | None,
) -> str:
    """The UNIT key a `(--step, --item)` pair names (`fr.run.units`) —
    spec §4.B's two key spaces (`phase/<n>/<member-id>` for a grouped member,
    `step/<step-id>` for a flat one) computed in exactly ONE place, so
    `claim`, `_resolve_member` and `advance`'s own flat-step key can never
    drift apart (P3.T1.S3). `step`/`parent` are `find_step`'s own return
    shape — `parent` is `None` for a top-level step, the group for a member.

    Raises `RunRefusal` (exit 2) for every input shape that cannot
    name a unit: a member given no `--item`, a non-member given one, or an
    `--item` naming a phase this run's recorded plan does not have.
    """
    if parent is not None:
        if item is None:
            raise RunRefusal(
                (
                    Say(
                        f"[red]{step.id}: a member outcome must address a phase item — "
                        "pass --item phase/<n>[/red]"
                    ),
                )
            )
        try:
            # (agentic, manual) since gh#496 — a `tag: manual` phase is never
            # dispatched, so only the agentic list can name a unit key.
            agentic, manual = group_phases(repo_root, state)
        except (RunStateError, AdoptError) as e:
            raise RunRefusal(
                (Say(f"[red]{parent.id}: {escape(str(e))}[/red]", soft_wrap=True),)
            ) from e
        expected = expected_group_items(parent, agentic)
        key = f"{item}/{step.id}"
        if key not in expected:
            # #496 (spec §3.D.3): a manual phase gets its own message BEFORE
            # the generic one. "not a phase member — expected phase/<n> for
            # phases [1,2,3]" reads as a bug in the phase list when phase 4
            # plainly exists in the plan; the reason it is absent is a
            # deliberate omission, and the refusal has to say so. It lives
            # HERE because this is the one place a unit key is validated: it
            # used to sit in `_resolve_member` behind a call to this function,
            # which refused first with the generic text — dead on arrival,
            # and `claim` never had it at all.
            if item_phase(item) in manual:
                raise RunRefusal(
                    (
                        Say(
                            f"[red]{key}: phase {item_phase(item)} is `tag: manual` and is "
                            "deliberately never dispatched, so there is no outcome to "
                            "record.[/red]\n"
                            "  Its record is the plan's own steps plus the PR's "
                            '"unimplemented — operator pushes to this PR".',
                            soft_wrap=True,
                        ),
                    )
                )
            raise RunRefusal(
                (
                    Say(
                        f"[red]{key}: not a phase member of {parent.id!r} — expected "
                        f"phase/<n> for phases {agentic} (from the recorded plan)[/red]"
                    ),
                )
            )
        return key
    if item is not None:
        if step.steps:
            members = ", ".join(m.id for m in step.steps)
            text = (
                f"[red]{step.id}: a group outcome must address a member step "
                f"({members}) — pass --step <member> --item phase/<n>[/red]"
            )
        else:
            text = (
                f"[red]{step.id}: --item is only for members of a grouped "
                f"`for_each` step — {step.id!r} has no members[/red]"
            )
        raise RunRefusal((Say(text),))
    return flat_unit_key(step.id)


def group_phases(repo_root: Path, state: RunState) -> tuple[list[int], list[int]]:
    """`(agentic, manual)` phase numbers, from the plan on disk — the one
    source of which phases exist.

    **The filter lives here, above everything else** (#496, spec §3.D.3).
    `expected_group_items` is the single place that decides which units
    exist, and BOTH of `_advance_group`'s refusals read that list: filter a
    manual phase out any later and a `tag: manual` phase can still be the
    `running` key an ALREADY RUNNING refusal names, or the unit a
    `--redispatch` re-briefs.

    The split keys on `tag` alone and never on completion. A ticked
    front-loaded manual phase waits on nobody (review `r4-f1`) but is still
    not work this run did, so it is recorded as skipped rather than done —
    and keeping the predicate completion-free is what lets `advance` and
    `fr run adopt` write identical markers without either parsing state.

    Fail-closed: a group advanced before its plan is recorded (or against an
    unparseable plan) names what is missing instead of dispatching against a
    guessed phase list.
    """
    plan_rel = emitted_plan(state)
    if plan_rel is None:
        raise RunStateError(
            "cannot dispatch per-phase members — no plan recorded yet "
            "(resolve the step that emits `plan` first)"
        )
    tags = plan_phase_tags(repo_root, plan_rel)
    agentic = sorted(n for n, tag in tags.items() if tag != "manual")
    manual = sorted(n for n, tag in tags.items() if tag == "manual")
    return agentic, manual


def manual_items(manual: list[int]) -> dict[str, str]:
    """The `phase/<n>: manual` markers for every phase the fan-out skipped.

    Item granularity, in the group's own map, so a deliberate omission is
    visible in `fr run status` beside everything that WAS dispatched — the
    alternative (leave them out entirely) is how a skipped phase becomes
    indistinguishable from a phase nobody noticed.
    """
    return {f"phase/{n}": MANUAL_ITEM for n in manual}


def item_phase(item: str) -> int | None:
    """The phase number a `phase/<n>` item names, or None when it names
    something else. Structural, not a cast: `--item` is operator input, so
    `phase/four` and `spec/1` must fall through to the generic refusal rather
    than raise."""
    head, _, tail = item.partition("/")
    return int(tail) if head == "phase" and tail.isdigit() else None


def group_done_line(step_id: str, expected: list[str], manual: list[int]) -> str:
    """The one completion line for a grouped fan-out.

    Printed from both places a group can complete — `_advance_group` (nothing
    left to dispatch) and `_resolve_member` (the last member's outcome) — so
    the count and the manual phases it names cannot drift between them.

    The manual phases are named rather than merely counted: "6 members done"
    over a 4-phase plan reads as an arithmetic bug until the line says which
    phase was never dispatched and why. It does NOT say "trailing", though
    the common case is: after review `r4-f1` a manual phase may legitimately
    be front-loaded-and-already-complete instead, and deciding which from
    here would be a second definition of "trailing" beside
    `fr.plan_review._trailing_manual_block`.
    """
    line = f"{step_id}: done ({len(expected)} members done"
    if manual:
        phases = ", ".join(f"phase {n}" for n in manual)
        line += (
            f"; {phases} `tag: manual`, never dispatched — the plan's own "
            "steps and the PR are its record"
        )
    return line + ")"


def phase_tier(repo_root: Path, state: RunState, phase_n: int) -> str | None:
    """The tier phase `phase_n` declares in its header on the plan this run
    recorded, or `None` when it declares none, no plan is recorded yet, or
    the plan is unparseable.

    Fail-soft by design (unlike `group_phases`, which fails closed): this is
    an observability field, not a dispatch precondition, and refusing to
    dispatch over an unreadable OPTIONAL tier would be a new failure mode for
    a field whose whole point is that a phase may legitimately not set it.
    "Observability must not break execution", rather than `group_phases`'s
    stance.
    """
    plan_rel = emitted_plan(state)
    if plan_rel is None:
        return None
    from fr.parser import PlanSchemaError, parse

    try:
        plan = parse(emitted_path(repo_root, plan_rel))
    except PlanSchemaError, OSError:
        return None
    return next((p.phase.tier for p in plan.phases if p.phase.number == phase_n), None)


def expected_group_items(group: Step, phases: list[int]) -> list[str]:
    """Every `phase/<n>/<member>` key of a grouped fan-out, in dispatch
    order: phase-major, then member order — implement before review, per
    phase, never the reverse.

    `phases` is `group_phases`'s AGENTIC list: a manual phase produces no
    expected key at all, so it is neither dispatchable, resolvable, nor
    countable towards the group's completion.
    """
    return [f"phase/{n}/{m.id}" for n in phases for m in group.steps]


class StepDriftError(RunStateError):
    """The step list a cursor recorded differs from the manifest's — the one
    refusal a read-only command downgrades to a warning (`resolve_manifest_for_read`)."""


def resolve_manifest_for_state(repo_root: Path, state: RunState) -> WorkflowManifest:
    """The manifest this run was started against — name AND schema version.

    `state.workflow` is `"<name>@<schema>"`. The suffix used to be sliced off
    and thrown away (review r5-e3), so a run started against `fr-goal@1` would
    happily keep advancing after the shape was rewritten as `schema: 2` — with
    a step graph the cursor was never computed for. The suffix is a version
    stamp; a version stamp nobody checks is decoration.
    """
    manifest = resolve_manifest_checked_schema(repo_root, state)
    check_step_drift(state, manifest)
    return manifest


def resolve_manifest_checked_schema(repo_root: Path, state: RunState) -> WorkflowManifest:
    name, _, recorded_schema = state.workflow.partition("@")
    manifest = resolve_workflow(name, repo_root)
    if recorded_schema and str(manifest.schema_version) != recorded_schema:
        raise RunStateError(
            f"run {state.run!r} was started against {state.workflow!r}, but "
            f"{name!r} now declares schema {manifest.schema_version}. A shape's "
            "schema version changes its step grammar; start a new run rather "
            "than advancing this one against a different one."
        )
    return manifest


def resolve_manifest_for_read(repo_root: Path, state: RunState, warn: Warn) -> WorkflowManifest:
    """`resolve_manifest_for_state` for a command that only READS the cursor
    (spec 2026-10-05-run-upgrade-midflight §B).

    A step-list drift is printed as ONE warning and the manifest returned
    anyway: refusing to say who cleared a gate because a later step was added
    helps nobody. A schema-version mismatch still refuses — a different grammar
    is not safe to read with. `warn` is how the calling command prints it. Mutating
    commands keep the strict resolver.
    """
    manifest = resolve_manifest_checked_schema(repo_root, state)
    try:
        check_step_drift(state, manifest)
    except StepDriftError as e:
        warn(Say(f"[yellow]warning: {escape(str(e))}[/yellow]", soft_wrap=True))
    return manifest


def reshape_hint(state: RunState) -> str:
    return (
        f" `fr run reshape {state.run}` moves the cursor onto the current list "
        "when that loses nothing it recorded."
    )


def check_step_drift(state: RunState, manifest: WorkflowManifest) -> None:
    """Refuse when the shape's STEPS have changed since `fr run start`.

    A step added, removed or renamed makes every recorded position suspect:
    the cursor may name a step that no longer exists, a new step silently
    never runs, and `next_step_id` moves the run somewhere the operator never
    reviewed. Each of those used to surface as a `KeyError` or a `ValueError`
    from `list.index` deep inside `advance` (review r5-e3) — or, for an added
    step, as nothing at all.

    Reported as a DIFF, because "the workflow changed" is not actionable and
    "added: verify; removed: spec-review" is.
    """
    added, removed = diff_ids(state.steps, (s.id for s in manifest.steps))
    if added or removed:
        parts = []
        if added:
            parts.append(f"added: {', '.join(added)}")
        if removed:
            parts.append(f"removed: {', '.join(removed)}")
        raise StepDriftError(
            f"run {state.run!r} was started against a different version of "
            f"{state.workflow!r} ({'; '.join(parts)}). A run's cursor is a position in "
            "a step list; start a new run rather than advancing this one against a "
            "list it was never computed for." + reshape_hint(state)
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
            added, removed = diff_ids(recorded_members, current_members)
            parts = []
            if added:
                parts.append(f"added: {', '.join(added)}")
            if removed:
                parts.append(f"removed: {', '.join(removed)}")
            raise StepDriftError(
                f"run {state.run!r} was started against a different version of "
                f"{state.workflow!r} (step {step.id!r} members changed: {'; '.join(parts)}). "
                "A run's cursor is a position in a step list; start a new run rather "
                "than advancing this one against a list it was never computed for."
                + reshape_hint(state)
            )


def rebind_shape(
    state: RunState,
    manifest: WorkflowManifest,
    step_id: str,
    target: str,
    repo_root: Path,
) -> WorkflowManifest | None:
    """The manifest a record's `shape: <target>` rebinds the run onto, `None`
    for a same-shape no-op — or `RunStateError` naming the rule it broke.

    2026-09-29-fr-goal-light-path §A (R1). A run's cursor is a position in a
    step list, so moving it onto another list is safe only before it has
    moved at all, and only onto a list that shares the position it is at:

    1. the step being resolved is the run's first step, and no other step has
       left `pending`;
    2. `resolve_workflow(target)` finds the shape, and its first step has the
       same id as the step being resolved;
    3. the target is not the run's current shape — that declaration is a
       no-op, so a re-applied record is idempotent.

    Pure: it validates, and `rebound` builds the new state. `apply_record`
    calls it before any write, and `resolve` again where it rewrites.
    """
    current = state.workflow.partition("@")[0]
    if target == current:
        return None
    first = manifest.steps[0].id
    if step_id != first:
        raise RunStateError(
            f"shape: {target!r} refused — only the run's first step ({first!r}) may "
            f"rebind it, and {step_id!r} is not that step. Start a new run with "
            f"`fr run start {target}` instead."
        )
    moved = sorted(
        sid for sid, rec in state.steps.items() if sid != step_id and rec.state != "pending"
    )
    if moved:
        raise RunStateError(
            f"shape: {target!r} refused — step(s) {', '.join(moved)} already left "
            "`pending`, so the run has moved on its current shape. Start a new run "
            f"with `fr run start {target}` instead."
        )
    try:
        rebound = resolve_workflow(target, repo_root)
    except WorkflowError as e:
        raise RunStateError(f"shape: {target!r} refused — {e}") from e
    if not rebound.steps or rebound.steps[0].id != step_id:
        begins = rebound.steps[0].id if rebound.steps else "nothing"
        raise RunStateError(
            f"shape: {target!r} refused — it begins with {begins!r}, not {step_id!r}; "
            "a run rebinds only onto a shape that begins with the step being resolved."
        )
    errors = check_workflow(rebound, repo_root)
    if errors:
        raise RunStateError(f"shape: {target!r} refused — not a valid workflow: {errors[0]}")
    from fr.workflow.available import refuse_disabled

    try:
        refuse_disabled(target, repo_root)
    except WorkflowError as e:
        raise RunStateError(f"shape: {target!r} refused — {e}") from e
    return rebound


def rebound(state: RunState, rebound: WorkflowManifest, step_id: str) -> RunState:
    """`state` on `rebound`'s step list: `workflow` rewritten, every step
    fresh and `pending` as `fr run start` builds them, bar `step_id`'s own
    record, which is carried over. The cursor stays on `step_id`, so the
    caller's `complete_step` moves it along the NEW list."""
    steps = {
        s.id: StepRecord(state="pending", members=[m.id for m in s.steps] or None)
        for s in rebound.steps
    }
    steps[step_id] = state.steps[step_id]
    return state.model_copy(
        update={"workflow": f"{rebound.workflow}@{rebound.schema_version}", "steps": steps}
    )


def with_step(state: RunState, step_id: str, record: StepRecord) -> RunState:
    new_steps = dict(state.steps)
    new_steps[step_id] = record
    return state.model_copy(update={"steps": new_steps})


def complete_step(
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
    fix r2-f8). Assigning `next_step_id(manifest, step_id)` unconditionally
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
    # The successor is the PRIOR record with the fields completion decides
    # overwritten — never a record rebuilt from a list of fields to keep.
    # Finding f7 is why: this used to be `StepRecord(state=…, gate=prior.gate,
    # members=prior.members, …)`, a hand-maintained carry-forward list, so any
    # durable field added later was DROPPED at completion by default. The
    # dispatch history was the one that got caught: the trail gh-503 asked for
    # ("who was holding this phase, and when") was deleted by the very act of
    # FINISHING — silently, because only `status`/`check` ever read it — and an
    # adopted flat fan-out went blind the same way (`_fan_out_items` scans
    # every record for exactly this). Now `gate`, `members`, `units` and
    # whatever comes next survive unless a line below says otherwise.
    completion: dict[str, object] = {
        "state": outcome,
        "at": now(),
        "answered_by": answered_by or (prior.answered_by if prior is not None else None),
        "exit": exit_code,
        "stdout": stdout,
        "emitted": dict(emitted) if emitted else None,
    }
    new_record = (
        prior.model_copy(update=completion)
        if prior is not None
        else StepRecord.model_validate(completion)
    )
    new_state = with_step(state, step_id, new_record)
    if outcome == "done" and step_id == state.cursor:
        next_id = next_step_id(manifest, step_id)
        if next_id is not None:
            new_state = new_state.model_copy(update={"cursor": next_id})
    return new_state
