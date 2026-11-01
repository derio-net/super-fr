"""Is this checkout a real fr-isolation workspace? — one Python answer.

Two Python callers ask it: `fr run start` (`fr.run.workspace`, which must write
a run inside its workspace) and the CLI-entry artifact gate
(`fr.artifacts.trigger`, which commits a migration in a non-interactive context
only inside a valid workspace — spec 2026-11-01-auto-migrate-own-commit R2,
§B). One implementation, so the two can never disagree about the same marker.

The authority this mirrors is the edit gate,
`plugins/super-fr/hooks/lib/fr-isolation-decision.sh` (`_fr_marker_valid` and
`_fr_branch_drift`, :214-251): the marker parses, its recorded `toplevel` is
this checkout, a missing `mode` reads as `worktree`, `worktree` must BE a linked
worktree, `external` needs container evidence, any other mode fails closed, and
HEAD on a branch other than the marker's `branch` is drift (no `branch`, or a
detached HEAD, is not).

The other marker readers (`isolation/where.py`, `isolation/external.py`,
`usage/capture.py`) read the marker for other purposes and do not use this.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fr.isolation.where import container_evidence

MARKER = ".fr-isolation"

__all__ = [
    "MARKER",
    "WorkspaceVerdict",
    "container_evidence",
    "is_linked_worktree",
    "marker_at",
    "marker_mode_holds",
    "valid_workspace",
]


def is_linked_worktree(root: Path) -> bool:
    """Is `root` a real linked worktree — `--git-common-dir` != `--git-dir`?

    The same structural check the `fr-isolation-required` PreToolUse hook makes
    for `mode: worktree`. A marker can be copied; a linked worktree cannot.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-dir", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if out.returncode != 0:
        return False
    lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    if len(lines) != 2:
        return False
    git_dir, common = (Path(root) / lines[0], Path(root) / lines[1])
    return git_dir.resolve() != common.resolve()


def marker_mode_holds(repo_root: Path, marker: dict[str, Any]) -> str | None:
    """`None` when the marker's `mode` is corroborated, else why it is not.

    **The same mode-specific validation the edit hook does** (review r5-e3).
    A toplevel match alone is satisfied trivially by a marker copied into a
    base clone, since the copy can simply be edited.

    - `worktree` (devcontainer or host-worktree), or no `mode` at all — the
      edit gate reads a missing mode as worktree — → must BE a linked worktree.
    - `external` (a preparer-adopted container) → the toplevel match plus
      container evidence, so a marker forged on a bare host never validates.
    - anything else → fail closed.
    """
    mode = marker.get("mode") or "worktree"
    if mode == "worktree":
        if is_linked_worktree(repo_root):
            return None
        return (
            f"{repo_root} carries a `mode: worktree` isolation marker but is not a "
            "linked git worktree — the marker is stale or was copied here"
        )
    if mode == "external":
        if container_evidence():
            return None
        return (
            f"{repo_root} carries a `mode: external` isolation marker but there is no "
            "container evidence (/.dockerenv, /run/.containerenv, "
            "$KUBERNETES_SERVICE_HOST) — an external marker is a preparer's hand-off, "
            "not something a bare host can claim"
        )
    return f"{repo_root} carries an isolation marker with unknown mode {mode!r}"


def _read(repo_root: Path) -> dict[str, Any] | str:
    """The parsed marker, or why there is none to use."""
    path = repo_root / MARKER
    if not path.is_file():
        return f"no {MARKER} marker at {repo_root}"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return f"the {MARKER} marker at {repo_root} is unreadable"
    if not isinstance(data, dict):
        return f"the {MARKER} marker at {repo_root} is unreadable (not a JSON object)"
    toplevel = data.get("toplevel")
    if not isinstance(toplevel, str) or Path(toplevel).resolve() != repo_root.resolve():
        return (
            f"the {MARKER} marker's recorded toplevel ({toplevel!r}) is not {repo_root} — "
            "it is stale or was copied here"
        )
    return data


def marker_at(repo_root: Path) -> dict[str, Any] | None:
    """The `.fr-isolation` marker IF it actually identifies `repo_root`.

    Same identity rule the `fr-isolation-required` PreToolUse hook applies: a
    marker whose recorded `toplevel` is not this checkout is stale or copied
    and proves nothing. Fails closed (returns `None`) on unreadable or
    non-mapping content — "not provably a workspace" must never be
    indistinguishable from "is one".
    """
    data = _read(repo_root)
    return data if isinstance(data, dict) else None


@dataclass(frozen=True)
class WorkspaceVerdict:
    """`ok`, or not a workspace with a one-line `reason`."""

    ok: bool
    reason: str | None = None


def valid_workspace(root: Path, branch: str | None) -> WorkspaceVerdict:
    """Does `root` (a repository toplevel, HEAD on `branch`) hold a valid marker?

    `branch` is the CURRENT branch, `None` for a detached HEAD. Drift is a
    present, non-empty `marker["branch"]` that differs from a non-None current
    branch (gh#553); a marker with no branch, or a detached HEAD, is not drift.
    """
    data = _read(root)
    if isinstance(data, str):
        return WorkspaceVerdict(ok=False, reason=data)
    problem = marker_mode_holds(root, data)
    if problem is not None:
        return WorkspaceVerdict(ok=False, reason=problem)
    recorded = data.get("branch")
    if isinstance(recorded, str) and recorded and branch is not None and branch != recorded:
        return WorkspaceVerdict(
            ok=False,
            reason=(
                f"branch drift: the workspace is isolated for {recorded!r} but HEAD is "
                f"{branch!r} (`git switch {recorded}` to return)"
            ),
        )
    return WorkspaceVerdict(ok=True)
