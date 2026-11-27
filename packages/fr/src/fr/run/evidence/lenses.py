"""The feature's lens set as a run command needs it (spec 2026-11-27-run-verdict R6).

Engine code: a lens set that cannot be computed is a `RunRefusal`, never an empty set in its place.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.markup import escape

from fr.run.model import RunState
from fr.run.verdict import RunRefusal, Say

if TYPE_CHECKING:
    from fr.lenses.accumulate import LensSet


def lens_set_or_refuse(key: str, repo_root: Path, state: RunState) -> LensSet:
    """The feature's lens set (`fr.lenses.accumulate.lens_set`), or a refusal naming
    why it cannot be told. Never an empty set in place of an error."""
    from fr.lenses.accumulate import lens_set
    from fr.lenses.model import LensError

    try:
        return lens_set(repo_root, state)
    except LensError as e:
        raise RunRefusal(
            (
                Say(
                    f"[red]{key}: refused — the feature's lens set cannot be computed: "
                    f"{escape(str(e))}. Nothing was written.[/red]",
                    soft_wrap=True,
                ),
            )
        ) from e
