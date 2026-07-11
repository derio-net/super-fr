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

from fr._hosts import HostBackend
from fr.isolation.types import IsolationError, harden_secret_file, secrets_env_file
from fr.plan_validator_wrapper import (
    ValidatorWrapperError,
    ensure_validator_wrapper,
    plans_dir_exists,
)

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

# No official devcontainer feature exists for glab or tea (confirmed against
# the containers.dev registry during the multi-backend design's research —
# only an unrelated "gitlab-ci-local" runner feature turned up). `None` here
# means "no feature — install via POST_CREATE instead" (see
# HOST_CLI_POST_CREATE below). See docs/superpowers/specs/
# 2026-07-09-multi-backend-git-host-adapters-design.md §9.
HOST_CLI_FEATURE: dict[HostBackend, str | None] = {
    "github": GH_FEATURE,
    "gitlab": None,
    "gitea": None,
}

# Versioned + checksummed installs (linux-amd64 only — the devcontainer
# base image's other architectures, e.g. arm64 hosts under Docker Desktop
# emulation, are a known gap, not solved here) — pinned to a specific
# released version, NOT "latest", matching BASE_IMAGE's own reproducibility
# rationale. Versions/checksums verified directly against each project's
# real release artifacts during this design (glab v1.107.0 via the GitLab
# releases API + its published checksums.txt; tea v0.14.2 via its Gitea
# release page + published checksums.txt) — reconfirm against current
# releases before reusing this snippet long after this PR merges.
HOST_CLI_POST_CREATE: dict[str, str] = {
    "gitlab": (
        "curl -fsSL "
        "'https://gitlab.com/api/v4/projects/gitlab-org%2Fcli/packages/generic/glab/"
        "1.107.0/glab_1.107.0_linux_amd64.tar.gz' -o /tmp/glab.tar.gz && "
        "echo 'eb42f56eb1a789cf4f22aa5960ff0ef60cf1e7fc1295327501f9f59030d5ae2c  "
        "/tmp/glab.tar.gz' | sha256sum -c - && "
        "tar -xzf /tmp/glab.tar.gz -C /tmp && "
        "sudo install -m 755 $(find /tmp -maxdepth 2 -name glab -type f | head -1) "
        "/usr/local/bin/glab"
    ),
    "gitea": (
        "curl -fsSL "
        "'https://gitea.com/gitea/tea/releases/download/v0.14.2/tea-0.14.2-linux-amd64' "
        "-o /tmp/tea && "
        "echo 'be4ab135752825ab223cfa87d30e7f328312a24120b70176b67c1bd4aba19cc3  "
        "/tmp/tea' | sha256sum -c - && "
        "sudo install -m 755 /tmp/tea /usr/local/bin/tea"
    ),
}

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
    commit: bool = True,
    backend: HostBackend = "github",
    host: str | None = None,
) -> Path:
    """Write the profile and (by default) commit it. Returns the devcontainer.json path.

    The profile must be committed for `fr isolation up` to see it — the
    worktree is cut from the branch's committed tree (super-fr#299 part 2). So
    scaffold commits by default; `commit=False` writes the files only.

    `backend`/`host` are repo-level (not per-profile — a repo lives on one
    host regardless of which devcontainer profile is active), written to
    `.devcontainer/fr-profiles.yaml`'s top-level keys, which
    `fr._hosts.detect_backend` reads. `backend="github"` (the default) is
    NOT written explicitly, matching `detect_backend`'s own fallback — an
    unmodified `fr-profiles.yaml` behaves identically to before this
    feature existed.
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

    host_feature = HOST_CLI_FEATURE.get(backend)
    features: dict[str, dict[str, str]] = {host_feature: {}} if host_feature else {}
    for feature in known.values():
        features[feature] = {}

    post_create = POST_CREATE
    host_post_create = HOST_CLI_POST_CREATE.get(backend)
    if host_post_create:
        post_create = f"{POST_CREATE}; {host_post_create}"

    env_file = env_file_path(repo_root, profile)
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
        "runArgs": [
            "--env-file",
            f"${{localEnv:HOME}}/.config/fr/secrets/{repo_root.name}/{profile}.env",
        ],
        "customizations": {"fr": {"profile": profile, "purpose": purpose}},
    }
    profile_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")

    _update_profiles_yaml(repo_root, profile, purpose, secrets, unknown, default, backend, host)
    _ensure_env_placeholders(env_file, repo_root.name, profile, secrets)
    include_validator_wrapper = False
    if plans_dir_exists(repo_root):
        try:
            ensure_validator_wrapper(repo_root)
        except ValidatorWrapperError as err:
            raise IsolationError(str(err)) from err
        include_validator_wrapper = True
    if commit:
        _commit_profile(repo_root, profile, include_validator_wrapper=include_validator_wrapper)
    return config_path


def _commit_profile(
    repo_root: Path, profile: str, *, include_validator_wrapper: bool = False
) -> None:
    """Scoped commit of just the profile files on the current branch (HEAD).

    Stages only what scaffold wrote — `.devcontainer/<profile>/` and
    `.devcontainer/fr-profiles.yaml` — so the operator's other working-tree
    changes are never swept in. The host secrets env-file lives outside the
    repo and is never committed. No-ops cleanly when nothing is staged: a
    git-ignored `.devcontainer` warns; an unchanged re-scaffold is silent.
    """
    paths = [f".devcontainer/{profile}", ".devcontainer/fr-profiles.yaml"]
    if include_validator_wrapper:
        paths.append("scripts/validate-plans.sh")
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
    backend: HostBackend = "github",
    host: str | None = None,
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
    # Repo-level (not per-profile) keys `fr._hosts.detect_backend` reads.
    # "github" is NOT written explicitly — matches detect_backend's own
    # fallback, so a repo that scaffolds nothing special behaves
    # identically to before this feature existed.
    if backend != "github":
        data["backend"] = backend
    if host:
        data["host"] = host
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
    harden_secret_file(env_file)  # 0600 file / 0700 dirs — never a world-readable store
