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
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from fr.artifacts.runner import MigrationReport, PlannedAction
from fr.git import (
    GIT_TIMEOUT_SECONDS,
    GitRefusal,
    GitUnavailableError,
    remote_default_ref,
    remote_name,
)
from fr.git import WELL_KNOWN_DEFAULTS as _WELL_KNOWN_DEFAULTS
from fr.git import git_answer as _git
from fr.git import ref_exists as _ref_exists

__all__ = [
    "GIT_TIMEOUT_SECONDS",
    "CommitOutcome",
    "GitContext",
    "GitRefusal",
    "GitState",
    "GitUnavailableError",
    "NoRepo",
    "commit_migration",
    "commit_paths",
    "git_context",
    "index_lock_held",
    "lock_path",
    "migration_commit_message",
    "on_default_branch",
    "uncommitted_paths",
    "uncommitted_veto",
]


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
    # True when there was nothing to commit because the files already match
    # HEAD: not a refusal — the content is already committed.
    unchanged: bool = False
    message: str | None = None


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


GitState = GitContext | NoRepo | GitRefusal


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
    remote = remote_name(root)
    if isinstance(remote, GitRefusal):
        return remote

    tracking = remote_default_ref(root)
    if isinstance(tracking, GitRefusal):
        return tracking
    if tracking is not None and remote is not None:
        # Steps 1–2 live in `fr.git.remote_default_ref` (one definition, shared
        # with `fr.archive.merge_evidence`); it answers `<remote>/<branch>`.
        # Strip the remote prefix once, so `release/main` survives.
        return tracking.removeprefix(f"{remote}/")

    if unborn:
        # A freshly `git init`ed repo has no refs at all, so no existence
        # question below can be asked — but `.git/HEAD` already names the
        # branch (`git init -b <name>` writes it there, config or no config),
        # and the branch HEAD points at IS the default by construction. Asking
        # `init.defaultBranch` here instead was review fix r5-ci1: it made the
        # answer depend on host git config, so the same repo reported `main`
        # on a machine with the config set and None on CI without it.
        head = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
        if head.returncode == 0 and head.stdout.strip():
            return head.stdout.strip()

    configured = _git(root, "config", "--get", "init.defaultBranch")
    if configured.returncode == 0 and configured.stdout.strip():
        name = configured.stdout.strip()
        if _ref_exists(root, f"refs/heads/{name}"):
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
    if fr_version is None:
        from fr import __version__

        fr_version = __version__
    return commit_paths(repo_root, paths, migration_commit_message(report, fr_version=fr_version))


_UNCOMMITTED = "the files are in your working tree, uncommitted"


_LOCK_POLL_SECONDS = 0.05


def commit_paths(
    repo_root: Path,
    paths: Sequence[Path],
    message: str,
    *,
    no_verify: bool = False,
    restore_index: bool = False,
    lock_wait: float = 0.0,
) -> CommitOutcome:
    """Commit exactly `paths` under `message`, or explain why it did not.

    The generic body `commit_migration` delegates to, and the one committer fr's
    own record writes use (gh#610, spec 2026-09-25 §3.C). Every refusal of the
    migration commit applies unchanged: no repo, a git refusal, a detached HEAD,
    the default branch, no HEAD, a held index lock, a path outside the repo.
    A relative path is read against `repo_root`, not the process cwd.

    The pathspec commit records each path's WHOLE working-tree file, so a hand
    edit sitting in one of these files rides along under `message` (p3-m2).

    The keywords are the record-commit policy (decision 248a1091887d), off by
    default so the migration commit is unchanged: `no_verify` skips the
    repository's commit hooks (signing is left as configured); `restore_index`
    puts the index entries of `paths` back as they were if the commit fails;
    `lock_wait` waits up to that many seconds for a held `index.lock` to clear
    before refusing (p3-r3).
    """
    paths = tuple(p if p.is_absolute() else repo_root / p for p in paths)
    if not paths:
        return CommitOutcome(committed=False, reason="no paths were written; nothing to commit")

    state = git_context(repo_root)
    if isinstance(state, GitRefusal):
        return CommitOutcome(committed=False, reason=f"{state.reason}; {_UNCOMMITTED}")
    if isinstance(state, NoRepo):
        return CommitOutcome(
            committed=False,
            reason=f"{repo_root} is not a git repository; the files are uncommitted",
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
                "orphaned. The files are in your working tree, uncommitted"
            ),
        )
    if state.branch == state.default_branch:
        return CommitOutcome(
            committed=False,
            reason=(
                f"refusing to commit on {state.branch!r}, the repository's default branch; "
                f"{_UNCOMMITTED}"
            ),
        )
    if not state.has_head:
        # A partial (pathspec) commit needs a HEAD to build its tree from. An
        # empty repo is not a case this feature exists for, so it refuses
        # rather than falling back to a whole-index commit that would sweep in
        # whatever else happened to be staged.
        return CommitOutcome(
            committed=False,
            reason=f"{toplevel} has no commits yet; the files are uncommitted",
        )
    held = index_lock_held(toplevel)
    deadline = time.monotonic() + lock_wait
    while held is not None and time.monotonic() < deadline:
        # Another writer in the same worktree (an executor's own commit) holds
        # the index for a moment; a bounded wait, then the same refusal.
        time.sleep(_LOCK_POLL_SECONDS)
        held = index_lock_held(toplevel)
    if held is not None:
        return CommitOutcome(
            committed=False,
            reason=f"another git process holds {held}; {_UNCOMMITTED}",
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

    # The index entries of `rel` as they stand now, so a failed commit can put
    # them back: a path the caller had already staged stays staged (at the
    # version it staged), a path only this call added is dropped again.
    before: str | None = None
    if restore_index:
        try:
            listed = _git(toplevel, "ls-files", "-s", "-z", "--", *rel)
        except GitUnavailableError as e:
            return CommitOutcome(committed=False, reason=f"refusing to commit: {e}")
        if listed.returncode != 0:
            return CommitOutcome(
                committed=False,
                reason=f"refusing to commit: `git ls-files` failed: {listed.stderr.strip()}",
            )
        before = listed.stdout

    def failed(reason: str) -> CommitOutcome:
        if before is not None:
            reason += _restore_index(toplevel, rel, before)
        return CommitOutcome(committed=False, reason=reason, paths=paths, message=message)

    # `add` first, so a file the caller *created* is tracked and can be named by
    # the pathspec below. Scoped with `--` so no path is ever read as an option.
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
    # from being committed under fr's message.
    try:
        pending = _git(toplevel, "diff", "--cached", "--name-only", "HEAD", "--", *rel)
    except GitUnavailableError as e:
        return CommitOutcome(committed=False, reason=f"refusing to commit: {e}")
    # pd-r2: a FAILED probe is not the same answer as an EMPTY one. Only
    # rc == 0 with empty stdout means "the files already match HEAD" — a
    # non-zero exit means git could not tell us, and reporting `unchanged`
    # for that would hand a caller false "cursor committed" assurance.
    if pending.returncode != 0:
        detail = pending.stderr.strip() or pending.stdout.strip()
        return CommitOutcome(
            committed=False,
            reason=f"could not inspect the index: {detail}",
        )
    if not pending.stdout.strip():
        return CommitOutcome(
            committed=False,
            reason="the files already match HEAD; no commit made",
            unchanged=True,
        )

    # The pathspec on `commit` is what keeps an unrelated *staged* file out:
    # without it git records the whole index. It also leaves that file staged.
    verify = ["--no-verify"] if no_verify else []
    try:
        # A commit can legitimately take longer than a read: pre-commit hooks
        # and signing run here. Still bounded, still reported.
        done = _git(
            toplevel,
            "commit",
            *verify,
            "-m",
            message,
            "--",
            *rel,
            timeout=GIT_TIMEOUT_SECONDS * 4,
        )
    except GitUnavailableError as e:
        return failed(f"the files are in your working tree but could not be committed: {e}")
    if done.returncode != 0:
        return failed(
            f"the files are in your working tree but could not be committed: "
            f"{done.stderr.strip() or done.stdout.strip()}"
        )
    return CommitOutcome(
        committed=True,
        reason=f"committed {len(rel)} path(s): {', '.join(rel)}",
        paths=paths,
        message=message,
    )


def _restore_index(toplevel: Path, rel: Sequence[str], before: str) -> str:
    """Put the index entries of `rel` back to `before` (`ls-files -s -z`).

    Returns "" on success, or a clause naming what could not be restored — the
    caller's refusal is still reported either way; this never raises.
    """
    try:
        reset = _git(toplevel, "reset", "-q", "--", *rel)
        if reset.returncode not in (0, 1):  # 1: "unstaged changes after reset"
            return f"; the index could not be restored: {reset.stderr.strip()}"
        entries = "".join(f"{entry}\0" for entry in before.split("\0") if entry.strip())
        if entries:
            done = subprocess.run(
                ["git", "update-index", "-z", "--index-info"],
                cwd=toplevel,
                input=entries,
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS,
                check=False,
            )
            if done.returncode != 0:
                return f"; the index could not be restored: {done.stderr.strip()}"
    except (GitUnavailableError, OSError, subprocess.SubprocessError) as e:
        return f"; the index could not be restored: {e}"
    return ""
