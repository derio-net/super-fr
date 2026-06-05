"""`vk archive` library — gate check, git mv, spec-archival sweep.

The lifecycle step the 2026-06-05 postmortem found missing: completed
plans move to `docs/superpowers/implemented/plans/`, and a spec whose
rows are all implemented follows to `implemented/specs/`. Moves are
`git mv` (rename history survives); committing is the operator's job.

The gate is `vk.render.archive_gate` — shared with the apply/status
nudge so the three surfaces can't disagree. The spec decision is
`vk.migrate._spec_fully_implemented` — shared with `vk migrate dirs`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from vk.migrate import DirsMove, MigrationError, _spec_fully_implemented

if TYPE_CHECKING:
    from vk.ghclient import GhClient

__all__ = ["ArchiveError", "archive_plan_dir", "paths_dirty", "spec_archive_sweep"]


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
        # `vk archive /path/in/another/repo` (or wrong cwd): a clean
        # refusal, not a traceback (review finding, 2026-06-06).
        raise ArchiveError(
            f"plan dir {plan_dir} is not under this repo root ({repo_root}); "
            f"run vk archive from the repo that owns the plan"
        ) from e
    dst_rel = Path("docs/superpowers/implemented/plans") / plan_dir.name
    _git_mv(repo_root, src_rel, dst_rel)
    return repo_root / dst_rel


def spec_archive_sweep(repo_root: Path, gh: GhClient | None) -> SpecSweepResult:
    """Move every spec whose rows are all implemented to implemented/specs/.

    Runs after plan moves (single archive or end of an `--all` sweep), so a
    spec whose last plans archived in the same run qualifies. Cross-repo
    rows resolve via the gh contents API when `gh` is given; unresolved
    rows leave the spec in place with a note — never a silent pass.
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
            moves.append(DirsMove(src=src_rel, dst=dst_rel, kind="spec"))
        elif note and "no Implementation Plans rows" not in note:
            notes.append(f"{spec_path.name}: {note}")
    return SpecSweepResult(moves=tuple(moves), notes=tuple(notes))


# Re-exported for callers that catch both error families with one except.
_ = MigrationError
