"""The git seam of the batch verbs (spec 2026-09-25-triage-batches §3.D, §3.F, §3.I).

`batch dispatch` and `batch merge` need a local clone of the batch's repo:
herdr's `--cwd`, the version `source` read from `origin/<default>`, and
merge's scratch worktree. Every `git` process they start is started HERE, and
only here, so the §3.J tripwire can ban `subprocess` from every batch module
while this one module keeps it (review r2p-f11).

What this module may run is closed: `git`, plus the commands a repo
declares in its own `.fr/triage.yaml` (`version.set`, `version.relock`, run in a
scratch worktree, and `post_merge`, run by the wave driver in the clone itself).
It never runs a forge CLI: every forge
operation goes through the `GhClient` adapter (§3.J), and
`tests/unit/test_forge_adapter_batch_ops.py` pins that this file names none.
"""

from __future__ import annotations

import fnmatch
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from fr.triage.errors import TriageError


class GitError(TriageError):
    """A git command failed; the message carries git's own words."""


def _run(argv: list[str], cwd: Path, *, text: bool = True, ok: tuple[int, ...] = (0,)) -> Any:
    """The one place a process starts (apart from `git_ok`): stdout as text, or raw bytes with
    `text=False`; a return code outside *ok* raises `GitError` with the command's own words."""
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=text, check=False)
    except OSError as exc:
        raise GitError(f"cannot run {argv[0]}: {exc}") from exc
    if result.returncode not in ok:
        err, out = result.stderr, result.stdout
        words = (err.decode("utf-8", "replace") if isinstance(err, bytes) else err).strip()
        if not words:
            words = (out.decode("utf-8", "replace") if isinstance(out, bytes) else out).strip()
        raise GitError(
            f"`{shlex.join(argv)}` failed in {cwd}: {words or f'exit {result.returncode}'}"
        )
    return result.stdout


def git_bytes(args: list[str], cwd: Path, *, ok: tuple[int, ...] = (0,)) -> bytes:
    """Run `git <args>` and return stdout as raw bytes (for `-z` output whose paths and
    contents are not necessarily UTF-8); a return code outside *ok* raises `GitError`."""
    out: bytes = _run(["git", *args], cwd, text=False, ok=ok)
    return out


def git(args: list[str], cwd: Path) -> str:
    """Run `git <args>` in *cwd* and return its stdout; raise `GitError` on failure."""
    out: str = _run(["git", *args], cwd)
    return out


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
        self._line_counts: dict[str, dict[str, int]] = {}

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

    def remote_branch_exists(self, branch: str) -> bool:
        out = git(["ls-remote", "--heads", "origin", f"refs/heads/{branch}"], self.path)
        return bool(out.strip())

    def rev_parse(self, ref: str) -> str:
        return git(["rev-parse", ref], self.path).strip()

    def short_rev(self, ref: str) -> str | None:
        """*ref*'s abbreviated commit, or None when it names no commit here."""
        try:
            return (
                git(
                    ["rev-parse", "--verify", "--quiet", "--short", f"{ref}^{{commit}}"], self.path
                ).strip()
                or None
            )
        except GitError:
            return None

    def text_line_counts(self, ref: str) -> dict[str, int]:
        """Path -> line count of every regular text file in the tree at *ref*.

        Two processes per ref, cached: `git ls-tree -r -l -z` (modes and sizes, paths
        unquoted) and `git grep -I -c '' -z` (one exact newline-based count per text
        file). Symlinks (mode 120000) and submodules (160000) are left out, binary files
        are skipped by `-I`, and an empty regular file counts 0 lines (its size is 0)."""
        cached = self._line_counts.get(ref)
        if cached is not None:
            return cached
        listing = git_bytes(["ls-tree", "-r", "-l", "-z", ref], self.path)
        regular: dict[str, int] = {}  # path -> size
        for entry in listing.split(b"\0"):
            meta, _, raw = entry.partition(b"\t")
            fields = meta.split()
            if len(fields) == 4 and fields[0] in (b"100644", b"100755"):
                regular[os.fsdecode(raw)] = int(fields[3]) if fields[3].isdigit() else -1
        counted = git_bytes(["grep", "-I", "-c", "-z", "", ref], self.path, ok=(0, 1))
        counts = {name: 0 for name, size in regular.items() if size == 0}
        prefix = f"{ref}:"
        for match in re.finditer(rb"([^\0]*)\0(\d+)\n", counted):
            path = os.fsdecode(match[1]).removeprefix(prefix)
            if path in regular:
                counts[path] = int(match[2])
        self._line_counts[ref] = counts
        return counts

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return git_ok(["merge-base", "--is-ancestor", ancestor, descendant], self.path)

    # ------------------------------------------------------ the wave driver

    def fast_forward(self) -> None:
        """Fetch, then fast-forward the checked-out default branch to origin's
        (wave-driver §B). A clone on any other branch is refused by name: the
        driver never switches an operator's branch for them."""
        self.fetch()
        default = self.default_branch()
        current = git(["rev-parse", "--abbrev-ref", "HEAD"], self.path).strip()
        if current != default:
            raise GitError(
                f"{self.path} is on {current}, not {default}; the driver fast-forwards "
                f"the default branch only — check out {default} there"
            )
        git(["merge", "--ff-only", "--quiet", f"origin/{default}"], self.path)

    def released_after(self, merge_commit: str) -> bool:
        """Whether `origin/<default>` carries a `release: ...` commit that descends
        from *merge_commit* — the release that follows THIS merge (wave-driver §B
        step 2). A release cut before the merge, or from a side line the merge is
        not on, does not count (review rg-9); an unknown merge commit is never
        released, so the caller falls back to the ten-minute rule."""
        if not merge_commit:
            return False
        tip = f"origin/{self.default_branch()}"
        if not self.is_ancestor(merge_commit, tip):
            return False
        out = git(["log", f"{merge_commit}..{tip}", "--format=%H %s"], self.path)
        for line in out.splitlines():
            sha, _, subject = line.partition(" ")
            if subject.startswith("release: ") and self.is_ancestor(merge_commit, sha):
                return True
        return False

    def added_paths(self, merge_commit: str) -> tuple[str, ...]:
        """The paths *merge_commit* added against its first parent: what a batch's
        merge brought in, read for the driver's "already archived" check. An unknown
        or root commit added nothing knowable, so it returns ()."""
        if not merge_commit or not git_ok(
            ["cat-file", "-e", f"{merge_commit}^1^{{commit}}"], self.path
        ):
            return ()
        out = git(
            ["diff", "--name-only", "--no-renames", "--diff-filter=A", "-z",
             f"{merge_commit}^1", merge_commit],
            self.path,
        )  # fmt: skip
        return tuple(p for p in out.split("\0") if p)

    def exists_at(self, ref: str, path: str) -> bool:
        return git_ok(["cat-file", "-e", f"{ref}:{path}"], self.path)

    def snapshot_paths(self, ref: str, paths: tuple[str, ...], dest: Path) -> None:
        """Write *paths* (files or directories) as they are at *ref* into *dest*, a
        fresh git repo with this clone's origin, so a reader that resolves a repo's
        declarations reads the default branch's, never this working tree's (review
        rg-5). Nothing in this clone changes."""
        git(["init", "--quiet", str(dest)], self.path)
        git(["remote", "add", "origin", self.origin_url()], dest)
        listed = git(["ls-tree", "-r", "--name-only", ref, "--", *paths], self.path)
        for name in listed.splitlines():
            text = self.show(ref, name)
            if text is None:
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def run_command(self, argv: list[str]) -> str:
        """Run the repo's declared `post_merge` argument list in this clone (R14).

        An argument list, never a shell string: nothing here reaches a shell."""
        if not argv:
            raise GitError("an empty post_merge command was declared")
        out: str = _run(list(argv), self.path)
        return out

    # ------------------------------------------------------- scratch worktree

    def add_worktree(self, where: Path, ref: str) -> Worktree:
        """A detached worktree of *ref* at *where*, replacing a CLEAN one there.

        A worktree merge kept for inspection may hold an operator's manual fix,
        so one with any local change (tracked or untracked) is refused by name
        rather than force-removed (review r3-f6); so is a directory there that
        is not a git worktree at all.
        """
        if where.exists():
            discard = f"`git worktree remove --force {where}`"
            if not (where / ".git").exists():
                raise GitError(
                    f"{where} exists and is not a git worktree; move it aside or delete it, "
                    "then re-run"
                )
            if git(["status", "--porcelain", "--untracked-files=all"], where).strip():
                raise GitError(
                    f"the scratch worktree kept at {where} has local changes, so it is not "
                    f"replaced. Keep what you need, then discard it with {discard} "
                    f"(run in {self.path}) and re-run"
                )
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
        """Start merging *ref* without committing; the conflicted paths ([] if none).

        `rerere` is off for this merge whatever the operator's config says: a
        replayed resolution would make a non-version conflict look clean, and
        only merge decides what may be resolved (review r3-f12).

        Directory-rename detection is off too (gh#800): fr's artifact
        directories are never renamed as a whole, but a close-out that moves
        the LAST file out of `runs/` or `journals/plans/` looks like one to
        git, which then moves the PR's new file after it and reports a
        conflict on a path that exists on neither side.
        """
        argv = [
            "-c",
            "rerere.enabled=false",
            "-c",
            "merge.directoryRenames=false",
            "merge",
            "--no-ff",
            "--no-commit",
            ref,
        ]
        clean = git_ok(argv, self.path)
        conflicted = git(["diff", "--name-only", "--diff-filter=U"], self.path).split()
        if not clean and not conflicted:
            raise GitError(f"`git merge {ref}` failed in {self.path} without a conflict")
        return conflicted

    def merge_base(self, ref: str) -> str:
        """The merge base of HEAD (the PR side) and *ref*."""
        return git(["merge-base", "HEAD", ref], self.path).strip()

    def show(self, ref: str, file: str) -> str | None:
        """*file*'s text at *ref*, or None when it does not exist there."""
        if not git_ok(["cat-file", "-e", f"{ref}:{file}"], self.path):
            return None
        return git(["show", f"{ref}:{file}"], self.path)

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

    def commit_all(self, message: str, version_files: list[str]) -> str | None:
        """Stage tracked changes plus the declared *version_files* globs, and
        commit; the new head, or None when nothing changed.

        Never `git add --all`: `set` / `relock` may leave build output behind,
        and anything untracked would ride into another run's PR (review r3-f7).
        """
        git(["add", "--update"], self.path)
        untracked = git(["ls-files", "-z", "--others", "--exclude-standard"], self.path)
        declared = [
            p
            for p in untracked.split("\0")
            if p and any(fnmatch.fnmatch(p, g) for g in version_files)
        ]
        if declared:
            git(["add", "--", *declared], self.path)
        merging = git_ok(["rev-parse", "-q", "--verify", "MERGE_HEAD"], self.path)
        if not merging and git_ok(["diff", "--cached", "--quiet"], self.path):
            return None
        git(["commit", "--no-verify", "-m", message], self.path)
        return git(["rev-parse", "HEAD"], self.path).strip()

    def push(self, branch: str) -> None:
        git(["push", "origin", f"HEAD:refs/heads/{branch}"], self.path)
