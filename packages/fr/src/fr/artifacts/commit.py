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


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def _toplevel(root: Path) -> Path | None:
    """The git toplevel containing `root`, or None when there is no repo."""
    try:
        done = _git(root, "rev-parse", "--show-toplevel")
    except (OSError, FileNotFoundError):  # pragma: no cover — git missing
        return None
    if done.returncode != 0:
        return None
    text = done.stdout.strip()
    return Path(text).resolve() if text else None


def _has_head(root: Path) -> bool:
    return _git(root, "rev-parse", "--verify", "--quiet", "HEAD").returncode == 0


# --- the default branch --------------------------------------------------

_WELL_KNOWN_DEFAULTS = ("main", "master")
"""Last resort when nothing in the repo declares a default."""


def _current_branch(root: Path) -> str | None:
    """The checked-out branch, or `None` on a detached HEAD / not a repo."""
    done = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    return done.stdout.strip() or None if done.returncode == 0 else None


def default_branch(root: Path) -> str | None:
    """The repository's default branch, best available answer.

    `origin/HEAD` is the authority when it exists — it is what the host says,
    so a repo whose trunk is `trunk` or `develop` is protected as such and a
    `main` that is *not* the default is not. `init.defaultBranch` is next, and
    the well-known names are the floor: a local repo with no remote sitting on
    `main` is still a base clone, and this predicate is used to refuse, so its
    failure mode should be one extra explicit step rather than one surprise
    commit.
    """
    done = _git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if done.returncode == 0 and done.stdout.strip():
        return done.stdout.strip().removeprefix("origin/")
    configured = _git(root, "config", "--get", "init.defaultBranch")
    if configured.returncode == 0 and configured.stdout.strip():
        return configured.stdout.strip()
    for name in _WELL_KNOWN_DEFAULTS:
        if _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}").returncode == 0:
            return name
    return None


def on_default_branch(root: Path) -> str | None:
    """The branch name when HEAD is the repository's default branch, else None.

    `None` for "not a git repo" and for a detached HEAD: neither is the case
    this guards, and a detached HEAD never reaches the automatic commit path
    anyway (CI is non-interactive, and the gate refuses there first).
    """
    toplevel = _toplevel(root)
    if toplevel is None:
        return None
    branch = _current_branch(toplevel)
    if branch is None:
        return None
    return branch if branch == default_branch(toplevel) else None


# --- artifacts the operator is already editing ---------------------------


def uncommitted_paths(root: Path) -> frozenset[Path]:
    """Every path git reports as changed — staged, unstaged or untracked."""
    toplevel = _toplevel(root)
    if toplevel is None:
        return frozenset()
    done = _git(toplevel, "status", "--porcelain", "-z", "--untracked-files=all")
    if done.returncode != 0:  # pragma: no cover — a working `git status` is the norm
        return frozenset()
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
        if code[0] in "RC" and i < len(fields):
            out.add((toplevel / fields[i]).resolve())
            i += 1
        out.add((toplevel / rel).resolve())
    return frozenset(out)


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

    toplevel = _toplevel(repo_root)
    if toplevel is None:
        return CommitOutcome(
            committed=False,
            reason=f"{repo_root} is not a git repository; the migrated files are uncommitted",
        )
    on_default = on_default_branch(toplevel)
    if on_default is not None:
        return CommitOutcome(
            committed=False,
            reason=(
                f"refusing to commit on {on_default!r}, the repository's default branch; "
                f"the migrated files are in your working tree, uncommitted"
            ),
        )
    if not _has_head(toplevel):
        # A partial (pathspec) commit needs a HEAD to build its tree from. An
        # empty repo is not a case this feature exists for, so it refuses
        # rather than falling back to a whole-index commit that would sweep in
        # whatever else happened to be staged.
        return CommitOutcome(
            committed=False,
            reason=f"{toplevel} has no commits yet; the migrated files are uncommitted",
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
    added = _git(toplevel, "add", "--", *rel)
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
    pending = _git(toplevel, "diff", "--cached", "--name-only", "HEAD", "--", *rel)
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
    done = _git(toplevel, "commit", "-m", message, "--", *rel)
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
