"""fr commits its own record writes (gh#610, spec 2026-09-25 §3.C).

The one CLI-layer hook every record-writing command (`fr run`, `fr plan`,
`fr journal`) calls after its write has landed. It commits exactly the paths
the command wrote, through `fr.artifacts.commit.commit_paths`, and it NEVER
fails the write: the record is already on disk, so a refused or broken commit
is one stderr line and the command's exit code is untouched.

Library functions (`plan_ops`, `save_run_state`, the journal writer) stay pure;
only the CLI decides commit cadence.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

from fr.artifacts.commit import CommitOutcome, NoRepo, commit_paths, git_context
from fr.git import GitUnavailableError, git_answer

__all__ = ["commit_records"]

_LOCK_WAIT_SECONDS = 2.0


def _shown(root: Path, paths: Iterable[Path]) -> str:
    out: list[str] = []
    for p in paths:
        try:
            out.append(p.resolve().relative_to(root.resolve()).as_posix())
        except (ValueError, OSError):
            out.append(str(p))
    return ", ".join(out)


def _short_head(root: Path) -> str:
    """HEAD's short sha, or `HEAD` if git will not say — the commit already happened."""
    try:
        done = git_answer(root, "rev-parse", "--short", "HEAD")
    except GitUnavailableError:
        return "HEAD"
    return done.stdout.strip() or "HEAD"


def commit_records(repo_root: Path, paths: Iterable[Path], message: str) -> CommitOutcome:
    """Commit `paths` under `message`; report on stderr; never raise.

    Returns the `CommitOutcome` (p4-r1) so a caller that prints a "push it"
    line — `run_cmd`'s closeout handoff — can tell a real commit from a
    refusal instead of assuming HEAD always reflects this call's write.
    """
    todo = list(dict.fromkeys(p if p.is_absolute() else repo_root / p for p in paths))
    try:
        # Decision 248a1091887d: fr's own bookkeeping skips the repo's commit
        # hooks (frequent; a fixer hook would fail every tick), keeps signing as
        # configured, restores the index on failure, and waits out a briefly
        # held index.lock (an executor committing in the same worktree, p3-r3).
        outcome = commit_paths(
            repo_root,
            todo,
            message,
            no_verify=True,
            restore_index=True,
            lock_wait=_LOCK_WAIT_SECONDS,
        )
        if outcome.committed:
            print(
                f"fr: committed {_short_head(repo_root)} {message.splitlines()[0]}",
                file=sys.stderr,
                flush=True,
            )
            return outcome
        if not todo or isinstance(git_context(repo_root), NoRepo):
            return outcome  # not in a git repo (or nothing written): a no-op, as before
        reason = outcome.reason
    except Exception as e:  # noqa: BLE001 — losing the commit must not lose the write
        reason = f"{type(e).__name__}: {e}"
        outcome = CommitOutcome(committed=False, reason=reason)
    print(f"fr: not committed ({reason}): {_shown(repo_root, todo)}", file=sys.stderr, flush=True)
    return outcome
