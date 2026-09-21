"""`fr triage` CLI — backlog triage (spec 2026-09-21-fr-triage-design).

`collect` reads the forge and writes `facts.json` under the scope's state
directory (`$HOME/.cache/fr/triage/<scope>/`, or `--dir`). The engine lives in
`fr.triage`; this module only parses flags and does I/O.

Gate-exempt: `triage` is in `fr.artifacts.trigger.READ_ONLY_COMMANDS` because
it never reads or writes a registered artifact (spec §3.F′).

Exit codes: 0 success (skipped repos and truncation warnings are reported,
not failed); 2 usage (not exactly one of --repo/--org), an unreadable
judgements.yaml, or a forge failure in repo scope.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

from fr.triage.collect import PR_LIMIT, Forge, GhForge, collect_facts
from fr.triage.errors import TriageError
from fr.triage.model import Facts, Scope, load_judgements, state_dir

console = Console()
err_console = Console(stderr=True)

triage_app = typer.Typer(
    name="triage",
    help="Backlog triage: collect forge facts, check judgements, render a board.",
    no_args_is_help=True,
)


def make_forge() -> Forge:
    """The forge `collect` reads. Tests replace this factory, never subprocess."""
    return GhForge()


def _scope(repo: str | None, org: str | None) -> Scope:
    if (repo is None) == (org is None):
        err_console.print("[red]error:[/red] give exactly one of --repo OWNER/REPO or --org OWNER")
        raise typer.Exit(code=2)
    if repo is not None:
        if repo.count("/") != 1 or not all(repo.split("/")):
            err_console.print(
                f"[red]error:[/red] --repo must be OWNER/REPO, got {escape(repr(repo))}"
            )
            raise typer.Exit(code=2)
        return Scope(kind="repo", target=repo)
    assert org is not None
    if not org or "/" in org:
        err_console.print(f"[red]error:[/red] --org must be an OWNER, got {escape(repr(org))}")
        raise typer.Exit(code=2)
    return Scope(kind="org", target=org)


def _report(facts: Facts) -> None:
    """Print what the forge could not give; every forge-sourced string escaped (r7)."""
    for s in facts.skipped:
        err_console.print(f"[yellow]skipped[/yellow] {escape(s.repo)}: {escape(s.reason)}")
    for w in facts.warnings:
        err_console.print(
            f"[yellow]warning:[/yellow] the {w.source} list for {escape(w.target)} returned "
            f"exactly its limit ({w.limit}), so it is possibly truncated"
            + (" — raise it with --pr-limit" if w.source == "prs" else "")
        )


@triage_app.command("collect")
def collect_command(
    repo: str | None = typer.Option(None, "--repo", help="Triage one repo: OWNER/REPO."),
    org: str | None = typer.Option(None, "--org", help="Triage every repo of OWNER."),
    dir_override: Path | None = typer.Option(
        None, "--dir", help="State directory (default: $HOME/.cache/fr/triage/<scope>/)."
    ),
    pr_limit: int = typer.Option(
        PR_LIMIT, "--pr-limit", min=1, help="PRs listed per repo (the PR -> issue window)."
    ),
) -> None:
    """Read the forge and write facts.json for the scope."""
    scope = _scope(repo, org)
    target_dir = state_dir(scope, dir_override)
    judgements = target_dir / "judgements.yaml"
    try:
        judged = list(load_judgements(judgements).issues) if judgements.exists() else []
        facts = collect_facts(
            make_forge(), scope, now=datetime.now(UTC), judged=judged, pr_limit=pr_limit
        )
    except TriageError as exc:
        err_console.print(f"[red]error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=2) from exc
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / "facts.json"
    out.write_text(
        json.dumps(facts.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _report(facts)
    n_open = sum(1 for i in facts.issues if i.state == "open")
    console.print(f"wrote {out} ({n_open} open issues)", markup=False)
