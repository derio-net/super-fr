"""The git seam of the batch verbs (spec 2026-09-25-triage-batches §3.D, §3.F, §3.I).

`batch dispatch` and `batch merge` need a local clone of the batch's repo:
herdr's `--cwd`, the version `source` read from `origin/<default>`, and
merge's scratch worktree. Every `git` process they start is started HERE, and
only here, so the §3.J tripwire can ban `subprocess` from every batch module
while this one module keeps it (review r2p-f11).

What this module may run is closed: `git`, plus the commands a repo
declares in its own `.fr/triage.yaml` (`version.set`, `version.relock`, run in a
scratch worktree, and `post_merge`, run by the wave driver in the clone itself),
the scope's `publish` argument list (`run_publish`, triage-claims R14), and this
`fr` itself (`Worktree.run_fr`: the collected close-out's own verbs, exit-gates §E).
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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from fr.safe_spawn import fr_argv, safe_fr_env
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
    stdin: str | bytes | None = None,
    coded: bool = False,
    passthrough: Literal["none", "stderr", "all"] = "none",
    exact_env: bool = False,
) -> Any:
    """The one place a process starts (apart from `git_ok`): stdout as text, or raw bytes with
    `text=False`; a return code outside *ok*, or a run past *timeout* seconds, raises
    `GitError` with the command's own words. *env* is laid over the process environment;
    *stdin* is fed to the command (text in text mode, bytes with `text=False`). *coded*:
    any return code is an answer, `(code, stdout + stderr)`, never a raise (text mode
    only). *passthrough* leaves streams with the operator instead of capturing them:
    `stderr` (stdout is still captured), or `all` (nothing is, for a command that asks on
    the terminal). *exact_env*: *env* is the child's WHOLE environment, not laid over this
    one, so a variable can be removed (`fr.safe_spawn.safe_fr_env` drops a relative
    `PYTHONPATH`)."""
    full_env = dict(env or {}) if exact_env else ({**os.environ, **env} if env else None)
    pipe = subprocess.PIPE
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            stdout=None if passthrough == "all" else pipe,
            stderr=pipe if passthrough == "none" else None,
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
    if coded:
        return result.returncode, f"{result.stdout or ''}{result.stderr or ''}"
    if result.returncode not in ok:
        err, out = result.stderr, result.stdout
        words = (err.decode("utf-8", "replace") if isinstance(err, bytes) else err).strip()
        if not words:
            words = (out.decode("utf-8", "replace") if isinstance(out, bytes) else out).strip()
        raise GitError(
            f"`{shlex.join(argv)}` failed in {cwd}: {words or f'exit {result.returncode}'}"
        )
    return result.stdout


# The patch-id an approval is pinned to (spec 2026-11-19-wave-merge-queue R12, §E): porcelain
# `git diff` with every setting that shapes its output pinned on the command line, so the id
# is the same on every host. `-c` pins what has no flag; the flags override the rest.
PATCH_ID_DIFF: Final[tuple[str, ...]] = (
    "git",
    "-c", "diff.noprefix=false",
    "-c", "diff.mnemonicPrefix=false",
    "-c", "diff.relative=false",
    "-c", "diff.suppressBlankEmpty=false",
    "-c", "core.quotePath=true",
    "diff", "--binary", "--full-index", "--no-color", "--no-ext-diff", "--no-textconv",
    "--no-renames", "--diff-algorithm=myers", "--unified=3", "--inter-hunk-context=0",
    "--indent-heuristic", "--src-prefix=a/", "--dst-prefix=b/", "--no-relative",
    "--ignore-submodules=none", "--submodule=short", "-O/dev/null",
)  # fmt: skip
PATCH_ID: Final[tuple[str, ...]] = (
    "git", "-c", "patchid.stable=false", "-c", "patchid.verbatim=true", "patch-id", "--verbatim",
)  # fmt: skip
# `GIT_DIFF_OPTS` may set the context width; this pins it to the flag's own value.
PATCH_ID_ENV: Final[dict[str, str]] = {"GIT_DIFF_OPTS": "--unified=3"}


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


def _head_branch(worktree: Path) -> str | None:
    """The branch *worktree* has checked out, or None when its HEAD is detached.
    `symbolic-ref`, not `rev-parse --abbrev-ref`: the latter says `heads/main` when a
    tag `main` also exists."""
    try:
        out = git(["symbolic-ref", "-q", "HEAD"], worktree).strip()
    except GitError:  # non-zero: HEAD is detached
        return None
    return out.removeprefix("refs/heads/") or None


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


# ------------------------------------------------- the state ref (a branch, CAS-pushed)

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


FETCHED_PREFIX = "refs/fr/fetched/"
"""Where a fetched state ref is kept in the local clone: never under `refs/heads/`, so the
workspace's `git branch` never lists the state branch it fetched."""


def fetched_ref(ref: str) -> str:
    """The local ref a fetch of the remote's fully qualified *ref* is kept in:
    `refs/heads/fr-triage/x` -> `refs/fr/fetched/heads/fr-triage/x`."""
    return FETCHED_PREFIX + ref.removeprefix("refs/")


def fetch_ref(cwd: Path, remote: str, ref: str) -> str | None:
    """Fetch *ref* from *remote* into `fetched_ref(ref)` here (forced: the remote is the
    truth), then read the sha that local ref now holds (p3-r5: one round trip, no window
    between reading a sha and fetching it). None when the remote has no such ref; a local
    copy left from an earlier fetch is then dropped, so it is never mistaken for the
    remote's."""
    local = fetched_ref(ref)
    try:
        git(["fetch", "--quiet", "--no-tags", remote, f"+{ref}:{local}"], cwd)
    except GitError as exc:
        if _NO_REMOTE_REF not in str(exc):
            raise
        git_ok(["update-ref", "-d", local], cwd)
        return None
    return git(["rev-parse", "--verify", "--quiet", f"{local}^{{commit}}"], cwd).strip() or None


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


class PushRefusedError(GitError):  # noqa: N818 - beside StateRefConflict, a refusal
    """The remote refused a push for a reason that is not a stale lease: a permission
    (HTTP 403 through a proxy), a hook that declined it, a connection the remote hung up.
    The remote's ref did not move, and nobody else moved it either."""


_STALE_LEASE = "(stale info)"
"""git's own words when `--force-with-lease` finds the remote's ref is not the expected
one: `! [rejected] <sha> -> <ref> (stale info)`. A remote that refuses the push says
`! [remote rejected] ... (pre-receive hook declined)`, `RPC failed; HTTP 403` or `the
remote end hung up unexpectedly` instead; git exits 1 for all of them."""


def push_ref_cas(cwd: Path, remote: str, sha: str, ref: str, *, expected_old: str | None) -> bool:
    """Push *sha* to *ref* on *remote* only if the remote still has *expected_old* there
    (`--force-with-lease=<ref>:<old>`; None means the ref must not exist yet). Whether
    it landed: False when the lease was stale, i.e. the remote's ref is not
    *expected_old* any more.

    Any other failure is the remote refusing the push (`PushRefusedError`, git's words
    carried): git exits 1 both ways, so the lease is told apart by git's `(stale info)`
    or, failing that, by reading the remote's ref again: a ref that is not *expected_old*
    is a lost race, one that still is (or that cannot even be read) was refused."""
    lease = f"--force-with-lease={ref}:{expected_old or ''}"
    try:
        git(["push", "--quiet", "--no-verify", lease, remote, f"{sha}:{ref}"], cwd)
    except GitError as exc:
        if _STALE_LEASE in str(exc):
            return False
        try:
            now = remote_ref(cwd, remote, ref)
        except GitError:
            raise PushRefusedError(str(exc)) from exc
        if now != expected_old:
            return False
        raise PushRefusedError(str(exc)) from exc
    return True


class LeaseLostError(GitError):  # noqa: N818 - a lost race, beside PushRefusedError
    """A leased push found a ref the remote holds at another sha than the lease named
    (git's `(stale info)`): another writer moved it. With `--atomic` no ref moved."""


class TransientPushError(GitError):  # noqa: N818 - beside PushRefusedError, a non-refusal
    """A push that failed in transport (a timeout, a hang-up, DNS, a server 5xx) and whose
    refs the remote does not hold: nobody refused it, so nothing is held for it; the
    caller tries again next pass (l-errors-r1)."""


_TRANSPORT = re.compile(
    r"timed out|hung up|could not resolve host|could not read from remote|failed to connect|"
    r"connection (?:reset|refused|timed out|closed)|network is unreachable|early eof|"
    r"temporary failure|ssl|HTTP 5\d\d|unexpected disconnect|broken pipe",
    re.I,
)


def is_transport_failure(words: str) -> bool:
    """Whether git's words read as a failed connection rather than a remote's refusal."""
    return "remote rejected" not in words and _TRANSPORT.search(words) is not None


class AtomicUnsupportedError(GitError):  # noqa: N818 - a refusal of the server's
    """The remote does not support `git push --atomic` (spec 2026-11-19-wave-merge-queue
    R10, R22): nothing was pushed, and there is no non-atomic fallback."""


_NO_ATOMIC = "does not support --atomic"
"""git's own words when the receiving end advertises no `atomic` capability."""


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


@dataclass(frozen=True)
class CheckoutFacts:
    """What `adopt --list` reads of an agent's working directory: the worktree's
    toplevel, `origin`'s URL and `owner/name` (None when it has none), the branch
    checked out there (None when detached), the default branch (None when
    `origin/HEAD` is unset) and the repository's main worktree."""

    toplevel: Path
    origin_url: str | None
    repo: str | None
    branch: str | None
    default: str | None
    main_worktree: Path


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

    @classmethod
    def facts(cls, cwd: Path) -> CheckoutFacts | None:
        """The facts of the checkout *cwd* sits in; None when it is no checkout. Only
        a missing toplevel is None: an `origin` or default branch that cannot be read
        is that field alone None."""
        if not cwd.is_dir():
            return None
        try:
            top = Path(git(["rev-parse", "--show-toplevel"], cwd).strip())
        except GitError:
            return None
        checkout = cls(top)
        try:
            url: str | None = checkout.origin_url()
        except GitError:
            url = None
        try:
            default: str | None = checkout.default_branch()
        except GitError:
            default = None
        try:
            main = checkout.main_worktree()
        except GitError:
            main = top.resolve()
        return CheckoutFacts(
            toplevel=top.resolve(),
            origin_url=url,
            repo=repo_of_url(url) if url else None,
            branch=checkout.head_branch(),
            default=default,
            main_worktree=main,
        )

    def origin_url(self) -> str:
        return git(["remote", "get-url", "origin"], self.path).strip()

    def origin_repo(self) -> str | None:
        return repo_of_url(self.origin_url())

    def default_branch(self) -> str:
        """`origin/HEAD`'s branch, which `git clone` records. A clone without it (a
        cloud session's, gh#1100) asks origin once and records the answer."""
        head = ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"]
        try:
            ref = git(head, self.path)
        except GitError:
            try:
                git(["remote", "set-head", "origin", "--auto"], self.path)
                ref = git(head, self.path)
            except GitError as exc:
                raise GitError(
                    f"cannot tell {self.path}'s default branch (origin/HEAD is unset, and "
                    f"origin did not say: {exc}); run `git remote set-head origin --auto` "
                    "there"
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

    def current_branch(self) -> str | None:
        """The branch checked out in the MAIN worktree, or None when HEAD is detached."""
        return _head_branch(self.main_worktree())

    def head_branch(self) -> str | None:
        """The branch checked out in THIS checkout's worktree, or None when detached."""
        return _head_branch(self.path)

    def dirty_paths(self) -> tuple[str, ...]:
        """The paths `git status --porcelain` reports in the MAIN worktree, tracked or
        untracked; empty when it is clean (default-branch adopt, R7)."""
        raw = git(["status", "--porcelain", "-z"], self.main_worktree()).split("\0")
        paths: list[str] = []
        skip = False
        for entry in raw:
            if skip:  # the source path of a rename or copy
                skip = False
                continue
            if len(entry) < 4:
                continue
            paths.append(entry[3:])
            skip = entry[0] in "RC"
        return tuple(paths)

    def unpushed(self, branch: str) -> tuple[str, ...]:
        """`<sha> <subject>` for each commit on local *branch* that `origin/<branch>`
        lacks, newest first, read in the main worktree (R7). Fetch first."""
        out = git(
            ["log", "--format=%h %s", f"origin/{branch}..refs/heads/{branch}"],
            self.main_worktree(),
        )
        return tuple(line for line in out.splitlines() if line)

    def ahead(self, ref: str, base: str) -> int:
        """How many commits *ref* has that *base* lacks (`base..ref`)."""
        out = git(["rev-list", "--count", f"{base}..{ref}"], self.main_worktree())
        return int(out.strip() or "0")

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

    def changed_paths(self, ref: str, head: str) -> frozenset[str]:
        """The paths *head* changed since it forked from *ref* (`ref...head`)."""
        out = git(["diff", "--name-only", "--no-renames", "-z", f"{ref}...{head}"], self.path)
        return frozenset(p for p in out.split("\0") if p)

    def changed_status(self, ref: str, head: str) -> frozenset[str]:
        """What *head* changed since it forked from *ref*, as `<status>\t<path>` (A, M, D;
        renames split into a D and an A): the collected close-out's recorded file set."""
        out = git(["diff", "--name-status", "--no-renames", "-z", f"{ref}...{head}"], self.path)
        parts = [p for p in out.split("\0") if p]
        return frozenset(f"{parts[i][0]}\t{parts[i + 1]}" for i in range(0, len(parts) - 1, 2))

    def patch_id(self, head: str, ref: str) -> str:
        """*head*'s patch-id against its merge base with *ref* (spec 2026-11-19-wave-merge-queue
        R12): `PATCH_ID_DIFF` from the merge base to *head*, piped to `PATCH_ID`, so
        whitespace and binary content count and no host configuration (prefixes, renames,
        context, algorithm, order, textconv, an external diff) moves it. The first field of
        the output; "" for an empty diff, which `git patch-id` answers with nothing."""
        base = git(["merge-base", head, ref], self.path).strip()
        diff: bytes = _run(
            [*PATCH_ID_DIFF, base, head], self.path, text=False, timeout=GIT_TIMEOUT_SECONDS,
            env=PATCH_ID_ENV,
        )  # fmt: skip
        if not diff:
            return ""
        out: bytes = _run(
            list(PATCH_ID), self.path, text=False, stdin=diff, timeout=GIT_TIMEOUT_SECONDS,
            env=PATCH_ID_ENV,
        )  # fmt: skip
        fields = out.decode("ascii", "replace").split()
        return fields[0] if fields else ""

    def clean_succession(self, approved: str, head: str) -> bool:
        """Whether *head* follows *approved* only by moves that cannot change the PR's diff
        (spec 2026-11-19-wave-merge-queue R12, l-security-r1): *approved* is an ancestor of
        *head*, and every commit on the first-parent chain between them is either an empty
        non-merge commit or a two-parent merge whose tree equals the automatic merge of its
        parents (`git merge-tree --write-tree`, clean). A hand-edited merge resolution, a
        commit that changes a tree, or a head that does not descend from *approved* is not.
        `git patch-id` ignores hunk positions, so this is what keeps a moved hunk from
        passing for the approved one. Raises `GitError` when git cannot run."""
        if approved == head:
            return True
        if not git_ok(["merge-base", "--is-ancestor", approved, head], self.path):
            return False
        chain = git(
            ["rev-list", "--first-parent", "--parents", "--topo-order", f"{approved}..{head}"],
            self.path,
        ).splitlines()
        if not chain:
            return False
        oldest = chain[-1].split()
        if len(oldest) < 2 or oldest[1] != approved:
            return False  # approved is reached only through a merge's second parent
        for line in chain:
            commit, *parents = line.split()
            tree = git(["rev-parse", f"{commit}^{{tree}}"], self.path).strip()
            if len(parents) == 1:
                if tree != git(["rev-parse", f"{parents[0]}^{{tree}}"], self.path).strip():
                    return False
            elif len(parents) == 2:
                code, out = _run(
                    ["git", "merge-tree", "--write-tree", "--no-messages", *parents],
                    self.path, coded=True, timeout=GIT_TIMEOUT_SECONDS,
                )  # fmt: skip
                if code != 0 or out.split() == [] or out.split()[0] != tree:
                    return False
            else:
                return False
        return True

    def refresh_remote_branch(self, branch: str) -> None:
        """Fetch origin's *branch* into `origin/<branch>` now (forced: the remote is the
        truth), for a read that must not use a stale copy (wave-merge-queue R12)."""
        git(["fetch", "--quiet", "--no-tags", "origin",
             f"+refs/heads/{branch}:refs/remotes/origin/{branch}"], self.path)  # fmt: skip

    def commits_since(self, ref: str, head: str) -> tuple[str, ...]:
        """The commits on *ref*..*head*, newest first."""
        return tuple(git(["rev-list", f"{ref}..{head}"], self.path).split())

    # ------------------------------------------------------ the wave driver

    def fast_forward(self, *, switch: bool = False) -> None:
        """Fetch, then fast-forward the checked-out default branch to origin's
        (wave-driver §B). A clone on any other branch is refused by name: the
        driver never switches an operator's branch for them. With *switch* — a clone
        that is the driver's own, a cloud session's (gh#1100) — a clean one on another
        branch or a detached HEAD is checked out on the default branch first."""
        self.fetch()
        default = self.default_branch()
        current = git(["rev-parse", "--abbrev-ref", "HEAD"], self.path).strip()
        if current != default and switch:
            if git(["status", "--porcelain", "--untracked-files=no"], self.path).strip():
                raise GitError(
                    f"{self.path} is on {current} with local changes, so the driver does "
                    f"not check out {default} there; commit or discard them"
                )
            git(["checkout", "--quiet", default], self.path)  # tracks origin's when new
            current = default
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

    def reach_commit(self, sha: str, branch: str) -> bool:
        """Whether this clone has commit *sha*, fetching origin's *branch* once when it
        does not (a PR head the clone never saw). A failed fetch is no commit."""
        if not sha:
            return False
        if has_commit(self.path, sha):
            return True
        try:
            fetch_ref(self.path, "origin", f"refs/heads/{branch}")
        except GitError:
            return False
        return has_commit(self.path, sha)

    def list_dir(self, ref: str, directory: str) -> list[str]:
        """The names of the entries directly under *directory* at *ref*; empty when it
        is absent there."""
        if not self.exists_at(ref, directory):
            return []
        out = git_bytes(["ls-tree", "-z", "--name-only", f"{ref}:{directory}"], self.path)
        return sorted(os.fsdecode(n) for n in out.split(b"\0") if n)

    def snapshot_paths(self, ref: str, paths: tuple[str, ...], dest: Path) -> None:
        """Write *paths* (files or directories) as they are at *ref* into *dest*, a
        fresh git repo with this clone's origin, so a reader that resolves a repo's
        declarations reads the default branch's, never this working tree's (review
        rg-5). Nothing in this clone changes."""
        git(["init", "--quiet", str(dest)], self.path)
        git(["remote", "add", "origin", self.origin_url()], dest)
        # `-z`: names unquoted, so a non-ASCII path is copied, not skipped as unknown. The
        # mode is kept: an executable at *ref* (a repo's `.fr/candidate-install`) is
        # executable in the copy, so a reader that asks whether it can run it is answered
        # as on the branch (p4-r7).
        listed = git_bytes(["ls-tree", "-r", "-z", ref, "--", *paths], self.path)
        for record in (r for r in listed.split(b"\0") if r):
            meta, _, raw = record.partition(b"\t")
            name = os.fsdecode(raw)
            content = self.show_bytes(ref, name)  # any file, binary included (gh#889)
            if content is None:
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            if meta.split(b" ")[0] == b"100755":
                target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        # Make the copy a coherent repo whose default branch IS the snapshot: the settings
        # loader reads policy from the default ref's commit and refuses a remote whose
        # default it cannot resolve (spec 2026-11-04-repo-feature-settings R2).
        git(["add", "-A", "--force"], dest)
        git(
            [
                "-c", "user.name=fr", "-c", "user.email=fr@fr.invalid",
                "-c", "commit.gpgsign=false",
                "commit", "--quiet", "--allow-empty", "--no-verify", "-m", f"snapshot of {ref}",
            ],
            dest,
        )  # fmt: skip
        git(["update-ref", "refs/remotes/origin/main", "HEAD"], dest)
        git(["symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main"], dest)

    # ------------------------------------------------ the wave merge queue

    def push_leased(
        self,
        refspecs: Sequence[tuple[str, str]],
        leases: Mapping[str, str | None],
        *,
        atomic: bool,
    ) -> None:
        """Push each `(sha, ref)` of *refspecs* to origin, every ref leased on the sha
        *leases* names for it (None: the ref must not exist yet), as ONE push; *atomic*
        makes it all or nothing (spec 2026-11-19-wave-merge-queue R4, R10).

        A lease the remote's ref no longer matches raises `LeaseLostError`; a remote that
        cannot push atomically `AtomicUnsupportedError`; any other refusal (a protection
        rule, a hook, a permission) `PushRefusedError` with git's own words, which carry
        the remote's (a GitHub `GH006` or `GH013`, say). Any other failure reads the remote's
        refs again: they hold exactly the pushed shas, the push landed (no error); they do
        not and git's words read as a failed connection, `TransientPushError`."""
        if not refspecs:
            return
        argv = ["push", "--quiet", "--no-verify", *(["--atomic"] if atomic else [])]
        for _sha, ref in refspecs:
            argv.append(f"--force-with-lease={ref}:{leases.get(ref) or ''}")
        argv += ["origin", *(f"{sha}:{ref}" for sha, ref in refspecs)]
        try:
            git(argv, self.path)
        except GitError as exc:
            words = str(exc)
            if _NO_ATOMIC in words:
                raise AtomicUnsupportedError(words) from exc
            if _STALE_LEASE in words:
                raise LeaseLostError(words) from exc
            # l-errors-r1: a refusal is told from a transport failure by the remote's refs
            try:
                held = {ref: remote_ref(self.path, "origin", ref) for _sha, ref in refspecs}
            except GitError:
                if is_transport_failure(words):
                    raise TransientPushError(words) from exc
                raise PushRefusedError(words) from exc
            if all(held[ref] == sha for sha, ref in refspecs):
                return  # the push landed and the connection died on the way back
            if is_transport_failure(words):
                raise TransientPushError(words) from exc
            raise PushRefusedError(words) from exc

    def remote_sha(self, ref: str) -> str | None:
        """The sha origin holds at the fully qualified *ref* now, None when none."""
        return remote_ref(self.path, "origin", ref)

    def fetch_remote_ref(self, ref: str) -> str | None:
        """Fetch origin's fully qualified *ref* (forced: the remote is the truth) and return
        the sha it holds, None when origin has none: the hold's read (R17)."""
        return fetch_ref(self.path, "origin", ref)

    def ref_commit(self, parent: str, message: str, *, previous: str | None = None) -> str:
        """A commit of *parent*'s tree on *parent* with *message* and fr's fixed identity,
        written without touching HEAD or any ref: a hold (R17). With *previous* (the hold
        commit the ref holds now) it is a merge commit whose SECOND parent is *previous*, so
        the push that replaces the hold is a fast-forward and a remote that refuses
        non-fast-forward pushes accepts it; the first parent keeps its meaning."""
        argv = ["git", "commit-tree", f"{parent}^{{tree}}", "-p", parent]
        if previous is not None and previous != parent:
            argv += ["-p", previous]
        out: str = _run(argv + ["-m", message], self.path, env=_REF_IDENTITY,
                        timeout=GIT_TIMEOUT_SECONDS)  # fmt: skip
        return out.strip()

    def release_commits(self, base: str, head: str) -> tuple[tuple[str, str], ...]:
        """`(sha, subject)` of every `release: v...` commit in *base*..*head*, oldest first:
        the releases cut while a queue was open (R27)."""
        out = git(["log", "--reverse", "--format=%H\t%s", "--grep=^release: v", f"{base}..{head}"],
                  self.path)  # fmt: skip
        rows = (line.partition("\t") for line in out.splitlines() if line)
        return tuple((sha, subject) for sha, _, subject in rows)

    def tree_of(self, rev: str) -> str:
        """The tree *rev* holds (`<rev>^{tree}`)."""
        return git(["rev-parse", f"{rev}^{{tree}}"], self.path).strip()

    def has_commit(self, sha: str) -> bool:
        return has_commit(self.path, sha)

    def merge_base(self, one: str, two: str) -> str:
        return git(["merge-base", one, two], self.path).strip()

    def parents(self, sha: str) -> tuple[str, ...]:
        """*sha*'s parents, first parent first."""
        return tuple(git(["rev-list", "--parents", "-1", sha], self.path).split()[1:])

    def message(self, sha: str) -> str:
        """*sha*'s full commit message."""
        return git(["log", "-1", "--format=%B", sha], self.path).rstrip("\n")

    def replayed(self, base: str, head: str) -> tuple[str, ...]:
        """The non-merge commits of *base*..*head*, oldest first: what a rebase replays."""
        return tuple(git(["rev-list", "--reverse", "--no-merges", f"{base}..{head}"],
                         self.path).split())  # fmt: skip

    def has_merges(self, base: str, head: str) -> bool:
        """*base*..*head* holds a merge commit: what `rebase` would not replay (p3-r9)."""
        return bool(git(["rev-list", "--merges", "-1", f"{base}..{head}"], self.path).strip())

    def diff_paths(self, one: str, two: str) -> tuple[str, ...]:
        """The paths whose content differs between commits (or trees) *one* and *two*."""
        out = git(["diff", "--name-only", "--no-renames", "-z", one, two], self.path)
        return tuple(p for p in out.split("\0") if p)

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

    def abort_merge(self) -> None:
        git(["merge", "--abort"], self.path)

    def read(self, file: str) -> str | None:
        target = self.path / file
        return target.read_text(encoding="utf-8") if target.is_file() else None

    def run(self, command: str, **fields: str) -> None:
        run_declared(command, self.path, **fields)

    def stage(self, version_files: Sequence[str]) -> None:
        """Stage tracked changes plus untracked files matching the declared
        *version_files* globs, never anything else (review r3-f7)."""
        git(["add", "--update"], self.path)
        untracked = git(["ls-files", "-z", "--others", "--exclude-standard"], self.path)
        declared = [
            p
            for p in untracked.split("\0")
            if p and any(fnmatch.fnmatch(p, g) for g in version_files)
        ]
        if declared:
            git(["add", "--", *declared], self.path)

    # ------------------------------------ the wave merge queue's combinations

    def take_ours(self, paths: list[str]) -> None:
        """Resolve *paths* to the side being built on (HEAD), so no file keeps conflict
        markers: the combination's, when a queue entry is merged into it."""
        git(["checkout", "--ours", "--", *paths], self.path)
        git(["add", "--", *paths], self.path)

    def write_tree(self) -> str:
        """The tree the index holds now."""
        return git(["write-tree"], self.path).strip()

    def commit_tree(
        self, tree: str, parents: Sequence[str], message: str, *, date: str | None = None
    ) -> str:
        """A commit of *tree* on *parents* with *message* (the clone's identity), written
        without touching HEAD; *date* (`@<epoch> +0000`) pins both its dates."""
        argv = ["commit-tree", tree, "-m", message]
        for parent in parents:
            argv += ["-p", parent]
        env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date} if date else None
        out: str = _run(["git", *argv], self.path, env=env, timeout=GIT_TIMEOUT_SECONDS)
        return out.strip()

    def commit_date(self, sha: str) -> int:
        """*sha*'s committer time, in seconds since the epoch."""
        return int(git(["log", "-1", "--format=%ct", sha], self.path).strip())

    def cherry_pick(self, sha: str) -> list[str]:
        """Replay *sha* onto HEAD, committing it; the conflicted paths ([] if none), with
        the pick left in progress for `continue_pick` or `abort_pick`. rerere is off, as
        for `merge`."""
        argv = ["-c", "rerere.enabled=false", "-c", "merge.directoryRenames=false",
                "cherry-pick", "--allow-empty", "--keep-redundant-commits", sha]  # fmt: skip
        clean = git_ok(argv, self.path)
        conflicted = git(["diff", "--name-only", "--diff-filter=U"], self.path).split()
        if not clean and not conflicted:
            raise GitError(f"`git cherry-pick {sha}` failed in {self.path} without a conflict")
        return conflicted

    def continue_pick(self) -> None:
        git(["-c", "core.editor=true", "cherry-pick", "--continue"], self.path)

    def abort_pick(self) -> None:
        git_ok(["cherry-pick", "--abort"], self.path)

    def amend(self, version_files: Sequence[str]) -> str:
        """Fold the staged and tracked changes (and *version_files*) into HEAD, keeping its
        message; the new HEAD."""
        self.stage(version_files)
        git(["commit", "--no-verify", "--quiet", "--amend", "--no-edit", "--allow-empty"],
            self.path)  # fmt: skip
        return self.head()

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

    # ------------------------------------ the collected close-out (exit-gates §E)

    def head(self) -> str:
        return git(["rev-parse", "HEAD"], self.path).strip()

    def start_branch(self, branch: str) -> None:
        """Put this worktree on a local *branch* at its HEAD (replacing a stale one of that
        name), so the close-out's own verbs commit on a branch, never a detached HEAD."""
        git(["switch", "--quiet", "-C", branch], self.path)

    def run_fr(self, args: list[str]) -> tuple[int, str]:
        """Run THIS `fr` (`python -m fr` of the running interpreter, never one found on
        PATH) with *args* in this worktree: `(exit code, its words)`. The collected
        close-out's verbs: verify-merge, closeout outcome, archive. An argument list,
        never a shell string."""
        code, out = _run(fr_argv(*args), self.path, coded=True, env=safe_fr_env(), exact_env=True)
        return int(code), str(out)

    def stale_artifacts(self) -> list[str]:
        """The live artifacts of this worktree a registered migration would move, as
        repo-relative paths (`fr.artifacts.runner.plan_migrations`, read-only): what the
        collected close-out's `fr migrate artifacts --path` then migrates (R16)."""
        from fr.artifacts.runner import plan_migrations

        seen: dict[str, None] = {}
        for action in plan_migrations(self.path):
            if not action.is_repair:
                seen[action.path.relative_to(self.path).as_posix()] = None
        return list(seen)

    def archive_moves(self, branch: str, default_ref: str) -> list[str] | None:
        """The live artifact paths `fr archive --branch <branch>` moves in this worktree: the
        archive's own classification (`fr.closeout.branch_artifacts`) of the paths *branch*
        changed against *default_ref*, over the same refs and recorded start the archive
        reads. A plan is its folder. None when the branch has no refs this clone can fetch
        (the archive then holds the batch on its own); a read that fails raises `GitError`
        carrying the cause (l-errors-r11)."""
        from fr.closeout import branch_artifacts
        from fr.isolation.local import (
            branch_changed_paths,
            recorded_start,
            resolve_branch_refs,
            subprocess_runner,
        )
        from fr.isolation.types import IsolationError

        remote = default_ref.split("/", 1)[0]
        try:
            refs, fetched = resolve_branch_refs(subprocess_runner, self.path, branch, remote)
            if not refs or not fetched:
                return None
            start = recorded_start(self.path, branch)
            changed = sorted({p for ref in refs for p in branch_changed_paths(
                subprocess_runner, self.path, ref, default_ref, start)})  # fmt: skip
        except (IsolationError, GitError, OSError) as exc:
            raise GitError(f"cannot read what {branch}'s archive moves: {exc}") from exc
        return [a.path.as_posix() for a in branch_artifacts(self.path, changed)]

    def reset_hard(self, sha: str) -> None:
        """Back to *sha*, every change and untracked file since gone: a held batch moves
        nothing (R15)."""
        git(["reset", "--hard", "--quiet", sha], self.path)
        git(["clean", "-fdq"], self.path)

    def squash_all(self, base: str, message: str) -> str | None:
        """Everything since *base* (commits, staged and unstaged changes, new files) as ONE
        commit on *base*; the new head, or None when nothing changed. `--all` is right
        here, unlike `commit_all`: the worktree is fresh and only fr's own verbs wrote in
        it, and an archive's moves are new files. With the close-out's migration commit
        (R16) as *base*, only the archive is squashed and the migration commit stays."""
        git(["add", "--all"], self.path)
        git(["reset", "--soft", "--quiet", base], self.path)
        if git_ok(["diff", "--cached", "--quiet"], self.path):
            return None
        git(["commit", "--no-verify", "--quiet", "-m", message], self.path)
        return self.head()

    def rebase_onto(self, new_base: str, upstream: str) -> None:
        """Replay only the commits after *upstream* onto *new_base* (`git rebase --onto`):
        the DevOps stage's ops branch, cut from a PR head that was then squash-merged,
        keeps only its own evidence commits (spec 2026-10-22-fr-ops R15). A conflict
        aborts the rebase and raises, leaving the branch where it was."""
        argv = ["rebase", f"--onto={new_base}", "--end-of-options", upstream]
        if git_ok(argv, self.path):
            return
        git_ok(["rebase", "--abort"], self.path)
        raise GitError(f"`git rebase --onto {new_base} {upstream}` failed in {self.path}")

    def push(self, branch: str, *, force: bool = False) -> None:
        """Push HEAD to *branch*; *force* overwrites it, for a branch fr owns (the
        driver's export branch, which a pass that died may have left behind)."""
        argv = ["push", *(["--force"] if force else []), "origin", f"HEAD:refs/heads/{branch}"]
        git(argv, self.path)


def run_this_fr(args: list[str], cwd: Path, *, terminal: bool = False) -> tuple[int, str]:
    """THIS `fr` (`python -m fr` of the running interpreter) in *cwd*: `(exit, stdout)`,
    its stderr passed through to the operator. *terminal*: every stream stays the
    operator's and nothing is captured (`(exit, "")`), for a command that asks there.
    The DevOps stage's host commands (spec 2026-10-22-fr-ops R15)."""
    code, out = _run(
        fr_argv(*args),
        cwd,
        coded=True,
        passthrough="all" if terminal else "stderr",
        env=safe_fr_env(),
        exact_env=True,
    )
    return code, "" if terminal else out


def run_publish(argv: list[str], cwd: Path, timeout: float) -> str | None:
    """Run the scope's `publish` argument list as is, with no shell (triage-claims R14), in
    *cwd* (the scope's state directory), inheriting the caller's full environment. None
    when it exited 0, else the cause on one line (`_run`'s words). Never raises."""
    try:
        _run(argv, cwd, timeout=timeout)
    except GitError as exc:
        return " ".join(str(exc).split())
    return None
