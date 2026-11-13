"""Placement drift, and `fr placement migrate-branch` (spec 2026-11-04-repo-feature-settings
R28; plan 2026-11-12-placement-resolver phase 7).

A feature branch whose artifacts do not match the repo's current placement must migrate
before it can merge. Two shapes of drift:

- **The workspace's** (`marker_drift`): its `.fr-isolation` marker recorded one
  placement at `up` and the quiet switch now names another, which is what a
  `fr placement move` leaves every live workspace with. Read from the filesystem alone
  (the marker, then the switch ref), so the CLI-entry gate can ask it before every
  command: a repo with no marker or no switch spawns no process, and nothing here ever
  reaches the network.
- **The branch's** (`branch_drift`): under quiet or stealth the branch's own tree
  carries fr artifacts (a placement-bound path it changed since it left the default
  ref), which must never reach a product branch (R23, R24). It needs git, so only the
  callers that are not every command ask it: `fr push`, `deliver` and `fr validate
  artifacts`, which is how CI, where there is no marker, sees it.

Detection never migrates, in any context, CI included: every caller refuses, naming
`fr placement migrate-branch`, which runs only in a valid workspace and moves the
artifacts as its own commit on each side.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from fr.artifacts import paths
from fr.settings import SettingsError

COMMAND: Final = "fr placement migrate-branch"


class DriftError(SettingsError):
    """A command refused because the branch's artifacts are not where the placement says."""


@dataclass(frozen=True)
class Drift:
    recorded: str
    """The placement the branch's artifacts follow."""
    current: str
    """The repo's placement now."""
    files: tuple[str, ...] = ()
    """For a branch's drift: the fr artifacts its own tree carries."""


def _current(root: Path) -> str | None:
    from fr.placement.quiet import read_switch

    try:
        return paths.QUIET if read_switch(root) is not None else paths.REPO
    except SettingsError:
        return None  # an unreadable switch is the command's own refusal to make


def marker_drift(root: Path) -> Drift | None:
    """The workspace recorded a placement the switch no longer names. Filesystem only."""
    from fr.isolation.marker import marker_at

    marker = marker_at(Path(root))
    if not marker:
        return None
    recorded = marker.get("placement", paths.REPO)
    if not isinstance(recorded, str) or recorded == paths.STEALTH:
        return None  # stealth is chosen per run (R24): no switch speaks for it
    current = _current(Path(root))
    if current is None or current == recorded:
        return None
    return Drift(recorded, current)


def _git(root: Path, *args: str) -> str | None:
    from fr.git import GitUnavailableError, git_answer

    try:
        done = git_answer(root, *args)
    except GitUnavailableError:
        return None
    return done.stdout if done.returncode == 0 else None


def _base(root: Path) -> str | None:
    from fr.placement.merged import default_ref

    ref, _ = default_ref(root)
    if ref is None:
        return None
    out = _git(root, "merge-base", "HEAD", ref)
    return out.strip() if out else None


def branch_files(root: Path) -> tuple[str | None, list[str]]:
    """(the branch's base on the default ref, the placement-bound paths the branch
    changed since it left it)."""
    base = _base(root)
    if base is None:
        return None, []
    out = _git(root, "diff", "--name-only", "--no-renames", base, "HEAD")
    names = [n for n in (out or "").splitlines() if n and paths.placement_bound(n)]
    return base, sorted(names)


def branch_drift(root: Path) -> Drift | None:
    """Under quiet or stealth, the branch's own tree carries fr artifacts."""
    root = Path(root)
    try:
        placement = paths.outside_repo(root)
    except SettingsError:
        return None
    if placement is None:
        return None
    _, names = branch_files(root)
    return Drift(paths.REPO, placement, tuple(names)) if names else None


def detect(root: Path, *, deep: bool = True) -> Drift | None:
    """The branch's drift: the workspace's always, the branch tree's with *deep*."""
    return marker_drift(Path(root)) or (branch_drift(Path(root)) if deep else None)


def refusal(found: Drift) -> str:
    if found.files:
        listed = ", ".join(found.files[:3]) + (" ..." if len(found.files) > 3 else "")
        what = (
            f"the repo is placement: {found.current}, and this branch's own tree carries fr "
            f"artifacts ({listed}), which never reach a product branch under it (R23, R24)"
        )
    else:
        what = (
            f"this workspace was set up under placement: {found.recorded}, and the repo is "
            f"now placement: {found.current}, so its branch's artifacts are in the wrong place"
        )
    return (
        f"placement drift: {what}. Run `{COMMAND}` in its workspace: it moves them as its "
        "own commit on each side and pushes them where they belong (R28). fr does not "
        "migrate them anywhere else, CI included"
    )


def refuse(root: Path, command: str, *, deep: bool = True) -> None:
    """Raise `DriftError` naming `fr placement migrate-branch` when the branch drifted."""
    found = detect(Path(root), deep=deep)
    if found is not None:
        raise DriftError(f"{command}: {refusal(found)}")


# --- fr placement migrate-branch ----------------------------------------------------------


def _show(root: Path, rev: str, rel: str) -> bytes | None:
    import subprocess

    from fr.git import git_argv

    done = subprocess.run(
        git_argv(root, "show", f"{rev}:{rel}"), cwd=root, capture_output=True, check=False
    )
    return done.stdout if done.returncode == 0 else None


def _run(root: Path, *args: str) -> str:
    from fr.git import git_answer

    done = git_answer(root, *args)
    if done.returncode != 0:
        raise SettingsError(f"{COMMAND}: `git {' '.join(args)}` failed: {done.stderr.strip()}")
    return done.stdout


def _remote(root: Path) -> str:
    from fr.commands.push_cmd import remote_of
    from fr.git_policy.push import PushRefusedError

    try:
        return remote_of(root)
    except PushRefusedError as e:
        raise SettingsError(f"{COMMAND}: {e}") from e


def _into_outside(root: Path, branch: str, current: str, emit: Callable[[str], None]) -> None:
    """The branch's own fr artifacts into its feature root (quiet or stealth), and off the
    branch: one commit on each side, then both pushed."""
    from fr.artifacts.commit import commit_paths
    from fr.artifacts.paths import artifact_root
    from fr.commands.push_cmd import _push_placement
    from fr.git_policy.push import PushRefusedError

    base, names = branch_files(root)
    if not names or base is None:
        emit(f"nothing to migrate: {branch} carries no fr artifact (placement {current})")
        return
    from fr.placement.move import _files, inside

    # Read from git, never the working tree: a symlinked artifact refuses (its target could
    # be any file on the host) instead of being copied into the other placement.
    at_head = _files(root, "HEAD", keep=set(names).__contains__)
    froot = artifact_root(root)
    written: list[Path] = []
    for rel in names:
        if rel not in at_head:
            continue  # the branch deleted it: nothing to carry over
        data = at_head[rel][1]
        path = inside(froot, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        written.append(path)
    if written:
        outcome = commit_paths(
            root, written, f"chore(fr): migrate {branch}'s artifacts to placement {current}"
        )
        if not (outcome.committed or outcome.unchanged):
            raise SettingsError(f"{COMMAND}: {outcome.reason}")
    for rel in names:
        if _show(root, base, rel) is not None:
            _run(root, "checkout", base, "--", rel)
        else:
            _run(root, "rm", "-q", "--cached", "--ignore-unmatch", "--", rel)
            inside(root, rel).unlink(missing_ok=True)
    _run(root, "commit", "-q", "--no-verify", "-m",
         f"chore(placement): move fr artifacts off {branch} (placement {current}, R28)",
         "--", *names)  # fmt: skip
    try:
        pushed = _push_placement(root, _remote(root), branch, code=True)
    except PushRefusedError as e:
        raise SettingsError(
            f"{COMMAND}: the commits are made; push them with `fr push`: {e}"
        ) from e
    emit(
        f"migrated {len(names)} artifact(s) of {branch} to placement {current}; pushed "
        f"{' and '.join(pushed)}"
    )


def _into_repo(root: Path, branch: str, emit: Callable[[str], None]) -> None:
    """The branch's quiet feature root back into its tree (repo layout), and off `fr`:
    one commit on each side, the placement recorded last (so a crash re-runs), pushed."""
    from fr.git_policy.push import PushRefusedError, atomic_push, push
    from fr.placement import quiet
    from fr.placement.move import META, _files, inside, record_placement

    frwt = quiet.worktree_path(root)
    fid = paths.checked_feature_id(branch)
    prefix = f"{paths.FEATURES_DIR}/{fid}"
    froot = frwt / prefix
    remote = _remote(root)
    if (frwt / ".git").exists() and froot.is_dir():
        quiet.fast_forward(root)
        # From git (the fr worktree's HEAD), never the working tree: a symlink refuses.
        got = _files(frwt, "HEAD", f"{prefix}/")
        files = {
            p.removeprefix(f"{prefix}/"): data
            for p, (_, data) in got.items()
            if p.removeprefix(f"{prefix}/").split("/", 1)[0] not in META
        }
        written: list[str] = []
        for rel, data in sorted(files.items()):
            target = inside(root, rel)
            if target.is_file() and target.read_bytes() == data:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            written.append(rel)
        if written:
            _run(root, "add", "--", *written)
            _run(root, "commit", "-q", "--no-verify", "-m",
                 f"chore(fr): migrate {branch}'s artifacts to placement repo (R28)",
                 "--", *written)  # fmt: skip
        with quiet.fr_worktree_lock(frwt):
            _run(frwt, "rm", "-r", "-q", "--", prefix)
            _run(frwt, "commit", "-q", "--no-verify", "-m",
                 f"chore(fr): {fid} migrated to placement repo (R28)", "--", prefix)  # fmt: skip
        try:
            push(root, remote, branch)
            atomic_push(root, frwt, remote, branch, code=False)
        except PushRefusedError as e:
            raise SettingsError(f"{COMMAND}: the commits are made; push them: {e}") from e
        emit(f"migrated {len(files)} artifact(s) of {branch} back to placement repo; pushed")
    else:
        emit(f"nothing to move: {branch} has no feature root on `fr`")
    record_placement(root, paths.REPO)


def migrate_branch(root: Path, *, emit: Callable[[str], None] = print) -> None:
    """Move this workspace branch's artifacts to the repo's current placement (R28).
    Refuses outside a valid workspace; a branch with nothing to move is a no-op."""
    from fr.isolation.marker import marker_at, valid_workspace
    from fr.placement.move import record_placement
    from fr.placement.quiet import head_branch

    root = Path(root)
    branch = head_branch(root)
    verdict = valid_workspace(root, branch)
    marker = marker_at(root)
    if not verdict.ok or marker is None:
        raise SettingsError(
            f"{COMMAND}: run it in a valid workspace (the fr-isolation worktree of the branch "
            f"it migrates): {verdict.reason or 'no marker'}"
        )
    if branch is None:
        raise SettingsError(f"{COMMAND}: HEAD is detached; switch to the workspace's branch")
    recorded = marker.get("placement", paths.REPO)
    if recorded == paths.STEALTH:
        current = paths.STEALTH
    else:
        found = _current(root)
        if found is None:
            raise SettingsError(f"{COMMAND}: the quiet switch (origin/fr) cannot be read")
        current = found
    if current in (paths.QUIET, paths.STEALTH):
        if recorded != current:
            record_placement(root, current)
        _into_outside(root, branch, current, emit)
    elif recorded == paths.QUIET:
        _into_repo(root, branch, emit)
    else:
        emit(f"nothing to migrate: {branch} already follows placement {current}")
