"""Pure classification of branch-changed paths into live artifacts (§A,
2026-09-28-closeout-always spec), plus `owed_artifacts` (§C) — the ONE
definition of "live, but its PR already merged" that `fr status` and
`fr archive --all` both iterate.

`branch_artifacts` makes no git calls: it only reads `changed` (repo-relative
paths, e.g. from `fr.isolation.local.branch_changed_paths`) against the
working tree, so it needs no git repo to be unit-tested. `owed_artifacts`
does read the working tree and `evidence` (a `MergeEvidence` the CALLER
already fetched) but makes no forge call and mutates nothing.

Path-root constants are reused from each kind's own module rather than
re-declared here (`fr.archive.PLANS_REL`, `fr.journal.model.JOURNALS_REL` +
its scope→dir map, `fr.run.model.RUNS_REL`, `fr.usage.file.USAGE_REL`) —
one source of truth per layout, per AGENTS.md's artifact-versioning rule.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from fr.archive import PLANS_REL
from fr.journal.model import JOURNALS_REL, SCOPE_DIRS
from fr.run.model import RUNS_REL
from fr.usage.file import USAGE_REL

if TYPE_CHECKING:
    from fr.archive import MergeEvidence
    from fr.parser import Plan

ArtifactKind = Literal["plan", "spec", "journal", "run", "usage"]

SPECS_REL = Path("docs/superpowers/specs")
IMPLEMENTED_PLANS_REL = Path("docs/superpowers/implemented/plans")
IMPLEMENTED_SPECS_REL = Path("docs/superpowers/implemented/specs")

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


def journal_scope_and_slug(path: Path) -> tuple[str, str] | None:
    """`(scope, slug)` for a live journal path
    (`docs/superpowers/journals/<scope-dir>/<slug>.md`), or `None` when
    `path` doesn't have that shape. The one classifier `branch_artifacts` and
    `owed_artifacts` both use, so a journal's scope is derived in exactly one
    place (2026-09-28-closeout-always §C)."""
    parts = path.parts
    journals_parts = JOURNALS_REL.parts
    if _under(parts, JOURNALS_REL) and len(parts) == len(journals_parts) + 2:
        scope_dir = parts[len(journals_parts)]
        scope = _JOURNAL_SCOPE_BY_DIR.get(scope_dir)
        if scope is not None and path.suffix == ".md":
            return scope, path.stem
    return None


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

        if _under(parts, JOURNALS_REL):
            scope_slug = journal_scope_and_slug(path)
            if scope_slug is not None:
                artifacts.append(BranchArtifact(kind="journal", path=path, owner=scope_slug[0]))
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


# --- §C: the repo-wide plan sweep's "archivable" bucket, and owed_artifacts -


@dataclass(frozen=True)
class PlanSweep:
    """The four buckets of the repo-wide plan sweep (spec 2026-09-23 §3.B).

    Moved here from `fr.commands.status_cmd` (2026-09-28-closeout-always §C)
    so `fr status` and `owed_artifacts` share exactly one "this plan is
    merged and locally complete, and waiting to be archived" predicate —
    `status_cmd` calls `plan_sweep` and imports this type back. Pure given
    `evidence`: it never fetches, so the caller controls when the network is
    touched (once per invocation, per #544).
    """

    evidence: MergeEvidence
    archivable: list[str]
    """Merged (see `_plan_merged`) and locally complete, manual phases included."""
    merged_manual_open: list[tuple[str, list[int]]]
    """Merged, but these local phase numbers are still open."""
    complete_unmerged: list[str]
    """Locally complete, not merged — or merge state unknown (`ref is None`)."""
    in_progress: list[str]
    """Everything else, a plan the working tree cannot parse included."""


def _plan_merged(name: str, plan: Plan, evidence: MergeEvidence) -> bool:
    """Every agentic phase of the WORKING-TREE plan is complete on the ref.

    `agentic_landed` alone is judged from the ref's copy of the plan, so a
    phase added on the branch after an earlier merge would not block it; each
    local agentic phase must be in `landed_phases`.
    """
    landed = evidence.landed_phases.get(name, frozenset())
    return name in evidence.agentic_landed and all(
        p.phase.number in landed for p in plan.phases if p.phase.tag == "agentic"
    )


def plan_sweep(repo_root: Path, evidence: MergeEvidence) -> PlanSweep:
    """Bucket every plan dir under `docs/superpowers/plans/` by `evidence`
    (already fetched by the caller — this never fetches)."""
    from fr.parser import PlanSchemaError, parse
    from fr.render import plan_locally_complete

    sweep = PlanSweep(evidence, [], [], [], [])
    plans_dir = repo_root / PLANS_REL
    names = (
        sorted(p.name for p in plans_dir.iterdir() if (p / "_meta.yaml").exists())
        if plans_dir.is_dir()
        else []
    )
    for name in names:
        try:
            plan = parse(plans_dir / name)
        except PlanSchemaError:
            sweep.in_progress.append(name)
            continue
        open_phases = [p.phase.number for p in plan.phases if not plan_locally_complete(p)]
        complete = bool(plan.phases) and not open_phases
        if _plan_merged(name, plan, evidence):
            if complete:
                sweep.archivable.append(name)
            else:
                sweep.merged_manual_open.append((name, open_phases))
        elif complete:
            sweep.complete_unmerged.append(name)
        else:
            sweep.in_progress.append(name)
    return sweep


OwedKind = Literal["debug_journal", "plan", "spec", "orphan_journal", "orphan_run"]


@dataclass(frozen=True)
class Owed:
    """One live artifact whose PR has merged, with the command that clears it
    (2026-09-28-closeout-always spec §C table)."""

    kind: OwedKind
    path: Path  # repo-relative, live location
    clear: str  # the `fr archive …` invocation that moves it


@dataclass(frozen=True)
class HeldSpec:
    """A live spec that is NOT owed, with the reason `_spec_fully_implemented`
    gave (a pending slice, an unresolved cross-repo row, or a row still
    active under `plans/`) — visible, never silent (R5)."""

    spec: str  # spec file name
    note: str


@dataclass(frozen=True)
class OwedArtifacts:
    owed: tuple[Owed, ...]
    held: tuple[HeldSpec, ...]


def _owed_debug_journals(repo_root: Path, evidence: MergeEvidence) -> list[Owed]:
    """A debug journal is done (d2/d3) once it is on the default ref — the
    same rule `fr archive --branch` uses for a branch's own debug journal."""
    if evidence.ref is None:
        return []
    from fr.git import file_on_ref

    debug_dir = repo_root / JOURNALS_REL / SCOPE_DIRS["debug"]
    if not debug_dir.is_dir():
        return []
    owed: list[Owed] = []
    for p in sorted(debug_dir.glob("*.md")):
        rel = p.relative_to(repo_root)
        if file_on_ref(evidence.ref.ref, str(rel), cwd=repo_root):
            owed.append(Owed(kind="debug_journal", path=rel, clear="fr archive --all"))
    return owed


def _owed_plans(repo_root: Path, evidence: MergeEvidence) -> list[Owed]:
    sweep = plan_sweep(repo_root, evidence)
    return [
        Owed(
            kind="plan",
            path=PLANS_REL / name,
            clear=f"fr archive {PLANS_REL / name}",
        )
        for name in sweep.archivable
    ]


def _owed_specs(repo_root: Path) -> tuple[list[Owed], list[HeldSpec]]:
    """`_spec_fully_implemented` with `gh=None` (no forge call, per §C):
    unresolved cross-repo rows degrade to a held note rather than a probe."""
    from fr.migrate import _spec_fully_implemented

    owed: list[Owed] = []
    held: list[HeldSpec] = []
    specs_dir = repo_root / SPECS_REL
    if not specs_dir.is_dir():
        return owed, held
    for spec_path in sorted(specs_dir.glob("*.md")):
        implemented, note = _spec_fully_implemented(spec_path, repo_root, gh=None)
        rel = spec_path.relative_to(repo_root)
        if implemented:
            owed.append(Owed(kind="spec", path=rel, clear="fr archive --sweep-only"))
        elif note and "no Implementation Plans rows" not in note:
            held.append(HeldSpec(spec=spec_path.name, note=note))
    return owed, held


def _owed_orphan_journals(repo_root: Path) -> list[Owed]:
    """A plan/spec journal whose owner is already archived — no ref check:
    the owner's own archive is the evidence, wherever it happened."""
    owed: list[Owed] = []
    for scope in ("plan", "spec"):
        live_dir = repo_root / JOURNALS_REL / SCOPE_DIRS[scope]
        if not live_dir.is_dir():
            continue
        for p in sorted(live_dir.glob("*.md")):
            slug = p.stem
            if scope == "plan":
                owner_archived = (repo_root / IMPLEMENTED_PLANS_REL / slug).is_dir()
            else:
                owner_archived = any(
                    (repo_root / IMPLEMENTED_SPECS_REL / name).is_file()
                    for name in (f"{slug}-design.md", f"{slug}.md")
                )
            if owner_archived:
                owed.append(
                    Owed(
                        kind="orphan_journal",
                        path=p.relative_to(repo_root),
                        clear="fr archive --all",
                    )
                )
    return owed


def _owed_orphan_runs(repo_root: Path, evidence: MergeEvidence) -> list[Owed]:
    """A run cursor whose `emitted.plan` is already archived, or one naming no
    plan whose `deliver` is done and which is itself on the default ref."""
    from fr.archive import deliver_done, emitted_plan
    from fr.git import file_on_ref

    owed: list[Owed] = []
    runs_dir = repo_root / RUNS_REL
    if not runs_dir.is_dir():
        return owed
    for cursor in sorted(runs_dir.glob("*.yaml")):
        rel = cursor.relative_to(repo_root)
        plan = emitted_plan(cursor)
        if plan:
            if (repo_root / IMPLEMENTED_PLANS_REL / Path(plan).name).is_dir():
                owed.append(Owed(kind="orphan_run", path=rel, clear="fr archive --all"))
            continue
        if evidence.ref is None:
            continue
        if deliver_done(cursor) and file_on_ref(evidence.ref.ref, str(rel), cwd=repo_root):
            owed.append(Owed(kind="orphan_run", path=rel, clear="fr archive --all"))
    return owed


def owed_artifacts(repo_root: Path, evidence: MergeEvidence) -> OwedArtifacts:
    """The ONE definition of "live, but its PR already merged" (§C). Reads the
    working tree and `evidence` only — no forge call, no fetch, no mutation.

    `fr status` prints this to tell an operator what a `fr pickup --branch`
    closeout left behind; `fr archive --all` iterates the same list to clear
    it. A spec `_spec_fully_implemented` cannot yet clear (a pending slice, an
    unresolved cross-repo row, a row still active under `plans/`) is reported
    in `held`, never silently dropped (R5).
    """
    owed: list[Owed] = []
    owed.extend(_owed_debug_journals(repo_root, evidence))
    owed.extend(_owed_plans(repo_root, evidence))
    spec_owed, held = _owed_specs(repo_root)
    owed.extend(spec_owed)
    owed.extend(_owed_orphan_journals(repo_root))
    owed.extend(_owed_orphan_runs(repo_root, evidence))
    return OwedArtifacts(owed=tuple(owed), held=tuple(held))


__all__ = [
    "ArtifactKind",
    "BranchArtifact",
    "HeldSpec",
    "Owed",
    "OwedArtifacts",
    "OwedKind",
    "PlanSweep",
    "branch_artifacts",
    "journal_scope_and_slug",
    "owed_artifacts",
    "plan_sweep",
]
