"""What every `run`-kind migration has in common: refuse what you cannot read.

**Read with the FROZEN model, never the live one.** Every guard here goes
through `fr.run.legacy.parse_run_state_v4`. It used to be the LIVE parser in
`fr.run.model`, and that was sound only while every change to the cursor
was additive, so the live model stayed a superset of every older shape. The
4 -> 5 rewrite REMOVES `items`, `dispatch` and `accounting` from an
`extra="forbid"` model: validated against the live model, a v2 cursor carrying
`items` stops parsing and the chain `2 -> 3 -> 4 -> 5` refuses every old
cursor at its FIRST hop — stranding exactly the files the framework exists to
carry. The standing rule is in `.claude/rules/artifact-versioning.md`.

The first three of the `run` kind's migrations are stamp-only — the field each one adds
is optional and absent-by-default, and absent is exactly what it means on
every older cursor, so there is no body to translate. That leaves one way a
stamp-only migration can still do harm: stamping a file it never understood.
A run cursor is git-tracked and hand-editable, and a truncated or half-merged
one stamped with a version it does not have is *worse* than one left behind —
it now claims a shape it lacks, and no migration will look at it again.

So the guard below is the whole of every such migration's `fn`, parameterised
by the version it refuses to certify. It lives here rather than in each
migration module because they would otherwise be the same function three
times, differing only in a number inside an error message.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fr.artifacts.runner import ArtifactMigrationError


class UnreadableRunCursorError(ArtifactMigrationError):
    """A run file the migration will not stamp, because it cannot read it."""


def refuse_unreadable_cursor(path: Path, to_version: int) -> None:
    """Parse `path` as a run cursor, or raise `UnreadableRunCursorError`.

    Goes through `parse_run_state_v4` — the frozen reader of versions 1-4,
    see the module docstring — rather than a second notion of "valid run
    state" that could drift from it. The runner records the raise as that one
    artifact's failure (invariant 3): every other cursor still migrates, the
    bad one stays unstamped, and the next run retries it.

    Imported inside the function: `fr.artifacts` is imported at CLI entry
    before every command, and must not drag the run models in with it.
    """
    from fr.run.legacy import parse_run_state_v4
    from fr.run.model import RunStateError

    try:
        parse_run_state_v4(path.read_text())
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
