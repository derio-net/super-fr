"""The end of S1's transition (spec 2026-11-28-s1-followups R1).

S1 (spec 2026-11-19-event-driven-a-la-carte) moved every repo configuration file into
`.fr/` and kept a transition: an old path is read with a notice, the old settings copy is
written in step with the new one, and the per-kind `FR_SHIPPED_*_DIR` variables keep
working. S1 ships in the 9.1 line, and the transition is one minor line long: from fr 9.2
on (every 9.2 pre-release included) the old forms are refused.

`refusing()` is the ONE Python definition of that end. An operator may end it early with
`FR_OLD_PATHS=refuse`; nothing keeps it open past 9.2. The shell and TypeScript readers
apply the same rule to their own release version (R7), with their own copy of `9.2` (R9).
"""

from __future__ import annotations

import os
from typing import Final

from packaging.version import InvalidVersion, Version

from fr.config.movers import is_moving, mover, moving
from fr.settings import SettingsError

__all__ = [
    "ENV",
    "REFUSE_FROM",
    "LegacyEnvRefused",
    "TransitionError",
    "is_moving",
    "keeps_old_copy",
    "mover",
    "moving",
    "old_path_refusal",
    "refuses_old_read",
    "refusing",
]

REFUSE_FROM: Final = (9, 2)
"""S1 ships in 9.1; the transition is one minor line."""

ENV: Final = "FR_OLD_PATHS"
"""Only `refuse` means anything: it ends the transition early, and never extends it."""

MIGRATE_COMMAND: Final = "fr migrate artifacts --yes"


class TransitionError(SettingsError):
    """An old configuration form found after the transition ended (exit 2)."""


class LegacyEnvRefused(TransitionError):  # noqa: N818 - the spec's name (R6)
    """A per-kind `FR_SHIPPED_*_DIR` variable set after the transition ended (R6)."""


def _line(version: str) -> tuple[int, int] | None:
    """`(major, minor)` of *version* in either spelling fr writes (`9.2.0rc1`, `9.2.0-rc.1`)."""
    try:
        parsed = Version(version)
    except InvalidVersion:
        return None
    return parsed.major, parsed.minor


def refusing() -> bool:
    """Whether the transition has ended: fr's release line is at or above 9.2, or
    `FR_OLD_PATHS=refuse`. An unparseable version counts as ended."""
    if os.environ.get(ENV) == "refuse":
        return True
    import fr  # read at call time, so a test (or a release) moves the answer

    line = _line(str(fr.__version__))
    return line is None or line >= REFUSE_FROM


def refuses_old_read() -> bool:
    """Whether a READER must refuse an old form it found: past the gate, outside a mover."""
    return refusing() and not is_moving()


def keeps_old_copy() -> bool:
    """Whether fr still keeps the old settings copy in step (before fr 9.2 only, R4)."""
    return not refusing()


def old_path_refusal(old: object, new: object) -> TransitionError:
    """The one refusal for a configuration file found only at its old path (R2)."""
    return TransitionError(
        f"{old} is an old configuration path, read only before fr 9.2; this fr reads "
        f"{new}. Move it: {MIGRATE_COMMAND}"
    )
