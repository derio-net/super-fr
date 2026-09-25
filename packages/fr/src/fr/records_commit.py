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

from fr.artifacts.commit import NoRepo, commit_paths, git_context
from fr.git import GitUnavailableError, git_answer

__all__ = ["commit_records"]


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


def commit_records(repo_root: Path, paths: Iterable[Path], message: str) -> None:
    """Commit `paths` under `message`; report on stderr; never raise."""
    todo = list(dict.fromkeys(p if p.is_absolute() else repo_root / p for p in paths))
    try:
        outcome = commit_paths(repo_root, todo, message)
        if outcome.committed:
            print(
                f"fr: committed {_short_head(repo_root)} {message.splitlines()[0]}",
                file=sys.stderr,
                flush=True,
            )
            return
        if not todo or isinstance(git_context(repo_root), NoRepo):
            return  # not in a git repo (or nothing written): a no-op, as before
        reason = outcome.reason
    except Exception as e:  # noqa: BLE001 — losing the commit must not lose the write
        reason = f"{type(e).__name__}: {e}"
    print(f"fr: not committed ({reason}): {_shown(repo_root, todo)}", file=sys.stderr, flush=True)
