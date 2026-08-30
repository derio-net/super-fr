"""The atomic commit — *only* the migrated paths (spec §3.D).

`git add -- <exact paths the migration rewrote>` then `git commit -m <msg> --
<those same paths>`. Never `add -A`, never a stash cycle.

In-flight work is a dirty tree by definition — that is the case this exists
for. Refusing until the tree is clean would block precisely the sessions it has
to serve, and a stash/unstash risks a pop conflict on top of work the operator
has not saved anywhere. Path-scoped staging leaves every unrelated edit exactly
where it was.

Two `git` mistakes this module is shaped to avoid, both of which pass a
clean-tree test:

1. **`git add -A`** sweeps the operator's unrelated *modified* files into the
   commit.
2. **A plain `git commit -m`** records the whole index, so it sweeps in an
   unrelated file the operator had *staged* before running the command — even
   if the staging was path-scoped. The commit itself has to carry the pathspec,
   which makes git build the tree from HEAD plus those paths and leave the rest
   of the index untouched.

Everything here is fail-closed. This runs automatically, before a command the
operator typed for some other reason, and it writes to git history: every
precondition is asserted rather than assumed to have been checked by the
caller, and any doubt returns a `CommitOutcome` that did nothing.
"""

from __future__ import annotations

import subprocess
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
