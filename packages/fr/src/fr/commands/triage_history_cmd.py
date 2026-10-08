"""`fr triage history render` (spec 2026-10-05-triage-pages-goal, R8, §F).

The same scope options as every `fr triage` verb. It reads the scope's state directory
(`facts.json`, `judgements.yaml`, `snapshots/`, `history/manifest.yaml` and the fragments
it names) and writes only `history.html` beside them, so `triage` stays in
`READ_ONLY_COMMANDS`. Exit codes: 0 success (a manifest entry with no file is reported, and
shown on the page, but is not a failure); 2 usage, a missing `facts.json` (the message names
the collect command), an unreadable state file, or a malformed fragment (nothing is written).
"""

from __future__ import annotations

import webbrowser

import typer
from rich.markup import escape

import fr.commands.triage_cmd as triage_cmd
from fr.commands.triage_cmd import (
    DirOpt,
    OrgOpt,
    RepoOpt,
    WorkspaceOpt,
    console,
    err_console,
    triage_app,
)
from fr.triage.errors import TriageError
from fr.triage.fragments import resolve_manifest
from fr.triage.history import GENERATED, HISTORY_DIR, MOVED, PAGE_FILE, render_history
from fr.triage.snapshot import stored_snapshots
from fr.triage.views import batch_stages, finished_waves

history_app = typer.Typer(
    name="history",
    help="The history page: the snapshot timeline and the finished waves.",
    no_args_is_help=True,
)
triage_app.add_typer(history_app)


@history_app.command("render")
def render_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
    open_: bool = typer.Option(False, "--open", help="Open the page in a browser."),
) -> None:
    """Write history.html: the snapshot timeline, the finished waves as tabs, then the
    authored fragments `history/manifest.yaml` places among them."""
    scope = triage_cmd._scope(repo, org)
    target, facts, judgements = triage_cmd._load_state(scope, dir_override, workspace)
    try:
        resolved = resolve_manifest(target / HISTORY_DIR, GENERATED, MOVED)
    except TriageError as exc:
        err_console.print(f"[red]error:[/red] {escape(str(exc))}", soft_wrap=True)
        raise typer.Exit(code=2) from exc
    notes = [f"manifest entry {name} has no file in {HISTORY_DIR}/" for name in resolved.missing]
    for name, page in resolved.moved.items():
        notes.append(f"manifest names `{name}`, which is now on the {page} page; skipped")
    if resolved.appended:
        notes.append(
            f"the manifest does not name {', '.join(resolved.appended)}; they are shown after "
            "the entries it lists, in the default order"
        )
    for note in notes:
        err_console.print(f"[yellow]warning:[/yellow] {escape(note)}", soft_wrap=True)
    out = target / PAGE_FILE
    out.write_text(
        render_history(
            facts,
            judgements,
            snapshots=stored_snapshots(target),
            resolved=resolved,
            notes=notes,
        ),
        encoding="utf-8",
    )
    done = finished_waves(judgements.batches, batch_stages(facts, judgements))
    console.print(
        f"wrote {out} ({len(done)} finished wave{'' if len(done) == 1 else 's'}, "
        f"{len(resolved.fragments)} fragment{'' if len(resolved.fragments) == 1 else 's'})",
        markup=False,
        soft_wrap=True,
    )
    if open_:
        webbrowser.open(out.resolve().as_uri())
