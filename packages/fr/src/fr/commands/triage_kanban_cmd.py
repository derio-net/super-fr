"""`fr triage batch focus` — the board's only contact with `fr_dispatch` (spec
2026-10-05-triage-batch-board §E; R8).

This module is `fr`'s third sanctioned soft point into `fr_dispatch`
(`tests/unit/test_import_direction.py` `_SOFT_POINTS`): every such import sits
inside a function, behind `importlib.util.find_spec("fr_dispatch")`. It imports
from `triage_cmd` and `fr.triage.*` only, never from `triage_batch_cmd`, so the
import between the two stays one-way.

Exit codes: 0 focused; 2 a refusal, always one line.
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, Annotated, Any, NoReturn

import typer
from rich.markup import escape
from rich.text import Text

from fr.commands.triage_cmd import (
    DirOpt,
    OrgOpt,
    RepoOpt,
    _load_state,
    _scope,
    batch_app,
    console,
    err_console,
)
from fr.triage.batch import batch_item_id, batch_repo, batch_workflow, last_dispatch
from fr.triage.batch_drive import (
    DEFAULT_WORKSPACE_PREFIX,
    closeout_event,
    closeout_item_id,
    wave_group,
)

if TYPE_CHECKING:
    from fr_dispatch.protocols import Runner
    from fr_dispatch.work_item import WorkItem

    from fr.triage.model import Batch

DISPATCH_INSTALL_HINT = (
    "this requires fr-dispatch — install it "
    "(e.g. `uv tool install --with fr-dispatch fr`) and re-run."
)


def _fail(message: str, code: int = 2) -> NoReturn:
    err_console.print(f"[red]error:[/red] {escape(message)}", soft_wrap=True)
    raise typer.Exit(code=code)


def load_runner(name: str) -> Runner:
    """Build runner *name* through `fr_dispatch.registry.load_runner`.

    The soft point: `fr_dispatch` is imported here, behind find_spec, never at
    module level. Tests replace this.
    """
    if importlib.util.find_spec("fr_dispatch") is None:
        _fail(DISPATCH_INSTALL_HINT)
    from fr_dispatch.registry import RunnerLoadError
    from fr_dispatch.registry import load_runner as _load

    try:
        return _load(name)
    except RunnerLoadError as exc:
        _fail(str(exc))


def _try_load(name: str) -> tuple[Runner | None, str]:
    """Runner *name* and no reason, or None and why it could not be loaded.

    `load_runner` reports a refusal through `_fail` (a red `error:` and an exit);
    an adapter's own import or `from_env()` failure is any exception. Either is
    one reason here, never a traceback.
    """
    try:
        with err_console.capture() as said:
            return load_runner(name), ""
    except typer.Exit:
        reason = Text.from_ansi(said.get()).plain.strip().removeprefix("error:").strip()
    except Exception as exc:  # noqa: BLE001 - a broken adapter is a refusal, not a crash
        reason = f"{type(exc).__name__}: {exc}"
    return None, reason or "no reason given"


def probe_item(
    scope_repo: str, batch: Batch, *, closeout: bool, prefix: str = DEFAULT_WORKSPACE_PREFIX
) -> WorkItem:
    """The batch's (or its close-out's) run item identity: what a runner matches a session by."""
    from fr_dispatch.work_item import WorkItem

    item_id = (closeout_item_id if closeout else batch_item_id)(scope_repo, batch.id)
    return WorkItem(
        id=item_id,
        unit="run",
        workflow=batch_workflow(batch),
        repo=scope_repo,
        parent=None,
        inputs=(),
        payload={"group": wave_group(prefix, batch.wave)},
        tracking=None,
    )


def _runner_name(batch: Batch, *, closeout: bool) -> str:
    """The runner the batch's latest dispatch (or its close-out) event names, or a refusal."""
    if closeout:
        event = closeout_event(batch)
        if event is None:
            _fail(f"batch {batch.id!r} has no close-out event")
        if event.runner == "hand":
            _fail(f"batch {batch.id!r}: an adopted close-out has no session")
        return str(event.runner)
    dispatch = last_dispatch(batch)
    if dispatch is None:
        _fail(f"batch {batch.id!r} has no dispatch event")
    return str(dispatch.runner)


@batch_app.command("focus")
def batch_focus_command(
    batch_id: Annotated[str, typer.Argument(help="The batch whose session to focus.")],
    closeout: Annotated[
        bool, typer.Option("--closeout", help="Focus the close-out's session instead.")
    ] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Switch the terminal to a batch's live session, through the runner that dispatched it."""
    _, facts, judgements = _load_state(_scope(repo, org), dir_override)
    wanted = batch_id.lower()
    batch = next((b for b in judgements.batches if b.id == wanted), None)
    if batch is None:
        _fail(f"no batch {batch_id!r} in judgements.yaml")
    owner_repo = batch_repo(batch, facts)
    if owner_repo is None:
        _fail(f"batch {batch.id!r}: its repo {batch.repo_name!r} is not in this scope's facts")
    name = _runner_name(batch, closeout=closeout)
    runner, reason = _try_load(name)
    if runner is None:
        _fail(f"runner `{name}` could not be loaded ({reason})")
    from fr_dispatch.protocols import SessionFocuser

    if not isinstance(runner, SessionFocuser):
        _fail(f"runner `{name}` cannot focus a session")
    probe: Any = probe_item(owner_repo, batch, closeout=closeout)
    try:
        refusal = runner.preflight([probe])
        if refusal:
            _fail(f"runner `{name}` cannot focus: {refusal}")
        focused = runner.focus(probe)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001 - a failed focus is a refusal
        _fail(f"runner `{name}` failed to focus: {exc}")
    if not focused:
        _fail(f"no live session for {probe.id}")
    console.print(f"focused {probe.id}", markup=False)
