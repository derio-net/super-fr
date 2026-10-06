"""Rename a workspace's branch everywhere fr keys on it (spec 2026-10-06-triage-batch-adopt §B).

A branch name is the key of four things fr owns besides git's own ref: the
isolation record (`state_path(repo, branch)`), the `.fr-isolation` marker's
`branch` (the edit gate denies edits when HEAD drifts from it), each bound
session's index file, and a live run cursor's committed `branch:` (`find_run`
locates the run by it at close-out). `rename_branch` moves all of them.

- **Plan first, then write.** `plan_rename` reads everything and raises
  `IsolationError` on every refusal; `rename_branch` writes only what the plan
  holds, so no refusal fires after a write.
- **Resumable.** Each key is moved only while it still names *old*: a second
  call, or one after a crash between two moves, finishes what remains and a
  fully applied rename returns no changes (R10).
- **Atomic, and crash-safe.** The marker and the isolation record are replaced
  whole (`write_text_atomic`); a cursor rewritten but not yet committed (a
  refusing hook, a crash) is committed by the next call.
- **The worktree path keeps its old slug.** Nothing re-derives a path from a
  branch: gc and containers key on the path.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from fr.artifacts.atomic import write_text_atomic

from .sessions import _write_index, read_session_index
from .types import IsolationError, delete_state, load_state, save_state

__all__ = ["IsolationError", "RenamePlan", "plan_rename", "rename_branch"]

MARKER = ".fr-isolation"
RUNS_REL = Path("docs") / "superpowers" / "runs"


@dataclass(frozen=True)
class RenamePlan:
    """What `rename_branch` would still move; `done` when nothing."""

    repo_root: Path
    worktree: Path
    old: str
    new: str
    branch: bool = False
    record: bool = False
    marker: bool = False
    sessions: tuple[str, ...] = ()
    cursors: tuple[Path, ...] = field(default_factory=tuple)
    # Cursors already naming *new* whose commit never landed (p1-r4).
    uncommitted: tuple[Path, ...] = field(default_factory=tuple)

    @property
    def done(self) -> bool:
        return not self.steps()

    def steps(self) -> list[str]:
        """One line per move still owed, in the order `rename_branch` makes them."""
        out: list[str] = []
        if self.branch:
            out.append(f"git branch -m {self.old} {self.new}")
        if self.record:
            out.append(f"isolation record {self.old} -> {self.new}")
        if self.marker:
            out.append(f"{MARKER} marker branch -> {self.new}")
        out += [f"session index {sid} branch -> {self.new}" for sid in self.sessions]
        out += [f"run cursor {c} branch -> {self.new} (committed)" for c in self.cursors]
        out += [f"run cursor {c}: commit its branch -> {self.new}" for c in self.uncommitted]
        return out


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """`git -C cwd args`; a failure with *check* is an `IsolationError` naming git's words."""
    done = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if check and done.returncode != 0:
        detail = (done.stderr or done.stdout).strip() or f"exit {done.returncode}"
        raise IsolationError(f"git {' '.join(args[:2])} failed in {cwd}: {detail}")
    return done


def _has_branch(cwd: Path, name: str) -> bool:
    return (
        _git(cwd, "show-ref", "--verify", "--quiet", f"refs/heads/{name}", check=False).returncode
        == 0
    )


def _git_path(wt: Path, name: str) -> Path:
    p = Path(_git(wt, "rev-parse", "--git-path", name).stdout.strip())
    return p if p.is_absolute() else wt / p


def _marker(wt: Path) -> dict[str, object] | None:
    """The worktree's `.fr-isolation` marker, or None unless it is a valid one: a
    JSON object whose `toplevel` is this worktree (p1-r5)."""
    try:
        data = json.loads((wt / MARKER).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        same = Path(str(data.get("toplevel") or "")).resolve() == wt.resolve()
    except OSError:
        return None
    return data if data.get("toplevel") and same else None


def _cursor_branch_line(name: str) -> re.Pattern[str]:
    return re.compile(rf"^branch:[ \t]*(['\"]?){re.escape(name)}\1[ \t]*$", re.MULTILINE)


def plan_rename(repo_root: Path, worktree: Path, old: str, new: str) -> RenamePlan:
    """Read every key and refuse before anything is written (spec §B, R9, R10)."""
    wt = Path(worktree)
    if _git_path(wt, "rebase-merge").exists() or _git_path(wt, "rebase-apply").exists():
        raise IsolationError(f"{wt} is mid-rebase: finish or abort it before renaming {old}")
    if _git_path(wt, "MERGE_HEAD").exists():
        raise IsolationError(f"{wt} is mid-merge: finish or abort it before renaming {old}")
    has_old, has_new = _has_branch(wt, old), _has_branch(wt, new)
    if old == new:  # nothing to move; the refusals above and below still hold (p1-r9)
        has_old = False
    if has_old and has_new:
        raise IsolationError(f"branch {new} already exists and is not {old} renamed: refusing")
    if not has_old and not has_new:
        raise IsolationError(f"no branch {old} (nor {new}) in {wt}")
    head = _git(wt, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if head not in (old, new):
        raise IsolationError(f"{wt} is not on {old} (HEAD is {head}): refusing to rename")

    runs = wt / RUNS_REL
    cursors: list[Path] = []
    uncommitted: list[Path] = []
    for f in sorted(runs.glob("*.yaml")) if runs.is_dir() else ():
        text = f.read_text()
        rel = f.relative_to(wt)
        if _cursor_branch_line(old).search(text):
            if _git(wt, "status", "--porcelain", "--", str(rel)).stdout.strip():
                raise IsolationError(f"run cursor {rel} is modified: commit or restore it first")
            if old != new:
                cursors.append(rel)
        elif old != new and _cursor_branch_line(new).search(text):
            committed = _git(wt, "show", f"HEAD:{rel.as_posix()}", check=False).stdout
            if _cursor_branch_line(old).search(committed):
                uncommitted.append(rel)  # rewritten, its commit never landed (p1-r4)
    if old == new:
        return RenamePlan(repo_root=Path(repo_root), worktree=wt, old=old, new=new)

    record = load_state(repo_root, old)
    held = record or load_state(repo_root, new)
    marker = _marker(wt)
    sessions = tuple(
        b.session_id
        for b in (held.sessions if held else ())
        if (idx := read_session_index(b.session_id)) is not None and idx.get("branch") == old
    )
    return RenamePlan(
        repo_root=Path(repo_root),
        worktree=wt,
        old=old,
        new=new,
        branch=has_old,
        record=record is not None,
        marker=marker is not None and marker.get("branch") == old,
        sessions=sessions,
        cursors=tuple(cursors),
        uncommitted=tuple(uncommitted),
    )


def rename_branch(
    repo_root: Path, worktree: Path, old: str, new: str, *, dry_run: bool = False
) -> list[str]:
    """Rename *old* to *new* in git and every fr key; return the moves made (`[]`: done).

    *dry_run* refuses exactly as the real call would and returns the moves it would
    make, writing nothing. Every failure is an `IsolationError`.
    """
    plan = plan_rename(repo_root, worktree, old, new)
    if dry_run:
        return plan.steps()
    wt = plan.worktree
    if plan.branch:
        _git(wt, "branch", "-m", old, new)
    state = load_state(repo_root, old) if plan.record else load_state(repo_root, new)
    if plan.record and state is not None:
        state = state.model_copy(update={"branch": new})
        save_state(state)
        delete_state(repo_root, old)
    if plan.marker:
        data = _marker(wt) or {}
        data["branch"] = new
        write_text_atomic(wt / MARKER, json.dumps(data, indent=2) + "\n")
    if state is not None:
        for b in state.sessions:
            if b.session_id in plan.sessions:
                _write_index(state, b)
    for rel in plan.cursors:
        f = wt / rel
        f.write_text(_cursor_branch_line(old).sub(f"branch: {new}", f.read_text(), count=1))
        _commit_cursor(wt, rel, new)
    for rel in plan.uncommitted:
        _commit_cursor(wt, rel, new)
    return plan.steps()


def _commit_cursor(wt: Path, rel: Path, new: str) -> None:
    """Commit the cursor *rel* alone: staged work elsewhere stays staged."""
    run_id = rel.stem
    _git(
        wt,
        "commit",
        "-q",
        "-m",
        f"chore(fr): run {run_id} — branch renamed to {new} by batch adopt",
        "--",
        str(rel),
    )
