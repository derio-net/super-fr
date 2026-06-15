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
import subprocess
import sys
from pathlib import Path

import yaml

from fr.isolation.secrets import CONTAINER_TOKEN_PATH
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

# Appended to postCreate for infisical-provider profiles (no devcontainer
# feature exists for the Infisical CLI). The operator verifies it on the first
# real run (see the manual phase / the spec's identity-side TTL note).
INFISICAL_INSTALL = (
    "curl -1sLf 'https://artifacts-cli.infisical.com/setup.deb.sh' | sudo -E bash 2>/dev/null; "
    "sudo apt-get install -y infisical || true"
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
    commit: bool = True,
    secret_provider: str = "env-file",
    infisical: dict[str, str] | None = None,
) -> Path:
    """Write the profile and (by default) commit it. Returns the devcontainer.json path.

    The profile must be committed for `fr isolation up` to see it — the
    worktree is cut from the branch's committed tree (super-fr#299 part 2). So
    scaffold commits by default; `commit=False` writes the files only.
    """
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

    is_infisical = secret_provider == "infisical"
    if is_infisical:
        # No host secrets env-file. Append the in-container Infisical CLI install
        # (composed, NOT overwriting POST_CREATE), and bind-mount the 0600 host
        # token-file the provider writes per request to CONTAINER_TOKEN_PATH.
        post_create = POST_CREATE + "; " + INFISICAL_INSTALL
        run_args = [
            "--mount",
            f"type=bind,source=${{localEnv:HOME}}/.cache/fr/run-tokens/"
            f"{repo_root.name}/{profile}.token,target={CONTAINER_TOKEN_PATH}",
        ]
    else:
        post_create = POST_CREATE
        run_args = [
            "--env-file",
            f"${{localEnv:HOME}}/.config/fr/secrets/{repo_root.name}/{profile}.env",
        ]
    config = {
        "name": f"{repo_root.name} — {profile}",
        "image": BASE_IMAGE,
        "features": features,
        "postCreateCommand": post_create,
        # Mount the workspace at its HOST path (not /workspaces/<name>):
        # linked-worktree gitdir back-pointers record host abspaths, so git
        # only works in-container when worktree + base .git share the host
        # layout. Pairs with the base-.git mount that `fr isolation up` adds.
        "workspaceMount": "source=${localWorkspaceFolder},target=${localWorkspaceFolder},type=bind",
        "workspaceFolder": "${localWorkspaceFolder}",
        "runArgs": run_args,
        "customizations": {"fr": {"profile": profile, "purpose": purpose}},
    }
    profile_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")

    _update_profiles_yaml(
        repo_root, profile, purpose, secrets, unknown, default, secret_provider, infisical
    )
    if is_infisical:
        print(
            f"reminder: profile {profile!r} uses Infisical (Universal Auth). Create a "
            "machine identity scoped READ-ONLY to the project/path with a SHORT "
            "Access-Token TTL (set on the identity — fr cannot set it at mint time), and "
            "export FR_INFISICAL_CLIENT_ID / FR_INFISICAL_CLIENT_SECRET on the host.",
            file=sys.stderr,
        )
    else:
        _ensure_env_placeholders(
            env_file_path(repo_root, profile), repo_root.name, profile, secrets
        )
    if commit:
        _commit_profile(repo_root, profile)
    return config_path


def _commit_profile(repo_root: Path, profile: str) -> None:
    """Scoped commit of just the profile files on the current branch (HEAD).

    Stages only what scaffold wrote — `.devcontainer/<profile>/` and
    `.devcontainer/fr-profiles.yaml` — so the operator's other working-tree
    changes are never swept in. The host secrets env-file lives outside the
    repo and is never committed. No-ops cleanly when nothing is staged: a
    git-ignored `.devcontainer` warns; an unchanged re-scaffold is silent.
    """
    paths = [f".devcontainer/{profile}", ".devcontainer/fr-profiles.yaml"]
    _git(repo_root, "add", "--", *paths)
    # `git diff --cached --quiet` → rc 0 means nothing staged (ignored/unchanged).
    if _git(repo_root, "diff", "--cached", "--quiet", "--", *paths).returncode == 0:
        if _git(repo_root, "check-ignore", "-q", f".devcontainer/{profile}").returncode == 0:
            print(
                f"warning: .devcontainer is git-ignored — profile {profile!r} written "
                "but not committed; `fr isolation up` won't see it.",
                file=sys.stderr,
            )
        return
    # Pathspec on `commit` records ONLY these paths — any other staged changes
    # the operator had stay staged, never swept into the scaffold commit.
    result = _git(
        repo_root,
        "commit",
        "-m",
        f"chore(fr): scaffold {profile} devcontainer profile",
        "--",
        *paths,
    )
    if result.returncode != 0:
        # Don't leave the profile half-staged on failure (e.g. no git identity).
        _git(repo_root, "reset", "-q", "--", *paths)
        raise IsolationError(f"git commit failed: {result.stderr.strip() or result.stdout.strip()}")


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True)


def _update_profiles_yaml(
    repo_root: Path,
    profile: str,
    purpose: str,
    secrets: list[str],
    unknown_tools: list[str],
    default: bool,
    secret_provider: str = "env-file",
    infisical: dict[str, str] | None = None,
) -> None:
    path = repo_root / ".devcontainer" / "fr-profiles.yaml"
    data = yaml.safe_load(path.read_text()) if path.is_file() else {}
    data = data or {}
    data.setdefault("profiles", {})
    entry: dict[str, object] = {"purpose": purpose, "secrets": secrets}
    if secret_provider != "env-file":
        entry["secret_provider"] = secret_provider
    if infisical:
        # Coordinates + WHERE to find the host identity (env-var names) — never
        # the secret values. The auth env-var names default to the spec's.
        entry["infisical"] = {
            "project_id": infisical["project_id"],
            "env": infisical["env"],
            "path": infisical["path"],
            "auth": {
                "method": "universal-auth",
                "client_id_env": infisical.get("client_id_env", "FR_INFISICAL_CLIENT_ID"),
                "client_secret_env": infisical.get(
                    "client_secret_env", "FR_INFISICAL_CLIENT_SECRET"
                ),
            },
        }
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
