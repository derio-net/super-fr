"""LocalWorktreeDevcontainerTarget — worktree + devcontainer over a Runner seam.

Every external call (git, devcontainer, docker, gh) goes through `runner` so
the lifecycle is unit-testable without Docker. The devcontainer CLI labels
containers with `devcontainer.local_folder=<workspace>`, which is how status
and down re-find the container.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vk.isolation.types import (
    IsolationError,
    IsolationState,
    resolve_profile,
    save_state,
    state_path,
)

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


def subprocess_runner(
    argv: list[str], cwd: Path | None = None, check: bool = False
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, check=check, capture_output=True, text=True)


def _home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


class LocalWorktreeDevcontainerTarget:
    def __init__(self, repo_root: Path, runner: Runner = subprocess_runner):
        self.repo_root = Path(repo_root)
        self.run = runner

    # ---------- lifecycle ----------

    def up(self, profile: str | None, branch: str, path: Path | None = None) -> IsolationState:
        if not (self.repo_root / ".git").exists():
            raise IsolationError(
                f"{self.repo_root} is not a git repo — vk isolation only runs inside one."
            )
        name = resolve_profile(self.repo_root, profile)

        worktree = path or (
            _home()
            / ".cache"
            / "vk"
            / "worktrees"
            / self.repo_root.name
            / branch.replace("/", "__")
        )
        worktree.parent.mkdir(parents=True, exist_ok=True)
        self._git_worktree_add(worktree, branch)

        env_file = self._env_file(name)
        if not env_file.is_file():
            env_file.parent.mkdir(parents=True, exist_ok=True)
            env_file.write_text(f"# vk isolation secrets — {self.repo_root.name}/{name}\n")

        config = worktree / ".devcontainer" / name / "devcontainer.json"
        git_dir = self.repo_root / ".git"
        result = self.run(
            [
                "devcontainer",
                "up",
                f"--workspace-folder={worktree}",
                f"--config={config}",
                f"--mount=type=bind,source={git_dir},target={git_dir}",
            ],
            cwd=worktree,
        )
        if result.returncode != 0:
            raise IsolationError(f"devcontainer up failed: {result.stderr or result.stdout}")

        state = IsolationState(
            repo_root=self.repo_root,
            branch=branch,
            worktree=worktree,
            profile=name,
            created_at=datetime.now(UTC).isoformat(),
        )
        save_state(state)
        return state

    def exec(self, state: IsolationState, argv: list[str]) -> int:
        config = state.worktree / ".devcontainer" / state.profile / "devcontainer.json"
        result = self.run(
            [
                "devcontainer",
                "exec",
                f"--workspace-folder={state.worktree}",
                f"--config={config}",
                *argv,
            ],
            cwd=state.worktree,
        )
        return result.returncode

    def status(self, state: IsolationState) -> dict[str, Any]:
        return {
            "repo": str(state.repo_root),
            "branch": state.branch,
            "profile": state.profile,
            "worktree": str(state.worktree),
            "worktree_exists": state.worktree.is_dir(),
            "container": self._container_state(state) or "not running",
            "pr": self._pr(state),
        }

    def down(self, state: IsolationState, force: bool = False) -> None:
        pr = self._pr(state)
        if pr and pr.get("state") == "OPEN" and not force:
            raise IsolationError(
                f"PR for {state.branch} is still open ({pr.get('url', '?')}) — "
                "the operator may push to it. Re-run with --force to tear down anyway."
            )
        container = self._container_id(state)
        if container:
            self.run(["docker", "stop", container])
            self.run(["docker", "rm", container])
        self.run(
            ["git", "worktree", "remove", "--force", str(state.worktree)],
            cwd=self.repo_root,
        )
        state_path(state.repo_root, state.branch).unlink(missing_ok=True)

    # ---------- helpers ----------

    def _git_worktree_add(self, worktree: Path, branch: str) -> None:
        if worktree.exists():
            return  # already provisioned — up() is idempotent on the worktree
        branches = self.run(["git", "branch", "--list", branch], cwd=self.repo_root)
        if branches.stdout.strip():
            argv = ["git", "worktree", "add", str(worktree), branch]
        else:
            argv = ["git", "worktree", "add", str(worktree), "-b", branch]
        result = self.run(argv, cwd=self.repo_root)
        if result.returncode != 0:
            raise IsolationError(f"git worktree add failed: {result.stderr}")

    def _env_file(self, profile: str) -> Path:
        return _home() / ".config" / "vk" / "secrets" / self.repo_root.name / f"{profile}.env"

    def _docker_ps(self, state: IsolationState) -> str:
        result = self.run(
            [
                "docker",
                "ps",
                "--all",
                f"--filter=label=devcontainer.local_folder={state.worktree}",
                "--format={{.ID}} {{.State}}",
            ]
        )
        return (result.stdout or "").strip()

    def _container_id(self, state: IsolationState) -> str | None:
        line = self._docker_ps(state)
        return line.split()[0] if line else None

    def _container_state(self, state: IsolationState) -> str | None:
        line = self._docker_ps(state)
        return line.split()[1] if line and len(line.split()) > 1 else None

    def _pr(self, state: IsolationState) -> dict[str, Any] | None:
        result = self.run(
            ["gh", "pr", "view", state.branch, "--json", "state,url"],
            cwd=self.repo_root,
        )
        if result.returncode != 0 or not (result.stdout or "").strip():
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
