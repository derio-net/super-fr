"""The runner plumbing under the isolation lifecycle (#1517).

Holds the `Runner` seam type, the devcontainer id derivation, the real
`subprocess_runner` and the detached-gc spawners. Split out of `local.py`;
a leaf module that imports nothing else from `fr.isolation`.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

Runner = Callable[..., "subprocess.CompletedProcess[str]"]

_BASE32 = "0123456789abcdefghijklmnopqrstuv"


def devcontainer_id(local_folder: str, config_file: str) -> str:
    """The devcontainer CLI's `${devcontainerId}` for a container's id labels:
    sha256 of the sorted label JSON, as a base-32 number padded to 52 chars.

    Features key per-workspace named volumes on it (docker-in-docker:
    `dind-var-lib-docker-<id>`), so it is how teardown tells a volume this
    workspace owns from one it merely shares."""
    labels = {
        "devcontainer.config_file": config_file,
        "devcontainer.local_folder": local_folder,
    }
    raw = json.dumps(labels, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    n = int.from_bytes(hashlib.sha256(raw.encode("utf-8")).digest(), "big")
    digits = ""
    while n:
        n, r = divmod(n, 32)
        digits = _BASE32[r] + digits
    return digits.rjust(52, "0")


def _missing_binary(err: FileNotFoundError, context: str) -> str:
    """One line naming the binary the runner could not find — from the error
    itself, never an assumed name."""
    missing = err.filename or (err.args[0] if err.args else "a required binary")
    return f"{missing} not found on PATH — {context}."


def subprocess_runner(
    argv: list[str],
    cwd: Path | None = None,
    check: bool = False,
    capture: bool = True,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """capture=False inherits stdio — exec passthrough must stream the
    container's output live (long builds/test runs), not swallow it.

    `timeout` makes the call bounded AND non-interactive: stdin is /dev/null,
    and an expiry returns exit 124 with a `timed out` stderr instead of
    raising, so a caller reads it as a failure (for a probe: `unknown`)."""
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            check=check,
            capture_output=capture,
            text=True,
            env=env,
            timeout=timeout,
            stdin=subprocess.DEVNULL if timeout is not None else None,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            argv, 124, stdout="", stderr=f"{argv[0]}: timed out after {timeout:g}s\n"
        )


def _home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


# --- opportunistic gc spawn seam (#354 Task B) ---
#
# `up`/`down` fire a detached `fr isolation gc` after their own work — the
# primary auto-trigger that bounds the steady-state leak to <=1 workspace with
# no daemon. Routed through an INJECTABLE seam (not the Runner: a fire-and-forget
# Popen is a different shape than subprocess.run) so the non-blocking /
# non-raising contract is testable. The library default is a NO-OP — production
# opts into the real spawn at the CLI boundary, so a Target built directly (every
# unit test, and gc's own sibling teardown Targets) never spawns.
#
# The second argument is the spawning target's MODE (gh#569, review p2-f2): a
# required part of the contract, so no wrapper or test double can silently drop
# it and hand the child sweep the caller's env instead.
GcSpawner = Callable[[Path, str], None]


def _detached_gc_spawn(repo_root: Path, mode: str) -> None:
    """Fire-and-forget `fr isolation gc`: detached (own session), non-blocking,
    output to a rotating-ish log. Any spawn error is swallowed — a caller must
    never fail because a background reap could not start.

    `mode` is always pinned as the child's `FR_ISOLATION_TARGET` (gh#569):
    the sweep's discovery and docker steps run in the SPAWNING target's mode,
    not whatever the caller's env says. A `down` of a host-worktree workspace
    run without the env would otherwise start a devcontainer sweep, which dies
    on `docker ps` (FileNotFoundError) on a docker-less pod.

    Named with `--repo` and run there rather than inheriting the caller's cwd
    (#423): a `down` fired from inside the worktree it just removed would
    otherwise hand the child a deleted cwd — `Path.cwd()` then raises and the
    sweep dies before classifying anything. It also keeps the child's
    state-record discovery source pointed at the repo the caller was working in.
    """
    try:
        log_path = _home() / ".cache" / "fr" / "isolation-gc.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = open(log_path, "a")  # noqa: SIM115 — handed to the child; not ours to close
        from fr.safe_spawn import fr_argv, safe_fr_env

        subprocess.Popen(
            fr_argv("isolation", "gc", "--repo", str(repo_root)),
            cwd=str(repo_root) if repo_root.is_dir() else None,
            env={**safe_fr_env(), "FR_ISOLATION_TARGET": mode},
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
        )
    except Exception:
        pass


def _noop_gc_spawn(repo_root: Path, mode: str) -> None:
    """The safe default — no background sweep (see GcSpawner)."""
