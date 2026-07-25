"""`fr archive` library — gate check, git mv, spec-archival sweep.

The lifecycle step the 2026-06-05 postmortem found missing: completed
plans move to `docs/superpowers/implemented/plans/`, and a spec whose
rows are all implemented follows to `implemented/specs/`. Moves are
`git mv` (rename history survives); committing is the operator's job.

The gate is `vk.render.archive_gate` — shared with the apply/status
nudge so the three surfaces can't disagree. The spec decision is
`vk.migrate._spec_fully_implemented` — shared with `fr migrate dirs`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr.journal.model import archived_journal_path, journal_path, spec_journal_slug
from fr.migrate import DirsMove, MigrationError, _spec_fully_implemented

if TYPE_CHECKING:
    from fr.ghclient import GhClient

__all__ = [
    "ArchiveError",
    "archive_plan_dir",
    "completed_unarchived_plans",
    "paths_dirty",
    "spec_archive_sweep",
]


def completed_unarchived_plans(repo_root: Path) -> list[str]:
    """Plan-dir names under ``docs/superpowers/plans/`` that are fully locally
    complete and therefore should have been archived (#334).

    The gh-free ("merged-but-unarchived") signal, shared by the ``fr status``
    repo sweep and the ``test_tripwire_unarchived_plans`` CI backstop so there
    is exactly one definition of the drift.

    A plan counts iff it has at least one phase and *every* phase satisfies
    ``render.plan_locally_complete`` (``completion.at`` set, or all steps
    ticked). This is the same offline arm ``archive_gate`` uses for
    never-dispatched plans, so it never flags a plan the mover would refuse.
    Deliberately offline (no gh observation) so plain ``pytest`` can enforce
    it. Malformed plan dirs are skipped, not flagged — a parse failure is a
    different problem and must not wedge the check red.
    """
    from fr.parser import PlanSchemaError, parse
    from fr.render import plan_locally_complete

    plans_dir = repo_root / "docs" / "superpowers" / "plans"
    if not plans_dir.is_dir():
        return []

    complete: list[str] = []
    for plan_dir in sorted(plans_dir.iterdir()):
        if not (plan_dir / "_meta.yaml").exists():
            continue
        try:
            plan = parse(plan_dir)
        except PlanSchemaError:
            continue
        if plan.phases and all(plan_locally_complete(p) for p in plan.phases):
            complete.append(plan_dir.name)
    return complete


class ArchiveError(Exception):
    pass


@dataclass(frozen=True)
class SpecSweepResult:
    moves: tuple[DirsMove, ...]
    notes: tuple[str, ...]


def paths_dirty(repo_root: Path, *paths: Path) -> bool:
    """True iff `git status --porcelain` reports changes under any path."""
    out = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain", "--", *map(str, paths)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return bool(out.strip())


def _git_mv(repo_root: Path, src_rel: Path, dst_rel: Path) -> None:
    (repo_root / dst_rel).parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "mv", str(src_rel), str(dst_rel)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise ArchiveError(
            f"git mv {src_rel} -> {dst_rel} failed: {(e.stderr or '').strip()}"
        ) from e


def archive_plan_dir(repo_root: Path, plan_dir: Path) -> Path:
    """`git mv` an active plan dir to implemented/plans/. Returns the new path.

    Caller has already run the archive gate and the dirty check.
    """
    try:
        src_rel = plan_dir.resolve().relative_to(repo_root)
    except ValueError as e:
        # `fr archive /path/in/another/repo` (or wrong cwd): a clean
        # refusal, not a traceback (review finding, 2026-06-06).
        raise ArchiveError(
            f"plan dir {plan_dir} is not under this repo root ({repo_root}); "
            f"run fr archive from the repo that owns the plan"
        ) from e
    dst_rel = Path("docs/superpowers/implemented/plans") / plan_dir.name
    if (repo_root / dst_rel).exists():
        # A prior botched archive (copied to implemented/ but never removed
        # from plans/) leaves a duplicate; `git mv` would nest src INTO the
        # existing dir (implemented/plans/X/X), corrupting the tree. Refuse
        # with a clear next step instead. (#334)
        raise ArchiveError(
            f"destination already exists: {dst_rel} — this plan appears already "
            f"archived. Remove the stale plans/ copy ({src_rel}) instead "
            f"(e.g. `git rm -r {src_rel}`)."
        )
    _git_mv(repo_root, src_rel, dst_rel)
    _archive_journal(repo_root, "plan", plan_dir.name)
    return repo_root / dst_rel


def _archive_journal(repo_root: Path, scope: str, slug: str) -> None:
    """Move a scoped journal to implemented/journals/<scope-dir>/.

    A no-op when no journal exists (back-compat with pre-journal plans/specs)
    or when the destination already holds one (a re-run). Path resolution is
    delegated to `fr.journal.model` so the layout has one source of truth
    (2026-07-22 fr-goal-subagent-execution spec §A).
    """
    src = journal_path(repo_root, scope, slug)  # type: ignore[arg-type]
    if not src.exists():
        return
    dst = archived_journal_path(repo_root, scope, slug)  # type: ignore[arg-type]
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    _git_mv(repo_root, src.relative_to(repo_root), dst.relative_to(repo_root))


def spec_archive_sweep(repo_root: Path, gh: GhClient | None) -> SpecSweepResult:
    """Move every spec whose rows are all implemented to implemented/specs/.

    Runs after plan moves (single archive or end of an `--all` sweep), so a
    spec whose last plans archived in the same run qualifies. Cross-repo
    rows resolve via the gh contents API when `gh` is given; unresolved
    rows leave the spec in place with a note — never a silent pass.

    A spec delivered in slices holds itself: a plan row whose File cell is a
    `pending`/`tbd` placeholder marks a decided-but-unbuilt slice and keeps
    the spec in place (a note is emitted) until that slice's plan is built and
    archived (#351).
    """
    moves: list[DirsMove] = []
    notes: list[str] = []
    specs_dir = repo_root / "docs" / "superpowers" / "specs"
    if not specs_dir.is_dir():
        return SpecSweepResult(moves=(), notes=())
    for spec_path in sorted(specs_dir.glob("*.md")):
        implemented, note = _spec_fully_implemented(spec_path, repo_root, gh)
        if implemented:
            src_rel = spec_path.relative_to(repo_root)
            dst_rel = Path("docs/superpowers/implemented/specs") / spec_path.name
            try:
                _git_mv(repo_root, src_rel, dst_rel)
            except ArchiveError as e:
                notes.append(str(e))
                continue
            # A spec journal is keyed by the bare feature slug, not the spec's
            # `<slug>-design` filename stem; strip the suffix so the move
            # resolves the real file and follows the spec into
            # implemented/journals/specs/ (2026-07-22 spec §A; #417).
            _archive_journal(repo_root, "spec", spec_journal_slug(spec_path.stem))
            moves.append(DirsMove(src=src_rel, dst=dst_rel, kind="spec"))
        elif note and "no Implementation Plans rows" not in note:
            notes.append(f"{spec_path.name}: {note}")
    return SpecSweepResult(moves=tuple(moves), notes=tuple(notes))


# Re-exported for callers that catch both error families with one except.
_ = MigrationError
