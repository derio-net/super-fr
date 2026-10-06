"""`fr triage board` and `fr triage batch focus` — the board's only contact with
`fr_dispatch` (spec 2026-10-05-triage-batch-board §E; R1, R7, R8).

This module is `fr`'s third sanctioned soft point into `fr_dispatch`
(`tests/unit/test_import_direction.py` `_SOFT_POINTS`): every such import sits
inside a function, behind `importlib.util.find_spec("fr_dispatch")`. It imports
from `triage_cmd` and `fr.triage.*` only, never from `triage_batch_cmd`, so the
import between the two stays one-way.

Exit codes: 0 focused or written; 2 a refusal, always one line. Reading session
statuses never refuses: whatever goes wrong is `unknown` plus one page note (R7).
"""

from __future__ import annotations

import importlib.util
import time
import webbrowser
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn, get_args

import typer
from rich.markup import escape
from rich.text import Text

from fr.artifacts.atomic import write_text_atomic
from fr.commands.triage_cmd import (
    DirOpt,
    OrgOpt,
    RepoOpt,
    _load_state,
    _scope,
    batch_app,
    collect_into,
    console,
    err_console,
    triage_app,
)
from fr.triage.batch import batch_item_id, batch_repo, batch_workflow, last_dispatch
from fr.triage.batch_drive import (
    DEFAULT_WORKSPACE_PREFIX,
    closeout_event,
    closeout_item_id,
    wave_group,
)
from fr.triage.drive_lock import live_driver
from fr.triage.errors import TriageError
from fr.triage.kanban import BoardStatus, build_board
from fr.triage.kanban_render import render_board
from fr.triage.merge_stops import load_stops
from fr.triage.model import Facts, Judgements, Scope, state_dir
from fr.triage.render import plural
from fr.triage.scope_config import load_scope_config, publish_board, scope_id

if TYPE_CHECKING:
    from fr_dispatch.protocols import Runner
    from fr_dispatch.work_item import WorkItem

    from fr.triage.model import Batch

BOARD_FILE = "board.html"
DEFAULT_REFRESH = 30
DEFAULT_WATCH_INTERVAL = 60
_STATUSES = frozenset(get_args(BoardStatus))

DISPATCH_INSTALL_HINT = (
    "this requires fr-dispatch — install it "
    "(e.g. `uv tool install --with fr-dispatch fr`) and re-run."
)


def _fail(message: str, code: int = 2) -> NoReturn:
    err_console.print(f"[red]error:[/red] {escape(message)}", soft_wrap=True)
    raise typer.Exit(code=code)


def one_line(exc: BaseException) -> str:
    """*exc*'s message on one line, or its type name when it has none."""
    return " ".join(str(exc).split()) or type(exc).__name__


def load_runner(name: str, install_hint: str = DISPATCH_INSTALL_HINT) -> Runner:
    """Build runner *name* through `fr_dispatch.registry.load_runner`.

    The soft point: `fr_dispatch` is imported here, behind find_spec, never at
    module level. Tests replace this. `triage_batch_cmd.load_runner` delegates
    here with its own install hint.
    """
    if importlib.util.find_spec("fr_dispatch") is None:
        _fail(install_hint)
    from fr_dispatch.registry import RunnerLoadError
    from fr_dispatch.registry import load_runner as _load

    try:
        return _load(name)
    except RunnerLoadError as exc:
        _fail(str(exc))


def try_load(name: str, loader: Callable[[str], Runner] | None = None) -> tuple[Runner | None, str]:
    """Runner *name* and no reason, or None and why it could not be loaded.

    `load_runner` reports a refusal through `_fail` (a red `error:` and an exit);
    an adapter's own import or `from_env()` failure is any exception. Either is
    one line of reason here, never a traceback and never printed. *loader* defaults
    to this module's `load_runner`; the drive passes its own cached one.
    """
    load = loader or load_runner
    try:
        with err_console.capture() as said:
            return load(name), ""
    except typer.Exit:
        text = Text.from_ansi(said.get()).plain.strip().removeprefix("error:").strip()
        reason = " ".join(text.split())
    except Exception as exc:  # noqa: BLE001 - a broken adapter is a refusal, not a crash
        reason = f"{type(exc).__name__}: {one_line(exc)}"
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
    runner, reason = try_load(name)
    if runner is None:
        _fail(f"runner `{name}` could not be loaded ({reason})")
    from fr_dispatch.protocols import SessionFocuser

    if not isinstance(runner, SessionFocuser):
        _fail(f"runner `{name}` cannot focus a session")
    probe = probe_item(owner_repo, batch, closeout=closeout)
    try:
        refusal = runner.preflight([probe])
        if refusal:
            _fail(f"runner `{name}` cannot focus: {refusal}")
        focused = runner.focus(probe)
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001 - a failed focus is a refusal
        _fail(f"runner `{name}` failed to focus: {one_line(exc)}")
    if not focused:
        _fail(f"no live session for {probe.id}")
    console.print(f"focused {probe.id}", markup=False)


# ---------------------------------------------------------------- the board


def scope_args(repo: str | None, org: str | None, dir_override: Path | None) -> list[str]:
    """The options a copied command carries so it reads the same state: `--repo` or `--org`
    as the operator gave it, and `--dir` only when they did (R5), made absolute: the
    command is pasted in another pane, whose working directory is not this one's."""
    args = ["--repo", repo] if repo is not None else ["--org", str(org)]
    if dir_override is not None:
        args += ["--dir", str(dir_override.resolve())]
    return args


def _probes(judgements: Judgements, facts: Facts, prefix: str) -> dict[str, list[WorkItem]]:
    """Each batch's session (its latest dispatch's runner) and each runner-started
    close-out's (its own), as probe items grouped by runner name. A `hand` close-out
    has no session and is never probed."""
    by_runner: dict[str, list[WorkItem]] = {}
    for batch in judgements.batches:
        repo = batch_repo(batch, facts)
        if repo is None:
            continue
        dispatch, closeout = last_dispatch(batch), closeout_event(batch)
        wanted = [(False, dispatch.runner)] if dispatch else []
        if closeout is not None and closeout.runner != "hand":
            wanted.append((True, closeout.runner))
        for is_closeout, name in wanted:
            probe = probe_item(repo, batch, closeout=is_closeout, prefix=prefix)
            by_runner.setdefault(str(name), []).append(probe)
    return by_runner


def session_statuses(
    judgements: Judgements, facts: Facts, *, prefix: str = DEFAULT_WORKSPACE_PREFIX
) -> tuple[dict[str, BoardStatus], list[str]]:
    """The live status of each batch's and each runner close-out's session, by item id,
    and one page note per runner that could not say (R7).

    Never refuses and prints nothing: a runner that cannot be loaded, fails its
    preflight, lacks `SessionInspector` or raises leaves its items out of the result
    (the board shows them `unknown`) and costs one note.
    """
    by_runner = _probes(judgements, facts, prefix) if judgements.batches else {}
    if not by_runner:
        return {}, []
    if importlib.util.find_spec("fr_dispatch") is None:
        return {}, ["fr-dispatch is not installed; session status is unavailable"]
    from fr_dispatch.protocols import SessionInspector

    statuses: dict[str, BoardStatus] = {}
    notes: list[str] = []
    for name, probes in sorted(by_runner.items()):
        runner, reason = try_load(name)
        if runner is None:
            notes.append(
                f"runner `{name}` could not be loaded ({reason}); its sessions show unknown"
            )
            continue
        if not isinstance(runner, SessionInspector):
            notes.append(f"runner `{name}` cannot report session status; its sessions show unknown")
            continue
        try:
            refusal = runner.preflight(probes)
            if refusal:
                notes.append(
                    f"runner `{name}` cannot report sessions: {' '.join(refusal.split())}; "
                    "its sessions show unknown"
                )
                continue
            found = runner.session_statuses(probes)
        except Exception as exc:  # noqa: BLE001 - a failed read is `unknown`, never a failed render
            notes.append(
                f"runner `{name}` failed to report sessions: {one_line(exc)}; "
                "its sessions show unknown"
            )
            continue
        for key, value in found.items():
            statuses[key] = value if value in _STATUSES else "unknown"
    return statuses, notes


def write_board(
    scope: Scope,
    target: Path,
    *,
    scope_args: Sequence[str],
    refresh: int = DEFAULT_REFRESH,
    prefix: str = DEFAULT_WORKSPACE_PREFIX,
) -> tuple[Path, int]:
    """Render `board.html` into the state directory *target* from the facts and judgements
    on disk now, with live session statuses. Returns the path written and its card count."""
    _, facts, judgements = _load_state(scope, target)
    statuses, notes = session_statuses(judgements, facts, prefix=prefix)
    now = datetime.now(UTC)
    try:
        me: str | None = scope_id(facts.scope)
    except TriageError as exc:  # the board is a view: say what it cannot show, never refuse
        me = None
        notes.append(f"claims are not shown: {one_line(exc)}")
    board = build_board(facts, judgements, statuses, stops=load_stops(target), me=me, now=now)
    page = render_board(
        board,
        scope_args=scope_args,
        rendered_at=now,
        refresh=refresh,
        notes=notes,
    )
    out = target / BOARD_FILE
    write_text_atomic(out, page)
    return out, len(judgements.batches)


def publish(scope: Scope, target: Path, board: Path, failures: set[str]) -> None:
    """Run the scope's configured `publish` command for *board* (R14). A failure is one
    warning per distinct cause (*failures* remembers them; a success forgets) and never
    changes an exit code, and a broken scope.yaml is the same kind of warning."""
    try:
        cause = publish_board(scope, load_scope_config(target), board)
    except TriageError as exc:
        cause = one_line(exc)
    if cause is None:
        failures.clear()
    elif cause not in failures:
        failures.add(cause)
        err_console.print(
            f"[yellow]warning:[/yellow] could not publish the board: {escape(cause)}",
            soft_wrap=True,
        )


def recollect(scope: Scope, target: Path) -> None:
    """Collect facts.json as `fr triage collect` does (no carry-over); tests replace this."""
    collect_into(scope, target)


def _sleep(seconds: float) -> None:
    """The watch loop's wait between iterations; tests replace it."""
    time.sleep(seconds)


def _watch(
    scope: Scope,
    target: Path,
    args: Sequence[str],
    refresh: int,
    interval: int,
    open_: bool,
    publish_: bool = False,
) -> None:
    """Re-collect and re-render every *interval* seconds until interrupted (R12). A live
    drive keeps the board fresh itself, so an iteration that finds its lock held skips."""
    if (holder := live_driver(target)) is not None:
        _fail(f"a drive ({holder}) holds {target / 'drive.lock'}; it keeps the board fresh")
    skipping, failures, opened = False, set[str](), False
    publish_failures: set[str] = set()

    def recovered(what: str) -> None:
        failures.difference_update({f for f in failures if f.startswith(f"{what}\0")})

    def warn_once(what: str, exc: BaseException) -> None:
        reason = one_line(exc)
        if f"{what}\0{reason}" not in failures:
            failures.add(f"{what}\0{reason}")
            err_console.print(
                f"[yellow]warning:[/yellow] {what} failed: {escape(reason)}; "
                f"retrying every {interval}s",
                soft_wrap=True,
            )

    try:
        while True:
            if (holder := live_driver(target)) is not None:
                if not skipping:
                    skipping = True
                    console.print(
                        f"a drive ({holder}) now holds the lock: skipping collect and render "
                        "until it is gone",
                        markup=False,
                        soft_wrap=True,
                    )
                _sleep(interval)
                continue
            skipping = False
            # Nothing but an interrupt ends the watch (R12): a degraded forge, a missing
            # facts.json or a failed write is one warning per cause, then the next interval.
            try:
                recollect(scope, target)
            except Exception as exc:  # noqa: BLE001
                warn_once("collect", exc)
            else:
                recovered("collect")
            try:
                with err_console.capture() as said:
                    out, cards = write_board(scope, target, scope_args=args, refresh=refresh)
            except typer.Exit:
                text = Text.from_ansi(said.get()).plain.strip().removeprefix("error:").strip()
                warn_once("render", RuntimeError(text or "refused"))
            except Exception as exc:  # noqa: BLE001
                warn_once("render", exc)
            else:
                recovered("render")
                console.print(
                    f"wrote {out} ({plural(cards, 'batch')})", markup=False, soft_wrap=True
                )
                if publish_:
                    publish(scope, target, out, publish_failures)
                if open_ and not opened:
                    webbrowser.open(out.resolve().as_uri())
                    opened = True
            _sleep(interval)
    except KeyboardInterrupt:
        console.print("stopped", markup=False)


@triage_app.command("board")
def board_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    refresh: Annotated[
        int,
        typer.Option("--refresh", min=0, help="Reload the page every N seconds (0: never)."),
    ] = DEFAULT_REFRESH,
    open_: Annotated[bool, typer.Option("--open", help="Open the board in a browser.")] = False,
    watch: Annotated[
        bool,
        typer.Option(
            "--watch", help="Re-collect and re-render every --interval seconds until interrupted."
        ),
    ] = False,
    interval: Annotated[
        int, typer.Option("--interval", min=1, help="Seconds between --watch iterations.")
    ] = DEFAULT_WATCH_INTERVAL,
    publish_: Annotated[
        bool,
        typer.Option(
            "--publish",
            help="After each render, run the scope's `publish` command from scope.yaml.",
        ),
    ] = False,
) -> None:
    """Write board.html: one card per batch in six lifecycle columns, with live session
    status and a jump command. Reads facts.json and judgements.yaml; collects nothing."""
    scope = _scope(repo, org)
    target = state_dir(scope, dir_override)
    args = scope_args(repo, org, dir_override)
    if watch:
        _watch(scope, target, args, refresh, interval, open_, publish_)
        return
    out, cards = write_board(scope, target, scope_args=args, refresh=refresh)
    console.print(f"wrote {out} ({plural(cards, 'batch')})", markup=False, soft_wrap=True)
    if publish_:
        publish(scope, target, out, set())
    if open_:
        webbrowser.open(out.resolve().as_uri())
