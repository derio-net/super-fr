"""Mechanical writer for devcontainer profiles (driven by the fr-init skill).

Writes three things per profile:
  - .devcontainer/<profile>/devcontainer.json  (committed)
  - .devcontainer/fr-profiles.yaml entry       (committed)
  - ~/.config/fr/secrets/<repo>/<profile>.env  (host-only placeholders;
    existing operator values are NEVER overwritten — only missing keys
    are appended as commented placeholders)
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from fr.isolation.types import IsolationError, secrets_env_file

# Pinned to an LTS tag, NOT the floating `:ubuntu`. The floating tag now
# resolves to Ubuntu "resolute", where the docker-in-docker feature fails to
# install (`moby` packages absent), breaking any profile scaffolded with
# `--tool docker-in-docker`. Pinning also keeps isolation workspaces
# reproducible. See super-fr#300.
BASE_IMAGE = "mcr.microsoft.com/devcontainers/base:ubuntu-24.04"

# Known tool → devcontainer feature mapping. Unknown tools land in the
# profile's notes for the skill/operator to wire via postCreateCommand.
KNOWN_TOOL_FEATURES: dict[str, str] = {
    "uv": "ghcr.io/jsburckhardt/devcontainer-features/uv:1",
    "node": "ghcr.io/devcontainers/features/node:1",
    "python": "ghcr.io/devcontainers/features/python:1",
    "go": "ghcr.io/devcontainers/features/go:1",
    "rust": "ghcr.io/devcontainers/features/rust:1",
    "kubectl": "ghcr.io/devcontainers/features/kubectl-helm-minikube:1",
    "docker-in-docker": "ghcr.io/devcontainers/features/docker-in-docker:2",
    "terraform": "ghcr.io/devcontainers/features/terraform:1",
}

GH_FEATURE = "ghcr.io/devcontainers/features/github-cli:1"

# Baseline: vk itself, installed from the repo's main branch at create time.
POST_CREATE = (
    "pipx install uv 2>/dev/null || true; "
    "uv tool install 'git+https://github.com/derio-net/super-fr#subdirectory=packages/fr' || true"
)


def env_file_path(repo_root: Path, profile: str) -> Path:
    return secrets_env_file(repo_root.name, profile)


def scaffold_profile(
    repo_root: Path,
    profile: str,
    purpose: str,
    tools: list[str],
    secrets: list[str],
    default: bool = False,
    force: bool = False,
) -> Path:
    """Write the profile. Returns the devcontainer.json path."""
    if not (repo_root / ".git").exists():
        raise IsolationError(
            f"{repo_root} is not a git repo — fr init scaffold only runs inside one."
        )

    profile_dir = repo_root / ".devcontainer" / profile
    config_path = profile_dir / "devcontainer.json"
    if config_path.exists() and not force:
        raise IsolationError(
            f"{config_path} already exists — re-run with --force to overwrite "
            "(the host secrets file is preserved either way)."
        )

    known = {t: KNOWN_TOOL_FEATURES[t] for t in tools if t in KNOWN_TOOL_FEATURES}
    unknown = [t for t in tools if t not in KNOWN_TOOL_FEATURES]

    features: dict[str, dict[str, str]] = {GH_FEATURE: {}}
    for feature in known.values():
        features[feature] = {}

    env_file = env_file_path(repo_root, profile)
    config = {
        "name": f"{repo_root.name} — {profile}",
        "image": BASE_IMAGE,
        "features": features,
        "postCreateCommand": POST_CREATE,
        # Mount the workspace at its HOST path (not /workspaces/<name>):
        # linked-worktree gitdir back-pointers record host abspaths, so git
        # only works in-container when worktree + base .git share the host
        # layout. Pairs with the base-.git mount that `fr isolation up` adds.
        "workspaceMount": "source=${localWorkspaceFolder},target=${localWorkspaceFolder},type=bind",
        "workspaceFolder": "${localWorkspaceFolder}",
        "runArgs": [
            "--env-file",
            f"${{localEnv:HOME}}/.config/fr/secrets/{repo_root.name}/{profile}.env",
        ],
        "customizations": {"fr": {"profile": profile, "purpose": purpose}},
    }
    profile_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")

    _update_profiles_yaml(repo_root, profile, purpose, secrets, unknown, default)
    _ensure_env_placeholders(env_file, repo_root.name, profile, secrets)
    return config_path


def _update_profiles_yaml(
    repo_root: Path,
    profile: str,
    purpose: str,
    secrets: list[str],
    unknown_tools: list[str],
    default: bool,
) -> None:
    path = repo_root / ".devcontainer" / "fr-profiles.yaml"
    data = yaml.safe_load(path.read_text()) if path.is_file() else {}
    data = data or {}
    data.setdefault("profiles", {})
    entry: dict[str, object] = {"purpose": purpose, "secrets": secrets}
    if unknown_tools:
        entry["notes"] = [
            f"tool {t!r} has no known devcontainer feature — wire it via postCreateCommand"
            for t in unknown_tools
        ]
    data["profiles"][profile] = entry
    if default or "default" not in data:
        data["default"] = profile if default else data.get("default", profile)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _ensure_env_placeholders(env_file: Path, repo: str, profile: str, secrets: list[str]) -> None:
    env_file.parent.mkdir(parents=True, exist_ok=True)
    existing = env_file.read_text() if env_file.is_file() else ""
    lines = [] if existing else [f"# fr isolation secrets — {repo}/{profile}", ""]
    present = {
        ln.lstrip("# ").split("=", 1)[0].strip() for ln in existing.splitlines() if "=" in ln
    }
    for key in secrets:
        if key in present:  # set or placeholder already present — never touch
            continue
        lines.append(f"# {key}=")
    if lines or not existing:
        env_file.write_text(
            existing + ("\n" if existing and lines else "") + "\n".join(lines) + "\n"
        )
