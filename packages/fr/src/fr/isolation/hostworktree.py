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

from fr.isolation.local import LocalWorktreeDevcontainerTarget
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

    def down(self, state: IsolationState, force: bool = False) -> None:
        """The local target's PR guard + verified worktree removal + marker/state
        retirement, minus every docker step (`_teardown_container` is a no-op
        here) and the background gc sweep."""
        self._down_worktree_tail(state, force)

    def _teardown_container(self, state: IsolationState) -> None:
        """No container in this mode — the host env is the env (spec §B)."""

    def _spawn_gc(self) -> None:
        """No-op: the host-wide gc sweep is docker-coupled (reaps containers /
        vsc-* images), meaningless without a docker socket in this mode."""
