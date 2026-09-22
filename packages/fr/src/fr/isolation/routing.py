"""Build the backend for an EXISTING workspace from its recorded mode (gh#569).

The rule: ``FR_ISOLATION_TARGET`` selects the mode only where no workspace
exists yet — ``up``, gc's discovery sweep, and ``verify-merge`` on a branch
whose workspace was already reaped. Every command that addresses a workspace
that exists (exec, restart, status, down, down --all, verify-merge, and gc's
per-workspace teardown) follows the mode the workspace was created in, read
from its state by ``types.recorded_mode``. A dispatched agent, a hook, or an
operator shell therefore needs no env to address a host-worktree workspace, and
an env that disagrees with a workspace can no longer misroute it.

This module never reads ``os.environ``.
"""

from __future__ import annotations

from fr.isolation.external import ExternalTarget
from fr.isolation.hostworktree import HostWorktreeTarget
from fr.isolation.local import GcSpawner, LocalWorktreeDevcontainerTarget, Runner
from fr.isolation.types import IsolationError, IsolationState, Target, recorded_mode


def target_for_state(state: IsolationState, runner: Runner, gc_spawner: GcSpawner) -> Target:
    """The Target that owns ``state``, chosen by its recorded mode alone.

    ``external`` is adopted through ``ExternalTarget.detect`` (valid marker plus
    live container evidence) and fails closed otherwise — it never falls
    through to devcontainer, because guessing a backend for a workspace fr did
    not build is how a preparer's checkout gets torn down.
    """
    mode = recorded_mode(state)
    if mode == "worktree":
        return HostWorktreeTarget(state.repo_root, runner=runner, gc_spawner=gc_spawner)
    if mode == "external":
        probe = state.worktree if state.worktree.is_dir() else state.repo_root
        adopted = ExternalTarget.detect(probe, runner=runner)
        if adopted is None:
            raise IsolationError(
                f"workspace {state.branch!r} was created in external mode but no valid "
                ".fr-isolation marker with container evidence is present — fr will not "
                "guess a backend"
            )
        return adopted
    return LocalWorktreeDevcontainerTarget(state.repo_root, runner=runner, gc_spawner=gc_spawner)
