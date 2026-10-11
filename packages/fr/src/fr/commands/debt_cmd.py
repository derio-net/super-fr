"""`fr debt` — what a repo owes, as one report (spec 2026-10-11-debt-engine, R1, R25).

`fr debt` itself is read-only, which is why `debt` is in
`fr.artifacts.trigger.READ_ONLY_COMMANDS`: it writes no registered artifact.
Exit 0 on a report, 2 on a usage error (a bad `.fr/debt.yaml` or `--stale-days`).

`fr debt issue` and `fr debt archive-pr` (R9-R12) are the weekly job's two forge
writes. Both preview unless `--yes`, and both write only to the repository the
origin remote names (`archive_followups.owed_identity`), never one a committed
file names.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from fr.commands.common import resolve_repo_root

if TYPE_CHECKING:
    from fr.debt.engine import DebtForge
    from fr.debt.model import DebtReport
    from fr.ghclient import GhClient

debt_app = typer.Typer(
    help="What this repo owes: acceptance, plans and owed actions (read-only).",
    invoke_without_command=True,
    no_args_is_help=False,
)


def _now() -> datetime:
    """The clock, one seam for tests."""
    return datetime.now(UTC)


def _forge(root: Path) -> tuple[DebtForge | None, str]:
    """The repo's forge adapter and, when there is none, the reason why."""
    try:
        from fr import _hosts
        from fr.commands.archive_cmd import _make_gh_client
        from fr.debt.forge import ClientDebtForge
        from fr.services.resolve import resolve_tracking

        if resolve_tracking(root, lenient=True).type == "none":
            return None, "tracking: none"
        slug = _hosts.origin_slug(root)
        if not slug:
            return None, "no origin remote to name the repository"
        return ClientDebtForge(_make_gh_client(), cwd=root, repo=slug), ""
    except Exception as e:
        return None, f"forge adapter unavailable ({type(e).__name__}: {e})"


def _identity(root: Path) -> str:
    """`owner/repo` of the origin remote, or a refusal (exit 1) saying why."""
    from fr.archive_followups import owed_identity

    slug, why = owed_identity(root, allow_nested=True)
    if slug is None:
        typer.echo(f"error: {why}", err=True)
        raise typer.Exit(1)
    return slug


def _client(root: Path) -> GhClient:
    """The forge adapter for this checkout (one seam for tests)."""
    from fr.hostclient import client_for

    return client_for(root)


def _compute(root: Path, client: GhClient, slug: str, stale_days: int | None) -> DebtReport:
    from fr.debt.engine import compute
    from fr.debt.forge import ClientDebtForge

    forge = ClientDebtForge(client, cwd=root, repo=slug)
    return compute(root, forge=forge, now=_now(), stale_days=stale_days, fetch=True)


def _warn(msg: str) -> None:
    """A CI annotation: visible in the run, never a failure by itself."""
    typer.echo(f"::warning::{msg}")


@debt_app.callback()
def debt(
    ctx: typer.Context,
    json_out: Annotated[bool, typer.Option("--json", help="Print the report as JSON.")] = False,
    stale_days: Annotated[
        int | None,
        typer.Option("--stale-days", help="Days without activity before a plan is stale."),
    ] = None,
    offline: Annotated[
        bool, typer.Option("--offline", help="Do not touch the forge or the network.")
    ] = False,
) -> None:
    """Print the debt report (text, or JSON with --json)."""
    if ctx.invoked_subcommand is not None:
        return
    from fr.debt import render
    from fr.debt.engine import DebtConfigError, compute

    root = resolve_repo_root()
    try:
        forge, why = (None, "offline") if offline else _forge(root)
        report = compute(
            root, forge=forge, now=_now(), stale_days=stale_days, fetch=not offline, forge_why=why
        )
    except DebtConfigError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from e
    typer.echo(report.model_dump_json(indent=2) if json_out else render.text(report))


ISSUE_LIMIT = 200


def _title(slug: str) -> str:
    return f"{slug.rsplit('/', 1)[-1]}: Technical debt"


def _is_zero(report: DebtReport) -> bool:
    """Zero debt that is also KNOWN: an unreadable source is never read as clean."""
    unreadable = any(v.state == "unavailable" for v in report.sources.values())
    return report.debt_total() == 0 and report.acceptance.available and not unreadable


@debt_app.command("issue")
def issue_cmd(
    yes: Annotated[bool, typer.Option("--yes", help="Write to the forge (else preview).")] = False,
    stale_days: Annotated[int | None, typer.Option("--stale-days")] = None,
) -> None:
    """Keep the one open `<repo>: Technical debt` issue current (R9-R11)."""
    from fr.debt import render
    from fr.debt.engine import DebtConfigError
    from fr.ghclient import ListingCapped, UnsupportedForgeOperation
    from fr.hostclient import FORGE_ERRORS

    root = resolve_repo_root()
    slug = _identity(root)
    title = _title(slug)
    try:
        client = _client(root)
        report = _compute(root, client, slug, stale_days)
        capped = False
        try:
            found = client.list_open_issues_with_body(
                slug, search=(render.MARKER, LEGACY_MARKER), limit=ISSUE_LIMIT
            )
        except ListingCapped as e:
            found, capped = e.issues, True
            _warn(f"partial: only the first {e.limit} open issues were scanned for the debt issue")
        found = [i for i in found if _marked(i)]
        zero = _is_zero(report)
        body = render.markdown(report)
        number = _number(found[0]) if found else None
        if len(found) > 1:
            others = ", ".join(f"#{_number(i)}" for i in found[1:])
            _warn(f"several debt issues are open; using the oldest (#{number}); also {others}")
        if number is None and zero:
            typer.echo("No technical debt, and no open debt issue: nothing to do.")
            return
        if number is None and capped:
            typer.echo(
                "error: the issue listing was capped, so an existing debt issue may be unseen; "
                "refusing to open a duplicate",
                err=True,
            )
            raise typer.Exit(1)
        verb = "close" if zero else "create" if number is None else "refresh"
        typer.echo(f"{verb}: {title}" + (f" (#{number})" if number is not None else ""))
        if not yes:
            typer.echo("(preview; re-run with --yes to write)")
            typer.echo(body)
            return
        if number is None:
            typer.echo(client.create_issue(slug, title=title, body=body, labels=frozenset()))
        elif zero:
            client.close_issue(
                slug, number, "No technical debt as of this run; closing. `fr debt` has the report."
            )
        else:
            client.edit_issue(slug, number, title=title, body=body)
    except DebtConfigError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from e
    except UnsupportedForgeOperation as e:
        typer.echo(f"error: this forge cannot do `{e.op}` ({e})", err=True)
        raise typer.Exit(1) from e
    except FORGE_ERRORS as e:
        typer.echo(f"error: the forge refused: {e}", err=True)
        raise typer.Exit(1) from e


LEGACY_MARKER = "<!-- fr-acceptance-digest -->"


def _marked(issue: dict[str, Any]) -> bool:
    """The marker stands on a line of its own, so an issue merely quoting it
    (a bug report about the digest) is never taken for the debt issue."""
    from fr.debt import render

    lines = {ln.strip() for ln in str(issue.get("body") or "").splitlines()}
    return render.MARKER in lines or LEGACY_MARKER in lines


def _number(issue: dict[str, Any]) -> int:
    """An issue number that is plain ASCII digits, or a refusal (argv safety)."""
    n = str(issue.get("number", ""))
    if not (n.isascii() and n.isdigit()):
        typer.echo(f"error: the forge returned an unusable issue number {n!r}", err=True)
        raise typer.Exit(1)
    return int(n)
