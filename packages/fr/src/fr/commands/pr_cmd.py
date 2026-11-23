"""`fr pr create` — every PR creation fr's skills make (spec 2026-11-04-repo-feature-settings
R11, R12, §3.C).

Always a draft: marking a PR ready and merging it are the operator's, and there is
no flag for anything else. Under `git.pr: ask` it waits for a verified operator
approval exactly like `fr push`. The PR's url is recorded on the run cursor
(`RunState.pr`), which is what `deliver` accepts under `pr: ask`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.console import Console
from rich.markup import escape

from fr._hosts import origin_slug
from fr.commands.common import resolve_repo_root
from fr.hostclient import FORGE_ERRORS, client_for
from fr.settle import poll as _settle_poll

if TYPE_CHECKING:
    from fr.settle.model import Modes

_SETTLE_DEFAULT_WAIT = _settle_poll.DEFAULT_WAIT
_SETTLE_CEILING = _settle_poll.WAIT_CEILING

pr_app = typer.Typer(help="Pull requests fr opens (always drafts).", no_args_is_help=True)
err_console = Console(stderr=True)
console = Console()


def _default_branch(repo_root: Path) -> str:
    """The product repo's default branch, read from its remote (review pr1431-r5). Never
    the settings source ref: under quiet that is `origin/fr`, under stealth the tracking
    repo's branch, and neither is a branch a PR merges into."""
    from fr.git import GitRefusal, remote_default_ref, remote_name
    from fr.git_policy.push import PushRefusedError

    ref = remote_default_ref(repo_root)
    remote = remote_name(repo_root)
    if ref is None or isinstance(ref, GitRefusal) or not isinstance(remote, str):
        why = f" ({ref.reason})" if isinstance(ref, GitRefusal) else ""
        raise PushRefusedError(
            f"cannot tell the default branch to open the PR against{why}; pass --base"
        )
    return ref.removeprefix(f"{remote}/")


def _refuse_fr_naming_under_stealth(repo_root: Path, title: str, body: str) -> None:
    """R24 "what reaches the target" (review pr1431-n5): under stealth the PR's title
    and body name nothing of fr. fr's markers are refused under `pr_body: minimal`; this
    adds the title and the prose (fr's commit scopes, its commands, the placement)."""
    from fr.artifacts.paths import STEALTH, outside_repo
    from fr.git_policy.push import PushRefusedError
    from fr.placement.stealth import fr_naming

    if outside_repo(repo_root) != STEALTH:
        return
    for what, text in (("title", title), ("body", body)):
        found = fr_naming(text)
        if found:
            raise PushRefusedError(
                f"under placement stealth the PR reaching the target names nothing of fr "
                f"(R24), and its {what} does: {'; '.join(found[:3])}. Write it as a plain "
                "summary of the code change"
            )


def _refuse_recorded_pr(repo_root: Path, url: str | None) -> None:
    """A run records one PR (review p4-r4): `fr pr create` never replaces it. OPEN
    means it exists already; MERGED or CLOSED means this branch is spent."""
    from fr.git_policy.push import PushRefusedError

    if url is None:
        return
    try:
        status = client_for(repo_root).pr_status_by_url(url)
    except FORGE_ERRORS as e:
        raise PushRefusedError(
            f"this run already records the PR {url}, and fr cannot read its state ({e}); "
            "fr pr create never replaces a recorded PR"
        ) from e
    pr_state = (status or {}).get("state")
    if pr_state == "OPEN":
        raise PushRefusedError(f"this run's PR already exists and is open: {url}")
    if pr_state in ("MERGED", "CLOSED"):
        raise PushRefusedError(
            f"this run's PR {url} is {pr_state}: start a fresh branch (and run) for new work"
        )
    raise PushRefusedError(
        f"this run already records the PR {url} (state {pr_state or 'unknown'}); "
        "fr pr create never replaces a recorded PR"
    )


@pr_app.command("create")
def create_cmd(
    title: str = typer.Option(..., "--title", help="The PR title."),
    body_file: Path = typer.Option(..., "--body-file", help="A file holding the PR body."),
    base: str | None = typer.Option(
        None, "--base", help="The branch to merge into (default: the repo's default branch)."
    ),
) -> None:
    """Open this run's PR as a draft and record it on the run cursor."""
    from fr.commands.push_cmd import approval_journal, branch_context, branch_runs
    from fr.git_policy.ask import AskRefusedError, consume, require_approval
    from fr.git_policy.push import PushRefusedError
    from fr.records_commit import commit_records
    from fr.run.model import run_path, save_run_state
    from fr.settings import SettingsError, load_settings

    repo_root = resolve_repo_root()
    try:
        settings = load_settings(repo_root).settings
        branch, head, git_dir = branch_context(repo_root)
        runs = branch_runs(repo_root)
        if len(runs) > 1:
            raise PushRefusedError(
                f"branch {branch!r} has {len(runs)} runs; fr pr create records the PR on the "
                "branch's one run"
            )
        # No run is an fr-debugging session (p4-r5): nothing to record the PR on.
        state = runs[0] if runs else None
        _refuse_recorded_pr(repo_root, state.pr if state is not None else None)
        try:
            body = body_file.read_text()
        except (OSError, UnicodeDecodeError) as e:
            raise PushRefusedError(f"cannot read --body-file {body_file}: {e}") from e
        if settings.forge.pr_body == "minimal":
            from fr.record.pr_body import fr_markers

            # R10, and R24 "what reaches the target": under a minimal body (which
            # stealth always sets) the PR carries a plain summary, no fr marker.
            markers = fr_markers(body)
            if markers:
                raise PushRefusedError(
                    "under forge.pr_body: minimal (stealth sets it) the PR body is a plain "
                    f"summary, and {body_file} carries fr markers ({'; '.join(markers)}); "
                    "pass a plain summary instead"
                )
        _refuse_fr_naming_under_stealth(repo_root, title, body)
        if settings.git.pr == "ask":
            require_approval(
                repo_root,
                kind="pr",
                branch=branch,
                head=head,
                journal=approval_journal(repo_root),
                git_dir=git_dir,
                still_current=True,
            )
        repo = origin_slug(repo_root)
        if repo is None:
            raise PushRefusedError("cannot read the forge repository from the origin remote")
        recorded_target = state.base_branch if state is not None else None
        if state is not None and recorded_target is None and base is not None:
            if base != _default_branch(repo_root):
                raise PushRefusedError(
                    "record a non-default merge target with `fr run target <run> --base <branch>` "
                    "before lens review; --base at PR creation cannot change the reviewed diff"
                )
        if recorded_target is not None and base is not None and base != recorded_target:
            raise PushRefusedError(
                f"--base {base!r} differs from the recorded merge target {recorded_target!r}; "
                "the PR must use the target reviewed by this run"
            )
        target = base or recorded_target or _default_branch(repo_root)
        try:
            made = client_for(repo_root).create_pr(
                repo, head=branch, base=target, title=title, body=body, draft=True
            )
        except FORGE_ERRORS as e:
            raise PushRefusedError(f"the forge refused to open the PR: {e}") from e
        if settings.git.pr == "ask":
            consume(git_dir, "pr", branch)
    except (SettingsError, PushRefusedError, AskRefusedError) as e:
        err_console.print(escape(f"fr pr create: {e}"), soft_wrap=True)
        raise typer.Exit(2) from e
    url = str(made["url"])
    if state is None:
        console.print(f"opened draft PR {url} (this branch has no run to record it on)")
        return
    save_run_state(repo_root, state.model_copy(update={"pr": url}))
    commit_records(
        repo_root, [run_path(repo_root, state.run)], f"chore(fr): run {state.run} — pr create"
    )
    console.print(f"opened draft PR {url} (recorded on run {state.run})", soft_wrap=True)


def _branch_modes(repo_root: Path, runs: list[Any]) -> tuple[Modes, list[str]]:
    """The settle modes of this branch's PR and the warnings to print first: the setting,
    then the run's spec line, else the branch's one debug journal's decision (R6). Why no
    journal was read is said, never dropped (l-errors-r2); more than one refuses."""
    from fr.commands.push_cmd import branch_debug_journals
    from fr.journal.model import journal_path
    from fr.requirements import run_spec
    from fr.settle.model import SettleRefused
    from fr.settle.modes import effective_modes, journal_settle_ids

    spec = next((s for s in map(run_spec, runs) if s), None)
    found = branch_debug_journals(repo_root)
    slugs = found if isinstance(found, list) else []
    warnings: list[str] = []
    journal = None
    if spec is not None:
        for slug in slugs:
            for eid in journal_settle_ids(journal_path(repo_root, "debug", slug)):
                warnings.append(
                    f"settle: debug journal {slug}'s decision {eid} is not applied: the run's "
                    "spec decides; put the override in its `## Verification`"
                )
    elif isinstance(found, str):
        warnings.append(f"settle: {found}; the repo setting applies")
    elif not slugs:
        warnings.append(
            "settle: this branch has no spec-driven run and added no debug journal; the "
            "repo setting applies"
        )
    elif len(slugs) > 1:
        raise SettleRefused(
            f"this branch added {len(slugs)} debug journals ({', '.join(slugs)}); fr does not "
            "guess which one holds this PR's settle override: keep one"
        )
    else:
        journal = journal_path(repo_root, "debug", slugs[0])
    return effective_modes(repo_root, spec=spec, debug_journal=journal), warnings


@pr_app.command("settle")
def settle_cmd(
    wait: float = typer.Option(
        _SETTLE_DEFAULT_WAIT,
        "--wait",
        help=f"Seconds to poll while a concern is unknown or pending (max {_SETTLE_CEILING}).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Print the verdict as JSON."),
) -> None:
    """Wait until this branch's PR merges cleanly and its CI has finished."""
    import time

    from fr.commands.push_cmd import branch_context, branch_runs
    from fr.git_policy.push import PushRefusedError
    from fr.settings import SettingsError
    from fr.settle import poll
    from fr.settle.evaluate import evaluate, managed_verdict
    from fr.settle.managed import driver_managed
    from fr.settle.model import EXIT_PENDING, EXIT_REFUSED, SettlePending, SettleRefused, Verdict
    from fr.settle.read import forge_repo, read_verdict

    def _out(verdict: Verdict) -> None:
        if as_json:
            typer.echo(verdict.model_dump_json())
        else:
            for line in verdict.lines:
                console.print(escape(line), soft_wrap=True, highlight=False)
        raise typer.Exit(verdict.exit_code)

    def _refuse(message: str, code: int = EXIT_REFUSED) -> typer.Exit:
        if as_json:  # l-errors-r6: a --json caller reads every outcome from stdout
            typer.echo(json.dumps({"exit_code": code, "error": message}))
        err_console.print(escape(f"fr pr settle: {message}"), soft_wrap=True)
        return typer.Exit(code)

    repo_root = resolve_repo_root()
    try:
        poll.check_wait(wait)
        branch, _head, _git_dir = branch_context(repo_root)
        if driver_managed(branch):
            _out(managed_verdict(branch))
        runs = branch_runs(repo_root)
        modes, warnings = _branch_modes(repo_root, runs)
        for line in warnings:
            err_console.print(escape(line), soft_wrap=True, highlight=False)
        if modes.both_off:
            _out(evaluate({}, [], None, modes, ci_none=False, head_committed_at=0, now=0))
        recorded = runs[0].pr if len(runs) == 1 else None
        client = client_for(repo_root)
        repo = forge_repo(origin_slug(repo_root), client)
        try:
            verdict = read_verdict(
                repo_root, client, repo, branch, recorded, modes,
                wait=wait, clock=time.time, sleep=time.sleep,
            )  # fmt: skip
        except SettlePending as e:
            raise _refuse(str(e), EXIT_PENDING) from e
    except (SettleRefused, SettingsError, PushRefusedError) as e:
        raise _refuse(str(e)) from e
    _out(verdict)
