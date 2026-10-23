"""How every probe runs (spec 2026-10-22-fr-ops R5): `check`, `na_if`, `escalate`,
`ready` and an identity's `from:`.

Each runs via `bash -euo pipefail -c` in the repo root with stdin closed, a bounded
timeout, and a minimal environment: `MINIMAL_ENV` from this process, the names
`.fr/ops.yaml` lists in `env_passthrough:`, and whatever the caller adds (an
identity's variables, for `check`/`apply` only). Probes are repo-authored code, run
only once the operator trusted them (R19); the minimal env keeps what they can read
to what the operator named.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

MINIMAL_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TERM", "TMPDIR", "USER")
DEFAULT_TIMEOUT = 60
TIMED_OUT = -1000
"""The exit a timed-out probe reports: outside every real exit and signal code."""
NOT_FOUND = 127
"""A probe's exit when its command could not run (bash: command not found)."""


def probe_env(
    passthrough: Sequence[str] = (), extra: Mapping[str, str] | None = None
) -> dict[str, str]:
    names = (*MINIMAL_ENV, *passthrough)
    env = {name: os.environ[name] for name in names if name in os.environ}
    env.update(extra or {})
    return env


def run_probe_full(
    command: str,
    cwd: Path,
    *,
    extra: Mapping[str, str] | None = None,
    passthrough: Sequence[str] = (),
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[int, str, str]:
    """`(exit, stdout, stderr)`; `TIMED_OUT` when the timeout expired, `NOT_FOUND` when
    bash could not start."""
    try:
        done = subprocess.run(
            ["bash", "-euo", "pipefail", "-c", command],
            cwd=cwd,
            env=probe_env(passthrough, extra),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return TIMED_OUT, "", ""
    except OSError:
        return NOT_FOUND, "", ""
    return done.returncode, done.stdout, done.stderr


def run_probe(
    command: str,
    cwd: Path,
    *,
    extra: Mapping[str, str] | None = None,
    passthrough: Sequence[str] = (),
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[int, str]:
    """`(exit, stdout)` — `run_probe_full` without the stderr."""
    rc, out, _ = run_probe_full(command, cwd, extra=extra, passthrough=passthrough, timeout=timeout)
    return rc, out


def run_interactive(
    command: str,
    cwd: Path,
    *,
    extra: Mapping[str, str] | None = None,
    passthrough: Sequence[str] = (),
    tty: str = "/dev/tty",
) -> int:
    """Run an `interactive: true` op's apply with the operator's terminal attached.

    The one deliberate departure from `run_probe`: stdin, stdout and stderr are the
    terminal (`tty`, never this process's own streams, which an agent's harness may
    own), there is no timeout (a person is answering), and the output is not
    captured, so it cannot be masked. The environment is still the minimal one.
    `NOT_FOUND` when there is no terminal to attach."""
    try:
        with open(tty, "r+b", buffering=0) as term:
            done = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", command],
                cwd=cwd,
                env=probe_env(passthrough, extra),
                stdin=term,
                stdout=term,
                stderr=term,
                check=False,
            )
    except OSError:
        return NOT_FOUND
    return done.returncode
