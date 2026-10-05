"""`fr triage origins collect|check|render` (spec 2026-10-02-wave-driver, R10).

The same scope options as every `fr triage` verb; all state lives in the scope's
triage state directory (`origins-facts.json`, `origins.yaml`, `origins.html`), so
`triage` stays in `READ_ONLY_COMMANDS`. Exit codes: 0 success (and always for
`check`); 2 usage (scope, `--since`), a forge failure, a missing `origins-facts.json`
(the message names the collect command) or an unreadable state file.
"""

from __future__ import annotations

import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape

import fr.commands.triage_cmd as triage_cmd
from fr.commands.triage_cmd import DirOpt, OrgOpt, RepoOpt, console, err_console, triage_app
from fr.triage.errors import TriageError
from fr.triage.model import Judgements, Scope, load_judgements, state_dir
from fr.triage.origins import (
    CLASSIFICATION_FILE,
    FACTS_FILE,
    ISSUE_LIMIT,
    PAGE_FILE,
    PR_LIMIT,
    Origins,
    OriginsFacts,
    check_origins,
    collect_origins,
    load_origins,
    load_scope_origins_facts,
    parse_since,
    render_origins,
    write_facts,
)
from fr.triage.render import plural

origins_app = typer.Typer(
    name="origins",
    help="Defect origins: collect issues filed since a date, classify them, render the page.",
    no_args_is_help=True,
)
triage_app.add_typer(origins_app)


def _fail(message: str) -> typer.Exit:
    err_console.print(f"[red]error:[/red] {escape(message)}", soft_wrap=True)
    return typer.Exit(code=2)


def _load(scope: Scope, dir_override: Path | None) -> tuple[Path, OriginsFacts, Origins]:
    target = state_dir(scope, dir_override)
    facts_path = target / FACTS_FILE
    if not facts_path.exists():
        flag = "org" if scope.kind == "org" else "repo"
        raise _fail(
            f"no origins facts at {facts_path}; run "
            f"`fr triage origins collect --{flag} {scope.target} --since YYYY-MM-DD` first"
        )
    try:
        facts = load_scope_origins_facts(facts_path, scope)
        return target, facts, load_origins(target / CLASSIFICATION_FILE)
    except TriageError as exc:
        raise _fail(str(exc)) from exc


@origins_app.command("collect")
def collect_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    since: Annotated[
        str, typer.Option("--since", help="Issues created on or after this date (YYYY-MM-DD).")
    ] = "",
    issue_limit: Annotated[
        int, typer.Option("--issue-limit", min=1, help="Issues listed per repo, newest first.")
    ] = ISSUE_LIMIT,
    pr_limit: Annotated[
        int, typer.Option("--pr-limit", min=1, help="PRs listed per repo, newest first.")
    ] = PR_LIMIT,
) -> None:
    """Read the issues created since a date and write origins-facts.json.

    A window one page of issues or PRs does not reach the start of is refused, never
    collected partially: narrow --since, or raise the limit it names (gh#888).
    """
    scope = triage_cmd._scope(repo, org)
    try:
        facts = collect_origins(
            triage_cmd.make_forge(),
            scope,
            since=parse_since(since),
            now=datetime.now(UTC),
            issue_limit=issue_limit,
            pr_limit=pr_limit,
        )
    except TriageError as exc:
        raise _fail(str(exc)) from exc
    out = state_dir(scope, dir_override) / FACTS_FILE
    write_facts(out, facts)
    for w in facts.warnings:
        err_console.print(f"[yellow]warning:[/yellow] {escape(w)}", soft_wrap=True)
    console.print(
        f"wrote {out} ({plural(len(facts.issues), 'issue')} since {facts.since})",
        markup=False,
        soft_wrap=True,
    )


@origins_app.command("check")
def check_command(repo: RepoOpt = None, org: OrgOpt = None, dir_override: DirOpt = None) -> None:
    """List issues with no classification, and classifications for issues not in the facts.

    Always exits 0; nothing is pruned.
    """
    _, facts, origins = _load(triage_cmd._scope(repo, org), dir_override)
    result = check_origins(facts, origins)
    console.print(f"[bold]unclassified ({len(result.unclassified)})[/bold] — filed, no origin yet")
    for i in result.unclassified:
        console.print(f"  {escape(i.key)}  {escape(i.title)}", soft_wrap=True)
    console.print(
        f"[bold]not in the facts ({len(result.unknown)})[/bold] — classified, "
        "but the facts do not hold the issue; never pruned"
    )
    for key in result.unknown:
        console.print(f"  {escape(key)}", soft_wrap=True)


@origins_app.command("render")
def render_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    open_: bool = typer.Option(False, "--open", help="Open the page in a browser."),
) -> None:
    """Write origins.html from origins-facts.json, origins.yaml and (for links) judgements.yaml."""
    scope = triage_cmd._scope(repo, org)
    target, facts, origins = _load(scope, dir_override)
    judgements = _judgements(target)
    out = target / PAGE_FILE
    out.write_text(render_origins(facts, origins, judgements), encoding="utf-8")
    console.print(
        f"wrote {out} ({plural(len(facts.issues), 'issue')})", markup=False, soft_wrap=True
    )
    if open_:
        webbrowser.open(out.resolve().as_uri())


def _judgements(target: Path) -> Judgements | None:
    """The batches the conclusion links to; none when there is no readable judgements.yaml."""
    path = target / "judgements.yaml"
    if not path.exists():
        return None
    try:
        return load_judgements(path)
    except TriageError as exc:
        raise _fail(str(exc)) from exc
