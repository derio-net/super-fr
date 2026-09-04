"""The atomic commit — *only* the migrated paths (spec §3.D).

`git add -- <exact paths the migration rewrote>` then `git commit -m <msg> --
<those same paths>`. Never `add -A`, never a stash cycle.

In-flight work is a dirty tree by definition — that is the case this exists
for. Refusing until the tree is clean would block precisely the sessions it has
to serve, and a stash/unstash risks a pop conflict on top of work the operator
has not saved anywhere. Path-scoped staging leaves every unrelated edit exactly
where it was.

Three `git` mistakes this module is shaped to avoid, all of which pass a
clean-tree test:

1. **`git add -A`** sweeps the operator's unrelated *modified* files into the
   commit.
2. **A plain `git commit -m`** records the whole index, so it sweeps in an
   unrelated file the operator had *staged* before running the command — even
   if the staging was path-scoped. The commit itself has to carry the pathspec,
   which makes git build the tree from HEAD plus those paths and leave the rest
   of the index untouched.
3. **`git add -- <a file the operator is editing>`** stages the *whole* file,
   migration and half-typed edit together. Path-scoping is not enough when the
   path is one the operator has open: the co-edited artifact is the case this
   module most has to get right, and `uncommitted_veto` below is how — the
   runner is told not to migrate that file at all, and the gate reports it.

And one that no pathspec can make safe: **committing on the default branch.**
`on_default_branch` refuses there. This runs automatically, before an unrelated
command; a commit on `main` is a commit the operator must notice and undo, and
in this repo's own doctrine the base clone is not where work happens.

Everything here is fail-closed. This runs automatically, before a command the
operator typed for some other reason, and it writes to git history: every
precondition is asserted rather than assumed to have been checked by the
caller, and any doubt returns a `CommitOutcome` that did nothing.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fr.artifacts.runner import MigrationReport, PlannedAction


@dataclass(frozen=True)
class CommitOutcome:
    """What the commit step did, and why.

    Never raises for an expected outcome — "not a git repo" and "nothing to
    commit" are ordinary answers, not errors. The caller reports `reason` and
    carries on with the command the operator actually typed.
    """

    committed: bool
    reason: str
    paths: tuple[Path, ...] = ()
    message: str | None = None


GIT_TIMEOUT_SECONDS = 30.0
"""Wall-clock cap on every git subprocess here (review r5-c5).

This layer runs at CLI entry, before the command the operator typed. A
`pre-commit` hook that waits on the network, a `gpg` signing prompt with no
agent, or an NFS mount that has gone away turns "fr status" into a process
that never returns and prints nothing. A timeout converts all of those into a
refusal that names what hung.
"""

_GIT_ENV: dict[str, str] = {
    # Force the C locale: this module PARSES git's stderr to tell "not a git
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
class GitContext:
    """Everything the commit step needs to know about the repo, read ONCE.

    Built by `git_context`, which is the only function here that shells out
    more than incidentally. Before it (review r5-c2) each predicate ran its own
    subprocesses and each swallowed failure independently, so "git is not on
    PATH" and "this directory has dubious ownership" both looked exactly like
    "not a git repository": the default-branch guard evaporated, the
    uncommitted-file veto returned an empty set, the reason string said "is not
    a git repository" about a repo that plainly was one, and — worst — from a
    subdirectory `resolve_repo_root` fell back to the cwd and the gate migrated
    a tree it had never established the state of.
    """

    toplevel: Path
    branch: str | None
    """`None` means a DETACHED HEAD. Never "no repo" — that is `NoRepo`."""
    default_branch: str | None
    """`None` only when the repo genuinely declares none (no remote, no
    matching local branch). When a remote exists and nothing resolves,
    `git_context` returns a refusal instead of guessing."""
    dirty: frozenset[Path]
    has_head: bool


@dataclass(frozen=True)
class NoRepo:
    """`root` is genuinely not inside a git repository. An ordinary answer."""

    root: Path


@dataclass(frozen=True)
class GitRefusal:
    """git state could not be established. Fail CLOSED: never act on this."""

    reason: str


GitState = GitContext | NoRepo | GitRefusal


def _git(
    root: Path, *args: str, timeout: float = GIT_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    """One git call, C-locale, prompt-free, time-boxed.

    Raises `GitUnavailableError` when git could not be RUN or did not finish;
    a non-zero exit is returned normally, because "this ref does not exist" is
    an answer.
    """
    try:
        return subprocess.run(
            ["git", *args],
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


_NOT_A_REPO_MARKERS = (
    "not a git repository",
    "not a working tree",
)
"""Substrings git uses for the ONE failure that means "there is no repo here".

Matched against C-locale stderr (see `_GIT_ENV`). Everything else — dubious
ownership, a corrupt object store, a permission error — is a refusal.
"""

_SCOPE_ENV_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")


def _scope_override() -> str | None:
    for name in _SCOPE_ENV_VARS:
        if os.environ.get(name):
            return name
    return None


def _classify_failure(what: str, done: subprocess.CompletedProcess[str]) -> NoRepo | GitRefusal:
    stderr = (done.stderr or "").strip()
    if any(marker in stderr.lower() for marker in _NOT_A_REPO_MARKERS):
        return NoRepo(root=Path())
    return GitRefusal(reason=f"git could not answer `{what}`: {stderr or 'no output'}")


def _remote_name(root: Path) -> str | None | GitRefusal:
    """Which remote speaks for "the default branch" (review r5-c3 / r5-e6).

    `origin` is a convention, not a rule. `checkout.defaultRemote` is git's own
    answer when there are several; a single remote of any name is unambiguous;
    two unnamed-by-config remotes are a genuine ambiguity and this module
    refuses rather than picking one — it is about to decide whether an
    automatic commit is allowed.
    """
    configured = _git(root, "config", "--get", "checkout.defaultRemote")
    if configured.returncode == 0 and configured.stdout.strip():
        return configured.stdout.strip()
    listed = _git(root, "remote")
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


def _ref_exists(root: Path, ref: str) -> bool:
    return _git(root, "rev-parse", "--verify", "--quiet", ref).returncode == 0


_WELL_KNOWN_DEFAULTS = ("main", "master", "trunk", "develop")
"""Candidate trunk names, remote-tracking first, then local. Last resort."""


def _default_branch(root: Path, *, unborn: bool) -> str | None | GitRefusal:
    """The repository's default branch — or a refusal rather than a guess.

    Four sources, in this order, each answering a strictly weaker question
    than the one above (review r5-c3, which found the previous order wrong in
    two ordinary configurations):

    1. `<remote>/HEAD` — what the HOST says, and the only authority. Ignored
       when it points at a ref that no longer exists (a deleted branch leaves
       a dangling symbolic-ref behind).
    2. `refs/remotes/<remote>/{main,master,trunk,develop}` — a remote WITHOUT
       a HEAD. This has to beat the two local sources: a repo whose trunk is
       `trunk` and which also has a local `main` was previously reported as
       `main`, so an automatic commit landed on the real trunk.
    3. `init.defaultBranch`, **only if that branch exists locally**. Trusted
       unconditionally before, so a global `init.defaultBranch = main` in a
       repo that only has `master` reported `main` — and the guard that is
       supposed to refuse on the default branch let a commit onto `master`.
    4. Local well-known names.

    When a remote exists and none of the four resolves, this REFUSES. The
    caller is deciding whether to commit automatically; "I could not tell
    which branch is protected" must never read as "none is".
    """
    remote = _remote_name(root)
    if isinstance(remote, GitRefusal):
        return remote

    if remote is not None:
        head = _git(root, "symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD")
        if head.returncode == 0 and head.stdout.strip():
            named = head.stdout.strip().removeprefix(f"{remote}/")
            # A branch with a `/` in it (`release/main`) survives this: only the
            # remote prefix is stripped, and only once.
            if named and _ref_exists(root, f"refs/remotes/{remote}/{named}"):
                return named
        for name in _WELL_KNOWN_DEFAULTS:
            if _ref_exists(root, f"refs/remotes/{remote}/{name}"):
                return name

    configured = _git(root, "config", "--get", "init.defaultBranch")
    if configured.returncode == 0 and configured.stdout.strip():
        name = configured.stdout.strip()
        # `unborn`: a freshly `git init`ed repo has no refs at all, so "does
        # the branch exist" cannot be asked. The configured name IS the branch
        # HEAD points at, so it is the default by construction.
        if unborn or _ref_exists(root, f"refs/heads/{name}"):
            return name

    for name in _WELL_KNOWN_DEFAULTS:
        if _ref_exists(root, f"refs/heads/{name}"):
            return name

    if remote is not None:
        return GitRefusal(
            reason=(
                f"{root} has a remote ({remote}) but fr could not determine its default "
                f"branch: no {remote}/HEAD, no {remote}/<well-known> branch, and no local "
                "branch matching one. Run `git remote set-head "
                f"{remote} --auto`."
            )
        )
    return None


def _dirty_paths(toplevel: Path) -> frozenset[Path]:
    """Every path git reports as changed — staged, unstaged or untracked.

    Raises `GitUnavailableError` on a non-zero exit (review r5-c2). Returning an
    empty set there silently disarmed the co-edited-artifact veto: the gate
    would then happily `git add` a file the operator was mid-edit in.
    """
    done = _git(toplevel, "status", "--porcelain", "-z", "--untracked-files=all")
    if done.returncode != 0:
        raise GitUnavailableError(f"`git status` failed: {done.stderr.strip() or 'no output'}")
    # `-z` entries are `XY <path>` with no quoting; a rename or copy emits the
    # ORIGINAL path as the NEXT field, and both ends of the move count as
    # touched.
    out: set[Path] = set()
    fields = [f for f in done.stdout.split("\0") if f]
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        code, rel = entry[:2], entry[3:]
        # `"R" in code`, not `code[0] in "RC"` (review r5-c5): a rename that is
        # staged-and-then-modified reports as `" R"`/`"R "`/`"RM"`, and only the
        # last of those has the letter in position 0. Missing it left the
        # ORIGINAL path unconsumed, so the next loop pass read a PATH as a
        # status code — silently shifting every remaining entry.
        if ("R" in code or "C" in code) and i < len(fields):
            out.add((toplevel / fields[i]).resolve())
            i += 1
        out.add((toplevel / rel).resolve())
    return frozenset(out)


def git_context(root: Path) -> GitState:
    """Resolve toplevel, branch, default branch and dirty set — once, or refuse.

    THE fail-closed boundary of this module. Exactly three outcomes:

    - `GitContext` — git answered every question.
    - `NoRepo` — `root` is genuinely not in a repository. Ordinary; the caller
      migrates without committing.
    - `GitRefusal` — git could not answer. The caller must do nothing.

    A **linked worktree** (`.git` is a FILE, not a directory) is a first-class
    case, not an edge one: fr's own isolation workspace is exactly that, so
    every question here is asked through `git` rather than by looking for a
    `.git` directory (review r5-e6).
    """
    override = _scope_override()
    if override is not None:
        return GitRefusal(
            reason=(
                f"${override} is set, so git's idea of 'this repository' is not the "
                "directory fr is looking at. fr will not migrate or commit under an "
                f"overridden git scope — unset ${override}, or run "
                "`fr migrate artifacts --yes` yourself."
            )
        )

    try:
        inside = _git(root, "rev-parse", "--is-inside-work-tree")
        if inside.returncode != 0:
            outcome = _classify_failure("rev-parse --is-inside-work-tree", inside)
            return NoRepo(root=root) if isinstance(outcome, NoRepo) else outcome
        if inside.stdout.strip() != "true":
            return GitRefusal(
                reason=(
                    f"{root} is inside a bare git repository, which has no working tree "
                    "to migrate or commit into."
                )
            )

        top = _git(root, "rev-parse", "--show-toplevel")
        if top.returncode != 0 or not top.stdout.strip():
            outcome = _classify_failure("rev-parse --show-toplevel", top)
            return NoRepo(root=root) if isinstance(outcome, NoRepo) else outcome
        toplevel = Path(top.stdout.strip()).resolve()

        head = _git(toplevel, "symbolic-ref", "--quiet", "--short", "HEAD")
        branch = head.stdout.strip() or None if head.returncode == 0 else None
        has_head = _git(toplevel, "rev-parse", "--verify", "--quiet", "HEAD").returncode == 0
        default = _default_branch(toplevel, unborn=not has_head)
        if isinstance(default, GitRefusal):
            return default
        dirty = _dirty_paths(toplevel)
    except GitUnavailableError as e:
        # Deliberately does NOT say "not a git repository": that sentence was
        # printed about repos that plainly were one, and it is the message an
        # operator would act on by re-running somewhere else (review r5-c2).
        return GitRefusal(reason=f"fr could not establish git state for {root}: {e}")

    return GitContext(
        toplevel=toplevel,
        branch=branch,
        default_branch=default,
        dirty=dirty,
        has_head=has_head,
    )


# --- thin wrappers kept for callers that ask one question -----------------


def on_default_branch(root: Path) -> str | None:
    """The branch name when HEAD is the repository's default branch, else None.

    Thin over `git_context`, and deliberately lossy: it cannot express a
    refusal. `fr.artifacts.trigger` calls `git_context` directly for that
    reason; this remains for callers that only want the one boolean fact.
    """
    state = git_context(root)
    if not isinstance(state, GitContext) or state.branch is None:
        return None
    return state.branch if state.branch == state.default_branch else None


def uncommitted_paths(root: Path) -> frozenset[Path]:
    """Every path git reports as changed. Raises `GitUnavailableError` on failure.

    Raising is the fix (review r5-c2): returning an empty set on a git error
    turned "I cannot see your working tree" into "your working tree is clean",
    which is the single most dangerous possible default for a function whose
    output is a veto list.
    """
    state = git_context(root)
    if isinstance(state, GitRefusal):
        raise GitUnavailableError(state.reason)
    if isinstance(state, NoRepo):
        return frozenset()
    return state.dirty


def uncommitted_veto(root: Path) -> Callable[[Path], str | None]:
    """A `run_migrations(veto=...)` hold over artifacts with local changes.

    Reads `git status` once, then answers from the set: the gate runs before
    every command, and a subprocess per artifact would be felt.

    Why refuse rather than migrate-and-not-commit: `git add -- <path>` stages
    the whole file, so there is no way to commit the migration without the
    operator's edit; and rewriting a file someone is typing in, then leaving it
    uncommitted for them to discover, trades a visible refusal for an invisible
    surprise. The refusal names the file and the two ways forward.
    """
    dirty = uncommitted_paths(root)

    def veto(path: Path) -> str | None:
        if path.resolve() not in dirty:
            return None
        return (
            "has uncommitted changes, so migrating it would rewrite a file you are "
            "editing and `git add` would commit your edit with it. Commit or stash it, "
            "then run `fr migrate artifacts --yes`."
        )

    return veto


# --- the advisory lock (review r5-e7) ------------------------------------

LOCK_NAME = "fr-migrate.lock"
"""Advisory lock file, in the repo's GIT DIRECTORY.

Not in the working tree: the lock must not be an artifact, must not be
committed, and must be shared by every linked worktree of one repository
(`--git-common-dir`), because two worktrees of the same repo commit to the
same object store. Same `flock` shape the VK bridge uses for its single-tick
lock.
"""


def lock_path(toplevel: Path) -> Path | None:
    """Where this repo's migration lock lives, or `None` if git cannot say."""
    try:
        done = _git(toplevel, "rev-parse", "--git-common-dir")
    except GitUnavailableError:
        return None
    if done.returncode != 0 or not done.stdout.strip():
        return None
    git_dir = Path(done.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (toplevel / git_dir).resolve()
    return git_dir / LOCK_NAME


def index_lock_held(toplevel: Path) -> Path | None:
    """`<gitdir>/index.lock` when another git process holds the index."""
    try:
        done = _git(toplevel, "rev-parse", "--git-dir")
    except GitUnavailableError:
        return None
    if done.returncode != 0 or not done.stdout.strip():
        return None
    git_dir = Path(done.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (toplevel / git_dir).resolve()
    candidate = git_dir / "index.lock"
    return candidate if candidate.exists() else None


def migration_commit_message(report: MigrationReport, *, fr_version: str) -> str:
    """A generated message that says exactly what happened (spec §3.D).

    Grouped by kind and transition rather than listing files: `git show --stat`
    already lists the files, and a consumer repo mid-upgrade can migrate dozens
    of plans at once. Groups keep their first-seen order, so the message is
    deterministic for a deterministic report.
    """
    groups: dict[str, set[Path]] = {}
    for action in report.applied:
        groups.setdefault(_group_of(action), set()).add(action.path)

    n = len(report.changed_paths)
    noun = "artifact" if n == 1 else "artifacts"
    lines = [f"chore(fr): migrate {n} {noun} to fr {fr_version}", ""]
    for label, paths in groups.items():
        files = "file" if len(paths) == 1 else "files"
        lines.append(f"- {label} ({len(paths)} {files})")
    lines += [
        "",
        "Migrated automatically at fr CLI entry: the installed fr changed under",
        "artifacts written for an older one (artifact migration framework, spec",
        "2026-08-30 §3.C/§3.D). Only the rewritten artifact paths are in this",
        "commit; unrelated working-tree and staged changes were left alone.",
    ]
    return "\n".join(lines) + "\n"


def _group_of(action: PlannedAction) -> str:
    if action.repair is not None:
        return f"{action.kind}: repair {action.repair}"
    return f"{action.kind}: schema {action.from_version} -> {action.to_version}"


def commit_migration(
    repo_root: Path, report: MigrationReport, *, fr_version: str | None = None
) -> CommitOutcome:
    """Commit exactly `report.changed_paths`, or explain why it did not."""
    paths = report.changed_paths
    if not paths:
        return CommitOutcome(committed=False, reason="nothing was migrated; nothing to commit")

    state = git_context(repo_root)
    if isinstance(state, GitRefusal):
        return CommitOutcome(
            committed=False,
            reason=f"{state.reason}; the migrated files are in your working tree, uncommitted",
        )
    if isinstance(state, NoRepo):
        return CommitOutcome(
            committed=False,
            reason=f"{repo_root} is not a git repository; the migrated files are uncommitted",
        )
    toplevel = state.toplevel
    if state.branch is None:
        # Detached HEAD (review r5-c1). The previous code returned None here and
        # called it unreachable — "a detached HEAD never reaches the automatic
        # commit path anyway". It does: `git rebase -i` stops detached, and so
        # does `git bisect`, and both are interactive with a TTY. A commit made
        # then is folded into the rebase or orphaned on the next checkout.
        return CommitOutcome(
            committed=False,
            reason=(
                "refusing to commit on a detached HEAD (a rebase, a bisect, or a checked-out "
                "commit): the commit would be folded into the operation in progress or "
                "orphaned. The migrated files are in your working tree, uncommitted"
            ),
        )
    if state.branch == state.default_branch:
        return CommitOutcome(
            committed=False,
            reason=(
                f"refusing to commit on {state.branch!r}, the repository's default branch; "
                f"the migrated files are in your working tree, uncommitted"
            ),
        )
    if not state.has_head:
        # A partial (pathspec) commit needs a HEAD to build its tree from. An
        # empty repo is not a case this feature exists for, so it refuses
        # rather than falling back to a whole-index commit that would sweep in
        # whatever else happened to be staged.
        return CommitOutcome(
            committed=False,
            reason=f"{toplevel} has no commits yet; the migrated files are uncommitted",
        )
    held = index_lock_held(toplevel)
    if held is not None:
        return CommitOutcome(
            committed=False,
            reason=(
                f"another git process holds {held}; the migrated files are in your "
                "working tree, uncommitted"
            ),
        )

    # Preconditions, asserted rather than trusted: this writes to git history
    # from a callback that runs before an unrelated command.
    rel: list[str] = []
    for path in paths:
        try:
            rel.append(path.resolve().relative_to(toplevel).as_posix())
        except ValueError:
            return CommitOutcome(
                committed=False,
                reason=f"refusing to commit: {path} is outside the git repository {toplevel}",
            )

    # `add` first, so an artifact a migration *created* is tracked and can be
    # named by the pathspec below. Scoped with `--` so no path is ever read as
    # an option.
    try:
        added = _git(toplevel, "add", "--", *rel)
    except GitUnavailableError as e:
        return CommitOutcome(committed=False, reason=f"refusing to commit: {e}")
    if added.returncode != 0:
        return CommitOutcome(
            committed=False,
            reason=f"refusing to commit: `git add` failed: {added.stderr.strip()}",
        )

    # Is there anything to record *for these paths*? Checked against HEAD, not
    # against the index, so the answer does not change when the operator has
    # staged something unrelated. No -> no empty commit, and — the important
    # half — no commit at all, which is what stops an unrelated staged file
    # from being committed under a migration message.
    try:
        pending = _git(toplevel, "diff", "--cached", "--name-only", "HEAD", "--", *rel)
    except GitUnavailableError as e:
        return CommitOutcome(committed=False, reason=f"refusing to commit: {e}")
    if pending.returncode != 0 or not pending.stdout.strip():
        return CommitOutcome(
            committed=False,
            reason="the migrated files already match HEAD; no commit made",
        )

    if fr_version is None:
        from fr import __version__

        fr_version = __version__
    message = migration_commit_message(report, fr_version=fr_version)

    # The pathspec on `commit` is what keeps an unrelated *staged* file out:
    # without it git records the whole index. It also leaves that file staged.
    try:
        # A commit can legitimately take longer than a read: pre-commit hooks
        # and signing run here. Still bounded, still reported.
        done = _git(toplevel, "commit", "-m", message, "--", *rel, timeout=GIT_TIMEOUT_SECONDS * 4)
    except GitUnavailableError as e:
        return CommitOutcome(
            committed=False,
            reason=f"the migration is in your working tree but could not be committed: {e}",
            paths=paths,
            message=message,
        )
    if done.returncode != 0:
        return CommitOutcome(
            committed=False,
            reason=(
                f"the migration is in your working tree but could not be committed: "
                f"{done.stderr.strip() or done.stdout.strip()}"
            ),
            paths=paths,
            message=message,
        )
    return CommitOutcome(
        committed=True,
        reason=f"committed {len(rel)} migrated path(s): {', '.join(rel)}",
        paths=paths,
        message=message,
    )
