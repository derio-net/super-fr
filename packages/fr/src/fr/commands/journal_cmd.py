"""`fr journal ...` CLI — the scope-keyed durable run-state primitive.

Spec: docs/superpowers/specs/2026-07-22-fr-goal-subagent-execution-design.md §A.

Four verbs:
   - ``add``    append one entry (duplicate ``--id`` values fail loudly).
   - ``update`` change a finding's state and optionally append a resolution note.
  - ``render`` emit the Markdown a PR body embeds (fail-open on missing/bad file).
  - ``check``  freshness gate: non-zero on open findings or a parse error
               (fail-closed), so a stale journal cannot ride into a PR silently.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import typer
from rich.console import Console

from fr.commands.common import resolve_repo_root
from fr.journal.model import (
    JournalEntry,
    JournalParseError,
    journal_path,
    parse_journal,
    resolve_journal_read_path,
    serialize_entry,
)

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

journal_app = typer.Typer(
    help="Scope-keyed durable run-state (spec|plan|debug): add / update / render / check.",
    no_args_is_help=True,
)


def _timestamp() -> str:
    """Wall-clock ISO stamp. Isolated so tests could monkeypatch if needed."""
    import datetime as _dt

    return _dt.datetime.now().replace(microsecond=0).isoformat()


def _load(path: Path) -> list[JournalEntry]:
    if not path.exists():
        return []
    return parse_journal(path.read_text())


@journal_app.command("add")
def add(
    scope: str = typer.Option(..., "--scope", help="spec | plan | debug."),
    slug: str = typer.Option(..., "--slug", help="Journal slug (spec/plan/debug slug)."),
    kind: str = typer.Option(..., "--kind", help="Entry kind (see spec §A)."),
    title: str = typer.Option(..., "--title", help="One-line entry title."),
    body: str = typer.Option("", "--body", help="Entry body (Markdown)."),
    phase: int | None = typer.Option(None, "--phase", help="Phase number, if any."),
    state: str | None = typer.Option(None, "--state", help="finding only: fixed | refuted | open."),
    entry_id: str | None = typer.Option(
        None, "--id", help="Stable entry id; must be unique within the journal."
    ),
) -> None:
    """Append one entry to ``docs/superpowers/journals/<slug>.md``."""
    root = resolve_repo_root()
    path = journal_path(root, scope, slug)  # type: ignore[arg-type]

    stamp = _timestamp()
    eid = (
        entry_id or hashlib.sha1(f"{kind}|{scope}|{slug}|{title}|{body}".encode()).hexdigest()[:12]
    )

    try:
        entry = JournalEntry(
            kind=kind,  # type: ignore[arg-type]
            scope=scope,  # type: ignore[arg-type]
            id=eid,
            created=stamp,
            phase=phase,
            title=title,
            body=body,
            state=state,  # type: ignore[arg-type]
        )
    except ValueError as e:
        err_console.print(f"[red]invalid entry:[/red] {e}")
        raise typer.Exit(2) from e

    existing = _load(path)
    if any(e.id == eid for e in existing):
        err_console.print(
            f"[red]duplicate journal id:[/red] {eid}; use `fr journal update --id {eid} ...` "
            "to change a finding."
        )
        raise typer.Exit(2)
    path.parent.mkdir(parents=True, exist_ok=True)
    block = serialize_entry(entry)
    if path.exists():
        prior = path.read_text()
        sep = "" if prior.endswith("\n\n") else ("\n" if prior.endswith("\n") else "\n\n")
        path.write_text(prior + sep + block)
    else:
        path.write_text(f"# Journal: {slug}\n\n{block}")


@journal_app.command("update")
def update(
    scope: str = typer.Option(..., "--scope", help="spec | plan | debug."),
    slug: str = typer.Option(..., "--slug", help="Journal slug (spec/plan/debug slug)."),
    entry_id: str = typer.Option(..., "--id", help="Existing finding id."),
    state: str = typer.Option(..., "--state", help="fixed | refuted | open."),
    note: str | None = typer.Option(
        None, "--note", help="Resolution detail appended to the finding body."
    ),
) -> None:
    """Update a finding's state while preserving its identity and creation time."""
    root = resolve_repo_root()
    path = resolve_journal_read_path(root, scope, slug)  # type: ignore[arg-type]
    try:
        entries = _load(path)
    except JournalParseError as e:
        err_console.print(f"[red]journal parse error:[/red] {e}")
        raise typer.Exit(2) from e
    current = next((entry for entry in entries if entry.id == entry_id), None)
    if current is None:
        err_console.print(f"[red]error:[/red] no journal entry with id {entry_id!r}")
        raise typer.Exit(2)
    if current.kind != "finding":
        err_console.print(f"[red]error:[/red] journal entry {entry_id!r} is not a finding")
        raise typer.Exit(2)
    body = current.body if note is None else f"{current.body.rstrip()}\n\n{note}".lstrip()
    try:
        replacement = JournalEntry.model_validate(
            current.model_dump() | {"state": state, "body": body}
        )
    except ValueError as e:
        err_console.print(f"[red]invalid update:[/red] {e}")
        raise typer.Exit(2) from e
    original = path.read_text()
    offsets: list[int] = []
    offset = 0
    for line in original.splitlines(keepends=True):
        if line.startswith("<!-- fr:journal "):
            offsets.append(offset)
        offset += len(line)
    start = next(
        offset
        for offset in offsets
        if f"id={entry_id}" in original[offset : original.find(" -->", offset)].split()
    )
    end = next((offset for offset in offsets if offset > start), len(original))
    path.write_text(original[:start] + serialize_entry(replacement) + original[end:])
    typer.echo(f"updated finding {entry_id} to {replacement.state}")


_SECTION_KINDS = {
    "findings": {"finding"},
    "decisions": {"decision"},
    "discoveries": {"discovery"},
    "reviews": {"review"},
}


@journal_app.command("render")
def render(
    scope: str = typer.Option(..., "--scope"),
    slug: str = typer.Option(..., "--slug"),
    section: str = typer.Option(
        "all", "--section", help="findings | decisions | discoveries | reviews | all."
    ),
) -> None:
    """Emit journal entries as Markdown (fail-open: missing/bad file → nothing)."""
    root = resolve_repo_root()
    # Read-resolve so a render still works after the spec/plan was archived.
    path = resolve_journal_read_path(root, scope, slug)  # type: ignore[arg-type]
    try:
        entries = _load(path)
    except JournalParseError:
        return  # fail-open: never block a render on a malformed file
    keep = _SECTION_KINDS.get(section)
    if keep is not None:
        entries = [e for e in entries if e.kind in keep]
    if not entries:
        return
    # Emit RAW — this feeds a PR body. A Rich console would treat `[...]` in a
    # finding title/body (Markdown links, `[PR #12]`) as markup and drop it.
    typer.echo("\n".join(serialize_entry(e) for e in entries))


@journal_app.command("check")
def check(
    scope: str = typer.Option(..., "--scope"),
    slug: str = typer.Option(..., "--slug"),
) -> None:
    """Freshness gate. Non-zero on a parse error or any `open` finding."""
    root = resolve_repo_root()
    # Read-resolve so a check still gates on an archived journal's findings.
    path = resolve_journal_read_path(root, scope, slug)  # type: ignore[arg-type]
    try:
        entries = _load(path)
    except JournalParseError as e:
        err_console.print(f"[red]journal parse error:[/red] {e}")
        raise typer.Exit(2) from e
    open_findings = [e for e in entries if e.kind == "finding" and e.state == "open"]
    if open_findings:
        err_console.print(
            f"[yellow]{len(open_findings)} open finding(s):[/yellow] "
            + ", ".join(e.id for e in open_findings)
        )
        raise typer.Exit(1)


@journal_app.command("handoff")
def handoff(
    scope: str = typer.Option(..., "--scope", help="plan (only plan journals have phases)."),
    slug: str = typer.Option(..., "--slug", help="Journal slug (plan slug for scope=plan)."),
    phase: int = typer.Option(..., "--phase", help="Phase number to compose the handoff for."),
    plan_dir: str | None = typer.Option(
        None,
        "--plan-dir",
        help="Plan folder (default docs/superpowers/plans/<slug>); the phase's "
        "depends_on comes from here.",
    ),
) -> None:
    """Compose the curated executor handoff for one phase (fail-closed).

    Unlike `render` (PR-body feed, fail-open), the handoff feeds an executor
    brief — a silently-empty handoff makes the executor guess, so a missing
    plan, an unknown phase, or a malformed journal is exit 2 naming what is
    wrong. Only a journal that was never written is empty (exit 0, no output):
    there is nothing to curate yet.
    """
    from fr.journal.model import compose_handoff
    from fr.parser import PlanSchemaError, parse

    if scope != "plan":
        err_console.print(
            f"[red]handoff needs --scope plan (got {scope!r}) — only plan journals "
            "have phases to compose for[/red]"
        )
        raise typer.Exit(2)
    root = resolve_repo_root()
    # Read-resolve so a handoff still composes after the journal was archived
    # alongside its spec/plan.
    path = resolve_journal_read_path(root, scope, slug)  # type: ignore[arg-type]
    if not path.exists():
        return  # fail-open: nothing written yet, nothing to curate
    try:
        entries = _load(path)
    except JournalParseError as e:
        err_console.print(f"[red]journal parse error:[/red] {e}")
        raise typer.Exit(2) from e
    plan_path = root / plan_dir if plan_dir else root / "docs" / "superpowers" / "plans" / slug
    try:
        plan = parse(plan_path)
    except (PlanSchemaError, OSError) as e:
        err_console.print(
            f"[red]cannot compose a dependency-scoped handoff: plan {plan_path} "
            f"is not parseable ({e})[/red]"
        )
        raise typer.Exit(2) from e
    headers = [p.phase for p in plan.phases if p.phase.number == phase]
    if not headers:
        known = sorted(p.phase.number for p in plan.phases)
        err_console.print(
            f"[red]phase {phase} is not a phase of plan {slug} (phases: {known})[/red]"
        )
        raise typer.Exit(2)
    depends_on = tuple(headers[0].depends_on)
    # Emit RAW — this feeds a dispatch brief. A Rich console would treat `[...]`
    # in a title/body (Markdown links, `[PR #12]`) as markup and drop it, same
    # reason `render` echoes raw.
    typer.echo(compose_handoff(entries, phase=phase, scope=scope, slug=slug, depends_on=depends_on))
