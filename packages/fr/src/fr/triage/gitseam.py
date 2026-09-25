"""The git seam of the batch verbs (spec 2026-09-25-triage-batches §3.D, §3.F, §3.I).

`batch dispatch` and `batch merge` need a local clone of the batch's repo:
herdr's `--cwd`, the version `source` read from `origin/<default>`, and
merge's scratch worktree. Every `git` process they start is started HERE, and
only here, so the §3.J tripwire can ban `subprocess` from every batch module
while this one module keeps it (review r2p-f11).

What this module may run is closed: `git`, plus the two commands a repo
declares in its own `.fr/triage.yaml` `version` block (`set` and `relock`),
run with a scratch worktree as cwd. It never runs a forge CLI: every forge
operation goes through the `GhClient` adapter (§3.J), and
`tests/unit/test_forge_adapter_batch_ops.py` pins that this file names none.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from datetime import datetime
from pathlib import Path

from fr.triage.errors import TriageError


class GitError(TriageError):
    """A git command failed; the message carries git's own words."""


def _run(argv: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise GitError(f"cannot run {argv[0]}: {exc}") from exc
    if result.returncode != 0:
        words = (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
        raise GitError(f"`{shlex.join(argv)}` failed in {cwd}: {words}")
    return result.stdout


def git(args: list[str], cwd: Path) -> str:
    """Run `git <args>` in *cwd* and return its stdout; raise `GitError` on failure."""
    return _run(["git", *args], cwd)


def git_ok(args: list[str], cwd: Path) -> bool:
    """Whether `git <args>` exits 0 (for predicates such as `merge-base --is-ancestor`)."""
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True).returncode == 0
    except OSError as exc:
        raise GitError(f"cannot run git: {exc}") from exc


def run_declared(command: str, cwd: Path, **fields: str) -> None:
    """Run a command the repo declares in `.fr/triage.yaml` (`set`, `relock`).

    `{name}` placeholders are filled from *fields* after splitting, so a value
    can never inject a second argument. No shell is involved.
    """
    argv = [part.format(**fields) for part in shlex.split(command)]
    if not argv:
        raise GitError("an empty version command was declared")
    _run(argv, cwd)


# ------------------------------------------------------------------ origin

_REMOTE = re.compile(
    r"^(?:[a-z+]+://(?:[^@/]+@)?[^/:]+(?::\d+)?/|[^@/:]+@[^:]+:)(?P<path>.+?)(?:\.git)?/?$"
)


def repo_of_url(url: str) -> str | None:
    """`OWNER/REPO` of a remote URL (https, ssh or scp-like); None for a local path."""
    m = _REMOTE.match(url.strip())
    if m is None:
        return None
    parts = m["path"].strip("/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else None


class Checkout:
    """A local clone of a batch's repo (spec §3.I), driven through git only."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def at(cls, path: Path | None) -> Checkout:
        """The clone at *path*, or the current directory's git toplevel."""
        start = path if path is not None else Path.cwd()
        if not start.is_dir():
            raise GitError(f"--checkout {start} is not a directory")
        try:
            top = git(["rev-parse", "--show-toplevel"], start).strip()
        except GitError as exc:
            raise GitError(
                f"{start} is not inside a git clone; give --checkout PATH to a clone "
                "of the batch's repo"
            ) from exc
        return cls(Path(top))

    def origin_url(self) -> str:
        return git(["remote", "get-url", "origin"], self.path).strip()

    def origin_repo(self) -> str | None:
        return repo_of_url(self.origin_url())

    def default_branch(self) -> str:
        """`origin/HEAD`'s branch, which `git clone` records."""
        try:
            ref = git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], self.path)
        except GitError as exc:
            raise GitError(
                f"cannot tell {self.path}'s default branch (origin/HEAD is unset); run "
                "`git remote set-head origin --auto` there"
            ) from exc
        return ref.strip().removeprefix("origin/")

    def fetch(self) -> None:
        git(["fetch", "--quiet", "--prune", "origin"], self.path)

    def show(self, ref: str, file: str) -> str | None:
        """*file*'s text at *ref*, or None when it does not exist there."""
        if not git_ok(["cat-file", "-e", f"{ref}:{file}"], self.path):
            return None
        return git(["show", f"{ref}:{file}"], self.path)

    def last_change(self, ref: str, file: str) -> datetime | None:
        """When the commit on *ref* that last touched *file* was made; None if never."""
        stamp = git(["log", "-1", "--format=%cI", ref, "--", file], self.path).strip()
        return datetime.fromisoformat(stamp) if stamp else None

    def remote_branch_exists(self, branch: str) -> bool:
        out = git(["ls-remote", "--heads", "origin", f"refs/heads/{branch}"], self.path)
        return bool(out.strip())

    def rev_parse(self, ref: str) -> str:
        return git(["rev-parse", ref], self.path).strip()

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return git_ok(["merge-base", "--is-ancestor", ancestor, descendant], self.path)

    # ------------------------------------------------------- scratch worktree

    def add_worktree(self, where: Path, ref: str) -> Worktree:
        """A detached worktree of *ref* at *where*, replacing a stale one there."""
        if where.exists():
            self.remove_worktree(where)
        where.parent.mkdir(parents=True, exist_ok=True)
        git(["worktree", "add", "--detach", str(where), ref], self.path)
        return Worktree(where)

    def remove_worktree(self, where: Path) -> None:
        git(["worktree", "remove", "--force", str(where)], self.path)
        git(["worktree", "prune"], self.path)


class Worktree:
    """merge's scratch worktree of one PR branch (spec §3.F step 3)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def merge(self, ref: str) -> list[str]:
        """Start merging *ref* without committing; the conflicted paths ([] if none)."""
        clean = git_ok(["merge", "--no-ff", "--no-commit", ref], self.path)
        conflicted = git(["diff", "--name-only", "--diff-filter=U"], self.path).split()
        if not clean and not conflicted:
            raise GitError(f"`git merge {ref}` failed in {self.path} without a conflict")
        return conflicted

    def take_theirs(self, paths: list[str]) -> None:
        """Resolve *paths* to main's side, so no file keeps conflict markers."""
        git(["checkout", "--theirs", "--", *paths], self.path)
        git(["add", "--", *paths], self.path)

    def abort_merge(self) -> None:
        git(["merge", "--abort"], self.path)

    def read(self, file: str) -> str | None:
        target = self.path / file
        return target.read_text(encoding="utf-8") if target.is_file() else None

    def run(self, command: str, **fields: str) -> None:
        run_declared(command, self.path, **fields)

    def commit_all(self, message: str) -> str | None:
        """Stage everything and commit; the new head, or None when nothing changed."""
        git(["add", "--all"], self.path)
        merging = git_ok(["rev-parse", "-q", "--verify", "MERGE_HEAD"], self.path)
        if not merging and git_ok(["diff", "--cached", "--quiet"], self.path):
            return None
        git(["commit", "--no-verify", "-m", message], self.path)
        return git(["rev-parse", "HEAD"], self.path).strip()

    def push(self, branch: str) -> None:
        git(["push", "origin", f"HEAD:refs/heads/{branch}"], self.path)
