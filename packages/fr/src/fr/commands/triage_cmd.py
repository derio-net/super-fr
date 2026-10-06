"""`fr triage` CLI — backlog triage (spec 2026-09-21-fr-triage-design).

`collect` reads the forge and writes `facts.json` under the scope's state
directory (`$HOME/.cache/fr/triage/<scope>/`, or `--dir`). `check` reports the
four sets (unranked, settled, orphaned, unreachable) and always exits 0.
`render` writes `triage.html`, and `--open` hands it to `webbrowser`.
The `batch` sub-app's verbs live in `fr.commands.triage_batch_cmd` (spec
2026-09-25-triage-batches). The engine lives in `fr.triage`; this module only
parses flags and does I/O.

Gate-exempt: `triage` is in `fr.artifacts.trigger.READ_ONLY_COMMANDS` because
it never reads or writes a registered artifact (spec §3.F′).

Exit codes: 0 success (skipped repos and truncation warnings are reported,
not failed); 2 usage (not exactly one of --repo/--org), an unreadable
judgements.yaml, a forge failure in repo scope, or an org scope in which
no repo could be read (review r-p2-empty); for check/render, a missing
facts.json (the message names the collect command) or an unreadable state file.
"""

from __future__ import annotations

import json
import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from fr.hostclient import client_for_backend
from fr.triage.batch import last_dispatch
from fr.triage.check import classify
from fr.triage.collect import PR_LIMIT, ClientForge, CollectStats, Forge, collect_facts_counted
from fr.triage.errors import TriageError
from fr.triage.fragments import resolve_manifest
from fr.triage.model import (
    Facts,
    Judgements,
    Scope,
    issue_key,
    load_facts,
    load_judgements,
    load_scope_facts,
    state_dir,
)
from fr.triage.render import GENERATED, plural, render
from fr.triage.snapshot import (
    acceptance_rows,
    diff_snapshots,
    latest_snapshot,
    matrix_for_scope,
    previous_snapshot,
    store_snapshot,
    take_snapshot,
)

console = Console()
err_console = Console(stderr=True)

BOARD_DIR = "board"  # `<state>/board/manifest.yaml`: the board's authored fragments

triage_app = typer.Typer(
    name="triage",
    help="Backlog triage: collect forge facts, check judgements, render a board.",
    no_args_is_help=True,
)


batch_app = typer.Typer(
    name="batch",
    help="Batches: groups of judged issues delivered as one run.",
    no_args_is_help=True,
)
triage_app.add_typer(batch_app)


# One option set for --repo/--org/--dir, shared by collect, check, render and batch.
RepoOpt = Annotated[
    str | None, typer.Option("--repo", help="Triage one repo OWNER/REPO, or a group: A/B,C/D.")
]
OrgOpt = Annotated[str | None, typer.Option("--org", help="Triage every repo of OWNER.")]
DirOpt = Annotated[
    Path | None,
    typer.Option("--dir", help="State directory (default: $HOME/.cache/fr/triage/<scope>/)."),
]


def make_forge() -> Forge:
    """The forge `collect` reads. Tests replace this factory, never subprocess.

    GitHub's adapter: triage is GitHub-only by its own scope, and with no
    checkout to resolve a backend from, that is the honest default."""
    return ClientForge(client_for_backend("github"))


def _group_scope(parts: list[str]) -> Scope:
    """A group scope over *parts*; two repos sharing a NAME are refused (exit 2) because
    a judgement key is `<repo-name>#<n>` (wave-driver §H). Nothing is written yet."""
    scope = Scope.group(parts)
    names: dict[str, str] = {}
    for r in scope.repos:
        name = r.split("/", 1)[1].lower()
        if name in names:
            err_console.print(
                f"[red]error:[/red] {escape(names[name])} and {escape(r)} share the repo name "
                f"{escape(name)}; judgement keys are <repo-name>#<n>, so a group may not hold both",
                soft_wrap=True,
            )
            raise typer.Exit(code=2)
        names[name] = r
    if len(scope.repos) == 1:
        return Scope(kind="repo", target=scope.repos[0])
    return scope


def _scope(repo: str | None, org: str | None) -> Scope:
    if (repo is None) == (org is None):
        err_console.print("[red]error:[/red] give exactly one of --repo OWNER/REPO or --org OWNER")
        raise typer.Exit(code=2)
    if repo is not None:
        parts = [p.strip() for p in repo.split(",")] if "," in repo else [repo]
        for part in parts:
            if part.count("/") != 1 or not all(part.split("/")):
                err_console.print(
                    f"[red]error:[/red] --repo must be OWNER/REPO or a comma-separated list "
                    f"of them, got {escape(repr(repo))}",
                    soft_wrap=True,
                )
                raise typer.Exit(code=2)
        if len(parts) == 1:
            return Scope(kind="repo", target=parts[0])
        return _group_scope(parts)
    assert org is not None
    if not org or "/" in org:
        err_console.print(
            f"[red]error:[/red] --org must be an OWNER, got {escape(repr(org))}", soft_wrap=True
        )
        raise typer.Exit(code=2)
    return Scope(kind="org", target=org)


def _report(facts: Facts) -> None:
    """Print what the forge could not give; every forge-sourced string escaped (r7)."""
    for s in facts.skipped:
        err_console.print(
            f"[yellow]skipped[/yellow] {escape(s.repo)}: {escape(s.reason)}", soft_wrap=True
        )
    for u in facts.unviewed:
        err_console.print(
            f"[yellow]unviewed[/yellow] {escape(u.key)}: {escape(u.reason)} "
            "(judged or named by `duplicate_of`, but the forge would not show it; "
            "not treated as orphaned)",
            soft_wrap=True,
        )
    for w in facts.warnings:
        err_console.print(
            f"[yellow]warning:[/yellow] {w.describe(escape(w.target))}",
            soft_wrap=True,
        )


@triage_app.command("collect")
def collect_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    pr_limit: int = typer.Option(
        PR_LIMIT, "--pr-limit", min=1, help="PRs listed per repo (the PR -> issue window)."
    ),
) -> None:
    """Read the forge and write facts.json for the scope."""
    scope = _scope(repo, org)
    try:
        facts, out, _ = collect_into(scope, state_dir(scope, dir_override), pr_limit=pr_limit)
    except TriageError as exc:
        err_console.print(f"[red]error:[/red] {escape(str(exc))}", soft_wrap=True)
        raise typer.Exit(code=2) from exc
    _report(facts)
    n_open = sum(1 for i in facts.issues if i.state == "open")
    console.print(f"wrote {out} ({plural(n_open, 'open issue')})", markup=False, soft_wrap=True)


def collect_into(
    scope: Scope,
    target_dir: Path,
    *,
    pr_limit: int = PR_LIMIT,
    carry: bool = False,
    lenient: bool = False,
) -> tuple[Facts, Path, CollectStats]:
    """Collect *scope* through `make_forge()` and write `<target_dir>/facts.json`.

    `collect` and the wave driver's every pass share it (wave-driver §B), so a
    driver pass reads the forge exactly as `fr triage collect` does. With
    *carry* (the driver's passes) a judged issue the previous facts.json for
    this scope holds closed is carried over instead of viewed again (gh#911);
    `fr triage collect` never carries. *lenient* (the driver's passes too) drops an
    unknown top-level `.fr/triage.yaml` key instead of refusing it (gh#998); `fr
    triage collect` stays strict. Returns the stats of single-issue reads.
    Raises `TriageError` on a refusal; writes nothing then.
    """
    judgements = target_dir / "judgements.yaml"
    loaded = load_judgements(judgements) if judgements.exists() else None
    # Every judged key, and every `duplicate_of` target (R6: a closed original must
    # read `closed`, not `missing`); one view each, whichever way it was named.
    judged = (
        list(dict.fromkeys([*loaded.issues, *sorted(loaded.duplicate_targets())])) if loaded else []
    )
    # The branch and time of each batch's last dispatch, unless it was cancelled
    # since (spec 2026-09-25-triage-batches §3.A): collect looks each one up by
    # head, unless the previous facts already show it terminal (review r2p-f3).
    # Close-out and post_merge events may follow the dispatch (wave-driver §B).
    branches = [
        (b.repo_name, event.branch, event.at)
        for b in (loaded.batches if loaded else [])
        if b.events and b.events[-1].kind != "cancel" and (event := last_dispatch(b)) is not None
    ]
    previous = _previous_facts(target_dir / "facts.json", scope)
    facts, stats = collect_facts_counted(
        make_forge(),
        scope,
        now=datetime.now(UTC),
        judged=judged,
        batch_branches=branches,
        known_batch_prs=previous.batch_prs if previous else [],
        pr_limit=pr_limit,
        carried=[i for i in previous.issues if i.state == "closed"] if previous and carry else (),
        lenient=lenient,
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / "facts.json"
    out.write_text(
        json.dumps(facts.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return facts, out, stats


def _previous_facts(path: Path, scope: Scope) -> Facts | None:
    """The previous collect's facts for *scope*; None when there is no usable file.

    Only an optimisation (review r2p-f3, gh#911): a missing, unreadable,
    older-schema or other-scope facts.json just means every dispatched batch is
    looked up and every judged closed issue viewed again.
    """
    if not path.exists():
        return None
    try:
        facts = load_facts(path)
    except TriageError:
        return None
    return facts if facts.matches(scope) else None


def _load_state(scope: Scope, dir_override: Path | None) -> tuple[Path, Facts, Judgements]:
    """The scope's facts and judgements, through the `fr.triage.model` loaders.

    No facts.json is an error naming `collect`, and so are facts collected for
    another scope (a `--dir` can point anywhere, gh#886); no judgements.yaml is
    allowed — everything is then unranked.
    """
    target_dir = state_dir(scope, dir_override)
    facts_path = target_dir / "facts.json"
    if not facts_path.exists():
        flag = "org" if scope.kind == "org" else "repo"
        err_console.print(
            f"[red]error:[/red] no facts at {escape(str(facts_path))}; run "
            f"`fr triage collect --{flag} {escape(scope.target)}` first",
            soft_wrap=True,
        )
        raise typer.Exit(code=2)
    judgements_path = target_dir / "judgements.yaml"
    try:
        facts = load_scope_facts(facts_path, scope)
        judgements = (
            load_judgements(judgements_path)
            if judgements_path.exists()
            else Judgements.model_validate({"schema": 1})
        )
    except TriageError as exc:
        err_console.print(f"[red]error:[/red] {escape(str(exc))}", soft_wrap=True)
        raise typer.Exit(code=2) from exc
    return target_dir, facts, judgements


@triage_app.command("check")
def check_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    as_json: bool = typer.Option(False, "--json", help="Emit check sets as JSON."),
) -> None:
    """Report unranked issues and PRs, settled, orphaned, unreachable, stale, unplaced,
    duplicate candidates, duplicates, awaiting live and more.

    Always exits 0.
    """
    _, facts, judgements = _load_state(_scope(repo, org), dir_override)
    result = classify(facts, judgements)
    if as_json:
        print(json.dumps(result.to_json(), indent=2, ensure_ascii=False))
        return
    console.print(f"[bold]unranked[/bold] ({len(result.unranked)}) — open, no judgement")
    for i in result.unranked:
        console.print(f"  {escape(i.key)}  {escape(i.title)}", soft_wrap=True)
    console.print(f"[bold]unranked PRs[/bold] ({len(result.unranked_prs)}) — open, no judgement")
    for pr in result.unranked_prs:
        console.print(
            f"  {escape(issue_key(pr.repo, pr.number))}  {escape(pr.title)}",
            soft_wrap=True,
        )
    console.print(f"[bold]settled[/bold] ({len(result.settled)}) — judged, now closed or merged")
    for i in result.settled:
        console.print(f"  {escape(i.key)}  {i.stage}  {escape(i.title)}", soft_wrap=True)
    console.print(
        f"[bold]settled PRs[/bold] ({len(result.settled_prs)}) — judged, now closed or merged"
    )
    for pr in result.settled_prs:
        console.print(
            f"  {escape(issue_key(pr.repo, pr.number))}  {pr.state.lower()}  {escape(pr.title)}",
            soft_wrap=True,
        )
    console.print(f"[bold]orphaned[/bold] ({len(result.orphaned)}) — judged, found nowhere")
    for key in result.orphaned:
        console.print(f"  {escape(key)}", soft_wrap=True)
    console.print(
        f"[bold]unreachable[/bold] ({len(result.unreachable)}) — judged, the forge would "
        "not show it; not orphaned"
    )
    for u in result.unreachable:
        console.print(f"  {escape(u.key)}  {escape(u.reason)}", soft_wrap=True)
    console.print(
        f"[bold]stale dispatch[/bold] ({len(result.stale)}) — fr:in-progress, batch marker "
        "older than the repo's threshold, no linked PR"
    )
    for st in result.stale:
        console.print(
            f"  {escape(st.key)}  {st.days}d since {escape(st.marker_at)}  {escape(st.title)}",
            soft_wrap=True,
        )
    console.print(
        f"[bold]unplaced[/bold] ({len(result.unplaced)}) — open, in no open batch, "
        "feature group or parked"
    )
    for i in result.unplaced:
        console.print(f"  {escape(i.key)}  {escape(i.title)}", soft_wrap=True)
    console.print(
        f"[bold]awaiting live[/bold] ({len(result.awaiting_live)}) — open, fr:awaiting-live: "
        "merged, a post-merge row still awaits its walk; not ranked or proposed"
    )
    for i in result.awaiting_live:
        console.print(f"  {escape(i.key)}  {escape(i.title)}", soft_wrap=True)
    console.print(
        f"[bold]no severity[/bold] ({len(result.no_severity)}) — open, judged, no severity"
    )
    for i in result.no_severity:
        console.print(f"  {escape(i.key)}  {escape(i.title)}", soft_wrap=True)
    console.print(
        f"[bold]duplicate unknown[/bold] ({len(result.duplicate_unknown)}) — `duplicate_of` "
        "names an issue the facts do not hold"
    )
    for key in result.duplicate_unknown:
        console.print(f"  {escape(key)}", soft_wrap=True)
    console.print(
        f"[bold]duplicate chained[/bold] ({len(result.duplicate_chained)}) — `duplicate_of` "
        "names an issue that is itself a duplicate (a chain or a cycle)"
    )
    for key in result.duplicate_chained:
        console.print(f"  {escape(key)}", soft_wrap=True)
    console.print(
        f"[bold]duplicate candidates[/bold] ({len(result.candidates)}) — open issues that "
        "may duplicate each other; judge each group"
    )
    for g in result.candidates:
        console.print(f"  {escape(', '.join(g.keys))}", soft_wrap=True)
        for p in g.pairs:
            console.print(
                f"    {escape(p.a)} ~ {escape(p.b)}: {escape('; '.join(p.reasons))}", soft_wrap=True
            )
    console.print(
        f"[bold]duplicates[/bold] ({len(result.duplicates)}) — judged duplicate_of an "
        "original; the printed command is never run by fr"
    )
    for d in result.duplicates:
        console.print(f"  {escape(d.key)} → {escape(d.original)} ({d.state})", soft_wrap=True)
        console.print(f"    {escape(d.command or d.reason)}", soft_wrap=True)


@triage_app.command("render")
def render_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    open_: bool = typer.Option(False, "--open", help="Open the board in a browser."),
    matrix: Annotated[
        Path | None,
        typer.Option("--matrix", help="Acceptance matrix to track (default: this checkout's)."),
    ] = None,
) -> None:
    """Write triage.html from facts.json and judgements.yaml.

    Also stores a snapshot of what the board shows under `snapshots/` in the state
    directory (the latest 30 are kept; one identical to the latest is not stored); the
    board's "Since last report" is the diff against the last DIFFERENT readable one.
    The acceptance matrix is read only for a single repo whose checkout you are in, or
    from --matrix.
    """
    scope = _scope(repo, org)
    target_dir, facts, judgements = _load_state(scope, dir_override)
    if matrix is not None:
        if not matrix.is_file():
            err_console.print(
                f"[red]error:[/red] no matrix at {escape(str(matrix))}", soft_wrap=True
            )
            raise typer.Exit(code=2)
        matrix_path: Path | None = matrix
    else:
        matrix_path = matrix_for_scope(scope.target if scope.kind == "repo" else None, Path.cwd())
    snap = take_snapshot(facts, judgements, acceptance=acceptance_rows(matrix_path))
    since = diff_snapshots(previous_snapshot(target_dir, snap), snap)
    try:
        resolved = resolve_manifest(target_dir / BOARD_DIR, GENERATED)
    except TriageError as exc:
        err_console.print(f"[red]error:[/red] {escape(str(exc))}", soft_wrap=True)
        raise typer.Exit(code=2) from exc
    for name in resolved.missing:
        err_console.print(
            f"[yellow]warning:[/yellow] manifest entry {escape(name)} has no file in {BOARD_DIR}/",
            soft_wrap=True,
        )
    out = target_dir / "triage.html"
    page = render(facts, judgements, since, resolved, board=(target_dir / "board.html").is_file())
    out.write_text(page, encoding="utf-8")
    # Stored only once the page exists, and only when the board differs from the latest
    # snapshot: a re-render with nothing new must not erase "Since last report".
    if snap != latest_snapshot(target_dir):
        store_snapshot(
            target_dir,
            snap,
            datetime.now(UTC),
            warn=lambda m: err_console.print(f"warning: {escape(m)}", soft_wrap=True),
        )
    console.print(
        f"wrote {out} ({plural(len(facts.issues), 'issue')})", markup=False, soft_wrap=True
    )
    if open_:
        webbrowser.open(out.resolve().as_uri())


# The batch verbs live in `triage_batch_cmd` (spec 2026-09-25-triage-batches
# §3.C names it as fr's second soft point for fr_dispatch). It reuses the
# helpers above and registers its commands on `batch_app`, so it is imported
# LAST: whichever of the two modules loads first, every name the other needs
# already exists.
import fr.commands.triage_architecture_cmd  # noqa: E402, F401
import fr.commands.triage_batch_cmd  # noqa: E402, F401
import fr.commands.triage_history_cmd  # noqa: E402, F401
import fr.commands.triage_kanban_cmd  # noqa: E402, F401
import fr.commands.triage_origins_cmd  # noqa: E402, F401
import fr.commands.triage_state_cmd  # noqa: E402, F401
