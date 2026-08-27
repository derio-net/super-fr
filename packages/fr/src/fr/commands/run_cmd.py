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
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import typer
from rich.console import Console

from fr.commands.common import resolve_repo_root
from fr.run.model import (
    RunState,
    RunStateError,
    StepRecord,
    load_run_state,
    run_path,
    save_run_state,
)
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
    """
    new_record = StepRecord(
        state=outcome,
        at=_now(),
        exit=exit_code,
        stdout=stdout,
        emitted=dict(emitted) if emitted else None,
    )
    new_state = _with_step(state, step_id, new_record)
    if outcome == "done":
        next_id = _next_step_id(manifest, step_id)
        if next_id is not None:
            new_state = new_state.model_copy(update={"cursor": next_id})
    return new_state


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


def _render_template(text: str, context: Mapping[str, str]) -> str:
    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in context:
            raise RunStateError(f"unresolved template variable: {{{{ {key} }}}}")
        return context[key]

    return _TEMPLATE_RE.sub(repl, text)


def _build_brief(step: Step, state: RunState) -> dict[str, Any]:
    """The dispatch brief for a `kind: agent` step — everything the harness
    needs to actually run it, and nothing fr itself executes.

    Phase 11 wires `fr-goal` onto `fr run`; it must produce/consume this
    same shape, so its keys are deliberately exhaustive of `Step`'s
    agent-relevant fields rather than a subset convenient for today's tests.
    """
    return {
        "run": state.run,
        "workflow": state.workflow,
        "step": step.id,
        "skill": step.skill,
        "agent": step.agent,
        "needs": list(step.needs),
        "emits": list(step.emits),
        "tier": step.tier,
    }


@run_app.command("start")
def start_cmd(
    workflow: str = typer.Argument(..., help="Workflow shape name (resolved repo > shipped)."),
    branch: str = typer.Option(..., "--branch", help="Branch this run operates on."),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Override the derived run id (default: date + sanitized branch)."
    ),
) -> None:
    """Start a run: resolve the shape, write run state with the cursor on step 1."""
    repo_root = resolve_repo_root()
    try:
        manifest = resolve_workflow(workflow, repo_root)
    except WorkflowError as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e
    if not manifest.steps:
        err_console.print(f"[red]workflow {workflow!r} has no steps[/red]")
        raise typer.Exit(2)

    rid = run_id or derive_run_id(branch)
    path = run_path(repo_root, rid)
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
    save_run_state(repo_root, state)
    console.print(f"started run {rid} ({state.workflow}) — cursor: {state.cursor}")


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
    dispatch brief and marks itself `running`. A `gate: operator` step
    marks `blocked` and stops before either happens.
    """
    repo_root = resolve_repo_root()
    try:
        state = load_run_state(repo_root, run_id)
        manifest = _resolve_manifest_for_state(repo_root, state)
        step = _step_by_id(manifest, state.cursor)
    except (RunStateError, WorkflowError) as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    record = state.steps[state.cursor]

    if step.gate == "operator" and record.state != "done":
        if record.state != "blocked":
            new_record = record.model_copy(update={"state": "blocked", "at": _now()})
            save_run_state(repo_root, _with_step(state, state.cursor, new_record))
        console.print(f"{step.id}: blocked on operator gate")
        return

    if step.kind == "agent":
        brief = _build_brief(step, state)
        if record.state != "running":
            new_record = record.model_copy(update={"state": "running", "at": _now()})
            save_run_state(repo_root, _with_step(state, state.cursor, new_record))
        console.print(f"{step.id}: dispatch brief")
        console.print(json.dumps(brief, sort_keys=True))
        return

    # kind == "cli"
    context = _template_context(state)
    try:
        command = _render_template(step.run or "", context)
    except RunStateError as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e

    proc = subprocess.run(  # noqa: S602 — shape manifests are operator-authored, like `fr apply`
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
    """Record the outcome of an `agent` step — the harness calls this when a
    dispatched agent returns. `advance` deliberately never executes an
    `agent` step, so this is the only way its cursor can move past
    `running`; `done` advances the cursor, `failed` leaves it put (same
    asymmetry `advance` already has for `cli` steps — see `_complete_step`).
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

    if step.kind != "agent":
        err_console.print(
            f"[red]{step_id}: kind {step.kind!r} — resolved by `fr run advance`, "
            "not `fr run resolve` (resolve is for `agent` steps only)[/red]"
        )
        raise typer.Exit(2)

    record = state.steps.get(step_id)
    if record is None or record.state != "running":
        got = record.state if record is not None else "unknown"
        err_console.print(
            f"[red]{step_id}: not running (state={got!r}) — only a running "
            "step can be resolved[/red]"
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
