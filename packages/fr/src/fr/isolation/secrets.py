"""The SecretProvider seam for fr isolation.

A provider turns a profile's declared secret keys into (a) host-side setup at
`fr isolation up`, and (b) a per-command injection for a command that requests
secrets. `env-file` (the default) keeps today's ambient model — all declared
keys mounted into the container via the devcontainer's `--env-file`. `infisical`
(added in a later phase) is on-demand and path-scoped.

See docs/superpowers/specs/2026-06-15-infisical-secret-provider-design.md.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from fr.isolation.types import IsolationError, _home, _warn_legacy


@dataclass(frozen=True)
class ProfileContext:
    """What a SecretProvider needs about one profile, built from
    IsolationState + the profile's `fr-profiles.yaml` entry."""

    repo: str
    profile: str
    keys: tuple[str, ...]
    config: Mapping[str, Any]
    worktree: Path


@dataclass(frozen=True)
class ExecWrap:
    """How to make a command's secrets available. `env-file` returns the empty
    wrap (ambient); a fetch provider returns an in-container argv prefix plus
    extra (non-secret) env for that one exec."""

    argv_prefix: tuple[str, ...] = ()
    exec_env: Mapping[str, str] = field(default_factory=dict)


class SecretProvider(Protocol):
    def up_prepare(self, ctx: ProfileContext) -> None: ...

    def exec_wrap(self, ctx: ProfileContext, want_secrets: bool) -> ExecWrap: ...


def _devcontainer_config(ctx: ProfileContext) -> Path:
    return ctx.worktree / ".devcontainer" / ctx.profile / "devcontainer.json"


def ensure_mounted_env_file(config: Path, repo_name: str) -> None:
    """Ensure the env-file the profile's devcontainer.json mounts exists.

    Mount-following (#272): the committed config is the source of truth — an
    unmigrated repo still mounts the legacy vk path, so creating the fr file
    would not help docker. Warn on the legacy spelling; no `--env-file` in
    runArgs → nothing to ensure. Factored out of
    `local.LocalWorktreeDevcontainerTarget._ensure_mounted_env_file` so the
    EnvFileProvider and the target share one implementation.
    """
    try:
        run_args = json.loads(config.read_text()).get("runArgs", [])
    except (OSError, json.JSONDecodeError):
        return
    for flag, value in zip(run_args, run_args[1:]):
        if flag != "--env-file":
            continue
        env_file = Path(value.replace("${localEnv:HOME}", str(_home())))
        if "/.config/vk/secrets/" in str(env_file):
            _warn_legacy("secrets env-file mount", env_file)
        if not env_file.is_file():
            env_file.parent.mkdir(parents=True, exist_ok=True)
            env_file.write_text(f"# fr isolation secrets — {repo_name}\n")


class EnvFileProvider:
    """Default provider. Secrets are ambient in the container via the
    devcontainer's `--env-file` mount; `up_prepare` ensures that file exists,
    and there is nothing to wrap per command."""

    def up_prepare(self, ctx: ProfileContext) -> None:
        ensure_mounted_env_file(_devcontainer_config(ctx), ctx.repo)

    def exec_wrap(self, ctx: ProfileContext, want_secrets: bool) -> ExecWrap:
        return ExecWrap()


def provider_for(ctx: ProfileContext) -> SecretProvider:
    """Select the provider named by the profile's `secret_provider` key,
    defaulting to `env-file` (back-compat: profiles without the key behave
    exactly as before)."""
    name = ctx.config.get("secret_provider", "env-file")
    if name == "env-file":
        return EnvFileProvider()
    raise IsolationError(
        f"unknown secret_provider {name!r} for profile {ctx.profile!r}; "
        "expected 'env-file' (or 'infisical')."
    )
