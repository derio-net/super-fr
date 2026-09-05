"""Is an artifact where the runner will look for it? (spec §4.E, Phase 8)

A remote runner works from its own checkout of `origin/HEAD`, so anything
a step *needs* has to be merged before the work is dispatched. That used to
be one hardcoded refusal in `fr apply` ("plan and spec must be on
origin/HEAD" — the 2026-05-17 dispatch-reachability-gate design). Here it
is two halves, neither of which names an artifact:

- **which** artifacts must be reachable — `required_inputs`, re-exported
  from `fr.workflow.artifacts`: whatever the shape's steps `needs` and no
  step `emits`;
- **whether** they are — `unreachable_paths`, a `git ls-tree` over
  `origin/HEAD`.

Both work on plain paths and artifact *names*, never on `WorkItem`s: `fr`
must not import `fr_dispatch` (`tests/unit/test_import_direction.py`). The
item-level `check_reachable` lives in `fr_dispatch.reachability` and calls
straight back into `unreachable_paths`, so there is exactly one
implementation of "on origin/HEAD" for both callers.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fr.git import file_on_ref
from fr.workflow.artifacts import REPO_TRACKED_ARTIFACTS, required_inputs

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "REPO_TRACKED_ARTIFACTS",
    "ORIGIN_HEAD",
    "required_inputs",
    "unreachable_paths",
]

ORIGIN_HEAD = "origin/HEAD"
"""The ref a remote runner's checkout resolves to. Named once so the gate,
its message and its tests cannot disagree about it."""


def unreachable_paths(repo_root: Path, paths: Iterable[str]) -> list[Path]:
    """Which of `paths` (repo-relative) are absent from `origin/HEAD`.

    Empty list = reachable. A path that is a **directory** in the working
    tree expands to its files, sorted: a plan is a folder, and "the folder
    exists on main" is not the question — an unpushed `03.yaml` inside a
    pushed plan dir is exactly the case the gate has to catch, and naming
    the file is what tells the operator what to merge.

    Raises if `origin/HEAD` isn't resolvable locally; the caller turns that
    into the `git remote set-head` hint.
    """
    missing: list[Path] = []
    for path in paths:
        target = repo_root / path
        if target.is_dir():
            candidates = [
                p.relative_to(repo_root) for p in sorted(target.rglob("*")) if p.is_file()
            ]
        else:
            candidates = [Path(path)]
        missing.extend(
            rel for rel in candidates if not file_on_ref(ORIGIN_HEAD, str(rel), cwd=repo_root)
        )
    return missing
