"""`fr triage` CLI — backlog triage (spec 2026-09-21-fr-triage-design).

`collect` reads the forge and writes `facts.json` under the scope's state
directory (the workspace's `.fr/triage-state/<scope>/`, or `~/.cache/fr/triage/<scope>/`
outside a clone; `--dir` names one outright). `check` reports the
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
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from fr.artifacts.trigger import is_interactive
from fr.ghclient import GhClient
from fr.hostclient import client_for_backend
from fr.triage.batch import last_dispatch
from fr.triage.check import ClaimSets, classify
from fr.triage.collect import PR_LIMIT, ClientForge, CollectStats, Forge, collect_facts_counted
from fr.triage.errors import TriageError
from fr.triage.fragments import resolve_manifest
from fr.triage.model import (
    Facts,
    Judgements,
    Scope,
    issue_key,
    legacy_state_dir,
    load_facts,
    load_judgements,
    load_scope_facts,
    state_dir,
)
from fr.triage.render import GENERATED, plural, render
from fr.triage.scope_config import load_durable, mirror_state_repo, scope_id, write_durable
from fr.triage.snapshot import (
    acceptance_rows,
    diff_snapshots,
    latest_snapshot,
    matrix_for_scope,
    previous_snapshot,
    store_snapshot,
    take_snapshot,
)
from fr.triage.state_ref import NEW_REPO, Ask, decide_state_repo

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


_COMMAND: ContextVar[tuple[typer.Context, set[Path]] | None] = ContextVar(
    "fr_triage_command", default=None
)
"""The running triage command's context and the state directories it already synced with
the ref (`_sync_with_ref`). Taken from the group callback because `click` is typer's
dependency, not fr's (typer ≥0.26 vendors it), so `click.get_current_context` is not
importable everywhere fr is installed."""


@triage_app.callback()
def _triage_command(ctx: typer.Context) -> None:
    token = _COMMAND.set((ctx, set()))
    # Registered first, so it runs last (the close callbacks unwind LIFO): every push
    # the wrapper registers still sees the command, and nothing outlives it.
    ctx.call_on_close(lambda: _COMMAND.reset(token))


# One option set for --repo/--org/--dir, shared by collect, check, render and batch.
RepoOpt = Annotated[
    str | None, typer.Option("--repo", help="Triage one repo OWNER/REPO, or a group: A/B,C/D.")
]
OrgOpt = Annotated[str | None, typer.Option("--org", help="Triage every repo of OWNER.")]
DirOpt = Annotated[
    Path | None,
    typer.Option(
        "--dir",
        help="State directory, outright (default: <workspace>/.fr/triage-state/<scope>/).",
    ),
]
WorkspaceOpt = Annotated[
    Path | None,
    typer.Option(
        "--workspace",
        help="The clone that holds the state (default: the clone of the working directory); "
        "--dir wins over it.",
    ),
]


def resolve_state_dir(
    scope: Scope, dir_override: Path | None, workspace: Path | None, *, sync: bool = True
) -> Path:
    """`fr.triage.model.state_dir`, with its refusal (a `--workspace` that is no clone) as
    exit 2, and THE state-ref wrapper (cloud-triage R5, §B, p3-r1): every triage command
    reaches its state directory here, so with *sync* (every verb but the explicit `state
    push|fetch`) the scope's ref is fetched first and pushed after a change, for every verb
    alike (`_sync_with_ref`)."""
    try:
        target = state_dir(scope, dir_override, workspace=workspace)
    except TriageError as exc:
        err_console.print(f"[red]error:[/red] {escape(str(exc))}", soft_wrap=True)
        raise typer.Exit(code=2) from exc
    if sync:
        _sync_with_ref(scope, target)
    return target


def drive_lock_dir(scope: Scope, dir_override: Path | None) -> Path:
    """Where the scope's `drive.lock` lives (cloud-triage R4, §B, p3-r3): `--dir` when it
    names the state directory outright, else `~/.cache/fr/triage/<scope>/` for EVERY
    workspace, so it stays the same-host check across clones. Created on use."""
    return dir_override if dir_override is not None else legacy_state_dir(scope)


def state_remote(state_repo: str) -> str:
    """The git remote the state ref of *state_repo* is fetched from and pushed to (R5).
    Tests replace this factory with a local bare repo."""
    return f"https://github.com/{state_repo}.git"


def _sync_with_ref(scope: Scope, target: Path) -> None:
    """Fetch the scope's state ref into *target* now, and push it when the command that
    asked for *target* has changed it (cloud-triage R5, §B "One state across workspaces").

    Acts once per command and state directory, only inside a CLI command (the push runs
    when the command's context closes). The fetch runs only when the scope has a
    `state_repo`; it adopts the ref when the local copy is not ahead and refuses (exit 2)
    when it would overwrite changes not yet pushed. The push runs only if the command
    changed a ref file and the scope then has a `state_repo` (a first collect that decided
    it included), as a compare-and-swap on the ref fetched here; a conflict refuses (exit
    2) with the fetch-and-retry line. A state directory in no git clone (the legacy
    `~/.cache` one, or a `--dir` outside any clone) has nowhere to hold the ref: it is used
    as before, unsynced, and the command says so."""
    from fr.triage.state_ref import fetch_state, local_tree

    command = _COMMAND.get()
    if command is None:
        return
    ctx, synced = command
    if target in synced:
        return
    synced.add(target)
    try:
        state_repo = load_durable(target).state_repo
        clone = state_clone(target)
        if clone is None:
            if state_repo is not None:
                err_console.print(
                    f"warning: {target} is in no git clone, so it is not synced with the state "
                    f"ref in {state_repo}; run from a clone, or pass --workspace",
                    markup=False,
                    soft_wrap=True,
                )
            return
        before = None  # no state repo yet: one decided by this command is a change
        if state_repo is not None:
            fetch_state(target, state_remote(state_repo), scope_id(scope), repo=clone)
            before = local_tree(target, repo=clone)
    except TriageError as exc:
        err_console.print(f"[red]error:[/red] {escape(str(exc))}", soft_wrap=True)
        raise typer.Exit(code=2) from exc
    ctx.call_on_close(lambda: _push_if_changed(scope, target, clone, before))


def _push_if_changed(scope: Scope, target: Path, clone: Path, before: object) -> None:
    """The wrapper's second half: push *target* to the scope's ref when its ref files are
    not what they were when the command started. Exit 2 on a refusal, the push conflict's
    fetch-and-retry line included."""
    from fr.triage.state_ref import local_tree, read_base, ref_name, ref_tree

    try:
        state_repo = load_durable(target).state_repo
        if state_repo is None:
            return
        now = local_tree(target, repo=clone)
        if before is not None and now == before:
            return
        remote, sid = state_remote(state_repo), scope_id(scope)
        base = read_base(target, remote=remote, ref=ref_name(sid))
        if base is not None and ref_tree(clone, base) == now:
            return  # pushed already, mid-command (`push_now`: the drive's every pass)
        sha = push_now(scope, target, clone=clone)
    except TriageError as exc:
        err_console.print(f"[red]error:[/red] {escape(str(exc))}", soft_wrap=True)
        raise typer.Exit(code=2) from exc
    if sha is not None:
        err_console.print(f"pushed {ref_name(sid)} {sha}", markup=False, soft_wrap=True)


def state_clone(target: Path) -> Path | None:
    from fr.triage import gitseam

    probe = target
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return gitseam.toplevel(probe)


def push_now(scope: Scope, target: Path, *, clone: Path | None = None) -> str | None:
    """Push *target* to the scope's state ref NOW, as the compare-and-swap on the ref it was
    last fetched from or pushed to (R5): the drive renews its lease and saves each pass
    through this, not only when the command ends (cloud-triage §B, §D). The new sha; None
    when the scope has no state repo or *target* is in no clone (nowhere to push). Raises
    `TriageError` (`StateRefConflict`, `PrivacyError` included); the caller decides."""
    from fr.triage.state_ref import push_state, read_base, ref_name

    state_repo = load_durable(target).state_repo
    clone = clone or state_clone(target)
    if state_repo is None or clone is None:
        return None
    remote, sid = state_remote(state_repo), scope_id(scope)
    return push_state(
        target,
        remote,
        sid,
        expected_old=read_base(target, remote=remote, ref=ref_name(sid)),
        scope=scope,
        state_repo=state_repo,
        client=make_visibility_client(),
        repo=clone,
    )


def fetch_now(scope: Scope, target: Path, *, state_repo: str | None = None) -> str | None:
    """Fetch the scope's state ref into *target* NOW (R5, R12): adopted when the local copy
    is not ahead, refused (`StateRefConflict`) when it would overwrite changes not yet
    pushed. *state_repo* names the ref's repo for a fresh workspace that has no state yet
    (the cloud driver's brief carries it, R11); it is recorded when the ref brought none.
    The ref's sha; None when there is no state repo, no clone or no ref yet."""
    from fr.triage.state_ref import fetch_state

    known = load_durable(target).state_repo
    repo_name = known or state_repo
    clone = state_clone(target)
    if repo_name is None or clone is None:
        return None
    sha = fetch_state(target, state_remote(repo_name), scope_id(scope), repo=clone)
    if load_durable(target).state_repo is None:
        write_durable(target, load_durable(target).model_copy(update={"state_repo": repo_name}))
        mirror_state_repo(target, repo_name)
    return sha


def make_forge() -> Forge:
    """The forge `collect` reads. Tests replace this factory, never subprocess.

    GitHub's adapter: triage is GitHub-only by its own scope, and with no
    checkout to resolve a backend from, that is the honest default."""
    return ClientForge(client_for_backend("github"))


def make_visibility_client() -> GhClient:
    """The forge client the privacy guard reads a state repo's visibility with (cloud-triage
    R8): GitHub's, as `make_forge`'s. Tests replace this factory."""
    return client_for_backend("github")


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
    workspace: WorkspaceOpt = None,
    pr_limit: int = typer.Option(
        PR_LIMIT, "--pr-limit", min=1, help="PRs listed per repo (the PR -> issue window)."
    ),
) -> None:
    """Read the forge and write facts.json for the scope."""
    scope = _scope(repo, org)
    try:
        facts, out, _ = collect_into(
            scope, resolve_state_dir(scope, dir_override, workspace), pr_limit=pr_limit, settle=True
        )
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
    settle: bool = False,
) -> tuple[Facts, Path, CollectStats]:
    """Collect *scope* through `make_forge()` and write `<target_dir>/facts.json`.

    `collect` and the wave driver's every pass share it (wave-driver §B), so a
    driver pass reads the forge exactly as `fr triage collect` does. With
    *carry* (the driver's passes) a judged issue the previous facts.json for
    this scope holds closed is carried over instead of viewed again (gh#911);
    `fr triage collect` never carries. *lenient* (the driver's passes too) drops an
    unknown top-level `.fr/triage.yaml` key instead of refusing it (gh#998); `fr
    triage collect` stays strict. *settle* (an explicit `fr triage collect` only, never
    the drive or watch loop, p3-r7) decides an undecided state repo; without it an
    undecided scope warns once and keeps its state local. Returns the stats of
    single-issue reads. Raises `TriageError` on a refusal; writes nothing then.
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
    if settle:
        _settle_state_repo(target_dir, facts)
    elif load_durable(target_dir).state_repo is None:
        err_console.print(f"warning: {NO_STATE_REPO}", markup=False, soft_wrap=True)
    return facts, out, stats


NO_STATE_REPO = (
    "no state repo for this scope: its state stays in this workspace and is never pushed. "
    "Run `fr triage collect` at a terminal to choose one (cloud-triage R7)."
)


def state_repo_prompt() -> Ask | None:
    """The operator's prompt for the state-repo choice; None when no operator is at a
    terminal (`fr.artifacts.trigger.is_interactive`). Tests replace this factory."""
    if not is_interactive():
        return None

    def ask(question: str, choices: list[str], warning: str | None) -> str | None:
        if warning:
            err_console.print(f"warning: {warning}", markup=False, soft_wrap=True)
        for n, choice in enumerate(choices, 1):
            console.print(f"  {n}. {choice}", markup=False, soft_wrap=True)
        picked: str = typer.prompt(f"{question} [1-{len(choices)}]", default="", show_default=False)
        if not picked.strip():
            return None
        if not picked.strip().isdigit() or not 1 <= int(picked) <= len(choices):
            return picked.strip()  # refused by the decision, naming the choices
        choice = choices[int(picked) - 1]
        if choice == NEW_REPO:
            name: str = typer.prompt("OWNER/REPO of the new repo (create it yourself, private)")
            return name.strip() or None
        return choice

    return ask


def _settle_state_repo(target_dir: Path, facts: Facts) -> None:
    """Decide where the scope's state ref lives on its first collect (R6, R7, §B), from the
    scope's repos and the visibility collect just recorded, and write it to
    `scope-durable.yaml` and the `scope.yaml` mirror. Decided once: an existing
    `state_repo` is never asked again. Undecided (non-interactive), it warns, once per
    collect, and the state stays local."""
    durable = load_durable(target_dir)
    if durable.state_repo:
        return
    chosen = decide_state_repo(facts.repos, facts.visibility, state_repo_prompt())
    if chosen is None:
        err_console.print(f"warning: {NO_STATE_REPO}", markup=False, soft_wrap=True)
        return
    write_durable(target_dir, durable.model_copy(update={"state_repo": chosen}))
    mirror_state_repo(target_dir, chosen)


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


def _load_state(
    scope: Scope, dir_override: Path | None, workspace: Path | None
) -> tuple[Path, Facts, Judgements]:
    """The scope's facts and judgements, through the `fr.triage.model` loaders.

    No facts.json is an error naming `collect`, and so are facts collected for
    another scope (a `--dir` can point anywhere, gh#886); no judgements.yaml is
    allowed — everything is then unranked.
    """
    target_dir = resolve_state_dir(scope, dir_override, workspace)
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
    workspace: WorkspaceOpt = None,
    as_json: bool = typer.Option(False, "--json", help="Emit check sets as JSON."),
) -> None:
    """Report unranked issues and PRs, settled, orphaned, unreachable, stale, unplaced,
    duplicate candidates, duplicates, awaiting live and more.

    Always exits 0.
    """
    scope = _scope(repo, org)
    _, facts, judgements = _load_state(scope, dir_override, workspace)
    try:
        me: str | None = scope_id(scope)
    except TriageError as exc:  # a broken host id: the claim sets are left out, never fatal
        err_console.print(f"[yellow]warning:[/yellow] {escape(str(exc))}", soft_wrap=True)
        me = None
    result = classify(facts, judgements, me=me, now=datetime.now(UTC))
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
    print_claim_sets(result.claims)


def print_claim_sets(sets: ClaimSets) -> None:
    """R7's three sets, shared by `check` and `claim list`."""
    console.print(
        f"[bold]held elsewhere[/bold] ({len(sets.held_elsewhere)}) — open, another scope's "
        "un-released claim holds it; this scope keeps hands off"
    )
    for h in sets.held_elsewhere:
        console.print(
            f"  {escape(h.key)}  {escape(h.claim.signer)}  batch {escape(h.claim.batch)}  "
            f"expires {escape(h.claim.expires)}  {escape(h.title)}",
            soft_wrap=True,
        )
    console.print(
        f"[bold]expired claims[/bold] ({len(sets.expired_claims)}) — un-released, past its "
        "expiry; still holds until `fr triage claim take` or `release`"
    )
    for e in sets.expired_claims:
        console.print(
            f"  {escape(e.key)}  {escape(e.claim.signer)}  batch {escape(e.claim.batch)}  "
            f"expired {escape(e.claim.expires)}",
            soft_wrap=True,
        )
    console.print(
        f"[bold]claims owed[/bold] ({len(sets.claims_owed)}) — this scope owes a claim the "
        "facts show unwritten; `fr triage claim sync --yes` writes it"
    )
    for o in sets.claims_owed:
        console.print(f"  {escape(o.key)}  batch {escape(o.batch)}", soft_wrap=True)


@triage_app.command("render")
def render_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
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
    target_dir, facts, judgements = _load_state(scope, dir_override, workspace)
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
    from fr.commands.triage_kanban_cmd import read_sessions  # it imports this module

    # A blocked session's own note, from a runner that gives one (cloud-triage R15); a
    # runner that cannot say leaves Needs you now as it was.
    noted = read_sessions(judgements, facts, target=target_dir).session_notes
    page = render(
        facts, judgements, since, resolved, board=(target_dir / "board.html").is_file(),
        session_notes=noted,
    )  # fmt: skip
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
import fr.commands.triage_claim_cmd  # noqa: E402, F401
import fr.commands.triage_drive_cmd  # noqa: E402, F401
import fr.commands.triage_history_cmd  # noqa: E402, F401
import fr.commands.triage_kanban_cmd  # noqa: E402, F401
import fr.commands.triage_origins_cmd  # noqa: E402, F401
import fr.commands.triage_state_cmd  # noqa: E402, F401
