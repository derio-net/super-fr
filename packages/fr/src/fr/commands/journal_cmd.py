"""`fr journal ...` CLI — the scope-keyed durable run-state primitive.

Spec: docs/superpowers/specs/2026-07-22-fr-goal-subagent-execution-design.md §A.

Verbs:
  - ``add``     append one entry (create-only; duplicate ``--id`` is refused).
  - ``resolve`` append a RESOLUTION RECORD closing a finding (spec §3.G.1) —
                never a rewrite of the finding, which would erase that it was
                ever open.
  - ``render``  emit the Markdown a PR body embeds (fail-open on missing/bad file).
  - ``check``   freshness gate: non-zero on open findings or a parse error
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
    open_finding_ids,
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
        None, "--id", help="Stable id; re-adding the same id is idempotent."
    ),
    resolves: str | None = typer.Option(
        None,
        "--resolves",
        help="finding only: this entry is a resolution record for that finding id "
        "(`fr journal resolve` is the ergonomic form; use this to RE-OPEN one).",
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
            resolves=resolves,
        )
    except ValueError as e:
        err_console.print(f"[red]invalid entry:[/red] {e}")
        raise typer.Exit(2) from e

    existing = _load(path)
    if any(e.id == eid for e in existing):
        err_console.print(
            f"[red]journal entry {eid!r} already exists; use `fr journal resolve` "
            "to change a finding[/red]"
        )
        raise typer.Exit(2)
    # Review r7-m2: `resolve` refuses an unknown id, and so must `--resolves`.
    # `effective_finding_states` deliberately tolerates a record naming a
    # finding that is not there, so that a hand-spliced journal cannot crash the
    # gate — which means a typo'd id here would report as open FOREVER with
    # nothing in the file to explain it. A gate wedged by an unfindable id is
    # the silent-stall shape this PR exists to remove, so refuse it at the door.
    if resolves is not None and not any(e.id == resolves and e.kind == "finding" for e in existing):
        err_console.print(
            f"[red]no finding with id {resolves!r} in this journal[/red] — "
            "`--resolves` must name a finding that exists"
        )
        raise typer.Exit(2)
    _append_entry(path, slug, entry)


def _append_entry(path: Path, slug: str, entry: JournalEntry) -> None:
    """The ONE writer — `add` and `resolve` both land here, so the two cannot
    disagree about separators, the file header, or the serialized shape."""
    path.parent.mkdir(parents=True, exist_ok=True)
    block = serialize_entry(entry)
    if path.exists():
        prior = path.read_text()
        sep = "" if prior.endswith("\n\n") else ("\n" if prior.endswith("\n") else "\n\n")
        path.write_text(prior + sep + block)
    else:
        path.write_text(f"# Journal: {slug}\n\n{block}")


RESOLUTION_STATES = ("fixed", "refuted")
"""What `resolve` may close a finding to. Re-opening is `add --resolves`:
`resolve` is the verb for "this is done with", and a re-open is new
information, which belongs in an entry with a body of its own."""


def _record_id(finding_id: str, taken: set[str]) -> str:
    """`<finding>-resolved`, then `-2`, `-3`… — predictable, and never a
    duplicate id (which `fr validate artifacts` fails a journal for)."""
    base = f"{finding_id}-resolved"
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


@journal_app.command("resolve")
def resolve(
    scope: str = typer.Option(..., "--scope", help="spec | plan | debug."),
    slug: str = typer.Option(..., "--slug", help="Journal slug (spec/plan/debug slug)."),
    entry_id: str = typer.Option(..., "--id", help="The FINDING id being resolved."),
    state: str = typer.Option(..., "--state", help="fixed | refuted."),
    note: str = typer.Option(
        ...,
        "--note",
        help="Why it is resolved (required — 'resolved' with no reason is the "
        "silent state change the rules forbid).",
    ),
    phase: int | None = typer.Option(None, "--phase", help="Phase doing the resolving, if any."),
) -> None:
    """Append a resolution record closing one finding (spec §3.G.1).

    Append-only on purpose: the finding keeps its own text and `state: open`,
    and `fr journal check` folds records into an EFFECTIVE state. A finding
    rewritten in place would erase that it was ever open, which is what later
    phases read the journal to learn.

    Fails, loudly and without writing, on an unknown id — a silent success here
    would leave the gate red with the operator believing it was cleared.
    """
    _validate_scope(scope)
    root = resolve_repo_root()
    # Resolve through the read path: a journal archived alongside its plan is
    # still the file the finding lives in, and a resolution record must land
    # there rather than conjure a new active journal holding only the record.
    # NAMING THE TRADE-OFF (review r7-m3): that means this command can append
    # under `docs/superpowers/implemented/`, which
    # `.claude/rules/artifact-versioning.md` otherwise treats as frozen. The
    # exception is deliberate and narrow — the rule freezes archived artifacts
    # against MIGRATION, i.e. against a tool rewriting history nobody asked it
    # to touch. This is an operator resolving a finding they can still see, and
    # the alternative writes a phantom journal the gate never reads.
    path = resolve_journal_read_path(root, scope, slug)  # type: ignore[arg-type]
    if state not in RESOLUTION_STATES:
        err_console.print(
            f"[red]--state must be one of {' | '.join(RESOLUTION_STATES)} (got {state!r})[/red] "
            "— re-open a finding with `fr journal add --resolves <id> --state open`"
        )
        raise typer.Exit(2)
    try:
        entries = _load(path)
    except JournalParseError as e:
        err_console.print(f"[red]journal parse error:[/red] {e}")
        raise typer.Exit(2) from e
    target = next((e for e in entries if e.id == entry_id), None)
    if target is None:
        err_console.print(
            f"[red]no journal entry `{entry_id}` in {path}[/red] — nothing resolved "
            "(`fr journal render` lists the ids this journal carries)"
        )
        raise typer.Exit(2)
    if target.kind != "finding":
        err_console.print(
            f"[red]entry `{entry_id}` is a `{target.kind}`, not a finding[/red] — only a "
            "finding has a state to resolve"
        )
        raise typer.Exit(2)

    record = JournalEntry(
        kind="finding",
        scope=scope,  # type: ignore[arg-type]
        id=_record_id(entry_id, {e.id for e in entries}),
        created=_timestamp(),
        phase=phase,
        title=f"resolves {entry_id}: {target.title}",
        body=note,
        state=state,  # type: ignore[arg-type]
        resolves=entry_id,
    )
    _append_entry(path, slug, record)
    typer.echo(f"{entry_id} → {state} (record {record.id})")


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
    _validate_scope(scope)
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
    """Freshness gate. Non-zero on a parse error or any EFFECTIVELY open finding.

    Effective, not per-entry: a finding closed by a later `fr journal resolve`
    record no longer counts, and one re-opened by a later record counts again
    (spec §3.G.1). A journal with no resolution records — every journal written
    before that verb existed — gates exactly as it did before.
    """
    _validate_scope(scope)
    root = resolve_repo_root()
    # Read-resolve so a check still gates on an archived journal's findings.
    path = resolve_journal_read_path(root, scope, slug)  # type: ignore[arg-type]
    try:
        entries = _load(path)
    except JournalParseError as e:
        err_console.print(f"[red]journal parse error:[/red] {e}")
        raise typer.Exit(2) from e
    still_open = open_finding_ids(entries)
    if still_open:
        # Output shape unchanged ("N open finding(s): <ids>") — things grep it.
        err_console.print(
            f"[yellow]{len(still_open)} open finding(s):[/yellow] " + ", ".join(still_open)
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

    _validate_scope(scope)
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
