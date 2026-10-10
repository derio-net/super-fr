"""The one herdr subprocess seam, apart from `runner` so `restart` can import it.

`runner` imports `fr_herdr.restart` at module top level (spec 2026-10-06 §A, sr-13), so
`restart` cannot import `runner` back; both reach herdr through here, and `runner`
re-exports these names (its tests replace `runner._run_herdr`).
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

PANE_BUSY_TRIES = 15
"""How often `agent start` is tried while the pane's shell is not up yet (gh#931)."""
PANE_BUSY_WAIT = 2.0
"""Seconds between those tries."""

_T = TypeVar("_T")


def poll(
    check: Callable[[], _T | None],
    *,
    timeout: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    interval: float = 1.0,
) -> _T | None:
    """Bounded foreground/startup observation shared by both harnesses."""
    deadline = clock() + timeout
    while True:
        answer = check()
        if answer is not None:
            return answer
        if clock() >= deadline:
            return None
        sleep(interval)


class HerdrError(Exception):
    """A herdr CLI call failed; the message carries herdr's own words, and *code* the
    `.error.code` of herdr's JSON envelope when it printed one."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


def _run_herdr(args: list[str]) -> dict[str, Any]:
    """Run `herdr <args>` and return its parsed JSON (`{}` for empty output)."""
    try:
        done = subprocess.run(
            ["herdr", *args], capture_output=True, text=True, check=True, timeout=60
        )
    except FileNotFoundError as exc:
        raise HerdrError("herdr is not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise HerdrError(f"herdr {' '.join(args[:2])} timed out; inspect before retry") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or f"exit {exc.returncode}"
        raise HerdrError(
            f"herdr {' '.join(args[:2])} failed: {detail}", code=_error_code(detail)
        ) from exc
    out = done.stdout.strip()
    if not out:
        return {}
    try:
        parsed = json.loads(out)
    except ValueError:
        return {"raw": out}
    # A JSON scalar or array (`pane read` of a pane that shows `123`) is text, not an
    # envelope: callers `.get` on the answer, so it is always a dict.
    return parsed if isinstance(parsed, dict) else {"raw": out}


def start_agent(
    argv: list[str],
    *,
    run: Callable[[list[str]], dict[str, Any]] = _run_herdr,
    sleep: Callable[[float], None] = time.sleep,
    tries: int = PANE_BUSY_TRIES,
    wait: float = PANE_BUSY_WAIT,
) -> None:
    """`agent start`, retried while the pane's shell is not up yet (gh#931).

    herdr needs the pane at its interactive shell prompt and refuses at once with
    `agent_pane_busy` otherwise; any other refusal (`agent_not_ready` is a dialog
    the operator must answer) is raised as it is. *run* and *sleep* are the caller's own
    seams, so each module's tests replace them where they already do.
    """
    for attempt in range(1, tries + 1):
        try:
            run(argv)
            return
        except HerdrError as exc:
            if exc.code != "agent_pane_busy" or attempt == tries:
                raise
        sleep(wait)


def _error_code(detail: str) -> str | None:
    """`.error.code` of herdr's JSON error envelope, if *detail* is one."""
    try:
        envelope = json.loads(detail)
    except ValueError:
        return None
    error = envelope.get("error") if isinstance(envelope, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return str(code) if code is not None else None
