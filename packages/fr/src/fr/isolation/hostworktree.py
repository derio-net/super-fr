"""HostWorktreeTarget — the worktree half of the local target, host env as-is.

Mode host-worktree (spec §B, Type 2): fr owns workspace isolation — a genuine
linked git worktree plus the `.fr-isolation` marker, exactly as the local
target — but the *host process env is the env*. There is no devcontainer, no
`resolve_profile` / profile-committed gate, no secrets env-file, and no docker:
the docker-less pods (VK, Hermes Talos) already carry their ESO-injected
credentials, so isolation here is honest that it isolates the filesystem/branch,
not credentials or toolchain. The marker stays `mode="worktree"` (it *is* a real
linked worktree, so the edit-gate hook is byte-identical); the host/devcontainer
flavor lives in `IsolationState.profile` ("host"), which is state, not
enforcement.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fr.isolation.local import GcAction, LocalWorktreeDevcontainerTarget
from fr.isolation.types import IsolationError, IsolationState, save_state

_EXTERNAL = "environment is externally managed — restart/inspect the host, not fr"


class HostWorktreeTarget(LocalWorktreeDevcontainerTarget):
    def up(
        self,
        profile: str | None,
        branch: str,
        path: Path | None = None,
        base: str | None = None,
        no_fetch: bool = False,
    ) -> IsolationState:
        worktree = self._worktree_up_core(branch, path)
        self._git_worktree_add(worktree, branch, base=base, no_fetch=no_fetch)

        state = IsolationState(
            repo_root=self.repo_root,
            branch=branch,
            worktree=worktree,
            profile="host",
            created_at=datetime.now(UTC).isoformat(),
        )
        save_state(state)
        self._write_isolation_marker(worktree, branch)
        self._spawn_gc()
        return state

    def exec(self, state: IsolationState, argv: list[str]) -> int:
        """Plain subprocess in the worktree, host env inherited — the argv is run
        verbatim (no `devcontainer exec` wrapper). capture=False streams output
        live, matching the local target's exec passthrough contract."""
        return self.run(argv, cwd=state.worktree, capture=False).returncode

    def restart(self, state: IsolationState, force: bool = False) -> str:
        raise IsolationError(_EXTERNAL)

    def stats(self, state: IsolationState) -> dict[str, str] | None:
        raise IsolationError(_EXTERNAL)

    def status(self, state: IsolationState) -> dict[str, Any]:
        """Same shape as the local target's status MINUS the docker probe: this
        mode has no container, so `_container_state` (which shells out to
        `docker ps`) must never run — on a docker-less pod that raises
        FileNotFoundError. `container` is the fixed sentinel "n/a (host)"; the
        worktree/PR fields are unchanged (git + gh work on the host)."""
        return {
            "repo": str(state.repo_root),
            "branch": state.branch,
            "profile": state.profile,
            "worktree": str(state.worktree),
            "worktree_exists": state.worktree.is_dir(),
            "container": "n/a (host)",
            "pr": self._pr(state),
        }

    # `down` is NOT overridden: the inherited one is already the shared
    # `_down_worktree_tail` (PR guard → verified worktree removal → marker/state
    # retirement) plus the opportunistic sweep, and the only docker step in it —
    # `_teardown_container` — is the no-op below.

    def _teardown_container(self, state: IsolationState) -> None:
        """No container in this mode — the host env is the env (spec §B)."""

    # ----- gc: the same reconciler, minus every docker step (#423) -----
    #
    # The sweep used to be refused outright here ("gc requires docker"), which
    # left docker-less pods with no reconciler at all — a workspace whose PR
    # merged after its session exited leaked forever. Only DISCOVERY and
    # TEARDOWN were ever docker-coupled; the merge / content / cleanliness
    # classification is substrate-neutral. So the three docker-only steps are
    # skipped (not faked) and everything else is inherited verbatim, which is
    # what keeps the two worktree modes from drifting apart.

    def _labelled_containers(self) -> list[tuple[str, Path]]:
        """No docker → no container discovery. The sweep's other two sources
        (the fr worktree cache, this repo's fr state records) are enough."""
        return []

    def _sweep_dangling_images(self, dry_run: bool) -> list[GcAction]:
        """No docker → no `vsc-*` devcontainer images to reclaim."""
        return []

    def _stale_state_reapable(self) -> bool:
        """Unconditionally true: this mode has no containers by construction, so
        a state record whose worktree is gone cannot be hiding one. (The local
        target gates this on a healthy `docker ps` — there is no such view to
        distrust here, and deferring forever on a host with no daemon would
        recreate the very leak this closes.)"""
        return True
