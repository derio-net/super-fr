"""The looping driver's failure vocabulary (spec 2026-11-19-batch-train-truth R1-R5).

Every failure that reaches the loop's one boundary is one of two things:

- a `DriverRefusal`: only the operator can fix it (another writer moved the state ref,
  another driver holds the scope, a forge operation the backend does not support, a config
  fr refuses strictly, a runner that refuses). The loop stops with exit 2 and says how to
  resume;
- a `TransientPassFailure`: everything else. The pass ends, the state stays local, and the
  next pass starts after a backoff.

`classify` is the one place that decides which, from `REFUSALS`, one table. A cause is a
stable id for the ledger and the report memory: it never carries the message text, because
messages carry heads, paths and hosts.
"""

from __future__ import annotations

import re
import shlex
from types import TracebackType

import click

from fr.forgeapi import ForgeApiError
from fr.ghclient import UnsupportedForgeOperation
from fr.triage.errors import ConfigError, TriageError
from fr.triage.gitseam import GitError
from fr.triage.lease import LeaseExpired, LeaseHeld
from fr.triage.privacy import PrivacyError, VisibilityUnreadable
from fr.triage.state_ref import StateRefConflict, StateRefPushRefused

RESUME = "fix it, then run `fr triage batch drive --yes` again"
"""The resume line of a refusal whose fix is the operator's own."""


class DriverRefusal(Exception):  # noqa: N818 - the name the spec gives it
    """A failure only the operator can fix: the looping driver stops (exit *code*)."""

    def __init__(self, cause: str, message: str, resume: str = RESUME, code: int = 2) -> None:
        super().__init__(message)
        self.cause, self.message, self.resume, self.code = cause, message, resume, code


class TransientPassFailure(Exception):  # noqa: N818 - the name the spec gives it
    """A failure one more pass may heal: the pass ends; `--once` exits with *code*."""

    def __init__(
        self,
        cause: str,
        message: str,
        code: int = 2,
        original: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.cause, self.message, self.code = cause, message, code
        self.original = original


# The refusal classes, most specific first: (class, cause, resume). `None` as the cause
# names the class itself (`config:<Class>`).
REFUSALS: tuple[tuple[type[BaseException], str | None, str], ...] = (
    (
        StateRefConflict,
        "state-ref-conflict",
        "another writer moved the state ref: look at what it wrote, then run "
        "`fr triage batch drive --yes` again (it fetches first)",
    ),
    (
        LeaseHeld,
        "lease-held",
        "another driver holds the scope (`fr triage lease show`): stop it, or wait for it "
        "to stop, then run `fr triage batch drive --yes` again",
    ),
    (LeaseExpired, "lease-expired", "fr triage lease take --yes"),
    (UnsupportedForgeOperation, "unsupported-forge-operation", RESUME),
    (ConfigError, None, RESUME),
    (ForgeApiError, None, RESUME),
)

# Transient classes with a cause of their own, checked before the general rules.
TRANSIENTS: tuple[tuple[type[BaseException], str], ...] = (
    (StateRefPushRefused, "push-refused"),
    (VisibilityUnreadable, "visibility-unreadable"),
)

FAIL_HELPERS = frozenset({"_fail"})
"""The functions that only raise the `Exit` a caller asked for: never the one named."""

_GIT_VALUE_OPTIONS = frozenset({"-C", "-c", "--git-dir", "--work-tree"})


def classify(exc: BaseException) -> DriverRefusal | TransientPassFailure:
    """*exc* as a refusal or a transient failure (R2-R4); an already classified one as is."""
    if isinstance(exc, DriverRefusal | TransientPassFailure):
        return exc
    message = str(exc)
    for transient, cause in TRANSIENTS:
        if isinstance(exc, transient):
            return TransientPassFailure(cause, message, original=exc)
    for refusal, named, resume in REFUSALS:
        if isinstance(exc, refusal):
            return DriverRefusal(named or f"config:{type(exc).__name__}", message, resume)
    if isinstance(exc, PrivacyError):  # after VisibilityUnreadable, its transient subclass
        return DriverRefusal("privacy", message)
    if isinstance(exc, click.exceptions.Exit):
        cause = f"exit:{_raiser(exc.__traceback__)}"
        if exc.exit_code == 2:
            return DriverRefusal(cause, message)
        return TransientPassFailure(cause, message, code=exc.exit_code, original=exc)
    if isinstance(exc, GitError):
        return TransientPassFailure(f"git:{git_op(message)}", message, original=exc)
    if isinstance(exc, TriageError):
        return TransientPassFailure(f"triage:{type(exc).__name__}", message, original=exc)
    return TransientPassFailure(f"unexpected:{type(exc).__name__}", message, original=exc)


def _raiser(tb: TracebackType | None) -> str:
    """The innermost function of an `fr.` module in *tb* that is not a fail helper."""
    name = "unknown"
    while tb is not None:
        frame = tb.tb_frame
        module = str(frame.f_globals.get("__name__", ""))
        if module.startswith("fr.") and frame.f_code.co_name not in FAIL_HELPERS:
            name = frame.f_code.co_name
        tb = tb.tb_next
    return name


def git_op(message: str) -> str:
    """The git subcommand a `GitError` message names (`fetch`, `push`), else `run`."""
    match = re.match(r"`([^`]*)`", message)
    if match is None:
        return "run"
    try:
        words = shlex.split(match.group(1))
    except ValueError:
        return "run"
    if not words or words[0] != "git":
        return "run"
    rest = iter(words[1:])
    for word in rest:
        if word in _GIT_VALUE_OPTIONS:
            next(rest, None)
        elif not word.startswith("-"):
            return word
    return "run"
