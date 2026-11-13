"""`fr pr create` — every PR creation fr's skills make (spec 2026-11-04-repo-feature-settings
R11, R12, §3.C).

Always a draft: marking a PR ready and merging it are the operator's, and there is
no flag for anything else. Under `git.pr: ask` it waits for a verified operator
approval exactly like `fr push`. The PR's url is recorded on the run cursor
(`RunState.pr`), which is what `deliver` accepts under `pr: ask`.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

from fr._hosts import origin_slug
from fr.commands.common import resolve_repo_root
from fr.hostclient import FORGE_ERRORS, client_for

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
        target = base or _default_branch(repo_root)
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
