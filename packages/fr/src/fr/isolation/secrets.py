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
import os
import shlex
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from fr.isolation.types import IsolationError, _home, harden_secret_file


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

    def post_exec(self, ctx: ProfileContext) -> None: ...

    def cleanup(self, ctx: ProfileContext) -> None: ...


def _devcontainer_config(ctx: ProfileContext) -> Path:
    return ctx.worktree / ".devcontainer" / ctx.profile / "devcontainer.json"


def ensure_mounted_env_file(config: Path, repo_name: str) -> None:
    """Ensure the env-file the profile's devcontainer.json mounts exists.

    Mount-following (#272): the committed config is the source of truth — the
    fr file is created so docker can read it. An unmigrated repo that still
    mounts the legacy vk secrets path hard-errors, pointing at `fr init
    migrate`; no `--env-file` in runArgs → nothing to ensure. Factored out of
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
            raise IsolationError(
                f"{config} still mounts the legacy vk secrets path ({env_file}) — "
                "run `fr init migrate` to rewrite the --env-file mount to "
                "~/.config/fr/secrets."
            )
        if not env_file.is_file():
            env_file.parent.mkdir(parents=True, exist_ok=True)
            env_file.write_text(f"# fr isolation secrets — {repo_name}\n")
        harden_secret_file(env_file)  # 0600 file / 0700 dirs — self-heals loose perms


class EnvFileProvider:
    """Default provider. Secrets are ambient in the container via the
    devcontainer's `--env-file` mount; `up_prepare` ensures that file exists,
    and there is nothing to wrap per command."""

    def up_prepare(self, ctx: ProfileContext) -> None:
        ensure_mounted_env_file(_devcontainer_config(ctx), ctx.repo)

    def exec_wrap(self, ctx: ProfileContext, want_secrets: bool) -> ExecWrap:
        return ExecWrap()

    def post_exec(self, ctx: ProfileContext) -> None:
        return None

    def cleanup(self, ctx: ProfileContext) -> None:
        return None


# ── Infisical provider (docker substrate; universal-auth) ──────────────────

# The container DIRECTORY the scaffold bind-mounts the host token dir to. A
# directory, not a file: each secret-bearing exec gets its own uniquely named
# token file inside it (no shared-file race between concurrent execs), and a
# single-file bind mount would keep pointing at the old inode once the file is
# replaced.
CONTAINER_TOKEN_DIR = "/run/fr-secrets"


def host_token_dir(repo: str, profile: str) -> Path:
    """Host directory (0700) holding the per-exec Infisical token files (0600)
    for one workspace. The scaffold bind-mounts it to ``CONTAINER_TOKEN_DIR``;
    `exec_wrap` writes one file per exec, `post_exec` unlinks that file, and
    `cleanup` removes the directory."""
    return _home() / ".cache" / "fr" / "run-tokens" / repo / profile


def _ensure_token_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    d.chmod(0o700)  # self-heals loose perms on every call


# Mint seam: run the host-side mint, return the access token. Injected in tests
# so no real `infisical` binary / network is needed.
TokenMinter = Callable[[Sequence[str], Mapping[str, str]], str]


def _subprocess_mint(argv: Sequence[str], env: Mapping[str, str]) -> str:
    result = subprocess.run(list(argv), env={**os.environ, **env}, capture_output=True, text=True)
    if result.returncode != 0:
        # Surface stderr only — stdout carries the token on success and must
        # never leak into an error message / logs.
        raise IsolationError(
            f"infisical mint failed (rc {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


class InfisicalAuth(Protocol):
    def mint_token(self, ctx: ProfileContext) -> str | None: ...


@dataclass
class UniversalAuth:
    """Docker-substrate auth: mint a short-TTL access token on the HOST from a
    Universal-Auth machine identity. The client-id/secret are supplied to the
    mint via the environment, NEVER as argv (argv is ps-visible). The token's
    short TTL is configured on the Infisical identity (platform-side); fr cannot
    set it at mint time."""

    minter: TokenMinter = _subprocess_mint

    def mint_token(self, ctx: ProfileContext) -> str:
        auth = ctx.config["infisical"]["auth"]
        cid = os.environ.get(auth["client_id_env"])
        csec = os.environ.get(auth["client_secret_env"])
        if not cid or not csec:
            missing = [
                name
                for name, val in (
                    (auth["client_id_env"], cid),
                    (auth["client_secret_env"], csec),
                )
                if not val
            ]
            raise IsolationError(
                f"Universal-Auth env var(s) unset: {', '.join(missing)} — set the "
                "machine-identity credentials for this profile (host env / keyring)."
            )
        # Both credentials travel via env, off argv.
        env = {
            "INFISICAL_UNIVERSAL_AUTH_CLIENT_ID": cid,
            "INFISICAL_UNIVERSAL_AUTH_CLIENT_SECRET": csec,
        }
        argv = ["infisical", "login", "--method=universal-auth", "--plain", "--silent"]
        return self.minter(argv, env)


@dataclass
class KubernetesAuth:
    """k8s-substrate placeholder. The pod authenticates itself (ServiceAccount
    via Infisical Kubernetes Auth) — no host mint. The real k8s delivery is
    ESO→Secret→env at boot; see the spec's implementor note. Interface only."""

    def mint_token(self, ctx: ProfileContext) -> str | None:
        return None


def auth_for(ctx: ProfileContext) -> InfisicalAuth:
    method = ctx.config.get("infisical", {}).get("auth", {}).get("method", "universal-auth")
    if method == "universal-auth":
        return UniversalAuth()
    if method == "kubernetes-auth":
        return KubernetesAuth()
    raise IsolationError(
        f"unknown infisical auth method {method!r}; expected universal-auth | kubernetes-auth."
    )


def _default_validate(ctx: ProfileContext) -> None:
    """Up-time touchpoint check: the host-side mint (universal-auth) needs the
    `infisical` CLI on the host PATH. The in-container CLI is checked at exec
    time (it lives in the image)."""
    method = ctx.config.get("infisical", {}).get("auth", {}).get("method", "universal-auth")
    if method == "universal-auth" and shutil.which("infisical") is None:
        raise IsolationError(
            "the `infisical` CLI is not on the host PATH — required to mint the "
            "Universal-Auth token for this profile. Install it, or use kubernetes-auth."
        )


@dataclass
class InfisicalProvider:
    """On-demand, path-scoped runtime secret provider. App-secret values are
    fetched in-container by `infisical run`; the only thing conveyed from the
    host is a short-TTL token via a 0600 file in a bind-mounted 0700 directory
    (off all argv).

    Instance state: `exec_wrap` remembers the per-exec token path it wrote so
    `post_exec` can unlink exactly that file. The Target builds ONE provider
    per exec (`provider_factory(ctx)` inside `exec`), so two concurrent execs
    never share an instance — that is the assumption this relies on."""

    auth: InfisicalAuth
    validate: Callable[[ProfileContext], None] = _default_validate
    _token_path: Path | None = field(default=None, init=False, repr=False)

    def up_prepare(self, ctx: ProfileContext) -> None:
        self.validate(ctx)
        # The mount SOURCE must exist before `devcontainer up`; NO secret at up.
        _ensure_token_dir(host_token_dir(ctx.repo, ctx.profile))

    def exec_wrap(self, ctx: ProfileContext, want_secrets: bool) -> ExecWrap:
        if not want_secrets:
            return ExecWrap()
        token = self.auth.mint_token(ctx)
        name = f"{uuid4().hex}.token"  # unique per exec: no shared-file race
        if token is not None:  # universal-auth host mint; k8s self-auths in-pod
            d = host_token_dir(ctx.repo, ctx.profile)
            _ensure_token_dir(d)
            tf = d / name
            # Create 0600 from the first byte — never a window where the file
            # is readable at the umask default before a chmod.
            fd = os.open(tf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(token)
            self._token_path = tf
        inf = ctx.config["infisical"]
        # shlex.quote every interpolated value — these come from the committed
        # fr-profiles.yaml, which is PR/branch-reachable, so an un-quoted value
        # would be a shell-injection vector into the privileged in-container
        # shell (where the token is live). The user command rides "$@", never
        # interpolated.
        run = (
            "infisical run "
            f"--projectId {shlex.quote(str(inf['project_id']))} "
            f"--env {shlex.quote(str(inf['env']))} "
            f"--path {shlex.quote(str(inf['path']))} --"
        )
        # The token is read from THIS exec's mounted file INTO the env
        # in-container, so it never appears on any argv (host or container).
        # $0 / "$@" pass the user command through verbatim.
        token_path = shlex.quote(f"{CONTAINER_TOKEN_DIR}/{name}")
        script = f'INFISICAL_TOKEN="$(cat {token_path})" exec {run} "$@"'
        return ExecWrap(argv_prefix=("sh", "-lc", script, "fr-secret-wrap"), exec_env={})

    def post_exec(self, ctx: ProfileContext) -> None:
        # Remove THIS exec's token once the command returns (or aborts) — the
        # fetch happens at command START, so the token is no longer needed.
        # Other execs' files are theirs to remove; idempotent.
        tf, self._token_path = self._token_path, None
        if tf is not None:
            _shred(tf)

    def cleanup(self, ctx: ProfileContext) -> None:
        # `down`: whatever an aborted exec left behind goes too, directory
        # included (the bind mount's source no longer needs to exist).
        remove_token_dir(host_token_dir(ctx.repo, ctx.profile))


def _shred(tf: Path) -> None:
    """Best-effort overwrite, then unlink (missing is fine)."""
    try:
        if tf.is_file():
            tf.write_text("")
    except OSError:
        pass
    tf.unlink(missing_ok=True)


def remove_token_dir(d: Path) -> None:
    """Shred every file in a token dir and remove it. Idempotent; never raises
    on an absent dir. Exposed so the devcontainer teardown can call it
    UNCONDITIONALLY — independent of which provider the (possibly unreadable)
    profile config resolves to (review finding I1)."""
    if not d.is_dir():
        return
    for p in d.iterdir():
        if p.is_file():
            _shred(p)
    shutil.rmtree(d, ignore_errors=True)


def provider_for(ctx: ProfileContext) -> SecretProvider:
    """Select the provider named by the profile's `secret_provider` key,
    defaulting to `env-file` (back-compat: profiles without the key behave
    exactly as before)."""
    name = ctx.config.get("secret_provider", "env-file")
    if name == "env-file":
        return EnvFileProvider()
    if name == "infisical":
        return InfisicalProvider(auth=auth_for(ctx))
    raise IsolationError(
        f"unknown secret_provider {name!r} for profile {ctx.profile!r}; "
        "expected 'env-file' or 'infisical'."
    )
