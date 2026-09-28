"""Pure classification of branch-changed paths into live artifacts (§A,
2026-09-28-closeout-always spec). No git calls: `branch_artifacts` only reads
`changed` (repo-relative paths, e.g. from `fr.isolation.local.
branch_changed_paths`) against the working tree, so it needs no git repo to
be unit-tested.

Path-root constants are reused from each kind's own module rather than
re-declared here (`fr.archive.PLANS_REL`, `fr.journal.model.JOURNALS_REL` +
its scope→dir map, `fr.run.model.RUNS_REL`, `fr.usage.file.USAGE_REL`) —
one source of truth per layout, per AGENTS.md's artifact-versioning rule.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fr.archive import PLANS_REL
from fr.journal.model import JOURNALS_REL, SCOPE_DIRS
from fr.run.model import RUNS_REL
from fr.usage.file import USAGE_REL

ArtifactKind = Literal["plan", "spec", "journal", "run", "usage"]

SPECS_REL = Path("docs/superpowers/specs")

# dir name (e.g. "specs") -> journal scope (e.g. "spec")
_JOURNAL_SCOPE_BY_DIR: dict[str, str] = {dirname: scope for scope, dirname in SCOPE_DIRS.items()}


@dataclass(frozen=True)
class BranchArtifact:
    """One live artifact a branch touched.

    `owner` is the plan dir name for a `plan` artifact, the journal scope
    (`spec`/`plan`/`debug`) for a `journal` artifact, and `None` for a
    `spec`, `run` or `usage` artifact — later phases (§B/§C) derive a
    run/usage's owning plan from the cursor's own `emitted.plan`, not from
    its path.
    """

    kind: ArtifactKind
    path: Path  # repo-relative, live location
    owner: str | None


def _under(parts: tuple[str, ...], rel: Path) -> bool:
    rel_parts = rel.parts
    return parts[: len(rel_parts)] == rel_parts


def branch_artifacts(repo_root: Path, changed: Iterable[str]) -> list[BranchArtifact]:
    """Classify `changed` (repo-relative paths) into live artifacts.

    A path no longer present in the working tree is a deletion and drops
    out (d2: added and modified are archived alike, but there is nothing
    live left to archive for a deletion). Every file under one plan dir
    collapses into a single `plan` artifact. `<run-id>.records/` (a
    step-record dir, transient by design) is never an artifact.
    """
    plans: dict[str, Path] = {}
    artifacts: list[BranchArtifact] = []
    plans_parts = PLANS_REL.parts
    specs_parts = SPECS_REL.parts
    journals_parts = JOURNALS_REL.parts
    runs_parts = RUNS_REL.parts
    usage_parts = USAGE_REL.parts

    for rel in changed:
        if not (repo_root / rel).exists():
            continue  # deleted
        path = Path(rel)
        parts = path.parts

        if _under(parts, PLANS_REL) and len(parts) > len(plans_parts) + 1:
            slug = parts[len(plans_parts)]
            plans.setdefault(slug, Path(*parts[: len(plans_parts) + 1]))
            continue

        if _under(parts, SPECS_REL) and len(parts) == len(specs_parts) + 1 and path.suffix == ".md":
            artifacts.append(BranchArtifact(kind="spec", path=path, owner=None))
            continue

        if _under(parts, JOURNALS_REL) and len(parts) == len(journals_parts) + 2:
            scope_dir = parts[len(journals_parts)]
            scope = _JOURNAL_SCOPE_BY_DIR.get(scope_dir)
            if scope is not None and path.suffix == ".md":
                artifacts.append(BranchArtifact(kind="journal", path=path, owner=scope))
            continue

        if _under(parts, RUNS_REL) and len(parts) == len(runs_parts) + 1:
            if path.suffix == ".yaml":
                artifacts.append(BranchArtifact(kind="run", path=path, owner=None))
            continue

        if _under(parts, USAGE_REL) and len(parts) == len(usage_parts) + 1:
            if path.suffix == ".yaml":
                artifacts.append(BranchArtifact(kind="usage", path=path, owner=None))
            continue

    for slug, plan_dir in plans.items():
        artifacts.append(BranchArtifact(kind="plan", path=plan_dir, owner=slug))

    return artifacts


__all__ = ["ArtifactKind", "BranchArtifact", "branch_artifacts"]
