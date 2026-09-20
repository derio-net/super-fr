"""What every `run`-kind migration has in common: refuse what you cannot read.

Both of the `run` kind's migrations are stamp-only — the field each one adds
is optional and absent-by-default, and absent is exactly what it means on
every older cursor, so there is no body to translate. That leaves one way a
stamp-only migration can still do harm: stamping a file it never understood.
A run cursor is git-tracked and hand-editable, and a truncated or half-merged
one stamped with a version it does not have is *worse* than one left behind —
it now claims a shape it lacks, and no migration will look at it again.

So the guard below is the whole of every such migration's `fn`, parameterised
by the version it refuses to certify. It lives here rather than in either
migration module because the two would otherwise be the same function twice,
differing only in a number inside an error message.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fr.artifacts.runner import ArtifactMigrationError


class UnreadableRunCursorError(ArtifactMigrationError):
    """A run file the migration will not stamp, because it cannot read it."""


def refuse_unreadable_cursor(path: Path, to_version: int) -> None:
    """Parse `path` as a run cursor, or raise `UnreadableRunCursorError`.

    Goes through `parse_run_state` — the one entry point — rather than a
    second notion of "valid run state" that could drift from the model. The
    runner records the raise as that one artifact's failure (invariant 3):
    every other cursor still migrates, the bad one stays unstamped, and the
    next run retries it.

    Imported inside the function: `fr.artifacts` is imported at CLI entry
    before every command, and must not drag the run models in with it.
    """
    from fr.run.model import RunStateError, parse_run_state

    try:
        parse_run_state(path.read_text())
    except (RunStateError, OSError) as e:
        raise UnreadableRunCursorError(
            f"{path}: not a readable run cursor, so fr will not stamp it as version "
            f"{to_version} ({e}). Fix the file by hand — it is left on its current "
            f"version and will be retried."
        ) from e


def cursor_guard(to_version: int) -> Callable[[Path], None]:
    """`refuse_unreadable_cursor` bound to the version being migrated TO."""

    def guard(path: Path) -> None:
        refuse_unreadable_cursor(path, to_version)

    return guard
