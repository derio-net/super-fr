"""Git subprocess wrappers.

Thin wrappers around git commands used by the vk toolchain. The plain wrappers
(`repo_root`, `add`, …) raise subprocess.CalledProcessError on failure.

The fail-closed half (`git_answer`, `remote_name`, `remote_default_ref`) is the
one definition of "which remote-tracking ref is the default branch", shared by
the migration commit guard (`fr.artifacts.commit._default_branch`) and the
archive merge evidence (`fr.archive.merge_evidence`). It returns a
`GitRefusal` rather than guessing, and raises `GitUnavailableError` only when
git could not be run at all.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    return result.stdout.strip()


def repo_root(cwd: Path | None = None) -> Path:
    """Return the root directory of the current git repository."""
    output = _run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    return Path(output.strip())


def add(paths: list[str], cwd: Path | None = None) -> None:
    """Stage files for commit."""
    _run_git(["add", *paths], cwd=cwd)


def commit(message: str, cwd: Path | None = None) -> None:
    """Create a commit with the given message."""
    _run_git(["commit", "-m", message], cwd=cwd)


def status(cwd: Path | None = None) -> str:
    """Return porcelain status output."""
    return _run_git(["status", "--porcelain"], cwd=cwd)


def file_on_ref(ref: str, path: str, cwd: Path | None = None) -> bool:
    """True iff `path` exists at the given git `ref`.

    Thin wrapper around `git ls-tree`. Used by the dispatch
    reachability gate to verify plan files are reachable on
    origin/HEAD before `fr apply --yes` creates an Issue.
    Raises if the ref doesn't exist locally.
    """
    output = _run_git(["ls-tree", ref, "--", path], cwd=cwd)
    return bool(output.strip())


# --- fail-closed answers: the default remote-tracking ref -----------------

GIT_TIMEOUT_SECONDS = 30.0
"""Wall-clock cap on every `git_answer` subprocess (review r5-c5).

These run at CLI entry, before the command the operator typed. A
`pre-commit` hook that waits on the network, a `gpg` signing prompt with no
agent, or an NFS mount that has gone away turns "fr status" into a process
that never returns and prints nothing. A timeout converts all of those into a
refusal that names what hung.
"""

_GIT_ENV: dict[str, str] = {
    # Force the C locale: callers PARSE git's stderr to tell "not a git
    # repository" (proceed) from every other failure (refuse). Under a German
    # or Japanese locale that string is translated, the match fails, and the
    # gate flips back to fail-OPEN — the exact regression review r5-c2 closed.
    "LC_ALL": "C",
    "LANG": "C",
    "LANGUAGE": "C",
    # Never block on credentials: a repo with an http remote can otherwise sit
    # waiting for a username at CLI entry.
    "GIT_TERMINAL_PROMPT": "0",
    # Read-only commands must not take `index.lock`; another fr (or the
    # operator's editor) may hold it, and we would rather report than contend.
    "GIT_OPTIONAL_LOCKS": "0",
}


class GitUnavailableError(Exception):
    """git could not answer — NOT "there is no repository here"."""


@dataclass(frozen=True)
class GitRefusal:
    """git state could not be established. Fail CLOSED: never act on this."""

    reason: str


def git_answer(
    root: Path, *args: str, timeout: float = GIT_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    """One git call, C-locale, prompt-free, time-boxed.

    Raises `GitUnavailableError` when git could not be RUN or did not finish;
    a non-zero exit is returned normally, because "this ref does not exist" is
    an answer.
    """
    try:
        return subprocess.run(
            git_argv(root, *args),
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **_GIT_ENV},
        )
    except FileNotFoundError as e:
        raise GitUnavailableError("git is not installed or not on PATH") from e
    except subprocess.TimeoutExpired as e:
        raise GitUnavailableError(
            f"`git {' '.join(args)}` did not finish within {timeout:g}s "
            "(a hook, a credential prompt, or a stalled filesystem?)"
        ) from e
    except OSError as e:
        raise GitUnavailableError(f"could not run git: {e}") from e


def ref_exists(root: Path, ref: str) -> bool:
    return git_answer(root, "rev-parse", "--verify", "--quiet", ref).returncode == 0


WELL_KNOWN_DEFAULTS = ("main", "master", "trunk", "develop")
"""Candidate trunk names, remote-tracking first, then local. Last resort."""


def remote_name(root: Path) -> str | None | GitRefusal:
    """Which remote speaks for "the default branch" (review r5-c3 / r5-e6).

    `origin` is a convention, not a rule. `checkout.defaultRemote` is git's own
    answer when there are several; a single remote of any name is unambiguous;
    two unnamed-by-config remotes are a genuine ambiguity and this refuses
    rather than picking one — callers decide whether an automatic commit is
    allowed, or whether a plan counts as merged, on the answer.
    """
    configured = git_answer(root, "config", "--get", "checkout.defaultRemote")
    if configured.returncode == 0 and configured.stdout.strip():
        return configured.stdout.strip()
    listed = git_answer(root, "remote")
    if listed.returncode != 0:
        return GitRefusal(reason=f"git could not list remotes: {listed.stderr.strip()}")
    names = [n for n in listed.stdout.split() if n]
    if not names:
        return None
    if len(names) == 1:
        return names[0]
    if "origin" in names:
        return "origin"
    return GitRefusal(
        reason=(
            f"{root} has {len(names)} remotes ({', '.join(sorted(names))}) and no "
            "`checkout.defaultRemote`, so fr cannot tell which one names the default "
            "branch. Set `git config checkout.defaultRemote <name>`."
        )
    )


def remote_default_ref(root: Path) -> str | None | GitRefusal:
    """The default branch as a REMOTE-TRACKING ref (`origin/main`), or why not.

    Only remote-tracking refs count: a local `main` shows nothing merged. Two
    sources, in order:

    1. `refs/remotes/<remote>/HEAD` — what the HOST says, and the only
       authority. Ignored when it points at a ref that no longer exists (a
       deleted branch leaves a dangling symbolic-ref behind).
    2. `refs/remotes/<remote>/{main,master,trunk,develop}` — a remote WITHOUT
       a HEAD (a plain `git fetch` never writes one).

    `None` when there is no remote, or neither source resolves; the remote's
    `GitRefusal` (e.g. two remotes, no `checkout.defaultRemote`) passes
    through. A branch with a `/` in it (`origin/release/main`) survives.
    """
    remote = remote_name(root)
    if remote is None or isinstance(remote, GitRefusal):
        return remote
    head = git_answer(root, "symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD")
    if head.returncode == 0 and head.stdout.strip():
        named = head.stdout.strip().removeprefix(f"{remote}/")
        if named and ref_exists(root, f"refs/remotes/{remote}/{named}"):
            return f"{remote}/{named}"
    for name in WELL_KNOWN_DEFAULTS:
        if ref_exists(root, f"refs/remotes/{remote}/{name}"):
            return f"{remote}/{name}"
    return None


def safe_directory_args(root: Path) -> list[str]:
    """`-c safe.directory=<repo>` for the repository enclosing `root`, else [].

    A bind-mounted worktree is foreign-owned inside a container, and git then
    refuses every call ("dubious ownership"). `safe.directory` is honoured only
    from system/global/command-line config, so a per-process `-c` naming exactly
    the enclosing worktree is valid, never persisted, and never a wildcard.
    Walks UP to the nearest `.git` entry (a file for a linked worktree, a
    directory otherwise) because git matches the repository toplevel, not the
    caller's cwd. Returns [] outside any repository, leaving the refusal loud.
    """
    try:
        here = Path(root).resolve()
    except OSError:
        return []
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return ["-c", f"safe.directory={candidate}"]
    return []


def git_argv(root: Path, *args: str) -> list[str]:
    """The one construction of a git argument vector that trusts `root`'s repo."""
    return ["git", *safe_directory_args(root), *args]
