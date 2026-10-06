"""The one herdr subprocess seam, apart from `runner` so `restart` can import it.

`runner` imports `fr_herdr.restart` at module top level (spec 2026-10-06 §A, sr-13), so
`restart` cannot import `runner` back; both reach herdr through here, and `runner`
re-exports these names (its tests replace `runner._run_herdr`).
"""

from __future__ import annotations

import json
import subprocess
from typing import Any


class HerdrError(Exception):
    """A herdr CLI call failed; the message carries herdr's own words, and *code* the
    `.error.code` of herdr's JSON envelope when it printed one."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


def _run_herdr(args: list[str]) -> dict[str, Any]:
    """Run `herdr <args>` and return its parsed JSON (`{}` for empty output)."""
    try:
        done = subprocess.run(["herdr", *args], capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise HerdrError("herdr is not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or f"exit {exc.returncode}"
        raise HerdrError(
            f"herdr {' '.join(args[:2])} failed: {detail}", code=_error_code(detail)
        ) from exc
    out = done.stdout.strip()
    if not out:
        return {}
    try:
        parsed: dict[str, Any] = json.loads(out)
    except ValueError:
        return {"raw": out}
    return parsed


def _error_code(detail: str) -> str | None:
    """`.error.code` of herdr's JSON error envelope, if *detail* is one."""
    try:
        envelope = json.loads(detail)
    except ValueError:
        return None
    error = envelope.get("error") if isinstance(envelope, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return str(code) if code is not None else None
