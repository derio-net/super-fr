"""The isolation precondition of `fr run start` — spec §4.B, review fix r2-f5.

**A run is born in its workspace.** `fr run start` ensures isolation itself
and writes `docs/superpowers/runs/<run-id>.yaml` inside the resulting
worktree; isolation is never a *step* the run performs on itself.

That distinction is the whole fix. With an `isolate` step, `fr run start`
wrote the run file at `git rev-parse --show-toplevel` (the base clone) and
step 1 then created a linked worktree — so from the worktree `advance`
resolved a different toplevel and could not find its own run, while from the
base clone every `cli` step ran with `cwd` in the base clone and
`fr plan self-review {{ artifacts.plan }}` looked for a plan that existed
only in the worktree. The run's first step moved the ground out from under
it. A run file in the base clone also defeats §4.B's own rationale: it is not
on the feature branch, so it never reaches the PR that makes the run
reviewable.

Making isolation a precondition matches this repo's standing doctrine —
fr-brainstorming §0 and fr-goal both treat isolation as a hard gate that
"precedes EVERYTHING", where "start with X" changes the first work item and
never the first action.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fr.isolation.types import IsolationError, load_state

MARKER = ".fr-isolation"

__all__ = ["RunWorkspaceError", "ensure_run_workspace"]


class RunWorkspaceError(Exception):
    """No workspace could be given to a run being started. CLI maps it to exit 2."""


def _marker_at(repo_root: Path) -> dict[str, Any] | None:
    """The `.fr-isolation` marker IF it actually identifies `repo_root`.

    Same identity rule the `fr-isolation-required` PreToolUse hook applies: a
    marker whose recorded `toplevel` is not this checkout is stale or copied
    and proves nothing. Fails closed (returns `None`) on unreadable or
    non-mapping content — "not provably a workspace" must never be
    indistinguishable from "is one".
    """
    path = repo_root / MARKER
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    toplevel = data.get("toplevel")
    if not isinstance(toplevel, str) or Path(toplevel).resolve() != repo_root.resolve():
        return None
    return data


def _select_target(repo_root: Path) -> Any:
    """Module seam over `fr isolation up`'s backend selection.

    Imported lazily: `fr.commands.isolation_cmd` is a CLI module and this one
    is imported *by* a CLI module, so a top-level import would be a cycle
    waiting to happen. Tests monkeypatch this name rather than a private of
    another module.
    """
    from fr.commands.isolation_cmd import _target

    return _target(repo_root)


def ensure_run_workspace(repo_root: Path, branch: str) -> Path:
    """The workspace root this run must be born in. Idempotent.

    Three cases, in order:

    1. **Already inside a workspace** (a valid marker at `repo_root`) — use
       it. This is the normal fr-goal case: the pipeline is already in
       isolation before a run exists. A marker naming a DIFFERENT branch is
       refused rather than used, since writing the run there would put it on
       the wrong PR.
    2. **A workspace already exists for `branch`** (recorded isolation state,
       worktree still on disk) — use it, without re-entering. `up` starts
       containers; "ensure" must not mean "restart".
    3. **Otherwise** — enter isolation for `branch` (`fr isolation up
       --branch <b>`, whichever backend `FR_ISOLATION_TARGET` selects) and use
       the worktree it returns.
    """
    marker = _marker_at(repo_root)
    if marker is not None:
        recorded = marker.get("branch")
        if isinstance(recorded, str) and recorded and recorded != branch:
            raise RunWorkspaceError(
                f"this workspace is isolated for branch {recorded!r}, not {branch!r} — "
                f"start the run with --branch {recorded} or run `fr run start` from "
                "outside the workspace"
            )
        return repo_root

    state = load_state(repo_root, branch)
    if state is not None and Path(state.worktree).is_dir():
        return Path(state.worktree)

    try:
        new_state = _select_target(repo_root).up(profile=None, branch=branch)
    except IsolationError as e:
        raise RunWorkspaceError(f"could not enter isolation for branch {branch!r}: {e}") from e
    return Path(new_state.worktree)
