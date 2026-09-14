"""The SecretProvider seam for fr isolation.

A provider turns a profile's declared secret keys into (a) host-side setup at
`fr isolation up`, and (b) a per-command injection for a command that requests
secrets. `env-file` (the default) keeps today's ambient model — all declared
keys mounted into the container via the devcontainer's `--env-file`. `infisical`
is on-demand and path-scoped: the command runs under `infisical run`, fed a
short-TTL token through a per-workspace, per-exec token file that the
profile's devcontainer.json bind-mounts (devcontainer mode only).

See docs/superpowers/specs/2026-06-15-infisical-secret-provider-design.md.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
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


def _run_args(config: Path) -> list[str]:
    """The profile's `runArgs`, or [] when the file is missing/unparseable."""
    try:
        args = json.loads(config.read_text()).get("runArgs", [])
    except (OSError, json.JSONDecodeError, AttributeError):
        return []
    return [str(a) for a in args] if isinstance(args, list) else []


def ensure_mounted_env_file(config: Path, repo_name: str) -> None:
    """Ensure the env-file the profile's devcontainer.json mounts exists.

    Mount-following (#272): the committed config is the source of truth — the
    fr file is created so docker can read it. An unmigrated repo that still
    mounts the legacy vk secrets path hard-errors, pointing at `fr init
    migrate`; no `--env-file` in runArgs → nothing to ensure. Shared by the
    EnvFileProvider and (historically) the local target.
    """
    run_args = _run_args(config)
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

# Host root of every token dir; the scaffold lays workspaces out beneath it.
TOKEN_DIR_ROOT = (".cache", "fr", "run-tokens")


TOKEN_LAYOUT = "~/.cache/fr/run-tokens/<repo>/<profile>/<workspace>"


def token_root() -> Path:
    return _home().joinpath(*TOKEN_DIR_ROOT)


def contain_token_dir(candidate: Path, origin: str) -> Path:
    """The ONLY way a token-dir path becomes usable (verification V1).

    `remove_token_dir` truncates and removes whatever it is pointed at, and the
    mount source it is derived from is committed, PR-reachable text — so the
    resolved path must be exactly ``<root>/<repo>/<profile>/<workspace>``:
    lexically under ``~/.cache/fr/run-tokens`` after `..` collapsing, three
    components deep, and with no symlink anywhere in those three components
    (a link would make `iterdir()` truncate the files it points at). Anything
    else is an actionable IsolationError naming `origin` and the layout."""
    if ".." in Path(candidate).parts:
        # Refused BEFORE normalisation (W2): normpath collapses `..` lexically
        # while the kernel resolves it through symlinks, so fr and docker could
        # disagree about which directory the mount names.
        raise IsolationError(
            f"refusing token dir {candidate} (from {origin}): `..` is not allowed anywhere in "
            f"the path — it must be exactly {TOKEN_LAYOUT}."
        )
    root = Path(os.path.normpath(token_root()))
    norm = Path(os.path.normpath(candidate))
    try:
        rel = norm.relative_to(root)
    except ValueError:
        rel = None
    if rel is None or len(rel.parts) != 3 or any(p in ("", ".", "..") for p in rel.parts):
        raise IsolationError(
            f"refusing token dir {candidate} (from {origin}): it must be exactly "
            f"{TOKEN_LAYOUT} — three components under ~/.cache/fr/run-tokens, nothing else. "
            "fr truncates and removes that directory at down, so no other path may be named."
        )
    if os.path.realpath(norm) != os.path.join(os.path.realpath(root), *rel.parts):
        raise IsolationError(
            f"refusing token dir {candidate} (from {origin}): a path component is a symlink — "
            f"the token dir must be a real directory under {TOKEN_LAYOUT}."
        )
    return norm


def canonical_token_dir(repo: str, profile: str, worktree: Path) -> Path:
    """The scaffold's layout for one WORKSPACE's token dir:
    ``~/.cache/fr/run-tokens/<repo>/<profile>/<worktree-basename>`` (0700,
    holding 0600 per-exec token files). Per workspace (review I1) so tearing
    one worktree down never removes a sibling's live bind-mount source.

    This is the FALLBACK spelling — used when the mount cannot be read (an
    unreadable devcontainer.json, a worktree that is already gone). Live code
    paths resolve the dir from the committed mount instead (`resolve_token_dir`).
    Contained like every other spelling (an empty basename or a `..` refuses).
    """
    return contain_token_dir(
        token_root() / repo / profile / worktree.name,
        f"canonical layout {repo!r}/{profile!r}/{worktree.name!r}",
    )


def token_mount_source(config: Path) -> str | None:
    """The raw (unsubstituted) `source=` of the `--mount` in the profile's
    `runArgs` whose target is ``CONTAINER_TOKEN_DIR``; None when absent or the
    config is unreadable. Accepts both `--mount <spec>` and `--mount=<spec>`."""
    run_args = _run_args(config)
    specs: list[str] = []
    for i, arg in enumerate(run_args):
        if arg == "--mount" and i + 1 < len(run_args):
            specs.append(run_args[i + 1])
        elif arg.startswith("--mount="):
            specs.append(arg[len("--mount=") :])
    for spec in specs:
        kv = dict(part.split("=", 1) for part in spec.split(",") if "=" in part)
        target = kv.get("target") or kv.get("dst") or kv.get("destination")
        if target == CONTAINER_TOKEN_DIR:
            return kv.get("source") or kv.get("src")
    return None


# `${localEnv:VAR}`, `${localEnv:VAR:default}` (verification V7),
# `${localWorkspaceFolderBasename}`, `${localWorkspaceFolder}` — the variables
# the devcontainer CLI substitutes in runArgs.
_VAR = re.compile(
    r"\$\{(localEnv:([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?"
    r"|localWorkspaceFolderBasename|localWorkspaceFolder)\}"
)


def _substitute(value: str, worktree: Path) -> str:
    """The devcontainer variables a mount source may carry, resolved the way
    the devcontainer CLI resolves them for THIS workspace."""

    def repl(m: re.Match[str]) -> str:
        if m.group(1) == "localWorkspaceFolderBasename":
            return worktree.name
        if m.group(1) == "localWorkspaceFolder":
            return str(worktree)
        name, default = m.group(2), m.group(3)
        if name == "HOME":
            return str(_home())
        # `env[name] || default` (W3): a variable that is set but EMPTY takes
        # the default, as a JS `||` does; no default → "" like a shell.
        return os.environ.get(name) or (default if default is not None else "")

    return _VAR.sub(repl, value)


def resolve_token_dir(config: Path, worktree: Path) -> Path:
    """The HOST directory the container will see at ``CONTAINER_TOKEN_DIR``,
    resolved from the profile's committed mount (review I2 — mirrors #272's
    mount-following for the env-file). The scaffold bakes the scaffold-time
    repo dir name into the mount; recomputing it at runtime from the
    main-checkout basename diverges whenever the clone is named differently,
    so the mount is the only source of truth. Raises an actionable
    IsolationError when the profile declares no such mount."""
    src = token_mount_source(config)
    if src is None:
        raise IsolationError(
            f"{config} declares no `--mount type=bind,source=…,target={CONTAINER_TOKEN_DIR}` "
            "in runArgs, so the container has nowhere to read the Infisical token from. "
            "Re-run `fr init scaffold --secret-provider infisical … --force` for this "
            "profile (the mount is per workspace: "
            "~/.cache/fr/run-tokens/<repo>/<profile>/${localWorkspaceFolderBasename})."
        )
    resolved = _substitute(src, worktree)
    if "${" in resolved:
        raise IsolationError(
            f"refusing token dir from mount source {src!r}: it carries a variable fr does not "
            f"resolve ({resolved!r}); the source must resolve to {TOKEN_LAYOUT}."
        )
    return contain_token_dir(Path(resolved), f"mount source {src!r}")


def _ensure_token_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    d.chmod(0o700)  # self-heals loose perms on every call


# Mint seam: run the host-side mint, return the access token. Injected in tests
# so no real `infisical` binary / network is needed.
TokenMinter = Callable[[Sequence[str], Mapping[str, str]], str]

MINT_TIMEOUT_S = 60


def _subprocess_mint(argv: Sequence[str], env: Mapping[str, str]) -> str:
    try:
        result = subprocess.run(
            list(argv),
            env={**os.environ, **env},
            capture_output=True,
            text=True,
            timeout=MINT_TIMEOUT_S,
        )
    except FileNotFoundError as e:
        raise IsolationError(
            "the `infisical` CLI is not on the host PATH — required to mint the "
            "Universal-Auth token. Install it on the host, or use kubernetes-auth."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise IsolationError(
            f"infisical mint timed out after {MINT_TIMEOUT_S}s — is the Infisical host "
            "reachable from this machine?"
        ) from e
    if result.returncode != 0:
        # Surface stderr only — stdout carries the token on success and must
        # never leak into an error message / logs.
        raise IsolationError(
            f"infisical mint failed (rc {result.returncode}): {result.stderr.strip()}"
        )
    token = result.stdout.strip()
    if not token:
        raise IsolationError(
            "infisical mint returned no token (rc 0, empty stdout) — refusing to write an "
            "empty token file; check the machine identity and the CLI version's --plain output."
        )
    return token


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
        auth = validate_infisical_config(ctx)["auth"]
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


AUTH_METHODS = ("universal-auth", "kubernetes-auth")


def _auth_method(ctx: ProfileContext) -> str:
    inf = ctx.config.get("infisical")
    auth = inf.get("auth") if isinstance(inf, Mapping) else None
    method = auth.get("method", "universal-auth") if isinstance(auth, Mapping) else "universal-auth"
    return str(method)


def validate_infisical_config(ctx: ProfileContext) -> Mapping[str, Any]:
    """The profile's `infisical:` block, checked BEFORE anything is minted
    (review I3): a half-written fr-profiles.yaml must fail as a clean
    IsolationError with no token ever written, never as a KeyError after the
    token hit disk. Returns the block with `auth` guaranteed present."""
    where = f"profile {ctx.profile!r} (.devcontainer/fr-profiles.yaml)"
    inf = ctx.config.get("infisical")
    if not isinstance(inf, Mapping):
        raise IsolationError(
            f"{where}: secret_provider is infisical but there is no `infisical:` block — "
            "re-run `fr init scaffold --secret-provider infisical --infisical-project … "
            "--infisical-env … --infisical-path …`."
        )
    missing = [k for k in ("project_id", "env", "path") if not inf.get(k)]
    if missing:
        raise IsolationError(
            f"{where}: `infisical:` block is missing {', '.join(missing)} — "
            "every infisical profile needs project_id, env and path."
        )
    auth = inf.get("auth", {})
    if not isinstance(auth, Mapping):
        raise IsolationError(f"{where}: `infisical.auth` must be a mapping.")
    method = str(auth.get("method", "universal-auth"))
    if method not in AUTH_METHODS:
        raise IsolationError(
            f"{where}: unknown infisical auth method {method!r}; expected "
            f"{' | '.join(AUTH_METHODS)}."
        )
    if method == "universal-auth":
        missing = [k for k in ("client_id_env", "client_secret_env") if not auth.get(k)]
        if missing:
            raise IsolationError(
                f"{where}: universal-auth needs {', '.join(missing)} under `infisical.auth` "
                "(the HOST env var names holding the machine-identity credentials)."
            )
    return {**inf, "auth": {**auth, "method": method}}


def auth_for(ctx: ProfileContext) -> InfisicalAuth:
    method = _auth_method(ctx)
    if method == "universal-auth":
        return UniversalAuth()
    if method == "kubernetes-auth":
        return KubernetesAuth()
    raise IsolationError(
        f"unknown infisical auth method {method!r}; expected {' | '.join(AUTH_METHODS)}."
    )


def _default_validate(ctx: ProfileContext) -> None:
    """Up-time touchpoint check: the host-side mint (universal-auth) needs the
    `infisical` CLI on the host PATH. The in-container CLI is checked at exec
    time (it lives in the image)."""
    if _auth_method(ctx) == "universal-auth" and shutil.which("infisical") is None:
        raise IsolationError(
            "the `infisical` CLI is not on the host PATH — required to mint the "
            "Universal-Auth token for this profile. Install it, or use kubernetes-auth."
        )


@dataclass
class InfisicalProvider:
    """On-demand, path-scoped runtime secret provider. App-secret values are
    fetched in-container by `infisical run`; the only thing conveyed from the
    host is a short-TTL token via a 0600 file in the workspace's bind-mounted
    0700 directory (off all argv).

    Instance state: `exec_wrap` remembers the per-exec token path it wrote so
    `post_exec` can unlink exactly that file. The Target builds ONE provider
    per exec (`provider_factory(ctx)` inside `exec`), so two concurrent execs
    never share an instance — that is the assumption this relies on."""

    auth: InfisicalAuth
    validate: Callable[[ProfileContext], None] = _default_validate
    _token_path: Path | None = field(default=None, init=False, repr=False)

    def up_prepare(self, ctx: ProfileContext) -> None:
        inf = validate_infisical_config(ctx)
        self.validate(ctx)
        config = _devcontainer_config(ctx)
        # The mount SOURCE must exist before `devcontainer up` (docker does not
        # create bind sources) — whenever the profile declares the mount,
        # whatever the auth method (verification V4: the scaffold always writes
        # it). universal-auth additionally REQUIRES it, since that is where the
        # host token travels. NO secret at up.
        if inf["auth"]["method"] == "universal-auth" or token_mount_source(config) is not None:
            _ensure_token_dir(resolve_token_dir(config, ctx.worktree))

    def exec_wrap(self, ctx: ProfileContext, want_secrets: bool) -> ExecWrap:
        if not want_secrets:
            return ExecWrap()
        # Everything that can fail on configuration fails HERE, before the mint,
        # so a bad profile never leaves a live token on disk (review I3).
        inf = validate_infisical_config(ctx)
        host_mint = inf["auth"]["method"] == "universal-auth"
        token_dir = (
            resolve_token_dir(_devcontainer_config(ctx), ctx.worktree) if host_mint else None
        )
        token = self.auth.mint_token(ctx)
        # shlex.quote every interpolated value — these come from the committed
        # fr-profiles.yaml, which is PR/branch-reachable, so an un-quoted value
        # would be a shell-injection vector into the privileged in-container
        # shell (where the token is live). The user command rides "$@", never
        # interpolated. `env -u INFISICAL_TOKEN -- "$@"` strips the token from
        # the child's env: `infisical run` injects the fetched secrets AND its
        # own INFISICAL_TOKEN, which the user command must not be able to reuse.
        # The `--` ends env's operand parsing so a command starting with
        # NAME=VALUE or -x is executed, not read as an assignment/option.
        run = (
            "infisical run "
            f"--projectId {shlex.quote(str(inf['project_id']))} "
            f"--env {shlex.quote(str(inf['env']))} "
            f"--path {shlex.quote(str(inf['path']))} -- "
            'env -u INFISICAL_TOKEN -- "$@"'
        )
        if token is None or token_dir is None:
            # In-pod auth (kubernetes-auth): no host token, so no file to read
            # and NO `INFISICAL_TOKEN=""` that would shadow the pod's own auth.
            return ExecWrap(argv_prefix=("sh", "-lc", f"exec {run}", "fr-secret-wrap"))
        _ensure_token_dir(token_dir)
        name = f"{uuid4().hex}.token"  # unique per exec: no shared-file race
        tf = token_dir / name
        # Create 0600 from the first byte — never a window where the file is
        # readable at the umask default before a chmod.
        fd = os.open(tf, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        # Remember the path BEFORE writing (verification V5): a write that fails
        # halfway still leaves a file post_exec must remove.
        self._token_path = tf
        with os.fdopen(fd, "w") as fh:
            fh.write(token)
        # The token is read from THIS exec's mounted file INTO the env
        # in-container, so it never appears on any argv (host or container).
        token_path = shlex.quote(f"{CONTAINER_TOKEN_DIR}/{name}")
        script = f'INFISICAL_TOKEN="$(cat {token_path})" exec {run}'
        return ExecWrap(argv_prefix=("sh", "-lc", script, "fr-secret-wrap"), exec_env={})

    def post_exec(self, ctx: ProfileContext) -> None:
        # Remove THIS exec's token once the command returns (or aborts) — the
        # fetch happens at command START, so the token is no longer needed.
        # Other execs' files are theirs to remove; idempotent, no-op when
        # exec_wrap never wrote a file.
        tf, self._token_path = self._token_path, None
        if tf is not None:
            _truncate_and_unlink(tf)

    def cleanup(self, ctx: ProfileContext) -> None:
        # `down`: whatever an aborted exec left behind goes too, directory
        # included (the bind mount's source no longer needs to exist). The
        # mount is the source of truth; an unreadable one falls back to the
        # canonical layout so cleanup still reaches the right workspace dir.
        try:
            d = resolve_token_dir(_devcontainer_config(ctx), ctx.worktree)
        except IsolationError:
            d = canonical_token_dir(ctx.repo, ctx.profile, ctx.worktree)
        remove_token_dir(d)


def _truncate_and_unlink(tf: Path) -> None:
    """Best-effort truncate, then unlink (missing is fine). Not a forensic
    shred — the token is short-TTL; this only keeps it out of a casual read of
    a file that outlived its exec.

    Host-side defence (W1): the token dir is bind-mounted into the container
    (read-only by the scaffold, but a hand-edited mount may not be), and code
    in there knows the per-exec file name. It could swap the file for a symlink
    to any host file this user can write, or for a FIFO. So the truncate opens
    with O_NOFOLLOW (ELOOP on a link — never truncate through it) and
    O_NONBLOCK (ENXIO on a reader-less FIFO — never hang), swallows every
    OSError, and the unlink removes the entry itself, never a target."""
    try:
        fd = os.open(tf, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW | os.O_NONBLOCK)
        os.close(fd)
    except OSError:
        pass  # ELOOP, ENXIO, ENOENT, EISDIR, … — the unlink below still applies
    try:
        tf.unlink(missing_ok=True)
    except OSError as e:  # a planted directory, a permission oddity — never raise from a finally
        print(f"warning: could not remove token file {tf}: {e}", file=sys.stderr)


def remove_token_dir(d: Path) -> None:
    """Truncate every file in a token dir and remove it. Idempotent; never
    raises on an absent dir. Exposed so the devcontainer teardown and gc can
    call it UNCONDITIONALLY — independent of which provider the (possibly
    unreadable) profile config resolves to (review finding I1).

    Defence in depth (verification V1): callers are expected to hand it a
    contained path, but it re-checks — a symlinked dir or a path outside
    ``TOKEN_LAYOUT`` is refused as a logged no-op, and symlinked children are
    never truncated through (rmtree removes the link itself, not its target)."""
    if d.is_symlink():
        print(f"warning: refusing to remove token dir {d}: it is a symlink", file=sys.stderr)
        return
    if not d.is_dir():
        return
    try:
        contain_token_dir(d, f"path {d}")
    except IsolationError as e:
        print(f"warning: refusing to remove token dir: {e}", file=sys.stderr)
        return
    for p in d.iterdir():
        if p.is_symlink() or p.is_dir():
            continue  # rmtree unlinks a link itself (never its target) and walks real subdirs
        _truncate_and_unlink(p)  # regular file, FIFO, whatever was planted: O_NOFOLLOW|O_NONBLOCK
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
