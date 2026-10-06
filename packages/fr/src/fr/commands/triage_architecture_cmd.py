"""`fr triage architecture render` (spec 2026-10-02-wave-driver, R11).

The same scope options as every `fr triage` verb. It reads the scope's state directory
(`facts.json`, `judgements.yaml`, `subsystems.yaml`, `architecture/manifest.yaml` and the
fragments it names) and the git checkout it measures, and writes only `architecture.html`
beside them, so `triage` stays in `READ_ONLY_COMMANDS`. Exit codes: 0 success (a manifest
entry with no file is reported, and shown on the page, but is not a failure); 2 usage, a
missing `facts.json` (the message names the collect command), an unreadable state file, or
a malformed fragment (nothing is written).
"""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape

import fr.commands.triage_cmd as triage_cmd
from fr.commands.triage_cmd import DirOpt, OrgOpt, RepoOpt, console, err_console, triage_app
from fr.triage.architecture import (
    ARCHITECTURE_DIR,
    GENERATED,
    MOVED,
    PAGE_FILE,
    SUBSYSTEMS_FILE,
    Measured,
    load_subsystems,
    measure_subsystems,
    render_architecture,
)
from fr.triage.errors import TriageError
from fr.triage.fragments import resolve_manifest
from fr.triage.gitseam import Checkout, GitError
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


def _warn(message: str) -> None:
    err_console.print(f"[yellow]warning:[/yellow] {escape(message)}", soft_wrap=True)


@architecture_app.command("render")
def render_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    checkout: Annotated[
        Path | None,
        typer.Option("--checkout", help="Clone to measure (default: this checkout's toplevel)."),
    ] = None,
    now_ref: Annotated[
        str, typer.Option("--now-ref", help="The ref 'now' is measured at.")
    ] = "HEAD",
    open_: bool = typer.Option(False, "--open", help="Open the page in a browser."),
) -> None:
    """Write architecture.html: the summary, subsystem cards and size table, with the
    authored fragments `architecture/manifest.yaml` places among them.

    Line counts are measured with `git ls-tree` and `git grep` at each subsystem's
    `then_ref` and at --now-ref; every measurement names its commit, and a figure that
    cannot be measured is an em dash.
    """
    scope = triage_cmd._scope(repo, org)
    target, facts, judgements = triage_cmd._load_state(scope, dir_override)
    try:
        subsystems = load_subsystems(target / SUBSYSTEMS_FILE)
        resolved = resolve_manifest(target / ARCHITECTURE_DIR, GENERATED, MOVED)
    except TriageError as exc:
        raise _fail(str(exc)) from exc

    measured: dict[str, Measured] = {}
    if subsystems.subsystems:
        try:
            measured = measure_subsystems(Checkout.at(checkout), subsystems, now_ref=now_ref)
        except GitError as exc:
            _warn(f"not measured: {exc}")

    notes = [
        f"manifest entry {name} has no file in {ARCHITECTURE_DIR}/" for name in resolved.missing
    ]
    for name, page in resolved.moved.items():
        notes.append(f"manifest names `{name}`, which is now on the {page} page; skipped")
    if resolved.appended:
        notes.append(
            f"the manifest does not name {', '.join(resolved.appended)}; they are shown after "
            "the entries it lists, in the default order"
        )
    for note in notes:
        _warn(note)
    out = target / PAGE_FILE
    out.write_text(
        render_architecture(
            facts,
            judgements,
            subsystems=subsystems,
            measured=measured,
            resolved=resolved,
            notes=notes,
        ),
        encoding="utf-8",
    )
    console.print(
        f"wrote {out} ({plural(len(subsystems.subsystems), 'subsystem')}, "
        f"{plural(len(resolved.fragments), 'fragment')})",
        markup=False,
        soft_wrap=True,
    )
    if open_:
        webbrowser.open(out.resolve().as_uri())
