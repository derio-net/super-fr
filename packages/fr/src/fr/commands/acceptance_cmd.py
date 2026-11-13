"""`fr acceptance ...` CLI — the acceptance-matrix registry and gate.

Spec: docs/superpowers/specs/2026-07-04-acceptance-matrix-design.md §4.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape

from fr.acceptance.fragment import FRAGMENTS_DIR
from fr.acceptance.model import AcceptanceError, Matrix, Row, Walk
from fr.artifacts.paths import KIND_DIRS, artifact_root, kind_dir, space_for
from fr.commands.common import resolve_repo_root

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

RETIRED_MATRIX_REL = Path(KIND_DIRS["acceptance"]) / "matrix.yaml"
"""The retired matrix (spec 2026-11-04-repo-feature-settings R19): read only from a
base ref older than the split, never written."""

acceptance_app = typer.Typer(
    help="Acceptance matrix: business-level acceptance tests × verification levels.",
    no_args_is_help=True,
)


def _refuse_if_off(root: Path, what: str) -> None:
    """R6: under `artifacts.acceptance: off` the matrix is not written (exit 2)."""
    from fr.settings import SettingsError, disabled, disabled_because

    try:
        off = disabled(root, "acceptance")
    except SettingsError as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(2) from e
    if off:
        err_console.print(f"[red]error:[/red] {escape(disabled_because('acceptance', what))}")
        raise typer.Exit(2)


def _say_if_off(root: Path) -> bool:
    """R6: under `artifacts.acceptance: off` a read-only surface says so, exit 0."""
    from fr.settings import DISABLED, disabled

    if disabled(root, "acceptance"):
        typer.echo(f"acceptance: {DISABLED} (artifacts.acceptance: off)")
        return True
    return False


def _load(root: Path) -> Matrix:
    """The effective matrix (`fr.acceptance.fold.load_effective`). A repo with no
    fragment and no `docs/acceptance/features/` directory has no acceptance: exit 1."""
    from fr.acceptance.fold import has_fragments, load_effective

    if not has_fragments(root) and not (artifact_root(root) / FRAGMENTS_DIR).is_dir():
        err_console.print(
            f"no acceptance fragments under {FRAGMENTS_DIR}/ "
            "(run `fr acceptance init` to scaffold, then `fr acceptance add`)"
        )
        raise typer.Exit(1)
    try:
        return load_effective(root)
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}", soft_wrap=True)
        raise typer.Exit(1) from e


def _contested(root: Path) -> tuple[frozenset[str], tuple[Row, ...]]:
    """The fold's contested rows (spec 2026-11-04 R17) and its retired rows (a retired
    one a merged amendment still names is contested debt too); `_load` already refused
    an unfoldable tree, and the fold is memoised, so this re-reads nothing."""
    from fr.acceptance.fold import effective

    try:
        folded = effective(root)
    except AcceptanceError:
        return frozenset(), ()
    return folded.contested, folded.retired


def _ids_at(root: Path, ref: str) -> set[str]:
    """Every row id `<ref>` defines: its fold, or — for a base from before the
    split (R19) — its retired matrix's ids. A ref with neither defines none."""
    import subprocess

    import yaml

    from fr.acceptance.fold import fold

    effective = fold(root, ref=ref, include_pending=False)
    ids = {r.id for r in effective.matrix.rows} | {r.id for r in effective.retired}
    if ids:
        return ids
    out = subprocess.run(
        ["git", "show", f"{ref}:{RETIRED_MATRIX_REL}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return set()
    try:
        old = yaml.safe_load(out.stdout) or {}
    except yaml.YAMLError as e:
        raise AcceptanceError(f"--added-since {ref}: base matrix unparseable: {e}") from e
    return {str(r["id"]) for r in old.get("rows") or [] if isinstance(r, dict) and "id" in r}


def _added_since(root: Path, ref: str, matrix: Matrix) -> list[str]:
    """Row ids present now but absent from `<ref>`'s effective matrix (spec decision
    6: mid-flight additions are defended at PR time, and this diff feeds the PR-body
    section). A base without fragments or a matrix means every row is new."""
    try:
        old_ids = _ids_at(root, ref)
    except AcceptanceError as e:
        raise AcceptanceError(f"--added-since {ref}: {e}") from e
    return [r.id for r in matrix.rows if r.id not in old_ids]


@acceptance_app.command("check")
def check_cmd(
    sibling_root: str = typer.Option(
        "..",
        "--sibling-root",
        help="Where sister repos live, relative to the repo root ('..' = repos as siblings).",
    ),
    added_since: str | None = typer.Option(
        None,
        "--added-since",
        help="Also list rows added since this git ref (feeds the PR-body section).",
    ),
    no_fetch: bool = typer.Option(
        False,
        "--no-fetch",
        help="Judge stale amendment bases against the last fetched default ref (offline).",
    ),
) -> None:
    """The gate: refs resolve, staleness, exit 2 on failing rows.

    It first fetches the default ref, then refuses (exit 2) a branch amendment whose
    base is stale and (exit 1) an in-place edit of a row merged on the default ref
    (spec 2026-11-04 R16, R17)."""
    from fr.acceptance.amend import branch_refusals
    from fr.acceptance.check import check

    root = resolve_repo_root()
    if _say_if_off(root):
        return
    branch = branch_refusals(root, fetch=not no_fetch)
    if branch.source:
        typer.echo(f"default ref: {branch.source}")
    for w in branch.warnings:
        typer.echo(f"::warning title=acceptance-matrix::{w}")
    matrix = _load(root)
    try:
        result = check(matrix, root, sibling_root)
        added = _added_since(root, added_since, matrix) if added_since else []
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(1) from e
    if added_since is not None:
        typer.echo(f"added since {added_since}:")
        by_id = {r.id: r for r in matrix.rows}
        for rid in added:
            typer.echo(f"  {rid} — {by_id[rid].acceptance}")
        if not added:
            typer.echo("  (none)")

    # Plain echo, never rich: `::warning::` annotations are parsed by GitHub
    # line-by-line — rich's soft-wrap would split them and they'd vanish.
    for r in result.warning_rows:
        typer.echo(
            f"::warning title=acceptance-matrix::{r.id} is {r.status}: "
            f"{r.acceptance} — backfill owed ({r.notes[:120]})"
        )
    for w in result.warnings:
        typer.echo(f"::warning title=acceptance-matrix::{w}")
    result.errors.extend(branch.errors)
    for e_line in result.errors:
        typer.echo(f"ERROR: {e_line}", err=True)
    for s_line in branch.stale:
        typer.echo(f"ERROR: stale amendment base: {s_line}", err=True)
    if result.failing_ids:
        typer.echo(f"ERROR: failing acceptance rows: {result.failing_ids}", err=True)
    code = 2 if branch.stale else result.exit_code
    if code == 0:
        typer.echo(result.summary)
    raise typer.Exit(code)


def _open_report(path: Path) -> None:
    """Open a written report in the operator's browser. The one opener `--open` goes
    through, so a test replaces it and never starts a real one."""
    import webbrowser

    webbrowser.open(path.resolve().as_uri())


@acceptance_app.command("report")
def report_cmd(
    link_mode: str = typer.Option(
        "local", "--link-mode", help="github (CI) | local (sibling checkouts)."
    ),
    ref: str = typer.Option("main", "--ref", help="Own-repo ref for github links."),
    sibling_root: str = typer.Option(
        "..", "--sibling-root", help="Where sister repos live, relative to the repo root."
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        help=f"Output file (repo-relative). Default: {KIND_DIRS['acceptance']}/report.html "
        "(report.md with --format md), both gitignored.",
    ),
    fmt: str = typer.Option("html", "--format", help="html | md."),
    open_it: bool = typer.Option(
        False, "--open", help="Open the written report in the browser (this machine only)."
    ),
) -> None:
    """Render the report from the folded matrix, to a file git ignores.

    Reports are derived, never committed (spec 2026-11-04 R20): this writes
    `docs/acceptance/report.html` (or `report.md`) and prints the path. CI publishes
    the same render as a job summary, an exposed artifact or on Pages."""
    from fr.acceptance.report import REPORT_OUTPUTS, render_report

    if link_mode not in ("github", "local"):
        err_console.print(f"--link-mode must be github|local, got {link_mode!r}")
        raise typer.Exit(2)
    if fmt not in REPORT_OUTPUTS:
        err_console.print(f"--format must be html|md, got {fmt!r}")
        raise typer.Exit(2)
    root = resolve_repo_root()
    _refuse_if_off(root, "`fr acceptance report` writes no report")
    matrix = _load(root)
    # The default lands at the artifact root: under quiet the fr worktree, never the
    # product checkout, where no `.gitignore` line keeps it out of `git add -A` (p3-r1).
    out_path = (
        (root / out) if out is not None else (artifact_root(root) / REPORT_OUTPUTS[fmt])
    ).resolve()
    try:
        text = render_report(matrix, root, out_path.parent, sibling_root, link_mode, ref, fmt)
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(1) from e
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    typer.echo(f"wrote {out_path}")
    if open_it:
        _open_report(out_path)


COMMENT_MARKER = "<!-- fr:acceptance-report -->"
COMMENT_LIMIT = 60_000
"""Characters kept of the report in the PR comment: GitHub refuses a comment over 65,536."""


def _login(name: Any) -> str:
    """A login as comparable text: GitHub spells the workflow bot `github-actions[bot]`,
    `github-actions` and `app/github-actions` in different answers."""
    return str(name or "").lower().removeprefix("app/").removesuffix("[bot]")


def _own_logins(client: Any) -> set[str]:
    """The logins the credentials write as: the authenticated account, or, when the forge
    will not say (an Actions token is no user), the workflow bot inside Actions. Empty when
    neither is known, so no existing comment is ever reused."""
    import os

    from fr.debt.render import BOT_LOGINS

    try:
        login = _login(client.authenticated_login())
    except Exception:
        login = ""
    if login:
        return {login}
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return {_login(b) for b in BOT_LOGINS}
    return set()


@acceptance_app.command("comment")
def comment_cmd(
    pr: int = typer.Option(..., "--pr", help="The pull request to comment on."),
    yes: bool = typer.Option(False, "--yes", help="Write the comment (without it: refused)."),
    ref: str = typer.Option("HEAD", "--ref", help="Own-repo ref for the report's links."),
) -> None:
    """Keep ONE comment on a PR carrying the Markdown report (forge.report_comment: on).

    The comment is found by its marker and edited in place, so a PR never collects a
    stack of them. Refused without `--yes`, when `forge.report_comment` is off and when
    `forge.comments` is off (spec 2026-11-04 R22). A report over the forge's size limit
    is cut at a line and says so."""
    from fr._hosts import origin_slug
    from fr.acceptance.report import render_report
    from fr.hostclient import FORGE_ERRORS, client_for
    from fr.settings import SettingsError, forge_block, load_settings

    root = resolve_repo_root()
    _refuse_if_off(root, "`fr acceptance comment` posts no report")
    try:
        if load_settings(root).settings.forge.report_comment != "on":
            err_console.print("[red]refused:[/red] forge.report_comment: off (the default)")
            raise typer.Exit(2)
        why = forge_block(root, "comments")
    except SettingsError as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(2) from e
    if why is not None:
        err_console.print(f"[red]refused:[/red] {escape(why)}")
        raise typer.Exit(2)
    slug = origin_slug(root)
    if slug is None:
        err_console.print("[red]error:[/red] no origin remote to name the repository")
        raise typer.Exit(2)
    matrix = _load(root)
    out_dir = kind_dir("acceptance", space_for(root))
    try:
        report = render_report(matrix, root, out_dir, "..", "github", ref, "md")
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(1) from e
    body = f"{COMMENT_MARKER}\n{report}"
    if len(body) > COMMENT_LIMIT:
        note = (
            "\n\n_Report truncated to fit the comment limit; the full report is the CI artifact._"
        )
        cut = body[: COMMENT_LIMIT - len(note)]
        body = cut[: cut.rfind("\n")] + note
    if not yes:
        err_console.print(
            f"[red]refused:[/red] would write the acceptance report ({len(body)} chars) on "
            f"{slug}#{pr}; pass --yes to write it"
        )
        raise typer.Exit(2)
    try:
        client = client_for(root)
        me = _own_logins(client)
        # Only a comment this identity wrote is ever edited: the marker is public text, so
        # anyone could plant it, and fr would then overwrite their comment (or post nothing).
        mine = [
            c
            for c in client.list_issue_comments(slug, pr)
            if COMMENT_MARKER in c["body"] and _login(c.get("author")) in me
        ]
        if mine:
            client.edit_issue_comment(slug, int(mine[0]["id"]), body)
            typer.echo(f"updated the acceptance report comment on {slug}#{pr}")
        else:
            client.comment_pr(slug, pr, body)
            typer.echo(f"posted the acceptance report comment on {slug}#{pr}")
    except FORGE_ERRORS as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(1) from e


@acceptance_app.command("pages-check")
def pages_check_cmd() -> None:
    """Exit 0 when a Pages site for the report would be no wider than the repo, 1 when not.

    Allowed only for a public repo or forge-reported access-controlled Pages; an unreadable
    visibility (Gitea, no token, a failed read) fails closed. The scaffolded Pages job runs
    this before every deploy and skips the deploy on 1 (spec R21)."""
    from fr.acceptance.pages import pages_allowed
    from fr.hostclient import client_for

    root = resolve_repo_root()
    allowed, reason = pages_allowed(root, client_for(root))
    typer.echo(reason)
    raise typer.Exit(0 if allowed else 1)


@acceptance_app.command("status")
def status_cmd(
    brief: bool = typer.Option(
        False, "--brief", help="Counts + the 3 oldest open rows (session-start injection)."
    ),
) -> None:
    """Terminal nag: counts by status + the open acceptance debt rows.

    Read-only and exit-0 always — allowlist-safe like `fr status`.
    """
    from collections import Counter

    from fr.acceptance.check import open_rows

    root = resolve_repo_root()
    if _say_if_off(root):
        return
    matrix = _load(root)
    from fr.debt.render import status_tag

    contested, retired = _contested(root)
    gone = {r.id for r in retired if r.id in contested}
    counts = Counter(r.status for r in matrix.rows)
    summary = ", ".join(f"{s}: {n}" for s, n in sorted(counts.items())) or "empty matrix"
    if contested:
        summary += f"; contested: {len(contested)}"
    typer.echo(f"acceptance: {summary}")
    if not brief:
        _echo_merged_features(root)
    opens = open_rows(matrix, contested, retired)
    if not opens:
        typer.echo("no acceptance debt.")
        return
    shown = opens[:3] if brief else opens
    for r in shown:  # open_rows: oldest origin date first
        tag = status_tag(r.status, retired=r.id in gone, contested=r.id in contested)
        typer.echo(f"  {r.id} [{tag}] {r.acceptance} — {r.notes}")
    if brief and len(opens) > len(shown):
        typer.echo(f"  … +{len(opens) - len(shown)} more (fr acceptance status)")


def _echo_merged_features(root: Path) -> None:
    """Under quiet and stealth, which features the fold took as merged, in merge order
    (R17's clause), and every `merged:` record it ignored. Nothing under `repo`."""
    from fr.artifacts.paths import outside_repo, space_for
    from fr.placement.merged import forge_for, merged_features

    if outside_repo(root) is None:
        return
    forge, why_not = forge_for(root)
    view = merged_features(space_for(root), root, forge=forge)
    listed = ", ".join(f"{f.feature} at {f.sha[:12]}" for f in view.features) or "none"
    typer.echo(f"merged: {listed}")
    if view.unmerged:
        state = why_not if forge is None else view.forge
        typer.echo(
            f"unmerged: {', '.join(view.unmerged)} (no merge found on "
            f"{view.ref or 'the default ref'}; a squash or rebase merge is found only "
            f"through the forge's merged PR, and the forge was {state})"
        )
    for notice in view.notices:
        typer.echo(f"note: {notice}")


@acceptance_app.command("summary")
def summary_cmd() -> None:
    """GitHub Actions-friendly Markdown summary: compact counts + collapsible debt."""
    from collections import Counter
    from html import escape

    from fr.acceptance.check import open_rows

    root = resolve_repo_root()
    if _say_if_off(root):
        return
    matrix = _load(root)
    counts = Counter(r.status for r in matrix.rows)
    lines = [
        "## Acceptance matrix",
        "",
        "| status | count |",
        "|---|---:|",
        f"| ci | {counts.get('ci', 0)} |",
        f"| scheduled | {counts.get('scheduled', 0)} |",
        f"| unwired | {counts.get('unwired', 0)} |",
        f"| walk-owed | {counts.get('walk-owed', 0)} |",
        f"| walked | {counts.get('walked', 0)} |",
        f"| manual | {counts.get('manual', 0)} |",
        f"| not-implemented | {counts.get('not-implemented', 0)} |",
        f"| failing | {counts.get('failing', 0)} |",
        "",
    ]
    opens = open_rows(matrix, *_contested(root))
    if not opens:
        lines.append("No open acceptance debt.")
    else:
        lines += [f"### Open acceptance debt ({len(opens)})", ""]
        for r in opens:
            lines += [
                f"<details><summary><code>{escape(r.id)}</code> [{escape(r.status)}]</summary>",
                "",
                escape(r.acceptance),
                "",
                f"**Notes:** {escape(r.notes)}",
                "",
                "</details>",
                "",
            ]
    lines += ["", "Full HTML report remains attached as the `acceptance-report` artifact."]
    typer.echo("\n".join(lines))


def _parse_levels(level: list[str], flag: str = "--level") -> dict[str, list[str]]:
    """`['unit=own:tests/x.py', …]` → `{'unit': ['own:tests/x.py']}`.

    `flag` names the option in the refusal, so a malformed `--drop-level`
    is not reported as a malformed `--level`."""
    levels: dict[str, list[str]] = {}
    for item in level:
        lv, sep, ref = item.partition("=")
        if not sep:
            err_console.print(f"{flag} must be '<level>=<ref>', got {item!r}")
            raise typer.Exit(2)
        levels.setdefault(lv, []).append(ref)
    return levels


def _check_verify(root: Path, verify: str | None) -> None:
    """`--verify` names a strategy that resolves here, or `none` (spec
    2026-10-06-verification-strategies §B) — refused before anything moves."""
    if verify is None:
        return
    from fr.record.apply import strategy_error

    if (why := strategy_error(verify, root)) is not None:
        err_console.print(f"[red]error:[/red] --verify: {escape(why)}")
        raise typer.Exit(2)


def _walk_at(value: str | None) -> str | None:
    """`--walk-at` as the walk's `at`: an ISO date (midnight UTC) or an ISO
    timestamp, for a walk recorded after the fact. None when not given; a value
    that is neither is refused, exit 2."""
    import datetime as _dt

    if value is None:
        return None
    try:
        if len(value) == 10:
            return _dt.date.fromisoformat(value).strftime("%Y-%m-%dT00:00:00Z")
        _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    except ValueError:
        err_console.print(
            f"[red]error:[/red] --walk-at {value!r} is not an ISO date or timestamp "
            "(e.g. 2026-07-09 or 2026-07-09T12:00:00Z); nothing changed"
        )
        raise typer.Exit(2) from None


def _walk_from_flags(
    root: Path,
    evidence: str | None,
    harness: str | None,
    model: str | None,
    strategy: str | None,
    outcome: str,
    at: str | None = None,
) -> Walk | None:
    """`--walk` and its companions as a `Walk`, or `None` without `--walk`.
    Each companion is required; the strategy must resolve (spec 2026-10-06 R14)."""
    import datetime as _dt

    from fr.record.apply import strategy_error
    from fr.verification.model import RESERVED

    if evidence is None:
        stray = [f for f, v in (("--harness", harness), ("--model", model),
                                ("--strategy", strategy), ("--walk-at", at))
                 if v is not None]  # fmt: skip
        if stray:
            err_console.print(f"[red]error:[/red] {', '.join(stray)} only go with --walk")
            raise typer.Exit(2)
        return None
    missing = [f for f, v in (("--harness", harness), ("--model", model),
                              ("--strategy", strategy)) if not v]  # fmt: skip
    if missing:
        err_console.print(
            f"[red]error:[/red] --walk needs {', '.join(missing)} — a walk names the harness, "
            "model and strategy it ran on; nothing changed"
        )
        raise typer.Exit(2)
    assert strategy is not None
    why = (
        f"{RESERVED!r} is not a strategy a walk can run"
        if strategy == RESERVED
        else strategy_error(strategy, root)
    )
    if why is not None:
        err_console.print(f"[red]error:[/red] --strategy: {escape(why)}")
        raise typer.Exit(2)
    try:
        return Walk(
            strategy=strategy,
            harness=harness,  # type: ignore[arg-type]  # checked non-empty above
            model=model,  # type: ignore[arg-type]
            outcome=outcome,  # type: ignore[arg-type]  # pydantic validates the literal
            at=_walk_at(at) or _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            evidence=evidence,
        )
    except Exception as e:  # pydantic ValidationError → operator-readable
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(2) from e


def _print_close_commands(root: Path, before: Row) -> None:
    """R16: the issues this walk freed, each with the forge's close and
    unlabel commands — nothing when forge issues are off (`forge.issues: off` or
    `tracking: none`). fr never closes them."""
    from fr.acceptance.walks import AWAITING_LIVE_LABEL, issues_now_closable
    from fr.hostclient import issue_command
    from fr.settings import forge_allows

    matrix = _load(root)
    after = next(r for r in matrix.rows if r.id == before.id)
    freed = issues_now_closable(matrix, before, after, root)
    if not freed or not forge_allows(root, "issues", lenient=True):
        return
    w = after.walks[-1]
    comment = f"Walk-verified ({w.strategy}, {w.harness}, {w.model}): {w.evidence}"
    for ref in freed:
        typer.echo(f"{ref}: every row citing it is walk-verified — close it:")
        typer.echo("  " + issue_command(root, "issue-close", ref=ref, comment=comment))
        typer.echo("  " + issue_command(root, "issue-unlabel", ref=ref, label=AWAITING_LIVE_LABEL))


def _validate_refs(row: Row) -> None:
    """Ref grammar checked BEFORE the file is touched — a shell-mangled ref
    (zsh's `$VAR:t` modifier eating "…:tests/…") must not land and surface
    only at the next `check`."""
    from fr.acceptance.logical import is_logical, parse_logical
    from fr.acceptance.model import split_ref

    for ref in row.refs():
        try:
            parse_logical(ref) if is_logical(ref) else split_ref(ref)
        except AcceptanceError as e:
            err_console.print(f"[red]error:[/red] {escape(str(e))}")
            raise typer.Exit(2) from e


def _apply_rows(
    root: Path,
    item: object,
    message: str,
    drops: dict[str, dict[str, tuple[str, ...]]] | None = None,
    *,
    feature: str | None = None,
    repo: str | None = None,
    amend_feature: str | None = None,
) -> None:
    """A one-entry record through the step-record engine (spec 2026-09-25
    §5.C.6): the fragment edit, one commit holding only the fragment.
    `amend_feature` is the fragment an amendment is written to (R16).

    `drops` (row id → level → refs to remove, gh#624) is passed only when it
    names something: the engine refuses an empty per-row mapping. `feature` names
    a new row's fragment and `repo` the first fragment's identity (`add`)."""
    from fr.record import apply as engine
    from fr.record.model import StepRecord

    try:
        outcome = engine.apply_record(
            root,
            None,
            StepRecord(acceptance=(item,)),  # type: ignore[arg-type]
            target=engine.RecordTarget(
                message=message,
                acceptance_drops=drops or {},
                acceptance_features={item.id: feature} if feature else {},  # type: ignore[attr-defined]
                acceptance_repo=repo,
                feature=amend_feature,
            ),
        )
    except engine.RecordRefusedError as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(2) from e
    for notice in outcome.notices:
        if notice.startswith("warning"):
            err_console.print(f"[yellow]{notice}[/yellow]")


def _check_set_status_form(
    status: str | None,
    notes: str | None,
    issue: list[str],
    others: dict[str, object],
) -> None:
    """R2: `--status` needs `--notes`; without `--status` the call is the link-only
    form (`--id`, `--issue`, optional `--notes`), and anything else is refused
    before any file is read, naming the missing `--status`."""
    if status is not None:
        if not notes:
            err_console.print(
                "[red]error:[/red] --status needs --notes — a status that moved for no "
                "recorded reason is a silent change; nothing changed"
            )
            raise typer.Exit(2)
        return
    given = sorted(f for f, v in others.items() if v)
    if not issue or given:
        why = (
            f"{', '.join(given)} only go with --status"
            if given
            else "--notes alone changes nothing"
            if notes
            else "nothing to change"
        )
        err_console.print(
            f"[red]error:[/red] missing --status ({why}); the link-only form is "
            "`--id <row> --issue <ref> [--notes <text>]`; nothing changed"
        )
        raise typer.Exit(2)


@acceptance_app.command("set-status")
def set_status_cmd(
    row_id: str = typer.Option(..., "--id", help="Existing row id (never created here)."),
    status: str | None = typer.Option(
        None,
        "--status",
        help="ci | scheduled | unwired | walk-owed | walked | manual | not-implemented | failing. "
        "Omit with --issue for a link-only update that keeps the status and note.",
    ),
    notes: str | None = typer.Option(
        None,
        "--notes",
        help="Why the status moved (required with --status — a status that moved for no "
        "recorded reason is the silent change the acceptance-matrix rule forbids). Without "
        "--status, appended to the row's note.",
    ),
    level: list[str] = typer.Option(
        [],
        "--level",
        help="'<level>=<repo>:<path>[#test_name]' evidence to ADD (repeatable) — the other "
        "half of the documented transition.",
    ),
    drop_level: list[str] = typer.Option(
        [],
        "--drop-level",
        help="'<level>=<ref>' evidence to REMOVE (repeatable); refused if the ref is not "
        "on the row.",
    ),
    verify: str | None = typer.Option(
        None,
        "--verify",
        help="<strategy|none>: the row's verification strategy (`fr verification list`; "
        "spec 2026-10-06 §B). Omit to leave the row's existing `verify` alone — "
        "set-status never clears it.",
    ),
    issue: list[str] = typer.Option(
        [],
        "--issue",
        help="'owner/repo#n' issue whose promise the row carries, ADDED to its `issues` "
        "(repeatable; spec 2026-10-06 R13).",
    ),
    scenario: str | None = typer.Option(
        None,
        "--scenario",
        help="Repo-relative walk scenario for the row (spec 2026-10-06 R10); omit to keep "
        "the row's existing one.",
    ),
    walk: str | None = typer.Option(
        None,
        "--walk",
        help="Record a walk of this row: its evidence (a log path or a note). Needs "
        "--harness, --model and --strategy (spec 2026-10-06 R14).",
    ),
    harness: str | None = typer.Option(None, "--harness", help="--walk: the harness walked."),
    model: str | None = typer.Option(None, "--model", help="--walk: the model that walked it."),
    strategy: str | None = typer.Option(
        None, "--strategy", help="--walk: the verification strategy the walk ran."
    ),
    walk_outcome: str | None = typer.Option(
        None, "--walk-outcome", help="--walk: pass | fail (default pass)."
    ),
    walk_at: str | None = typer.Option(
        None,
        "--walk-at",
        help="--walk: when the walk happened (ISO date or timestamp); default now. For a "
        "walk recorded after the fact, from the evidence's own date.",
    ),
    feature: str | None = typer.Option(
        None,
        "--feature",
        help="The feature (spec slug) whose fragment the amendments of a MERGED row are "
        "written to; default: the spec of this branch's run, else refused.",
    ),
) -> None:
    """Move an existing row's status, with a reason (spec §3.G.2).

    A row still pending on this branch is rewritten in place in its fragment. A row
    merged on the default ref changes only by amendment (spec 2026-11-04 R16): the
    move is appended to this feature's fragment (`--feature`, else this branch's
    run's spec, else refused, naming `--feature`) as `set-status`, `add-level` and
    `drop-level` amendments.

    The effective matrix is CURRENT state, not a log: `check` reads today's
    status. Provenance lives in git history and in the amendments.

    Refuses an unknown id rather than creating a row: that is `add`'s job, and
    silently creating one on a typo'd id is how a row gets orphaned.

    `--drop-level` removes a stale evidence ref in the same rewrite (gh#624),
    so a row can be re-pointed — drop the old ref, `--level` the new one — in
    one call. A drop naming a ref not on the row, an unknown level, or a ref
    also named in `--level` is refused (exit 2) with nothing changed.

    `--issue` adds issues the row carries; `--walk` appends a walk (spec
    2026-10-06 §E). When that walk makes the row walk-verified and no other
    row still holds one of its issues open, the forge's close and unlabel
    commands are printed — fr never closes the issue itself, and prints
    nothing under `tracking: none`.

    `--verify <strategy|none>` names the row's verification strategy, in the
    same rewrite; omitting the flag preserves whatever the
    row already carries (`add`'s create-only, and there is no delete verb, so
    this is the only way to set it on an existing row without hand-editing
    its fragment).
    """
    from typing import get_args

    from fr.acceptance.amend import resolve_feature
    from fr.acceptance.edit import describe_move, drop_levels, merge_levels
    from fr.acceptance.model import Status

    _check_set_status_form(
        status,
        notes,
        issue,
        {
            "--level": level,
            "--drop-level": drop_level,
            "--verify": verify,
            "--scenario": scenario,
            "--walk": walk,
            "--harness": harness,
            "--model": model,
            "--strategy": strategy,
            "--walk-outcome": walk_outcome,
            "--walk-at": walk_at,
        },
    )
    root = resolve_repo_root()
    _refuse_if_off(root, "`fr acceptance set-status` writes no row")
    matrix = _load(root)

    valid = list(get_args(Status))
    if status is not None and status not in valid:
        err_console.print(
            f"[red]error:[/red] unknown status {status!r} (valid: {' | '.join(valid)})"
        )
        raise typer.Exit(2)
    _check_verify(root, verify)
    new_walk = _walk_from_flags(
        root, walk, harness, model, strategy, walk_outcome or "pass", walk_at
    )
    target = next((r for r in matrix.rows if r.id == row_id), None)
    if target is None:
        known = ", ".join(r.id for r in matrix.rows) or "none"
        err_console.print(
            f"[red]error:[/red] no row with id {row_id!r} — nothing changed "
            f"(`fr acceptance add` creates rows; existing ids: {known})"
        )
        raise typer.Exit(2)
    link_only = status is None
    new_status = target.status if status is None else status
    if not link_only:
        new_notes = notes or ""
    elif notes and notes not in target.notes.split("; "):  # a re-run adds nothing
        new_notes = "; ".join(n for n in (target.notes, notes) if n)
    else:
        new_notes = target.notes

    additions = _parse_levels(level)
    drops = _parse_levels(drop_level, flag="--drop-level")
    both = sorted(
        f"{lv}={ref}" for lv, refs in drops.items() for ref in refs if ref in additions.get(lv, [])
    )
    if both:
        err_console.print(
            f"[red]error:[/red] {', '.join(both)} named in both --level and --drop-level "
            "— nothing changed"
        )
        raise typer.Exit(2)
    try:
        merged = merge_levels(drop_levels(target.levels, drops), additions)
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(2) from e
    new_verify = verify if verify is not None else target.verify
    try:
        new_row = Row(
            id=target.id,
            capability=target.capability,
            acceptance=target.acceptance,
            origin=target.origin,
            levels=merged,
            status=new_status,  # type: ignore[arg-type]  # pydantic validates the literal
            notes=new_notes,
            verify=new_verify,
            visual=target.visual,  # set-status never touches `visual` (spec 2026-09-28 §A)
            scenario=scenario if scenario is not None else target.scenario,
            issues=target.issues + tuple(i for i in dict.fromkeys(issue) if i not in target.issues),
            harnesses=target.harnesses,
            walks=target.walks + ((new_walk,) if new_walk is not None else ()),
        )
    except Exception as e:  # pydantic ValidationError → operator-readable
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(2) from e
    _validate_refs(new_row)
    from fr.acceptance.model import walked_error

    if (why := walked_error(new_row)) is not None:
        err_console.print(f"[red]error:[/red] {escape(why)}; nothing changed")
        raise typer.Exit(2)

    from fr.record.model import AcceptanceItem

    _apply_rows(
        root,
        AcceptanceItem(
            id=row_id,
            status=new_status,
            notes=new_notes,
            levels={k: tuple(v) for k, v in additions.items()},
            verify=verify,  # None preserves; apply.py falls back to existing
            issues=tuple(issue),
            scenario=scenario,
            walk=new_walk,
        ),
        f"chore(fr): acceptance — {row_id} {describe_move(target, new_row)}",
        {row_id: {k: tuple(v) for k, v in drops.items()}} if drops else None,
        amend_feature=resolve_feature(root, feature),
    )
    typer.echo(f"{row_id}: {describe_move(target, new_row)}")
    if new_walk is not None:
        _print_close_commands(root, target)


@acceptance_app.command("amend")
def amend_cmd(
    row_id: str | None = typer.Option(None, "--id", help="The row to amend."),
    op: str | None = typer.Option(
        None, "--op", help="reword | set-status | add-level | drop-level | retire."
    ),
    why: str | None = typer.Option(None, "--why", help="Why the row changes (required)."),
    acceptance: str | None = typer.Option(None, "--acceptance", help="reword: the statement."),
    capability: str | None = typer.Option(None, "--capability", help="reword: the heading."),
    status: str | None = typer.Option(None, "--status", help="set-status: the new status."),
    notes: str | None = typer.Option(
        None, "--notes", help="set-status, retire: the row's note (required by both)."
    ),
    issue: list[str] = typer.Option(
        [], "--issue", help="set-status: an 'owner/repo#n' issue to add (repeatable)."
    ),
    verify: str | None = typer.Option(None, "--verify", help="set-status: the strategy."),
    scenario: str | None = typer.Option(None, "--scenario", help="set-status: the scenario."),
    level: str | None = typer.Option(
        None, "--level", help="add-level, drop-level: '<level>=<ref>'."
    ),
    base: int | None = typer.Option(
        None, "--base", help="The row revision this is based on; default: the current one."
    ),
    feature: str | None = typer.Option(
        None,
        "--feature",
        help="The feature (spec slug) whose fragment the amendment is written to; "
        "default: the spec of this branch's run.",
    ),
    rebase: bool = typer.Option(
        False,
        "--rebase",
        help="Re-base every stale amendment of this branch onto its row's current "
        "revision (after reviewing the row), instead of writing one.",
    ),
) -> None:
    """Append an amendment of a row to this feature's fragment (spec 2026-11-04 R16).

    A row another feature merged changes only by amendment: `reword` (acceptance,
    capability), `set-status` (status, notes, issue, verify, scenario), `add-level`
    and `drop-level` (one ref), `retire` (notes). The amendment names the row
    revision it is based on (default: the current one); a base another feature's
    merged amendment has since passed is refused by `fr acceptance check` and
    `deliver` until `--rebase` (R17). One commit holding only the fragment."""
    from fr.acceptance.amend import resolve_feature
    from fr.acceptance.fragment import AMENDMENT_OPS
    from fr.record.model import AmendmentItem

    root = resolve_repo_root()
    _refuse_if_off(root, "`fr acceptance amend` writes no amendment")
    if rebase:
        _rebase(root)
        return
    if row_id is None or op is None or not why:
        err_console.print(
            "[red]error:[/red] --id, --op and --why are required (or --rebase); nothing changed"
        )
        raise typer.Exit(2)
    if op not in AMENDMENT_OPS:
        err_console.print(
            f"[red]error:[/red] unknown op {op!r} (valid: {' | '.join(AMENDMENT_OPS)})"
        )
        raise typer.Exit(2)
    lv, ref = None, None
    if level is not None:
        (lv, refs), *more = _parse_levels([level]).items()
        ref = refs[0]
    _load(root)
    try:
        item = AmendmentItem(
            row=row_id, op=op, why=why, base=base, acceptance=acceptance,  # type: ignore[arg-type]
            capability=capability, status=status, notes=notes, issues=tuple(issue),
            verify=verify, scenario=scenario, level=lv, ref=ref,
        )  # fmt: skip
    except ValueError as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}; nothing changed")
        raise typer.Exit(2) from e
    _apply_rows(
        root,
        item,
        f"chore(fr): acceptance — amend {row_id} ({op})",
        amend_feature=resolve_feature(root, feature),
    )
    typer.echo(f"{row_id}: {op} amendment written")


def _rebase(root: Path) -> None:
    """`amend --rebase`: every stale pending amendment's `base` set to the revision
    its row has when it applies (R17), one commit holding only the fragments."""
    from fr.acceptance.edit import rebase_amendment
    from fr.acceptance.fold import effective
    from fr.artifacts.atomic import write_text_atomic
    from fr.artifacts.commit import commit_paths

    try:
        stale = effective(root).stale_pending
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(1) from e
    if not stale:
        typer.echo("no stale amendment base: nothing to re-base")
        return
    written: dict[Path, str] = {}
    for s in stale:
        path = artifact_root(root) / s.path  # the fold's paths hang from the artifact root
        text = written.get(path, path.read_text())
        written[path] = rebase_amendment(text, s.index, s.revision)
        typer.echo(f"{s.row}: {s.op} amendment re-based {s.base} → {s.revision}")
    for path, text in written.items():
        write_text_atomic(path, text)
    outcome = commit_paths(
        root, sorted(written), "chore(fr): acceptance — re-base stale amendments"
    )
    if not outcome.committed:
        err_console.print(f"[yellow]not committed: {escape(outcome.reason or '')}[/yellow]")


@acceptance_app.command("add")
def add_cmd(
    row_id: str = typer.Option(..., "--id", help="Stable kebab-case row id."),
    capability: str = typer.Option(..., "--capability", help="Grouping heading."),
    acceptance: str = typer.Option(..., "--acceptance", help="The business-level statement."),
    origin: list[str] = typer.Option(
        [],
        "--origin",
        help="'spec:<slug>[#R<n>]', 'plan:<slug>' or '<repo>:<path>[#anchor]' ref "
        "(repeatable; a spec or plan path is written as its logical ref).",
    ),
    level: list[str] = typer.Option(
        [], "--level", help="'<level>=<repo>:<path>[#test_name]' test ref (repeatable)."
    ),
    status: str = typer.Option(
        ...,
        "--status",
        help="ci | scheduled | unwired | walk-owed | walked | manual | not-implemented | failing.",
    ),
    notes: str = typer.Option("", "--notes", help="Evidence detail / backfill owed."),
    verify: str | None = typer.Option(
        None,
        "--verify",
        help="<strategy|none>: the row's verification strategy (`fr verification list`); "
        "a post-merge one is listed as owed in the PR body (spec 2026-10-06 §B).",
    ),
    visual_state: list[str] = typer.Option(
        [],
        "--visual-state",
        help="A named UI state visual evidence must cover (repeatable; spec 2026-09-28 §A).",
    ),
    visual_interaction: list[str] = typer.Option(
        [],
        "--visual-interaction",
        help="A named UI interaction (limits included) visual evidence must cover "
        "(repeatable; spec 2026-09-28 §A).",
    ),
    issue: list[str] = typer.Option(
        [],
        "--issue",
        help="'owner/repo#n' issue whose promise the row carries (repeatable; "
        "spec 2026-10-06 R13).",
    ),
    scenario: str | None = typer.Option(
        None, "--scenario", help="Repo-relative walk scenario for the row (spec 2026-10-06 R10)."
    ),
    harness: list[str] = typer.Option(
        [],
        "--harness",
        help="A harness the row's promise covers (repeatable; spec 2026-10-06 R14).",
    ),
    feature: str | None = typer.Option(
        None,
        "--feature",
        help=f"The fragment ({KIND_DIRS['acceptance-fragment']}/<feature>.yaml) to write the row "
        "to, when its origins name no single spec (`legacy` for none).",
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        help="'<org>/<repo>' for the repo's first fragment, when the origin remote does "
        "not name it.",
    ),
) -> None:
    """Insert a schema-validated row into the fragment of the feature that owns it
    (its one origin spec, or --feature), after its capability's last row (agents
    never hand-edit YAML shapes); a new capability goes at the end of `rows:`.

    `add` CREATES rows; moving an existing row's status is
    `fr acceptance set-status` (re-adding an id is refused below, by design).
    """
    from fr.acceptance.model import Visual

    root = resolve_repo_root()
    _refuse_if_off(root, "`fr acceptance add` writes no row")
    matrix = _load(root)
    _check_verify(root, verify)

    levels = _parse_levels(level)
    try:
        visual = (
            Visual(states=tuple(visual_state), interactions=tuple(visual_interaction))
            if visual_state or visual_interaction
            else None
        )
        new_row = Row(
            id=row_id,
            capability=capability,
            acceptance=acceptance,
            origin=tuple(origin),
            levels={k: tuple(v) for k, v in levels.items()},
            status=status,  # type: ignore[arg-type]  # pydantic validates the literal
            notes=notes,
            verify=verify,
            visual=visual,
            scenario=scenario,
            issues=tuple(dict.fromkeys(issue)),
            harnesses=tuple(dict.fromkeys(harness)),
        )
    except Exception as e:  # pydantic ValidationError → operator-readable
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(2) from e
    if any(r.id == new_row.id for r in matrix.rows):
        err_console.print(
            f"[red]error:[/red] duplicate row id: {new_row.id} "
            "(move an existing row with `fr acceptance set-status`)"
        )
        raise typer.Exit(2)
    _validate_refs(new_row)

    from fr.record.model import AcceptanceItem

    # The engine inserts textually: a load→dump cycle would destroy the
    # header comments.
    _apply_rows(
        root,
        AcceptanceItem(
            id=new_row.id,
            capability=new_row.capability,
            acceptance=new_row.acceptance,
            origin=new_row.origin,
            levels={k: v for k, v in new_row.levels.items() if v},
            status=new_row.status,
            notes=new_row.notes,
            verify=new_row.verify,
            visual=new_row.visual,
            scenario=new_row.scenario,
            issues=new_row.issues,
            harnesses=new_row.harnesses,
        ),
        f"chore(fr): acceptance — add {new_row.id}",
        feature=feature,
        repo=repo,
    )
    typer.echo(f"added row {new_row.id} ({new_row.status})")


def _init_quiet(root: Path, *, refresh_ci: bool) -> bool:
    """Under quiet, `init` scaffolds only the fragment directory, in this feature's root
    on the `fr` branch (p3-r1). The CI gate, the rule file, the `.gitignore` lines and
    the badge are product-branch files, and a quiet product branch holds no row for them
    to read (R23). False (nothing done) when the repo is not quiet."""
    from fr.artifacts.paths import outside_repo
    from fr.records_commit import commit_records

    placement = outside_repo(root)  # quiet, and stealth alike (R24: nothing in the target)
    if placement is None:
        return False
    # review p4-r9: name the placement this workspace is in, and its requirement
    req = "R24" if placement == "stealth" else "R23"
    where = "the target" if placement == "stealth" else "the product branches"
    what = (
        "a stealth target receives no fr file"
        if placement == "stealth"
        else ("a quiet repo keeps no acceptance gate on its product branches")
    )
    if refresh_ci:
        err_console.print(
            f"`fr acceptance init --refresh-ci` is not available under placement {placement}: "
            f"{what} ({req})",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    keep = artifact_root(root) / FRAGMENTS_DIR / ".gitkeep"
    if keep.exists():
        typer.echo(f"exists  {keep} (left untouched)")
    else:
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text("")
        typer.echo(f"created {keep}")
    typer.echo(
        f"{placement:<7} no CI workflow, rule file, .gitignore lines or badge: under placement "
        f"{placement} fr writes nothing on {where} ({req})"
    )
    commit_records(root, [keep], "chore(fr): acceptance init")
    return True


@acceptance_app.command("init")
def init_cmd(
    with_ci: bool = typer.Option(
        False,
        "--with-ci",
        help="Scaffold the CI workflow even though the repo has no CI config for its "
        "backend yet (by default one is written only beside existing CI).",
    ),
    refresh_ci: bool = typer.Option(
        False,
        "--refresh-ci",
        help="Rewrite an existing fr-scaffolded GitHub/Gitea workflow to the current "
        "scaffold (a file that is not fr's is refused). For GitLab, whose "
        ".gitlab-ci.yml is shared, print the job to paste instead.",
    ),
) -> None:
    """Scaffold matrix + CI workflow + backfill rule + gitignore (idempotent).

    The CI workflow is written only when the repo already has CI for its
    backend, or with `--with-ci` (gh#775)."""
    from fr._hosts import detect_backend
    from fr.acceptance.check import resolve_identity
    from fr.acceptance.scaffold import init

    root = resolve_repo_root()
    _refuse_if_off(root, "`fr acceptance init` scaffolds no matrix, report or CI")
    if _init_quiet(root, refresh_ci=refresh_ci):
        return
    try:
        org, repo = resolve_identity(Matrix(), root)
    except AcceptanceError as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(1) from e
    backend = detect_backend(root)
    from fr.services.model import CI_FOR_FORGE, ServicesError
    from fr.services.resolve import resolve_services

    try:
        services = resolve_services(root)
    except ServicesError as e:
        err_console.print(f"[red]error:[/red] {escape(str(e))}")
        raise typer.Exit(2) from e
    ci = services.ci
    if refresh_ci:
        _refresh_ci(root, services, with_ci=with_ci)
        return
    if ci.source == "declared" and ci.type == "none":
        if with_ci:
            err_console.print(
                "[red]error:[/red] --with-ci contradicts the declared `ci: {type: none}` in "
                ".devcontainer/fr-profiles.yaml — change it with `fr services` or drop the flag"
            )
            raise typer.Exit(2)
    from fr.acceptance.ci import ci_none_reason

    reason = ci_none_reason(root, services)
    ci_type = ci.type
    if ci_type == "none" and with_ci:
        ci_type = CI_FOR_FORGE[services.forge.type]
    outcome = init(
        root,
        org,
        repo,
        backend=backend,
        with_ci=with_ci,
        ci_type=ci_type,
        tracking_type=services.tracking.type,
        no_ci_reason=reason,
        pages_decision=_pages_decision(root, ci_type),
    )
    for rel in outcome.created:
        typer.echo(f"created {rel}")
    for rel in outcome.modified:
        typer.echo(f"modified {rel}")
    for rel in outcome.skipped:
        typer.echo(f"exists  {rel} (left untouched)")
    for notice in outcome.notices:
        typer.echo(notice)
    # gh#775: commit every path changed here, as every fr writer does (gh#610).
    # Left to the next command, only ITS paths were committed, and the rule
    # file and `.gitignore` sat dirty until close-out stashed them. Never fails
    # init: a refused commit (the default branch, no repo) is one stderr line.
    from fr.records_commit import commit_records

    paths = _committable(root, outcome.written)
    if paths:
        commit_records(root, [Path(rel) for rel in paths], "chore(fr): acceptance init")


def _pages_decision(root: Path, ci_type: str) -> tuple[bool, str] | None:
    """`pages_allowed`'s answer for a CI type that can publish Pages (GitHub Actions,
    GitLab CI); None for the others, which never do. The one forge read init makes."""
    from fr.acceptance.pages import pages_allowed
    from fr.acceptance.scaffold import PAGES_STEP
    from fr.hostclient import client_for

    if ci_type not in PAGES_STEP:
        return None
    return pages_allowed(root, client_for(root))


def _refresh_ci(root: Path, services: Any, *, with_ci: bool) -> None:
    """`init --refresh-ci`: exit 0 rewritten/current, 1 refused (foreign file,
    nothing to refresh, or GitLab's shared file with the job to paste)."""
    from fr.acceptance.ci import SCAFFOLD_PATHS
    from fr.acceptance.scaffold import debt_steps, publish_plan, refresh_ci
    from fr.records_commit import commit_records

    if with_ci:
        err_console.print("[red]error:[/red] --refresh-ci takes no --with-ci")
        raise typer.Exit(2)
    ci_type = services.ci.type
    if ci_type not in SCAFFOLD_PATHS:
        err_console.print(
            f"[red]error:[/red] this repo's ci service is {ci_type!r}: nothing to refresh"
        )
        raise typer.Exit(1)
    debt, debt_off = debt_steps(root, ci_type, services.tracking.type)
    if debt_off is not None:
        typer.echo(f"no debt  {debt_off}; see `fr settings show`")
    plan = publish_plan(root, ci_type, _pages_decision(root, ci_type))
    for notice in plan.notices:
        typer.echo(notice)
    out = refresh_ci(root, ci_type, debt=debt, pages=plan.pages, comment=plan.comment)
    if out.status == "missing":
        err_console.print(f"[red]error:[/red] {out.path} does not exist; run `fr acceptance init`")
        raise typer.Exit(1)
    if out.status == "foreign":
        err_console.print(
            f"[red]error:[/red] {out.path} is not an fr-scaffolded acceptance pipeline; "
            "not touching it"
        )
        raise typer.Exit(1)
    if out.status == "paste":
        typer.echo(
            f"{out.path} is shared by every job in the repo, so fr will not rewrite it. "
            "Replace the `acceptance-report:` job with these jobs "
            "(keep `acceptance` in `stages:`):\n"
        )
        typer.echo(out.text)
        raise typer.Exit(1)
    if out.status == "current":
        typer.echo(f"{out.path} is already current")
        return
    typer.echo(
        f"rewrote {out.path} to the current scaffold (review the diff: local edits are replaced)"
    )
    commit_records(root, [Path(out.path)], "chore(fr): acceptance init --refresh-ci")


def _committable(root: Path, written: list[str]) -> list[str]:
    """The paths of `written` git will take in one `git add`: one it cannot
    (a gitignored path) fails the whole add, and
    so the whole commit (gh#775 review). An ignored path cannot dirty the tree,
    so leaving it out loses nothing; it is named so nobody assumes otherwise."""
    from fr.git import GitUnavailableError, git_answer

    if not written:
        return []
    try:
        ignored = set(git_answer(root, "check-ignore", "--", *written).stdout.split())
    except GitUnavailableError:
        return written  # commit_records reports whatever git then says
    for rel in sorted(ignored):
        typer.echo(f"ignored {rel} (gitignored here, so not committed)")
    return [p for p in written if p not in ignored]


BACKFILL_PROTOCOL = """\
## Backfill work-protocol (agent-driven — see the fr-acceptance skill)

1. Inventory: the uncited Test Plan specs and unlinked plans above, plus any
   design/study docs with acceptance-like tables, and the test tree(s).
2. DRAFT rows — one row per business acceptance, not per test — with real
   refs and HONEST statuses: per-PR-automated evidence ⇒ `ci`; a test that
   exists but does not run in CI ⇒ `unwired`; proven live by a recorded walk
   ⇒ `walked`; a live walk still owed ⇒ `walk-owed`; a process that is never
   automatable ⇒ `manual`; absent ⇒ `not-implemented`. The drift channel is
   precisely the hand-tracked claims — when in doubt between `ci` and
   `unwired`, choose unwired.
3. Add rows via `fr acceptance add` (never hand-edit YAML shapes), run
   `fr acceptance check`, fix, and open a review PR — the operator audits
   statuses; do not inflate coverage.
"""


@acceptance_app.command("backfill")
def backfill_cmd() -> None:
    """Emit the agent backfill protocol + deterministic inventory (markdown)."""
    import yaml

    from fr.acceptance.check import SPEC_DIRS, spec_test_plan
    from fr.acceptance.model import archive_twin, split_ref

    root = resolve_repo_root()
    _refuse_if_off(root, "`fr acceptance backfill` writes no row")
    matrix = _load(root)

    referenced: set[str] = set()
    for r in matrix.rows:
        for ref in r.origin:
            try:
                _, path, _ = split_ref(ref)
            except AcceptanceError:
                continue
            referenced.add(path)
            twin = archive_twin(path)
            if twin:
                referenced.add(twin)
    uncited = [
        str(spec.relative_to(root))
        for spec_dir in SPEC_DIRS
        for spec in sorted((root / spec_dir).glob("*.md"))
        if spec_test_plan(root, spec)[0] and str(spec.relative_to(root)) not in referenced
    ]

    unlinked_plans: list[str] = []
    plans_dir = kind_dir("plan", space_for(root))
    if plans_dir.is_dir():
        for plan_dir in sorted(p for p in plans_dir.iterdir() if p.is_dir()):
            linked = False
            for phase_file in sorted(plan_dir.glob("[0-9][0-9].yaml")):
                try:
                    doc = yaml.safe_load(phase_file.read_text()) or {}
                except yaml.YAMLError:
                    continue  # unparseable plans are skipped gracefully
                if (doc.get("phase") or {}).get("acceptance"):
                    linked = True
                    break
            if not linked:
                unlinked_plans.append(plan_dir.name)

    lines = ["# Acceptance backfill — inventory + protocol", ""]
    lines.append("## Specs with a Test Plan not yet cited by any row")
    lines += [f"- {p}" for p in uncited] or ["- (none — every Test Plan spec is cited)"]
    lines += ["", "## Live plans with no `acceptance:` links"]
    lines += [f"- {p}" for p in unlinked_plans] or ["- (none)"]
    lines += ["", "## Test-tree hints"]
    tests_dir = root / "tests"
    if tests_dir.is_dir():
        lines += [f"- tests/{d.name}/" for d in sorted(tests_dir.iterdir()) if d.is_dir()] or [
            "- tests/ (flat)"
        ]
    else:
        lines.append("- (no tests/ directory found)")
    lines += ["", BACKFILL_PROTOCOL]
    typer.echo("\n".join(lines))


DIGEST_MARKER = "<!-- fr-acceptance-digest -->"


@acceptance_app.command("digest")
def digest_cmd() -> None:
    """Markdown for the upserted "Acceptance debt" issue (idempotence marker
    included; zero debt prints a closable body)."""
    from fr.debt.engine import acceptance_from_matrix
    from fr.debt.model import AcceptanceDebt
    from fr.debt.render import acceptance_section
    from fr.settings import disabled

    root = resolve_repo_root()
    if disabled(root, "acceptance"):
        section = acceptance_section(AcceptanceDebt(available=False), off=True)
    else:
        matrix = _load(root)
        section = acceptance_section(acceptance_from_matrix(matrix, *_contested(root)))
    lines = [section, "", DIGEST_MARKER, "", "_generated by `fr acceptance digest`_"]
    typer.echo("\n".join(lines))
