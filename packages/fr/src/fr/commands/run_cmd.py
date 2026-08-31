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
import re
import shlex
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import typer
from rich.console import Console

from fr.commands.common import resolve_repo_root
from fr.run.adopt import AdoptError, adopt_run
from fr.run.model import (
    RunState,
    RunStateError,
    StepRecord,
    load_run_state,
    run_path,
    save_run_state,
)
from fr.run.workspace import RunWorkspaceError, ensure_run_workspace
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


def derive_run_id(branch: str, *, today: _dt.date | None = None) -> str:
    """Derive a run id from `branch` when `--run-id` is not given.

    Must satisfy `fr_dispatch.work_item.run_item_id`'s constraint: a single
    non-empty path segment, no `/` (Phase 2 review fix — that validation
    exists specifically because this function feeds it). `branch` routinely
    contains `/` (e.g. `feat/ticket-polling`), so it is flattened; the
    date prefix mirrors the plan-slug shape spec §4.B's own example
    (`2026-08-14-ticket-polling`) uses, keeping a run id visually
    consistent with the plan slug a `unit: run` shape will go on to create.
    """
    day = today or _dt.date.today()
    sanitized = branch.strip("/").replace("/", "-")
    return f"{day.isoformat()}-{sanitized}"


def _step_by_id(manifest: WorkflowManifest, step_id: str) -> Step:
    for step in manifest.steps:
        if step.id == step_id:
            return step
    raise RunStateError(f"step {step_id!r} not found in workflow {manifest.workflow!r}")


def _next_step_id(manifest: WorkflowManifest, step_id: str) -> str | None:
    ids = [s.id for s in manifest.steps]
    idx = ids.index(step_id)
    return ids[idx + 1] if idx + 1 < len(ids) else None


def _resolve_manifest_for_state(repo_root: Path, state: RunState) -> WorkflowManifest:
    name = state.workflow.split("@", 1)[0]
    return resolve_workflow(name, repo_root)


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

    The prior record's `gate` is carried forward: an operator authorizes a
    step once, so a cleared gate survives the step's completion (and any
    later retry of it).
    """
    prior = state.steps.get(step_id)
    new_record = StepRecord(
        state=outcome,
        at=_now(),
        gate=prior.gate if prior is not None else None,
        exit=exit_code,
        stdout=stdout,
        emitted=dict(emitted) if emitted else None,
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


def _parse_emitted(pairs: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep:
            raise RunStateError(f"--emitted must be 'name=path', got {pair!r}")
        result[name] = value
    return result


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
    per phase) or the fact that a step is gated at all.
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
    }


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

    try:
        workspace = ensure_run_workspace(repo_root, branch)
    except RunWorkspaceError as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    rid = run_id or derive_run_id(branch)
    path = run_path(workspace, rid)
    if path.exists():
        err_console.print(f"[red]run {rid!r} already exists at {path}[/red]")
        raise typer.Exit(2)

    steps = {s.id: StepRecord(state="pending") for s in manifest.steps}
    state = RunState(
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
        console.print(f"  {len(complete)}/{len(items)} phases complete")
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


@run_app.command("status")
def status_cmd(run_id: str = typer.Argument(..., help="Run id.")) -> None:
    """Print the cursor and every step's state."""
    repo_root = resolve_repo_root()
    try:
        state = load_run_state(repo_root, run_id)
    except RunStateError as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    console.print(f"run: {state.run}")
    console.print(f"workflow: {state.workflow}")
    console.print(f"branch: {state.branch}")
    console.print(f"cursor: {state.cursor}")
    for step_id, record in state.steps.items():
        console.print(f"  {step_id}: {record.state}")


@run_app.command("advance")
def advance_cmd(run_id: str = typer.Argument(..., help="Run id.")) -> None:
    """Advance the cursor by one step.

    `kind: cli` executes directly (exit code + stdout captured; cursor
    moves only on success). `kind: agent` is NEVER executed — it emits a
    dispatch brief and marks itself `running`. A `gate: operator` step whose
    gate is unanswered marks `blocked` and executes nothing; an `agent` step
    still prints its brief there, since the gate stops the run, not the
    harness's view of what the step is. `fr run resolve` answers the gate.
    """
    repo_root = resolve_repo_root()
    try:
        state = load_run_state(repo_root, run_id)
        manifest = _resolve_manifest_for_state(repo_root, state)
        step = _step_by_id(manifest, state.cursor)
    except (RunStateError, WorkflowError) as e:
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
        # A gate stops the RUN, not the harness's view of the step: an `agent`
        # step still prints its brief here, because the skill/agent named in it
        # is how the operator's question gets asked in the first place. Nothing
        # is executed either way — a `cli` step's side effect is exactly what
        # the gate is guarding.
        if step.kind == "agent":
            console.print(json.dumps(_build_brief(step, state), sort_keys=True), soft_wrap=True)
        return

    if step.kind == "agent":
        brief = _build_brief(step, state)
        if record.state != "running":
            new_record = record.model_copy(update={"state": "running", "at": _now()})
            save_run_state(repo_root, _with_step(state, state.cursor, new_record))
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


@run_app.command("resolve")
def resolve_cmd(
    run_id: str = typer.Argument(..., help="Run id."),
    step_id: str = typer.Option(..., "--step", help="Step id to resolve (must be `running`)."),
    state_value: str = typer.Option(..., "--state", help="done | failed."),
    emitted: list[str] = typer.Option(
        [], "--emitted", help="'name=path' artifact this step emitted (repeatable)."
    ),
) -> None:
    """Record the outcome of an `agent` step, or answer a step's operator gate.

    The harness calls this when a dispatched agent returns. `advance`
    deliberately never executes an `agent` step, so this is the only way its
    cursor can move past `running`; `done` advances the cursor, `failed`
    leaves it put (same asymmetry `advance` already has for `cli` steps —
    see `_complete_step`).

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

    repo_root = resolve_repo_root()
    try:
        state = load_run_state(repo_root, run_id)
        manifest = _resolve_manifest_for_state(repo_root, state)
        step = _step_by_id(manifest, step_id)
        emitted_map = _parse_emitted(emitted)
    except (RunStateError, WorkflowError) as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    record = state.steps.get(step_id)
    if record is None:
        err_console.print(
            f"[red]{step_id}: no step record in run {run_id!r} — workflow "
            f"{state.workflow!r} changed after `fr run start`[/red]"
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

    if record.state not in ("running", "blocked"):
        err_console.print(
            f"[red]{step_id}: not running or blocked (state={record.state!r}) — "
            "only a dispatched or gated step can be resolved[/red]"
        )
        raise typer.Exit(2)

    new_state = _complete_step(
        state,
        manifest,
        step_id,
        state_value,  # type: ignore[arg-type]  # validated above
        emitted=emitted_map,
    )
    save_run_state(repo_root, new_state)
    console.print(f"{step_id}: {state_value}")


@run_app.command("check")
def check_cmd(run_id: str = typer.Argument(..., help="Run id.")) -> None:
    """Freshness gate: non-zero when the cursor sits on a failed step."""
    repo_root = resolve_repo_root()
    try:
        state = load_run_state(repo_root, run_id)
    except RunStateError as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    record = state.steps.get(state.cursor)
    step_state = record.state if record is not None else "unknown"
    console.print(f"{state.run}: cursor={state.cursor} ({step_state})")
    if record is not None and record.state == "failed":
        err_console.print(f"[red]{state.cursor}: failed[/red]")
        raise typer.Exit(1)
