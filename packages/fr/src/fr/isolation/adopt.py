"""The isolation seam of `fr triage batch adopt` (spec 2026-10-11-batch-adopt-safety-2
§B "The isolation seam").

Every isolation call adopt and `adopt --list` make goes through this module, so the
batch tripwire (`tests/unit/test_forge_adapter_batch_ops.py`) admits a closed set of
imports rather than `fr.isolation` at large. *repo_root* is always the checkout's
main worktree. No function here runs git itself: what a branch carries is the
caller's read (`gitseam.Checkout.ahead`), passed in.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .sessions import attach, read_session_index
from .types import IsolationError, default_worktree_path, list_states, load_state


def _select_target(repo_root: Path) -> Any:
    """`fr isolation up`'s backend selection (honours `FR_ISOLATION_TARGET`), imported
    lazily as `fr.run.workspace._select_target` does: `fr.commands.isolation_cmd` is a
    CLI module. Tests monkeypatch this name."""
    from fr.commands.isolation_cmd import _target

    return _target(repo_root)


def enter_workspace(repo_root: Path, branch: str) -> Path:
    """The worktree of *branch*'s fr workspace, entered as `fr isolation up --branch`
    would: a new branch cut from freshly fetched `origin/<default>`, or a resume.

    Always calls `up`, never skips it on an existing workspace: `up` is a documented
    resume, so a container whose first start failed after its state was recorded
    (gh#578) is started now (R9). Raises `IsolationError`."""
    state = _select_target(repo_root).up(profile=None, branch=branch)
    return Path(state.worktree)


def workspace_path(repo_root: Path, branch: str) -> Path:
    """Where *branch*'s workspace is, or will be once `enter_workspace` makes it: the
    recorded worktree, else where `up` puts a new one. For the plan, before any write."""
    try:
        state = load_state(repo_root, branch)
    except (ValueError, OSError):
        state = None
    return Path(state.worktree) if state is not None else default_worktree_path(repo_root, branch)


def bind_session(repo_root: Path, branch: str, session_id: str, harness: str) -> str | None:
    """Bind *session_id* to *branch*'s workspace. None on success; on failure a warning
    to print, never an exception — a binding is traceability, not a step that can stop
    adopt (as `run_cmd._bind_session` rules)."""
    try:
        attach(repo_root, branch, session_id, harness)
    except (IsolationError, OSError) as exc:
        return f"warning: could not bind session {session_id} to {branch}: {exc}"
    return None


def reusable_workspace(
    repo_root: Path, branch: str, session_id: str | None, *, ahead: int
) -> Path | None:
    """The worktree of an fr workspace recorded in this checkout for *branch* that a
    default-branch adopt may take over (R7), else None: one whose branch has no commits
    beyond `origin/<default>` (*ahead*, the caller's count), or one *session_id* is
    already bound to. A workspace an earlier failed dispatch left with commits is never
    silently reused."""
    try:
        state = load_state(repo_root, branch)
    except (ValueError, OSError):
        return None
    if state is None or not Path(state.worktree).is_dir():
        return None
    bound = session_id is not None and any(b.session_id == session_id for b in state.sessions)
    return Path(state.worktree) if ahead == 0 or bound else None


def session_worktree(session_id: str) -> Path | None:
    """The workspace worktree *session_id* is bound to, from the session index."""
    try:
        index = read_session_index(session_id)
    except IsolationError:  # an id no index can be named by
        return None
    worktree = index.get("worktree") if index else None
    return Path(str(worktree)) if worktree else None


def workspace_containing(repo_root: Path, path: Path) -> Path | None:
    """The worktree of the fr workspace of *repo_root* that contains *path*."""
    try:
        states = list_states(repo_root)
    except (IsolationError, OSError, ValueError):
        return None
    where = path.resolve()
    for state in states:
        worktree = Path(state.worktree).resolve()
        if where == worktree or worktree in where.parents:
            return Path(state.worktree)
    return None
