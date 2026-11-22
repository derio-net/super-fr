"""How fr starts another `fr` safely from an untrusted checkout (spec 2026-10-22-fr-ops,
p4-isolated-python, p4-r7).

A child `python -m fr` run with a PR checkout as its cwd must never import a `fr/`
package that checkout plants. `-P` (safe_path, Python >= 3.11) keeps the cwd and script
dir off `sys.path`; but an EMPTY or RELATIVE `PYTHONPATH` entry (`:`, `.`, `lib`) still
resolves against the cwd, so the child's environment keeps only absolute entries. Every
spawn site uses both: `fr_argv` for the argv, `safe_fr_env` for the environment.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping


def fr_argv(*args: str) -> list[str]:
    """`[python, -P, -m, fr, *args]` for THIS interpreter."""
    return [sys.executable, "-P", "-m", "fr", *args]


def safe_fr_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """*base* (default: this process's environment) with `PYTHONPATH` reduced to its
    absolute entries, and removed when none remain."""
    env = dict(os.environ if base is None else base)
    entries = [e for e in env.pop("PYTHONPATH", "").split(os.pathsep) if os.path.isabs(e)]
    if entries:
        env["PYTHONPATH"] = os.pathsep.join(entries)
    return env


def process_start(pid: int) -> str | None:
    """The OS's start time of process *pid* (`ps -o lstart=`, the C locale), or None when it
    is not running or cannot be read. A pid alone proves nothing once the OS recycles it:
    the pid with this time is the process."""
    try:
        out = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True, text=True, timeout=5, check=False,
            env={**os.environ, "LC_ALL": "C"},
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None
    text = " ".join(out.stdout.split())
    return text if out.returncode == 0 and text else None


class Child:
    """A started child process, as the driver supervisor (`fr.triage.supervise`) sees it. It
    lives here because `fr.triage` starts no process outside its git seam."""

    def __init__(self, argv: list[str]) -> None:
        # No `start_new_session`: the child stays in its caller's session and process group.
        self._proc = subprocess.Popen(argv, env=safe_fr_env())
        self.pid = self._proc.pid

    def wait(self, timeout: float | None = None) -> int | None:
        """The child's return code (negative: killed by that signal), None on a timeout."""
        try:
            return self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def poll(self) -> int | None:
        return self._proc.poll()

    def terminate(self) -> None:
        try:
            self._proc.terminate()
        except ProcessLookupError:
            pass

    def kill(self) -> None:
        try:
            self._proc.kill()
        except ProcessLookupError:
            pass
