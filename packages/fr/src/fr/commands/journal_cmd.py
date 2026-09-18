"""`fr journal ...` CLI — the scope-keyed durable run-state primitive.

Spec: docs/superpowers/specs/2026-07-22-fr-goal-subagent-execution-design.md §A.

Four verbs:
  - ``add``    append one entry (create-only on ``--id``).
  - ``update`` change a finding's state and append a resolution note.
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
    help="Scope-keyed durable run-state (spec|plan|debug): add / render / check.",
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


def _validate_scope(scope: str) -> None:
    if scope not in {"spec", "plan", "debug"}:
        err_console.print(
            f"[red]invalid journal scope: {scope!r} (expected spec, plan, or debug)[/red]"
        )
        raise typer.Exit(2)


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
        None, "--id", help="Stable id; duplicate ids are rejected."
    ),
) -> None:
    """Append one entry to ``docs/superpowers/journals/<slug>.md``."""
    _validate_scope(scope)
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

    try:
        existing = _load(path)
    except JournalParseError as e:
        err_console.print(f"[red]journal parse error:[/red] {e}")
        raise typer.Exit(2) from e
    if any(e.id == eid for e in existing):
        err_console.print(
            f"[red]journal entry {eid!r} already exists; use `fr journal update` "
            "to change a finding[/red]"
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
    state: str = typer.Option(..., "--state", help="finding state: open | fixed | refuted."),
    note: str | None = typer.Option(None, "--note", help="Resolution note to append."),
) -> None:
    """Update one finding while preserving journal preamble and entry order."""
    _validate_scope(scope)
    root = resolve_repo_root()
    # Resolve through the archive boundary: never create an active twin for an
    # archived journal that is the current readable source of truth.
    path = resolve_journal_read_path(root, scope, slug)  # type: ignore[arg-type]
    if not path.exists():
        err_console.print(f"[red]journal {scope}/{slug} does not exist[/red]")
        raise typer.Exit(2)

    text = path.read_text()
    try:
        entries = parse_journal(text)
    except JournalParseError as e:
        err_console.print(f"[red]journal parse error:[/red] {e}")
        raise typer.Exit(2) from e
    if not all(entry._rewrite_safe for entry in entries):
        err_console.print(
            "[red]journal contains legacy headings that cannot be safely rewritten[/red]"
        )
        raise typer.Exit(2)

    target = next((entry for entry in entries if entry.id == entry_id), None)
    if target is None:
        err_console.print(f"[red]journal finding {entry_id!r} does not exist[/red]")
        raise typer.Exit(2)
    if target.kind != "finding":
        err_console.print(f"[red]journal entry {entry_id!r} is not a finding[/red]")
        raise typer.Exit(2)

    body = target.body if note is None else f"{target.body}\n\n{note}".strip()
    try:
        data = target.model_dump()
        data.update(state=state, body=body)
        replacement = JournalEntry(**data)  # type: ignore[arg-type]
    except ValueError as e:
        err_console.print(f"[red]invalid finding update:[/red] {e}")
        raise typer.Exit(2) from e

    # Parsing has succeeded and every requested replacement has been validated;
    # only now construct and write the canonical journal body.
    marker = "<!-- fr:journal "
    preamble = text[: text.index(marker)]
    rewritten = [replacement if entry.id == entry_id else entry for entry in entries]
    path.write_text(preamble + "\n".join(serialize_entry(entry) for entry in rewritten))


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
