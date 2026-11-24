"""Running one `kind: cli` workflow step, bounded (super-fr#1507).

`fr run advance` executes a cli step itself. Before this module the step ran
under `subprocess.run(shell=True)` with no timeout, and its whole stdout went
into the cursor, a git-tracked file. Here it runs with a timeout that kills
its whole process group, and the cursor keeps a bounded tail of its stdout.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from pathlib import Path

CLI_STEP_TIMEOUT_ENV = "FR_CLI_STEP_TIMEOUT"
CLI_STEP_DEFAULT_TIMEOUT = 600.0
CLI_STEP_TIMEOUT_EXIT = 124  # what coreutils `timeout` reports
CLI_STEP_STDOUT_MAX_CHARS = 16 * 1024
_DRAIN_SECONDS = 5.0


def parse_timeout(raw: str) -> float | None:
    """Seconds from `FR_CLI_STEP_TIMEOUT`'s value: empty is the default, `0` is
    no limit. Raises `ValueError`, naming the variable, for anything else; the
    caller refuses, never falls back to a default."""
    raw = raw.strip()
    if not raw:
        return CLI_STEP_DEFAULT_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        value = -1.0
    if not value >= 0:  # negative, NaN, or not a number
        raise ValueError(
            f"{CLI_STEP_TIMEOUT_ENV}={raw}: expected a number of seconds (0 for no limit)"
        )
    return value or None


def timeout_from_env() -> float | None:
    """The cli step timeout this process runs under (see `parse_timeout`)."""
    return parse_timeout(os.environ.get(CLI_STEP_TIMEOUT_ENV, ""))


def failure_line(step_id: str, returncode: int, timed_out_after: float | None) -> str:
    """What `advance` prints for a failed cli step; a timeout says how to allow longer."""
    if timed_out_after is None:
        return f"{step_id}: failed (exit {returncode})"
    return (
        f"{step_id}: timed out after {timed_out_after:g}s (exit {returncode}); "
        f"set {CLI_STEP_TIMEOUT_ENV} to allow longer, 0 for no limit"
    )


def run_step(command: str, cwd: Path, step_id: str) -> tuple[int, str, str | None]:
    """Run one cli step under `FR_CLI_STEP_TIMEOUT`; returns (exit code, bounded
    stdout, the failure line or None). A malformed timeout raises `ValueError`
    before anything runs."""
    timeout = timeout_from_env()
    returncode, stdout, timed_out = run_cli_command(command, cwd, timeout)
    failure = None
    if returncode != 0:
        failure = failure_line(step_id, returncode, timeout if timed_out else None)
    return returncode, bounded_stdout(stdout), failure


def run_cli_command(command: str, cwd: Path, timeout: float | None) -> tuple[int, str, bool]:
    """Run `command` in a shell; returns (exit code, stdout, timed out).

    The shell leads its own process group, so a timeout kills the whole
    pipeline: killing only the shell leaves `sleep 30 | cat`'s children holding
    stdout open, and the read would still wait for them.

    A group of its own is also out of reach of the Ctrl-C or kill that stops
    fr, so any exception here (KeyboardInterrupt included) kills the group
    before it propagates, as `subprocess.run` killed its child. After a kill the
    read waits only briefly: a process that left the group (`setsid`) may hold
    stdout open for as long as it likes."""
    proc = subprocess.Popen(  # noqa: S602 — manifest is operator-authored; values are shlex-quoted
        command,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        start_new_session=True,
    )

    def kill_group() -> None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)

    try:
        try:
            stdout, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_group()
            try:
                stdout, _ = proc.communicate(timeout=_DRAIN_SECONDS)
            except subprocess.TimeoutExpired as drained:
                stdout = _partial_text(drained.stdout)
                for pipe in (proc.stdout, proc.stderr):
                    if pipe is not None:
                        pipe.close()
                proc.wait()
            return CLI_STEP_TIMEOUT_EXIT, stdout or "", True
    except BaseException:
        kill_group()
        proc.wait()
        raise
    return proc.returncode, stdout or "", False


def _partial_text(data: str | bytes | None) -> str:
    """What `communicate` had read before it timed out: bytes on POSIX even in
    text mode."""
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


def bounded_stdout(stdout: str) -> str:
    """The tail the cursor keeps of a cli step's stdout. The cursor is a
    git-tracked file; the end of the output is where a failure says why."""
    if len(stdout) <= CLI_STEP_STDOUT_MAX_CHARS:
        return stdout
    dropped = len(stdout) - CLI_STEP_STDOUT_MAX_CHARS
    return (
        f"[fr: stdout truncated: first {dropped} of {len(stdout)} characters dropped]\n"
        + stdout[-CLI_STEP_STDOUT_MAX_CHARS:]
    )
