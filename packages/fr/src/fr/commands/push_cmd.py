"""`fr push` — every push of a run's feature branch (spec 2026-11-04-repo-feature-settings
R11-R14, §3.C).

In order: resolve the run from the branch; under `git.push: ask`, require a verified
operator decision journalled after the request; check the unpushed subjects against
the templates (R14); squash under `git.history: squash-unpushed` (R13); push, as a
fast-forward, never forced. The subjects are checked BEFORE the squash so a bad one
refuses before anything is rewritten; the squash then only composes subjects fr
renders itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.markup import escape

from fr.commands.common import resolve_repo_root

if TYPE_CHECKING:
    from fr.git_policy.ask import ApprovalJournal
    from fr.run.model import RunState

err_console = Console(stderr=True)
console = Console()


def _fail(message: str) -> typer.Exit:
    err_console.print(escape(message), soft_wrap=True)
    return typer.Exit(2)


def branch_context(repo_root: Path) -> tuple[str, str, Path]:
    """(branch, head sha, git dir) of the checkout, or a refusal."""
    from fr.git_policy.push import PushRefusedError, _git

    branch = _git(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD").strip()
    head = _git(repo_root, "rev-parse", "HEAD").strip()
    git_dir = Path(_git(repo_root, "rev-parse", "--absolute-git-dir").strip())
    if not branch:
        raise PushRefusedError("HEAD is detached: fr pushes a run's feature branch")
    return branch, head, git_dir


def remote_of(repo_root: Path) -> str:
    from fr.git import GitRefusal, remote_name
    from fr.git_policy.push import PushRefusedError

    remote = remote_name(repo_root)
    if isinstance(remote, GitRefusal):
        raise PushRefusedError(remote.reason)
    if remote is None:
        raise PushRefusedError("this repository has no remote to push to")
    return remote


def approval_journal(repo_root: Path) -> ApprovalJournal | str:
    """Where `ask` records and reads the operator's approval: the run's own journal
    (review p4-r5). The spec journal of the branch's spec-driven run; else, for an
    fr-debugging session (no run, no spec), the one debug journal the branch added
    since it left the default branch. A string says why there is none."""
    from fr.archive import spec_slug_of
    from fr.git import GitRefusal, remote_default_ref
    from fr.git_policy.ask import ApprovalJournal
    from fr.git_policy.push import run_git
    from fr.journal.model import JOURNALS_REL, SCOPE_DIRS
    from fr.requirements import run_spec

    for state in branch_runs(repo_root):
        spec = run_spec(state)
        if spec:
            return ApprovalJournal("spec", spec_slug_of(Path(spec)))
    default = remote_default_ref(repo_root)
    if default is None or isinstance(default, GitRefusal):
        why = default.reason if isinstance(default, GitRefusal) else "no default ref"
        return f"this branch has no spec-driven run, and fr cannot find its base ({why})"
    base = run_git(repo_root, ["merge-base", "HEAD", default])
    debug_dir = (JOURNALS_REL / SCOPE_DIRS["debug"]).as_posix()
    added = run_git(
        repo_root,
        ["diff", "--name-only", "--no-renames", "--diff-filter=A", base.stdout.strip(), "HEAD",
         "--", f"{debug_dir}/"],
    )  # fmt: skip
    if base.returncode != 0 or added.returncode != 0:
        return "this branch has no spec-driven run, and fr cannot read its debug journals"
    slugs = sorted(Path(p).stem for p in added.stdout.splitlines() if p.endswith(".md"))
    if len(slugs) == 1:
        return ApprovalJournal("debug", slugs[0])
    if not slugs:
        return (
            "this branch has no spec-driven run and added no debug journal; record the "
            "investigation with `fr journal add --scope debug` first"
        )
    return (
        f"this branch has no spec-driven run and added {len(slugs)} debug journals "
        f"({', '.join(slugs)}); fr does not guess which one is this session's"
    )


def branch_runs(repo_root: Path) -> list[RunState]:
    """Every readable run whose `branch` is the one checked out at *repo_root*."""
    from fr.commands.run_cmd import _runs_on_this_branch

    return _runs_on_this_branch(repo_root)


def push_still_current(repo_root: Path, git_dir: Path, branch: str, head: str) -> bool:
    """Does the stored push request still cover HEAD? Only journal commits may follow it."""
    from fr.git_policy.ask import JOURNALS_PREFIX, stored
    from fr.git_policy.push import run_git

    request = stored(git_dir, "push", branch)
    if request is None:
        return False
    if request.head == head:
        return True
    if run_git(repo_root, ["merge-base", "--is-ancestor", request.head, head]).returncode != 0:
        return False
    # `--no-renames`: a rename-following diff names only a moved file's destination,
    # so code moved into the journals tree would keep a stale approval (p4-r6).
    diff = run_git(repo_root, ["diff", "--name-only", "--no-renames", request.head, head])
    if diff.returncode != 0:  # a diff fr cannot read keeps nothing approved
        return False
    return all(p.startswith(JOURNALS_PREFIX) for p in diff.stdout.splitlines())


def refuse_closed_pr(repo_root: Path) -> None:
    """The merged-PR push guard, inside `fr push` (#320): a push to a branch whose PR
    (the one `fr pr create` recorded) is MERGED or CLOSED orphans the commit from the
    default branch. The shell hook matches `git push` only, so `fr push` asks itself.
    Fails open, like the hook, when the PR cannot be read."""
    from fr.git_policy.push import PushRefusedError
    from fr.hostclient import FORGE_ERRORS, client_for

    for state in branch_runs(repo_root):
        if state.pr is None:
            continue
        try:
            status = client_for(repo_root).pr_status_by_url(state.pr)
        except FORGE_ERRORS:
            continue
        pr_state = (status or {}).get("state")
        if pr_state in ("MERGED", "CLOSED"):
            raise PushRefusedError(
                f"this branch's PR {state.pr} is {pr_state}: pushing here orphans the commit "
                "from the default branch (#320). Cherry-pick it onto a fresh branch and PR"
            )


def _code_pending(rng: object) -> bool:
    """The feature branch has something to push: unpushed commits, or no remote branch."""
    return bool(getattr(rng, "commits", ())) or getattr(rng, "remote_sha", None) is None


def _push_placement(repo_root: Path, remote: str, branch: str, *, code: bool) -> list[str]:
    """The push itself: `repo` pushes the branch; quiet pushes the branch and `fr`
    together, atomically, or `fr` alone (R23). The refs pushed."""
    from fr.artifacts.paths import QUIET, space_for
    from fr.git_policy.push import atomic_push, push

    space = space_for(repo_root)
    if space.placement != QUIET:
        push(repo_root, remote, branch)
        return [branch]
    return atomic_push(repo_root, space.root, remote, branch, code=code)


def _refuse_fr_paths_under_stealth(repo_root: Path, commits: list[str]) -> None:
    """R24 "what reaches the target": under stealth only the code is pushed, so a commit
    carrying a path only fr writes (an artifact, `.claude/agents/fr-*.md`, `.fr/`, the
    plan validator...) refuses the push, naming it (review p4-r3)."""
    from fr.artifacts.paths import STEALTH, outside_repo
    from fr.git_policy.push import PushRefusedError
    from fr.placement.stealth import fr_paths_in

    if outside_repo(repo_root) != STEALTH:
        return
    found = fr_paths_in(repo_root, commits)
    if found:
        raise PushRefusedError(
            f"under placement stealth no fr file reaches the target (R24), and the commits to "
            f"push carry {', '.join(found[:5])}{' ...' if len(found) > 5 else ''}. Remove "
            "them from those commits (fr keeps its state in the tracking repo) and push again"
        )


def push_cmd() -> None:
    """Push this run's feature branch, under the repo's git policy (`git.*`)."""
    from fr.artifacts.commit import on_default_branch
    from fr.git_policy.ask import AskRefusedError, consume, require_approval
    from fr.git_policy.push import PushRefusedError, check_subjects, squash, unpushed
    from fr.git_policy.templates import run_issue
    from fr.settings import SettingsError, load_settings

    repo_root = resolve_repo_root()
    try:
        settings = load_settings(repo_root).settings
        branch, head, git_dir = branch_context(repo_root)
        if on_default_branch(repo_root) is not None:
            raise PushRefusedError(f"{branch!r} is the default branch: fr pushes a feature branch")
        remote = remote_of(repo_root)
        refuse_closed_pr(repo_root)
        issue = run_issue(repo_root)
        if settings.git.push == "ask":
            require_approval(
                repo_root,
                kind="push",
                branch=branch,
                head=head,
                journal=approval_journal(repo_root),
                git_dir=git_dir,
                still_current=push_still_current(repo_root, git_dir, branch, head),
            )
        rng = unpushed(repo_root, remote, branch)
        _refuse_fr_paths_under_stealth(repo_root, [c.sha for c in rng.commits])
        # R14 and R13 are the product branch's: `fr` is never subject-checked or squashed.
        check_subjects(settings, rng.commits, issue)
        if settings.git.history == "squash-unpushed":
            new = squash(repo_root, settings, branch, rng.commits, issue)
            if new is not None:
                console.print(
                    f"squashed {len(rng.commits)} unpushed commit(s) into {new[:12]} "
                    "(git.history: squash-unpushed)",
                    soft_wrap=True,
                )
        pushed = _push_placement(repo_root, remote, branch, code=_code_pending(rng))
        if settings.git.push == "ask":
            consume(git_dir, "push", branch)
    except (SettingsError, PushRefusedError, AskRefusedError) as e:
        raise _fail(f"fr push: {e}") from e
    console.print(f"pushed {' and '.join(pushed) or 'nothing'} to {remote}", soft_wrap=True)
