"""The settle vocabulary: states, modes and the verdict (spec 2026-11-23-pr-readiness-wait §B).

Closed models, so a verdict printed as JSON (`fr pr settle --json`) has one shape.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

ConflictState = Literal["clean", "conflicting", "unknown", "unsupported", "off", "managed"]
CiState = Literal[
    "green", "red", "pending", "missing", "unrunnable", "none", "unsupported", "off", "managed"
]
Mode = Literal["off", "report", "fix"]
ModeSource = Literal["default", "repo", "spec", "journal"]
"""Where a key's mode came from: the setting (`default` or `repo`, as `fr settings show`
says), or an override (R6: a spec `## Verification` line, a debug-journal decision)."""

FAILING: Final = frozenset({"conflicting", "red", "missing", "unrunnable"})
"""The states a `fix` concern exits 4 on (R4)."""
UNSETTLED: Final = frozenset({"unknown", "pending"})
"""The states the poll waits on, and a `fix` concern exits 75 on at the end of the wait."""

EXIT_OK: Final = 0
EXIT_REFUSED: Final = 2
EXIT_FAILING: Final = 4
EXIT_PENDING: Final = 75


class SettleRefused(Exception):  # noqa: N818 — a refusal, exit 2 (R4)
    """`fr pr settle` refuses: exit 2 with the message."""


class SettlePending(Exception):  # noqa: N818 — a hold, exit 75 (R4, R8)
    """A `fix` concern is still unknown or pending, or a forge read failed transiently:
    exit 75, and the `deliver` witness records nothing."""

    exit_code = EXIT_PENDING


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class KeyMode(_Closed):
    mode: Mode
    source: ModeSource
    reason: str = ""
    """An override's recorded reason (R6); empty for the setting."""


class Modes(_Closed):
    conflicts: KeyMode
    ci: KeyMode

    @classmethod
    def from_setting(cls, *, conflicts: str, ci: str, source: str = "default") -> Modes:
        """Both keys from the repo setting, with one source (tests and defaults)."""
        return cls.model_validate(
            {
                "conflicts": {"mode": conflicts, "source": source},
                "ci": {"mode": ci, "source": source},
            }
        )

    @property
    def both_off(self) -> bool:
        return self.conflicts.mode == "off" and self.ci.mode == "off"


class Verdict(_Closed):
    conflict_state: ConflictState
    ci_state: CiState
    failing_checks: tuple[str, ...] = ()
    exit_code: int
    lines: tuple[str, ...]
    """What `fr pr settle` prints, one line each, in order."""
    head: str = ""
    witness: str
    """`<conflicts mode>/<ci mode>:<conflict state>/<ci state>@<head>` (R8)."""
    settled: bool
    """No concern under `report` or `fix` is `unknown` or `pending`: the poll stops."""
