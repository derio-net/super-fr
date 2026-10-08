"""The git seam of the batch verbs (spec 2026-09-25-triage-batches §3.D, §3.F, §3.I).

`batch dispatch` and `batch merge` need a local clone of the batch's repo:
herdr's `--cwd`, the version `source` read from `origin/<default>`, and
merge's scratch worktree. Every `git` process they start is started HERE, and
only here, so the §3.J tripwire can ban `subprocess` from every batch module
while this one module keeps it (review r2p-f11).

What this module may run is closed: `git`, plus the commands a repo
declares in its own `.fr/triage.yaml` (`version.set`, `version.relock`, run in a
scratch worktree, and `post_merge`, run by the wave driver in the clone itself) and
the scope's `publish` argument list (`run_publish`, triage-claims R14).
It never runs a forge CLI: every forge
operation goes through the `GhClient` adapter (§3.J), and
`tests/unit/test_forge_adapter_batch_ops.py` pins that this file names none.
"""

from __future__ import annotations

import fnmatch
import os
import re
import shlex
import stat
import subprocess
from pathlib import Path
from typing import Any

from fr.triage.errors import TriageError


class GitError(TriageError):
    """A git command failed; the message carries git's own words."""


GIT_TIMEOUT_SECONDS = 300.0
"""The longest one `git` call may take (gh#921): a fetch or push that stalls on a
degraded forge raises like a failed one, so the wave driver skips that pass and
reads again, as a stalled `gh` call does since gh#909. Generous on purpose: a
clone's first fetch of a large repo is slow but finishes. A command the repo
declares (`post_merge`, `version.set`/`relock`) is the repo's own and is not bounded."""


def _run(
    argv: list[str],
    cwd: Path,
    *,
    text: bool = True,
    ok: tuple[int, ...] = (0,),
    timeout: float | None = None,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
) -> Any:
    """The one place a process starts (apart from `git_ok`): stdout as text, or raw bytes with
    `text=False`; a return code outside *ok*, or a run past *timeout* seconds, raises
    `GitError` with the command's own words. *env* is laid over the process environment;
    *stdin* is fed to the command (text mode only)."""
    full_env = {**os.environ, **env} if env else None
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=text,
            check=False,
            timeout=timeout,
            env=full_env,
            input=stdin,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"`{shlex.join(argv)}` timed out after {timeout:g}s in {cwd}") from exc
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
    out: bytes = _run(["git", *args], cwd, text=False, ok=ok, timeout=GIT_TIMEOUT_SECONDS)
    return out


def git(args: list[str], cwd: Path) -> str:
    """Run `git <args>` in *cwd* and return its stdout; raise `GitError` on failure."""
    out: str = _run(["git", *args], cwd, timeout=GIT_TIMEOUT_SECONDS)
    return out


def show_bytes(cwd: Path, ref: str, file: str) -> bytes | None:
    """*file*'s content at *ref*, exactly as stored, or None when it does not exist there."""
    if not git_ok(["cat-file", "-e", f"{ref}:{file}"], cwd):
        return None
    return git_bytes(["show", f"{ref}:{file}"], cwd)


def show_text(cwd: Path, ref: str, file: str) -> str | None:
    """*file*'s content at *ref* as UTF-8 text, line endings untouched, or None when it
    does not exist there. A blob that is not UTF-8 (a binary file) is a `GitError` naming
    it, never a `UnicodeDecodeError` (gh#889): every text caller reads a manifest or a
    config, and a copy that must keep any file intact reads `show_bytes` instead."""
    content = show_bytes(cwd, ref, file)
    if content is None:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GitError(f"{file} at {ref} is not UTF-8 text ({exc.reason}); cannot read it") from exc


def git_ok(args: list[str], cwd: Path) -> bool:
    """Whether `git <args>` exits 0 (for predicates such as `merge-base --is-ancestor`)."""
    try:
        done = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, timeout=GIT_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired as exc:
        raise GitError(
            f"`{shlex.join(['git', *args])}` timed out after {GIT_TIMEOUT_SECONDS:g}s in {cwd}"
        ) from exc
    except OSError as exc:
        raise GitError(f"cannot run git: {exc}") from exc
    return done.returncode == 0


def toplevel(path: Path) -> Path | None:
    """The git toplevel of the clone (or linked worktree) holding *path*; None when
    *path* is in none (spec 2026-10-07-cloud-triage R4)."""
    try:
        out: str = _run(["git", "rev-parse", "--show-toplevel"], path, timeout=GIT_TIMEOUT_SECONDS)
    except GitError:
        return None
    return Path(out.strip()) if out.strip() else None


def common_dir(root: Path) -> Path:
    """`git rev-parse --git-common-dir` of the clone at *root*, absolute: the main
    repository's `.git` even from a linked worktree, where `info/exclude` lives."""
    out = git(["rev-parse", "--git-common-dir"], root).strip()
    path = Path(out)
    return path if path.is_absolute() else (root / path).resolve()


def ensure_excluded(root: Path, entry: str) -> bool:
    """Append *entry* to `<common dir>/info/exclude` unless a line already says it;
    whether it wrote. The exclude file is the repository's own and untracked, so no
    tracked file changes, on any branch (R4)."""
    exclude = common_dir(root) / "info" / "exclude"
    try:
        text = exclude.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    if entry in text.splitlines():
        return False
    exclude.parent.mkdir(parents=True, exist_ok=True)
    sep = "" if not text or text.endswith("\n") else "\n"
    with exclude.open("a", encoding="utf-8") as fh:
        fh.write(f"{sep}{entry}\n")
    return True


# ------------------------------------------------------- refs outside refs/heads

_REF_IDENTITY = {
    "GIT_AUTHOR_NAME": "fr triage",
    "GIT_AUTHOR_EMAIL": "fr-triage@example.invalid",
    "GIT_COMMITTER_NAME": "fr triage",
    "GIT_COMMITTER_EMAIL": "fr-triage@example.invalid",
}
"""Who a state-ref commit is by: fixed, so a container with no git identity can write
one, and nothing about the operator rides along (cloud-triage §B)."""


def remote_ref(cwd: Path, remote: str, ref: str) -> str | None:
    """The sha *remote* has at the fully qualified *ref*, or None when it has none."""
    out = git(["ls-remote", "--refs", remote, ref], cwd)
    for line in out.splitlines():
        sha, _, name = line.partition("\t")
        if name == ref:
            return sha
    return None


_NO_REMOTE_REF = "couldn't find remote ref"
"""git's own words when a fetched ref does not exist on the remote."""


def fetch_ref(cwd: Path, remote: str, ref: str) -> str | None:
    """Fetch *ref* from *remote* into the same ref here (forced: the remote is the truth),
    then read the sha the local ref now holds (p3-r5: one round trip, no window between
    reading a sha and fetching it). None when the remote has no such ref; a local copy
    left from an earlier fetch is then dropped, so it is never mistaken for the remote's."""
    try:
        git(["fetch", "--quiet", "--no-tags", remote, f"+{ref}:{ref}"], cwd)
    except GitError as exc:
        if _NO_REMOTE_REF not in str(exc):
            raise
        git_ok(["update-ref", "-d", ref], cwd)
        return None
    return git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd).strip() or None


def has_commit(cwd: Path, sha: str) -> bool:
    """Whether *sha* names a commit this clone has."""
    return git_ok(["cat-file", "-e", f"{sha}^{{commit}}"], cwd)


def file_mode(path: Path) -> str:
    """The git mode of the regular file at *path*: `100755` when its owner may execute
    it, else `100644` (p3-r12), as `git add` decides."""
    return "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"


def hash_paths(cwd: Path, root: Path, paths: list[str], *, write: bool = False) -> list[str]:
    """The blob sha of each of *paths* (POSIX, relative to *root*), in order, as `git
    hash-object` names its current bytes; with *write*, the blobs are stored too."""
    if not paths:
        return []
    argv = ["git", "hash-object", *(["-w"] if write else []), "--no-filters", "--stdin-paths"]
    out: str = _run(
        argv, cwd, stdin="".join(f"{root / p}\n" for p in paths), timeout=GIT_TIMEOUT_SECONDS
    )
    return out.split()


def commit_tree_from_paths(
    cwd: Path, root: Path, paths: list[str], *, parent: str | None, message: str
) -> str:
    """A commit whose tree holds exactly *paths* (POSIX, relative to *root*) with their
    current bytes and git mode (`file_mode`), built in a temporary index: the clone's own
    index, HEAD and worktree are never touched. Blobs are written with `hash-object -w`;
    the commit carries *parent* when given and a fixed identity."""
    import tempfile

    blobs = hash_paths(cwd, root, paths, write=True)
    with tempfile.TemporaryDirectory(prefix="fr-state-ref-") as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        info = "".join(
            f"{file_mode(root / p)} {sha}\t{p}\n" for sha, p in zip(blobs, paths, strict=True)
        )
        _run(
            ["git", "update-index", "--add", "--index-info"],
            cwd,
            env=env,
            stdin=info,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        tree = _run(["git", "write-tree"], cwd, env=env, timeout=GIT_TIMEOUT_SECONDS).strip()
    argv = ["git", "commit-tree", tree, "-m", message]
    if parent is not None:
        argv += ["-p", parent]
    out: str = _run(argv, cwd, env=_REF_IDENTITY, timeout=GIT_TIMEOUT_SECONDS)
    return out.strip()


def push_ref_cas(cwd: Path, remote: str, sha: str, ref: str, *, expected_old: str | None) -> bool:
    """Push *sha* to *ref* on *remote* only if the remote still has *expected_old* there
    (`--force-with-lease=<ref>:<old>`; None means the ref must not exist yet). Whether
    it landed: False when the lease was stale, i.e. the remote's ref is not
    *expected_old* any more. Any other failure raises `GitError`."""
    lease = f"--force-with-lease={ref}:{expected_old or ''}"
    try:
        git(["push", "--quiet", "--no-verify", lease, remote, f"{sha}:{ref}"], cwd)
    except GitError:
        if remote_ref(cwd, remote, ref) != expected_old:
            return False
        raise
    return True


def tree_files(cwd: Path, sha: str) -> list[tuple[str, str, str]]:
    """`(mode, blob sha, path)` for every blob in *sha*'s tree, recursively."""
    out = git_bytes(["ls-tree", "-r", "-z", "--full-tree", sha], cwd)
    entries = []
    for record in out.split(b"\0"):
        if not record:
            continue
        meta, _, path = record.partition(b"\t")
        mode, kind, blob = meta.decode().split(" ")
        if kind == "blob":
            entries.append((mode, blob, path.decode("utf-8", "surrogateescape")))
    return entries


def blob_bytes(cwd: Path, sha: str) -> bytes:
    """The bytes of blob *sha*, exactly as stored."""
    return git_bytes(["cat-file", "blob", sha], cwd)


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
        """*file*'s UTF-8 text at *ref*, or None when it does not exist there (`show_text`:
        a non-UTF-8 blob is a `GitError`)."""
        return show_text(self.path, ref, file)

    def show_bytes(self, ref: str, file: str) -> bytes | None:
        """*file*'s exact content at *ref*, or None when it does not exist there."""
        return show_bytes(self.path, ref, file)

    def remote_branch_exists(self, branch: str) -> bool:
        out = git(["ls-remote", "--heads", "origin", f"refs/heads/{branch}"], self.path)
        return bool(out.strip())

    def has_branch(self, branch: str) -> bool:
        """A local branch *branch* exists."""
        return git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], self.path)

    def worktree_of(self, branch: str) -> Path | None:
        """The worktree *branch* is checked out in (`git worktree list`), or None."""
        out = git(["worktree", "list", "--porcelain"], self.path)
        where: Path | None = None
        for line in out.splitlines():
            if line.startswith("worktree "):
                where = Path(line.removeprefix("worktree ")).resolve()
            elif line == f"branch refs/heads/{branch}" and where is not None:
                return where
        return None

    def main_worktree(self) -> Path:
        """The repository's main (non-linked) worktree, wherever this checkout is: the
        first entry of `git worktree list`."""
        for line in git(["worktree", "list", "--porcelain"], self.path).splitlines():
            if line.startswith("worktree "):
                return Path(line.removeprefix("worktree ")).resolve()
        return self.path.resolve()

    def publish_branch(self, branch: str) -> None:
        """Push local *branch* to origin and make that its upstream (batch adopt, §C)."""
        git(
            ["push", "--quiet", "-u", "origin", f"refs/heads/{branch}:refs/heads/{branch}"],
            self.path,
        )

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

    def commits_behind(
        self, head: str, ref: str
    ) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
        """The first-parent commits of *ref* that *head* lacks, each with its
        (status, path) changes against its first parent, renames split into a
        delete and an add (gh#927). Together they are everything *ref* changed
        since *head* forked from it."""
        shas = git(["rev-list", "--first-parent", f"{head}..{ref}"], self.path).split()
        out = []
        for sha in shas:
            raw = git(
                ["diff", "--name-status", "--no-renames", "-z", f"{sha}^1", sha], self.path
            ).split("\0")
            pairs = zip(raw[0::2], raw[1::2], strict=False)
            out.append((sha, tuple((s, p) for s, p in pairs if s and p)))
        return tuple(out)

    def changed_paths(self, ref: str, head: str) -> frozenset[str]:
        """The paths *head* changed since it forked from *ref* (`ref...head`)."""
        out = git(["diff", "--name-only", "--no-renames", "-z", f"{ref}...{head}"], self.path)
        return frozenset(p for p in out.split("\0") if p)

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
        # `-z`: names unquoted, so a non-ASCII path is copied, not skipped as unknown.
        listed = git_bytes(["ls-tree", "-r", "-z", "--name-only", ref, "--", *paths], self.path)
        for name in (os.fsdecode(n) for n in listed.split(b"\0") if n):
            content = self.show_bytes(ref, name)  # any file, binary included (gh#889)
            if content is None:
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

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
        """*file*'s UTF-8 text at *ref*, or None when it does not exist there (`show_text`)."""
        return show_text(self.path, ref, file)

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

    def commit_paths(self, paths: list[str], message: str) -> str | None:
        """Stage exactly *paths* (directories included, untracked files under them too)
        and commit only them; the new head, or None when nothing under them changed.

        The driver's state export (pages-goal §I): unlike `commit_all`, untracked files
        are what it commits, and nothing outside *paths* rides along. Never `--force`:
        a repo's `.gitignore` says what must never be committed (p4-r9); `ignored`
        names what it kept out."""
        if not paths:
            raise GitError("commit_paths needs at least one path")
        git(["add", "--all", "--", *paths], self.path)
        if git_ok(["diff", "--cached", "--quiet", "--", *paths], self.path):
            return None
        git(["commit", "--no-verify", "-m", message, "--", *paths], self.path)
        return git(["rev-parse", "HEAD"], self.path).strip()

    def ignored(self, paths: list[str]) -> tuple[str, ...]:
        """The *paths* this repo's ignore rules exclude (`git check-ignore`), sorted;
        a tracked path is never ignored."""
        out: set[str] = set()
        for i in range(0, len(paths), 200):  # bounded argv
            chunk = paths[i : i + 200]
            raw = git_bytes(
                ["-c", "core.quotePath=false", "check-ignore", "--", *chunk], self.path, ok=(0, 1)
            )
            out.update(line for line in os.fsdecode(raw).splitlines() if line)
        return tuple(sorted(out))

    def push(self, branch: str, *, force: bool = False) -> None:
        """Push HEAD to *branch*; *force* overwrites it, for a branch fr owns (the
        driver's export branch, which a pass that died may have left behind)."""
        argv = ["push", *(["--force"] if force else []), "origin", f"HEAD:refs/heads/{branch}"]
        git(argv, self.path)


def run_publish(argv: list[str], cwd: Path, timeout: float) -> str | None:
    """Run the scope's `publish` argument list as is, with no shell (triage-claims R14), in
    *cwd* (the scope's state directory), inheriting the caller's full environment. None
    when it exited 0, else the cause on one line (`_run`'s words). Never raises."""
    try:
        _run(argv, cwd, timeout=timeout)
    except GitError as exc:
        return " ".join(str(exc).split())
    return None
