"""`fr triage history render` (spec 2026-10-05-triage-pages-goal, R8, §F).

The same scope options as every `fr triage` verb. It reads the scope's state directory
(`facts.json`, `judgements.yaml`, `snapshots/`, `history/manifest.yaml` and the fragments
it names) and writes only the History page beside them, so `triage` stays in
`READ_ONLY_COMMANDS`. Exit codes: 0 success (a manifest entry with no file is reported, and
shown on the page, but is not a failure); 2 usage, a missing `facts.json` (the message names
the collect command), an unreadable state file, or a malformed fragment (nothing is written).
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import typer

import fr.commands.triage_cmd as triage_cmd
from fr.artifacts.atomic import write_text_atomic
from fr.commands.triage_cmd import (
    DirOpt,
    OrgOpt,
    PageWritten,
    RepoOpt,
    WorkspaceOpt,
    console,
    say_warning,
    triage_app,
)
from fr.triage.components import fragment_dir, page, pages_present, refresh_navs
from fr.triage.errors import TriageError
from fr.triage.fragments import moved_notes, resolve_manifest
from fr.triage.history import GENERATED, MOVED, render_history
from fr.triage.model import Scope
from fr.triage.snapshot import stored_snapshots
from fr.triage.views import batch_stages, finished_waves

history_app = typer.Typer(
    name="history",
    help="The history page: the snapshot timeline and the finished waves.",
    no_args_is_help=True,
)
triage_app.add_typer(history_app)


def write_history(
    scope: Scope,
    target: Path,
    *,
    now: datetime,
    warn: Callable[[str], None] = say_warning,
) -> PageWritten:
    """Render the History page into the state directory *target* with *now* as the render
    time (spec 2026-11-18-triage-pages-ux §C). Raises `TriageError` for a broken manifest."""
    _, facts, judgements = triage_cmd._load_state(scope, target, None, read_only=True)
    folder, _ = fragment_dir(target, "history")
    resolved = resolve_manifest(folder, GENERATED, MOVED)
    notes = [f"manifest entry {name} has no file in {folder.name}/" for name in resolved.missing]
    notes += moved_notes(resolved)
    if resolved.appended:
        notes.append(
            f"the manifest does not name {', '.join(resolved.appended)}; they are shown after "
            "the entries it lists, in the default order"
        )
    for note in notes:
        warn(note)
    out = target / page("history").file
    write_text_atomic(
        out,
        render_history(
            facts,
            judgements,
            snapshots=stored_snapshots(target),
            resolved=resolved,
            notes=notes,
            present=pages_present(target, "history"),
            rendered_at=now,
        ),
    )
    refresh_navs(target, "history", warn=triage_cmd.warn_nav)
    done = finished_waves(judgements.batches, batch_stages(facts, judgements))
    return PageWritten(
        out,
        f"{out} ({len(done)} finished wave{'' if len(done) == 1 else 's'}, "
        f"{len(resolved.fragments)} fragment{'' if len(resolved.fragments) == 1 else 's'})",
    )


@history_app.command("render")
def render_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
    open_: bool = typer.Option(False, "--open", help="Open the page in a browser."),
) -> None:
    """Write the History page: the snapshot timeline, the finished waves as tabs, then the
    authored fragments `history/manifest.yaml` places among them."""
    scope = triage_cmd._scope(repo, org)
    target, _, _ = triage_cmd._load_state(scope, dir_override, workspace)
    try:
        written = write_history(scope, target, now=datetime.now(UTC))
    except TriageError as exc:
        raise triage_cmd.refuse(exc) from exc
    console.print(f"wrote {written.detail}", markup=False, soft_wrap=True)
    if open_:
        webbrowser.open(written.path.resolve().as_uri())
