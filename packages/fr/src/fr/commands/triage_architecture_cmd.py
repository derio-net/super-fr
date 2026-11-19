"""`fr triage architecture render` (spec 2026-10-02-wave-driver, R11).

The same scope options as every `fr triage` verb. It reads the scope's state directory
(`facts.json`, `judgements.yaml`, `subsystems.yaml`, `architecture/manifest.yaml` and the
fragments it names) and the git checkout it measures, and writes only the Architecture
page beside them, so `triage` stays in `READ_ONLY_COMMANDS`. Exit codes: 0 success (a manifest
entry with no file is reported, and shown on the page, but is not a failure); 2 usage, a
missing `facts.json` (the message names the collect command), an unreadable state file, or
a malformed fragment (nothing is written).
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape

import fr.commands.triage_cmd as triage_cmd
from fr.artifacts.atomic import write_text_atomic
from fr.commands.triage_cmd import (
    DirOpt,
    OrgOpt,
    PageWritten,
    RepoOpt,
    WorkspaceOpt,
    console,
    err_console,
    say_warning,
    triage_app,
)
from fr.triage.architecture import (
    GENERATED,
    MOVED,
    SUBSYSTEMS_FILE,
    Measured,
    load_subsystems,
    measure_subsystems,
    render_architecture,
)
from fr.triage.components import fragment_dir, page, pages_present, refresh_navs
from fr.triage.errors import TriageError
from fr.triage.fragments import moved_notes, resolve_manifest
from fr.triage.gitseam import Checkout, GitError
from fr.triage.model import Scope
from fr.triage.render import plural

architecture_app = typer.Typer(
    name="architecture",
    help="The architecture page: measured sections plus authored fragments.",
    no_args_is_help=True,
)
triage_app.add_typer(architecture_app)


def _fail(message: str) -> typer.Exit:
    err_console.print(f"[red]error:[/red] {escape(message)}", soft_wrap=True)
    return typer.Exit(code=2)


def write_architecture(
    scope: Scope,
    target: Path,
    *,
    now: datetime,
    warn: Callable[[str], None] = say_warning,
    checkout: Checkout | Path | None = None,
    now_ref: str = "HEAD",
    measured: dict[str, Measured] | None = None,
) -> PageWritten:
    """Render the Architecture page into the state directory *target* with *now* as the
    render time (spec 2026-11-18-triage-pages-ux §C). Line counts are measured through
    *checkout* (a `Checkout`, or a path to a clone; None is the current directory's) at
    *now_ref*, unless *measured*, an earlier measurement, is given: then no git call is
    made. The measurement used is on the result. A clone that cannot be read is a warning
    and an unmeasured page. Raises `TriageError` for a broken subsystems file or manifest."""
    _, facts, judgements = triage_cmd._load_state(scope, target, None, read_only=True)
    subsystems = load_subsystems(target / SUBSYSTEMS_FILE)
    folder, _ = fragment_dir(target, "architecture")
    resolved = resolve_manifest(folder, GENERATED, MOVED)

    used: dict[str, Measured] = {}
    if measured is not None:
        used = measured
    elif subsystems.subsystems:
        try:
            clone = checkout if isinstance(checkout, Checkout) else Checkout.at(checkout)
            used = measure_subsystems(clone, subsystems, now_ref=now_ref)
        except GitError as exc:
            warn(f"not measured: {exc}")

    notes = [f"manifest entry {name} has no file in {folder.name}/" for name in resolved.missing]
    notes += moved_notes(resolved)
    if resolved.appended:
        notes.append(
            f"the manifest does not name {', '.join(resolved.appended)}; they are shown after "
            "the entries it lists, in the default order"
        )
    for note in notes:
        warn(note)
    out = target / page("architecture").file
    write_text_atomic(
        out,
        render_architecture(
            facts,
            judgements,
            subsystems=subsystems,
            measured=used,
            resolved=resolved,
            notes=notes,
            present=pages_present(target, "architecture"),
            rendered_at=now,
        ),
    )
    refresh_navs(target, "architecture", warn=triage_cmd.warn_nav)
    return PageWritten(
        out,
        f"{out} ({plural(len(subsystems.subsystems), 'subsystem')}, "
        f"{plural(len(resolved.fragments), 'fragment')})",
        measured=used,
    )


@architecture_app.command("render")
def render_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
    checkout: Annotated[
        Path | None,
        typer.Option("--checkout", help="Clone to measure (default: this checkout's toplevel)."),
    ] = None,
    now_ref: Annotated[
        str, typer.Option("--now-ref", help="The ref 'now' is measured at.")
    ] = "HEAD",
    open_: bool = typer.Option(False, "--open", help="Open the page in a browser."),
) -> None:
    """Write the Architecture page: the summary, subsystem cards and size table, with the
    authored fragments `architecture/manifest.yaml` places among them.

    Line counts are measured with `git ls-tree` and `git grep` at each subsystem's
    `then_ref` and at --now-ref; every measurement names its commit, and a figure that
    cannot be measured is an em dash.
    """
    scope = triage_cmd._scope(repo, org)
    target, _, _ = triage_cmd._load_state(scope, dir_override, workspace)
    try:
        written = write_architecture(
            scope, target, now=datetime.now(UTC), checkout=checkout, now_ref=now_ref
        )
    except TriageError as exc:
        raise _fail(str(exc)) from exc
    console.print(f"wrote {written.detail}", markup=False, soft_wrap=True)
    if open_:
        webbrowser.open(written.path.resolve().as_uri())
