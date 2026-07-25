"""`fr journal ...` CLI — the scope-keyed durable run-state primitive.

Spec: docs/superpowers/specs/2026-07-22-fr-goal-subagent-execution-design.md §A.

Three verbs:
  - ``add``    append one entry (idempotent on ``--id``).
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
        None, "--id", help="Stable id; re-adding the same id is idempotent."
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
        # Idempotent: the id is already recorded; leave the file untouched.
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    block = serialize_entry(entry)
    if path.exists():
        prior = path.read_text()
        sep = "" if prior.endswith("\n\n") else ("\n" if prior.endswith("\n") else "\n\n")
        path.write_text(prior + sep + block)
    else:
        path.write_text(f"# Journal: {slug}\n\n{block}")


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
