"""`fr gate` — the post-merge gate ledger's explicit route (spec 2026-10-14-exit-gates R14,
§D).

A post-merge gate (`tester`, `devops`) passes in one of two ways, and both do the same
thing: comment what passed it on the PR, then swap its `gate:<g>` label for
`gate:<g>-passed`. The driver does it when every row the gate gates reads `walked` on
the default branch; `fr gate pass` is the route for a gate with no row (a run-level
`gate: devops`) or a pass the operator records by hand. The merged PR's labels are the
ledger, so a pass needs no commit: this group touches no registered artifact and is in
`fr.artifacts.trigger.READ_ONLY_COMMANDS`. Dry-run without `--yes`.

`--gate devops` also folds the run's recorded op evidence (spec 2026-10-22-fr-ops R14):
the run is `--run <id>`, else the one whose `branch` is the PR's head ref. It refuses
while any plan op, or Test Plan step whose effective gate is devops, is not closed by
what this checkout recorded. It never runs a probe.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer

from fr.gates import GATES, POST_MERGE_GATES
from fr.ghclient import UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS, client_for_url
from fr.labels import gate_label, held_gates
from fr.verification.labels import gate_pass_comment, pass_gate

if TYPE_CHECKING:
    from fr.run.model import RunState

gate_app = typer.Typer(
    help="Post-merge gates: record that a gate passed on its PR (the gate ledger).",
    no_args_is_help=True,
)

RELEASE_WORKFLOW = "release.yml"
DEFAULT_HOST = "github.com"
_FORGE_FAILURES: tuple[type[Exception], ...] = (*FORGE_ERRORS, UnsupportedForgeOperation)


NO_RUN_EVIDENCE = "--no-run-evidence"


def _cursors(root: Path) -> list[Path]:
    """Every run cursor this checkout holds, live then archived (R14: archived runs count)."""
    from fr.record.model import RUNS_REL
    from fr.run.model import IMPLEMENTED_RUNS_REL

    dirs = (root / RUNS_REL, root / IMPLEMENTED_RUNS_REL)
    return [p for d in dirs if d.is_dir() for p in sorted(d.glob("*.yaml"))]


def _run_for(root: Path, run: str | None, head_ref: str) -> RunState | None:
    """The run whose devops evidence the pass folds: `--run` (live or archived), else the
    one run whose `branch` is the PR's head ref; `None` when none is. Several matches, or
    a cursor that cannot be read, are refusals: an unreadable cursor may be the run."""
    from fr.run.model import RunStateError, parse_run_state

    if run is not None:
        for path in _cursors(root):
            if path.stem == run:
                try:
                    return parse_run_state(path.read_text())
                except (RunStateError, OSError) as exc:
                    _refuse(f"cannot read run {run!r} ({path.relative_to(root)}): {exc}")
        _refuse(f"no run {run!r} in this checkout (live or archived)")
    found = []
    for path in _cursors(root):
        try:
            state = parse_run_state(path.read_text())
        except (RunStateError, OSError) as exc:
            _refuse(
                f"cannot read run cursor {path.relative_to(root)}: {exc}; it may be this PR's "
                "run, so no run is assumed: fix it, or pass --run <id>"
            )
        if head_ref and state.branch == head_ref:
            found.append(state)
    if len(found) > 1:
        _refuse(f"runs {', '.join(s.run for s in found)} all name branch {head_ref!r}: pass --run")
    return found[0] if found else None


def _devops_evidence(run: str | None, head_ref: str, *, no_run_evidence: bool) -> bool:
    """R14: refuse (exit 2, listing them) while recorded evidence leaves anything open, and
    whenever no run resolves unless `--no-run-evidence` says the gate is row-only. Returns
    whether the escape was used, for the pass comment."""
    from fr.acceptance.model import AcceptanceError
    from fr.ops.holds import devops_blockers
    from fr.ops.load import OpsLoadError
    from fr.verification.spec_section import SectionError

    if no_run_evidence and run is not None:
        _refuse(f"--run and {NO_RUN_EVIDENCE} contradict each other: give one")
    root = _repo_root()
    if root is None:
        _refuse(
            "not inside a checkout, so no run's op evidence can be folded: run this from the "
            f"repo with --run <id> (or {NO_RUN_EVIDENCE} for a row-only devops gate)"
        )
    state = _run_for(root, run, head_ref)
    if state is None:
        if no_run_evidence:
            typer.echo(f"{NO_RUN_EVIDENCE}: no run's op evidence folded (a row-only devops gate)")
            return True
        _refuse(
            f"no run here names the PR's head ref {head_ref or '(none)'!r}: pass --run <id> "
            f"(or {NO_RUN_EVIDENCE} for a row-only devops gate on a repo with no run)"
        )
    if no_run_evidence:
        _refuse(
            f"run {state.run} names this branch: its evidence is folded, drop {NO_RUN_EVIDENCE}"
        )
    try:
        blockers = devops_blockers(root, state)
    except OpsLoadError as exc:
        _refuse(f"run {state.run}: the plan's ops cannot be read: {exc}")
    except (SectionError, AcceptanceError, OSError) as exc:
        _refuse(f"run {state.run}: its exit cannot be read: {exc}")
    if blockers:
        lines = "\n".join(f"  {b}" for b in blockers)
        _refuse(
            f"run {state.run}'s devops gate is still held by its recorded evidence "
            f"(nothing was probed):\n{lines}\nbring them to DONE/N/A through the "
            f"DevOps stage (`fr ops gate --run {state.run}`), then pass again"
        )
    typer.echo(f"run {state.run}: every op and devops step is recorded closed")
    return False


def _refuse(message: str) -> NoReturn:
    typer.echo(f"fr gate pass: {message}", err=True)
    raise typer.Exit(code=2)


def _repo_root() -> Path | None:
    """The checkout's root, or `None` outside one (a refusal for a devops pass)."""
    from fr.git import repo_root

    try:
        return repo_root(Path.cwd())
    except Exception:  # noqa: BLE001 — any git failure means "no checkout here"
        return None


def release_command(repo: str) -> str:
    """The dispatch that cuts the final once the last gate passed (R20)."""
    return f"gh workflow run {RELEASE_WORKFLOW} --repo {repo}"


def resolve_target(repo: str | None, host: str | None, root: Path) -> tuple[str, str]:
    """`(OWNER/REPO, host)` of the PR (p4-r6), read from evidence before falling back to
    github.com, as the triage driver's `_host_of` does: *host* when named; else the
    checkout's origin host when its origin is *repo* (or *repo* is not named); else
    `github.com`. A repo that cannot be named at all is refused."""
    from fr import _hosts

    origin = _hosts.origin_slug(root)
    repo = repo or origin
    if repo is None:
        _refuse("no `origin` remote here to name the repo: pass --repo OWNER/REPO")
    assert repo is not None
    if host:
        return repo, host
    if origin is not None and origin.lower() == repo.lower():
        return repo, _hosts.origin_hostname(root) or DEFAULT_HOST
    return repo, DEFAULT_HOST


@gate_app.command("pass")
def pass_command(
    pr: Annotated[int, typer.Option("--pr", help="The merged PR whose gate passed.")],
    gate: Annotated[str, typer.Option("--gate", help="The post-merge gate: tester | devops.")],
    notes: Annotated[str, typer.Option("--notes", help="What passed it (the PR comment).")],
    repo: Annotated[
        str | None,
        typer.Option("--repo", help="OWNER/REPO; default: this checkout's origin."),
    ] = None,
    host: Annotated[
        str | None,
        typer.Option("--host", help="The forge host; default: the origin's, else github.com."),
    ] = None,
    run: Annotated[
        str | None,
        typer.Option(
            "--run",
            help="devops: the run whose recorded op evidence must be closed "
            "(default: the run whose branch is the PR's head ref).",
        ),
    ] = None,
    no_run_evidence: Annotated[
        bool,
        typer.Option(
            NO_RUN_EVIDENCE,
            help="devops: pass a row-only gate on a repo with no run (recorded in the comment).",
        ),
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Write to the forge.")] = False,
) -> None:
    """Comment why PR <n>'s gate <g> passed, then swap gate:<g> for gate:<g>-passed (R14)."""
    if gate not in GATES:
        _refuse(f"unknown gate {gate!r}: one of {', '.join(sorted(GATES))}")
    if gate not in POST_MERGE_GATES:
        _refuse(
            f"{gate!r} is not a post-merge gate: only {', '.join(sorted(POST_MERGE_GATES))} "
            "hold a merge, so only they pass"
        )
    repo, forge_host = resolve_target(repo, host, Path.cwd())
    held, passed = gate_label(gate).name, gate_label(gate, passed=True).name
    try:
        client = client_for_url(f"https://{forge_host}/{repo}")
        view = client.pr_view(repo, pr)
    except _FORGE_FAILURES as exc:
        _refuse(f"cannot read PR #{pr} of {repo} on {forge_host}: {exc}")
        return
    state = str(view.get("state") or "UNKNOWN")
    if state != "MERGED":
        _refuse(f"PR #{pr} of {repo} is {state}, not merged: a post-merge gate passes on a merge")
    labels = {str(n) for n in view.get("labels") or []}
    if held not in labels:
        have = ", ".join(sorted(n for n in labels if n.startswith("gate:"))) or "no gate label"
        _refuse(f"PR #{pr} of {repo} does not carry {held} ({have}): nothing to pass")
    if gate == "devops":
        head_ref = str(view.get("head_ref") or "")
        if _devops_evidence(run, head_ref, no_run_evidence=no_run_evidence):
            notes = f"{notes} (passed with {NO_RUN_EVIDENCE}: no run's op evidence was folded)"
    left = sorted(held_gates((labels - {held}) | {passed}))
    typer.echo(f"PR #{pr} ({repo}): {held} -> {passed}")
    typer.echo(f"comment: {gate_pass_comment(gate, notes)}")
    if yes:
        try:
            pass_gate(client, repo, pr, gate, why=notes)
        except _FORGE_FAILURES as exc:
            typer.echo(f"fr gate pass: the forge refused: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"passed: PR #{pr} now carries {passed}")
    if left:  # p4-r9: no final while a post-merge gate still holds this PR
        typer.echo(f"{', '.join(f'gate:{g}' for g in left)} still holds PR #{pr}: no release yet")
    else:
        typer.echo(f"release: this was the PR's last gate; cut the final: {release_command(repo)}")
    if not yes:
        typer.echo("nothing done; re-run with --yes to act")
