"""State, profiles, and the Target protocol for fr isolation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel


class IsolationError(Exception):
    """User-facing isolation failure; CLI maps it to exit 2."""


class IsolationState(BaseModel):
    """Everything needed to re-address an isolation workspace later."""

    repo_root: Path
    branch: str
    worktree: Path
    profile: str
    created_at: str

    model_config = {"frozen": True}


def _sanitize(branch: str) -> str:
    return branch.replace("/", "__")


def state_dir(repo_root: Path) -> Path:
    return repo_root / ".git" / "vk" / "isolation"


def state_path(repo_root: Path, branch: str) -> Path:
    return state_dir(repo_root) / f"{_sanitize(branch)}.json"


def save_state(state: IsolationState) -> Path:
    p = state_path(state.repo_root, state.branch)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(state.model_dump_json(indent=2) + "\n")
    return p


def load_state(repo_root: Path, branch: str) -> IsolationState | None:
    p = state_path(repo_root, branch)
    if not p.is_file():
        return None
    return IsolationState.model_validate_json(p.read_text())


def list_states(repo_root: Path) -> list[IsolationState]:
    d = state_dir(repo_root)
    if not d.is_dir():
        return []
    return [IsolationState.model_validate_json(f.read_text()) for f in sorted(d.glob("*.json"))]


def discover_profiles(repo_root: Path) -> list[str]:
    base = repo_root / ".devcontainer"
    return sorted(p.parent.name for p in base.glob("*/devcontainer.json"))


def profiles_config(repo_root: Path) -> dict[str, Any]:
    cfg = repo_root / ".devcontainer" / "vk-profiles.yaml"
    if not cfg.is_file():
        return {}
    return yaml.safe_load(cfg.read_text()) or {}


def resolve_profile(repo_root: Path, name: str | None) -> str:
    """Resolve the requested (or default) profile, or explain how to get one.

    Hard requirement by design: no devcontainer profile → refuse with a
    pointer at vk-init. There is no unisolated fallback.
    """
    available = discover_profiles(repo_root)
    if not available:
        raise IsolationError(
            "no devcontainer profiles found (.devcontainer/<profile>/devcontainer.json). "
            "Run the vk-init skill to scaffold one — isolation never degrades to unisolated."
        )
    if name is None:
        default = profiles_config(repo_root).get("default")
        if default and default in available:
            return str(default)
        if len(available) == 1:
            return available[0]
        raise IsolationError(
            f"multiple profiles ({', '.join(available)}) and no default in "
            ".devcontainer/vk-profiles.yaml — pass --profile or set a default via vk-init."
        )
    if name not in available:
        raise IsolationError(f"unknown profile {name!r}; available: {', '.join(available)}")
    return name


class Target(Protocol):
    """Pluggable isolation backend (local worktree+devcontainer now; remote later)."""

    def up(self, profile: str | None, branch: str, path: Path | None = None) -> IsolationState: ...

    def exec(self, state: IsolationState, argv: list[str]) -> int: ...

    def status(self, state: IsolationState) -> dict[str, Any]: ...

    def down(self, state: IsolationState, force: bool = False) -> None: ...
