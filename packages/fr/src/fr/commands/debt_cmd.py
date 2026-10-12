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

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

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
        typer.echo(f"error: {_clean(why, 300)}", err=True)
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
        typer.echo(f"error: {_clean(e, 300)}", err=True)
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
        found = _trusted(client, found)
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
            typer.echo(
                _clean(client.create_issue(slug, title=title, body=body, labels=frozenset()), 300)
            )
        elif zero:
            client.close_issue(
                slug, number, "No technical debt as of this run; closing. `fr debt` has the report."
            )
        else:
            client.edit_issue(slug, number, title=title, body=body)
    except DebtConfigError as e:
        typer.echo(f"error: {_clean(e, 300)}", err=True)
        raise typer.Exit(2) from e
    except UnsupportedForgeOperation as e:
        typer.echo(f"error: this forge cannot do `{_clean(e.op)}` ({_clean(e)})", err=True)
        raise typer.Exit(1) from e
    except FORGE_ERRORS as e:
        typer.echo(f"error: the forge refused: {_clean(e, 300)}", err=True)
        raise typer.Exit(1) from e


LEGACY_MARKER = "<!-- fr-acceptance-digest -->"


BOT_LOGINS = frozenset({"github-actions[bot]", "github-actions", "app/github-actions"})
# Control characters plus the bidi and format marks that reorder or hide text.
_CONTROL = re.compile("[\x00-\x1f\x7f-\x9f\u200e\u200f\u202a-\u202e\u2066-\u2069]")


def _clean(value: object, limit: int = 120) -> str:
    """A forge-returned string made safe to echo: no control characters."""
    from fr.debt.render import redact

    return _CONTROL.sub("?", redact(str(value)))[:limit]


def _login(issue: dict[str, Any]) -> str:
    a = issue.get("author")
    return str(a.get("login") or "") if isinstance(a, dict) else str(a or "")


def _trusted(client: GhClient, found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The marker-bearing issues fr may edit, rename or close: written by the
    viewer or by the workflow's own bot. A marker anyone can paste selects
    nothing by itself; any other match is named and left alone."""
    allowed = set(BOT_LOGINS)
    try:
        allowed.add(client.authenticated_login().lower())
    except Exception as e:  # any failure: trust the bot accounts only
        import os

        # In Actions, the workflow's GITHUB_TOKEN may not read `/user` (403): the
        # viewer is then the workflow bot, which BOT_LOGINS already trusts.
        text = str(e).lower()
        if not (
            os.environ.get("GITHUB_ACTIONS") == "true"
            and ("403" in text or "resource not accessible" in text)
        ):
            _warn(f"cannot tell who the viewer is ({_clean(type(e).__name__)}); trusting bots only")
    out = []
    for i in found:
        if not _marked(i):
            continue
        if _login(i).lower() in allowed:
            out.append(i)
        else:
            _warn(
                f"ignoring issue #{_clean(i.get('number'))} by {_clean(_login(i))}: it carries "
                "the debt marker but was not written by this account or the workflow's bot"
            )
    return out


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
        typer.echo(f"error: the forge returned an unusable issue number {_clean(n)!r}", err=True)
        raise typer.Exit(1)
    return int(n)


PUSH_REMEDY = "The token cannot push; set FR_DEBT_TOKEN to a token with contents:write."
REFUSAL_REMEDIES = (
    "enable Settings > Actions > General > 'Allow GitHub Actions to create and approve "
    "pull requests', or set the FR_DEBT_TOKEN secret to a token that may open pull requests"
)


def _git(root: Path, *args: str, check: bool = True) -> str:
    import subprocess

    done = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    if check and done.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {(done.stderr or done.stdout).strip()}")
    return done.stdout.strip()


def _held(root: Path, name: str) -> list[str]:
    """R19's reason lines for a plan the Test Plan hold keeps, else []."""
    from fr.archive import outcome_hold
    from fr.parser import PlanSchemaError, parse

    rel = Path("docs/superpowers/plans") / name
    try:
        return outcome_hold(root, parse(root / rel), rel)
    except (PlanSchemaError, OSError, ValueError, KeyError, TypeError):
        # A plan fr cannot read has no hold to report here; `fr archive` itself
        # then refuses it and the sweep lists it as not archived.
        return []


def _archive_one(root: Path, name: str, env: dict[str, str]) -> tuple[bool, str]:
    """`fr archive <plan-dir>` as a subprocess; (ok, last stderr/stdout line)."""
    import subprocess
    import sys

    done = subprocess.run(
        [sys.executable, "-m", "fr", "archive", f"docs/superpowers/plans/{name}"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    text = (done.stderr or done.stdout or "").strip()
    return done.returncode == 0, (text.splitlines() or [""])[-1]


@debt_app.command("archive-pr")
def archive_pr_cmd(
    yes: Annotated[
        bool, typer.Option("--yes", help="Push and open the PR (else preview).")
    ] = False,
    stale_days: Annotated[int | None, typer.Option("--stale-days")] = None,
) -> None:
    """Open or refresh the one draft PR archiving long-merged plans (R12)."""
    import os

    from fr.archive import merge_evidence
    from fr.debt import sweep as sw
    from fr.debt.engine import DebtConfigError
    from fr.ghclient import UnsupportedForgeOperation
    from fr.hostclient import FORGE_ERRORS

    root = resolve_repo_root()
    slug = _identity(root)
    token = os.environ.get("FR_DEBT_TOKEN", "").strip()
    if token:
        # The forge writes below (PR, owed issues) act with the dedicated token.
        os.environ["GH_TOKEN"] = token
        os.environ["GITLAB_TOKEN"] = token
    try:
        client = _client(root)
        report = _compute(root, client, slug, stale_days)
    except DebtConfigError as e:
        typer.echo(f"error: {_clean(e, 300)}", err=True)
        raise typer.Exit(2) from e
    except FORGE_ERRORS as e:
        typer.echo(f"error: the forge refused: {_clean(e, 300)}", err=True)
        raise typer.Exit(1) from e
    chosen = sw.select(report)
    if not chosen:
        typer.echo(
            f"No plan has been merged and unarchived for more than {report.stale_days} days."
        )
        return
    result = sw.Sweep()
    for plan in chosen:
        why = _held(root, plan.name)
        if why:
            result.held.append((plan, why))
        else:
            result.archived.append(plan)
    for plan, why in result.held:
        typer.echo(f"{sw.HELD_REASON}: {plan.name}")
        for line in why[1:]:
            typer.echo(line)
    if not result.archived:
        typer.echo("Every selected plan is held; nothing to archive.")
        return
    typer.echo("archive: " + ", ".join(p.name for p in result.archived))
    if not yes:
        typer.echo("(preview; re-run with --yes to push the branch and open the draft PR)")
        return

    if _git(root, "status", "--porcelain", "--untracked-files=no") or _git(
        root, "status", "--porcelain", "--untracked-files=all", "--", "docs"
    ):
        typer.echo("error: the checkout has uncommitted changes; refusing to sweep", err=True)
        raise typer.Exit(1)
    ev = merge_evidence(root, fetch=False)
    if ev.ref is None or not sw.SAFE_REF.match(ev.ref.ref):
        typer.echo(f"error: the default branch is unknown ({_clean(ev.ref_error, 300)})", err=True)
        raise typer.Exit(1)
    start = _git(root, "rev-parse", "--verify", "--end-of-options", f"{ev.ref.ref}^{{commit}}")
    came_from = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if came_from == "HEAD":
        came_from = _git(root, "rev-parse", "HEAD")
    base = ev.ref.ref.split("/", 1)[-1]
    entered = False
    try:
        _git(root, "switch", "-C", sw.BRANCH, start)
        entered = True
        env = dict(os.environ)
        landed: list[Any] = []
        for plan, _ in [(p, None) for p in result.archived]:
            ok, last = _archive_one(root, plan.name, env)
            if ok:
                landed.append(plan)
            else:
                result.failed.append((plan, last))
        result.archived = landed
        for plan, last in result.failed:
            typer.echo(f"not archived: {plan.name}: {_clean(last, 300)}")
        _git(root, "add", "-A", "--", "docs")
        if not result.archived or not _git(root, "diff", "--cached", "--name-only"):
            typer.echo("Nothing was archived; no branch pushed.")
            return
        _commit(root)
        try:
            _push(root)
        except RuntimeError as e:
            _warn(f"could not push {sw.BRANCH}: {_clean(e, 300)}. {PUSH_REMEDY}")
            return
        _open_or_refresh(root, client, slug, base, result, report.stale_days, bool(token))
    except RuntimeError as e:
        typer.echo(f"error: {_clean(e, 300)}", err=True)
        raise typer.Exit(1) from e
    except UnsupportedForgeOperation as e:
        _warn(
            f"this forge cannot do `{e.op}`; the branch {sw.BRANCH} is pushed, open the PR by hand"
        )
    except FORGE_ERRORS as e:
        detail = _clean(" ".join(str(e).split()), 300)
        if _is_pr_permission_refusal(str(e)):
            _warn(
                f"the forge refused to open the archive PR: {detail}. "
                f"Remedies: {REFUSAL_REMEDIES}. The branch {sw.BRANCH} is pushed."
            )
        else:
            _warn(
                f"the forge failed to open the archive PR (forge error): {detail}. "
                f"The branch {sw.BRANCH} is pushed."
            )
    finally:
        if entered:
            _leave(root, came_from)


def _is_pr_permission_refusal(message: str) -> bool:
    """GitHub's refusal when Actions may not create PRs (403 / "not permitted to
    create or approve pull requests"): the only error the remedies fit."""
    m = message.lower()
    return "not permitted to create" in m or "403" in m


def _leave(root: Path, came_from: str) -> None:
    """Back to where the run started, discarding what a failed sweep left staged
    or untracked under docs/ (the tree was verified clean on entry), and saying so
    when the switch back fails."""
    detached = re.fullmatch(r"[0-9a-f]{40}", came_from) is not None
    _git(root, "reset", "-q", "--hard", check=False)
    _git(root, "clean", "-fdq", "--", "docs", check=False)
    try:
        _git(root, "switch", *(["--detach"] if detached else []), came_from)
    except RuntimeError as e:
        _warn(f"could not switch back to {_clean(came_from)}: {_clean(e, 200)}")


def _commit(root: Path) -> None:
    ident: list[str] = []
    if not _git(root, "config", "user.email", check=False):
        ident = ["-c", "user.name=fr-debt", "-c", "user.email=fr-debt@users.noreply.invalid"]
    _git(root, *ident, "commit", "-q", "-m", "chore(fr): archive merged plans (debt sweep)")


def _push(root: Path) -> None:
    """Force-push the bot-owned branch, leased on what the remote holds NOW."""
    from fr.debt import sweep as sw

    ref = f"refs/heads/{sw.BRANCH}"
    held = _git(root, "ls-remote", "--heads", "origin", ref)
    expect = held.split()[0] if held else ""
    _git(root, "push", f"--force-with-lease={ref}:{expect}", "origin", f"{sw.BRANCH}:{ref}")


def _open_or_refresh(
    root: Path,
    client: GhClient,
    slug: str,
    base: str,
    result: Any,
    stale_days: int,
    own_token: bool,
) -> None:
    from fr.debt import sweep as sw

    body = sw.pr_body(result, stale_days=stale_days, own_token=own_token)
    # Only an open PR whose head is in THIS repo is ever refreshed; a fork's PR on
    # the same head name is never pushed to or edited.
    existing = client.open_pr_in_repo(slug, sw.BRANCH)
    if existing is None:
        made = client.create_pr(
            slug, head=sw.BRANCH, base=base, title=sw.PR_TITLE, body=body, draft=True
        )
        typer.echo(f"opened draft PR: {_clean(made.get('url') or made.get('number'), 300)}")
        return
    number = existing.get("number")
    text = str(number)
    if not (text.isascii() and text.isdigit()):
        raise RuntimeError(f"the forge returned an unusable PR number {_clean(text)!r}")
    client.edit_pr(slug, int(text), body=body)
    typer.echo(f"refreshed draft PR #{int(text)}")
