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
    # `d` excluded: a deletion carries no fr artifact anywhere (review p7-r3), so the
    # move's own removal branch, and a branch that drops a stale file, are not drift.
    out = _git(root, "diff", "--name-only", "--no-renames", "--diff-filter=d", base, "HEAD")
    names = [n for n in (out or "").splitlines() if n and paths.placement_bound(n)]
    return base, sorted(names)


FETCH_HINT: Final = "fetch `origin/fr` and the default branch (`fetch-depth: 0` in CI)"


def refs_problem(root: Path) -> str | None:
    """Why this checkout cannot see what drift detection reads (the default ref and its
    history, and so `origin/fr` too), or None. A repo with no remote has no placement to
    drift from (R23: no origin is `repo`)."""
    from fr.git import GitRefusal, GitUnavailableError, remote_name
    from fr.placement.merged import default_ref

    try:
        remote = remote_name(root)
    except GitUnavailableError:
        return None
    if remote is None or isinstance(remote, GitRefusal):
        return None
    if (_git(root, "rev-parse", "--is-shallow-repository") or "").strip() == "true":
        return "this clone is shallow (`origin/fr` and the default branch's history are missing)"
    ref, why = default_ref(root)
    if ref is None:
        return why or "no default ref"
    return None


def _refs_checked(root: Path) -> None:
    """Review p7-r7: detection never fails open silently. Under a CI marker a checkout that
    cannot see the refs refuses (exit 2), the posture of `fr acceptance check`; anywhere
    else it warns on stderr and goes on."""
    import sys

    from fr.artifacts.trigger import in_ci

    problem = refs_problem(root)
    if problem is None:
        return
    text = f"placement drift cannot be checked: {problem}; {FETCH_HINT}"
    if in_ci():
        raise DriftError(text)
    print(f"warning: {text}", file=sys.stderr)


def return_copy(root: Path, names: list[str]) -> bool:
    """Is this branch `fr placement move --to repo`'s copy back into the repo (review
    p7-r3)? Recognised by structure, never by a marker the branch could assert: its tree
    holds EXACTLY what `fr` holds for the merged features, path for path and byte for byte
    (the same reading the move copies from), and the fr files it adds are among them. So it
    carries nothing `fr` does not already hold as merged history."""
    from fr.placement.move import Ctx, _files

    try:
        flat = Ctx(root, paths.REPO, paths.QUIET, {}, lambda _line: None).flat()
        if not flat or not set(names) <= set(flat):
            return False
        at_head = {p: d for p, (_, d) in _files(root, "HEAD", keep=flat.__contains__).items()}
    except SettingsError:
        return False
    return at_head == flat


def branch_drift(root: Path) -> Drift | None:
    """Under quiet or stealth, the branch's own tree carries fr artifacts."""
    root = Path(root)
    _refs_checked(root)
    try:
        placement = paths.outside_repo(root)
    except SettingsError:
        return None
    if placement is None:
        return None
    _, names = branch_files(root)
    if not names:
        return None
    if placement == paths.QUIET and return_copy(root, names):
        return None
    return Drift(paths.REPO, placement, tuple(names))


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


_OFF_SUBJECT: Final = "chore(placement): move fr artifacts off {branch}"
_INTO_SUBJECT: Final = "chore(fr): migrate {branch}'s artifacts to placement repo"


def _migration_pending(root: Path, branch: str, remote: str) -> bool:
    """A commit `migrate-branch` made on *branch* that *remote* does not hold yet (review
    p7-r2): a run killed between its commits and its push leaves one, and the re-run,
    finding nothing left to move, must still push it."""
    tracking = f"refs/remotes/{remote}/{branch}"
    since = tracking if _git(root, "rev-parse", "--verify", "--quiet", tracking) else _base(root)
    if since is None:
        return False
    subjects = (_git(root, "log", "--format=%s", f"{since.strip()}..HEAD") or "").splitlines()
    mine = (_OFF_SUBJECT.format(branch=branch), _INTO_SUBJECT.format(branch=branch))
    return any(s.startswith(mine) for s in subjects)


def _into_outside(root: Path, branch: str, current: str, emit: Callable[[str], None]) -> None:
    """The branch's own fr artifacts into its feature root (quiet or stealth), and off the
    branch: one commit on each side, then both pushed. Idempotent mid-step: a re-run with
    nothing left to move still pushes what an earlier run committed."""
    from fr.artifacts.commit import commit_paths
    from fr.artifacts.paths import artifact_root
    from fr.commands.push_cmd import _push_placement
    from fr.git_policy.push import PushRefusedError, fr_pending

    base, names = branch_files(root)
    remote = _remote(root)
    if names and base is not None:
        from fr.placement.move import _files, inside, refuse_foreign

        refuse_foreign(names, f"branch {branch}")
        # Read from git, never the working tree: a symlinked artifact refuses (its target
        # could be any file on the host) instead of being copied into the other placement.
        at_head = _files(root, "HEAD", keep=set(names).__contains__)
        froot = artifact_root(root)
        written: list[Path] = []
        for rel in names:
            if rel not in at_head:
                continue
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
             f"{_OFF_SUBJECT.format(branch=branch)} (placement {current}, R28)",
             "--", *names)  # fmt: skip
    code = bool(names) or _migration_pending(root, branch, remote)
    if not code and not (current == paths.QUIET and fr_pending(root, remote)):
        emit(f"nothing to migrate: {branch} carries no fr artifact (placement {current})")
        return
    try:
        pushed = _push_placement(root, remote, branch, code=code)
    except PushRefusedError as e:
        raise SettingsError(
            f"{COMMAND}: the commits are made; push them with `fr push`: {e}"
        ) from e
    what = f"migrated {len(names)} artifact(s) of {branch}" if names else (
        f"pushed the migration of {branch} an earlier run committed"
    )  # fmt: skip
    emit(f"{what} to placement {current}; pushed {' and '.join(pushed) or 'nothing new'}")


def _refuse_stealth_bound(root: Path) -> None:
    """Review p7-r6: no fr artifact is ever written into a branch whose repo is bound to
    stealth (R24): a stealth workspace, or a repo a move to stealth is in progress on."""
    import json

    from fr.placement import stealth
    from fr.placement.move import state_path

    bound = paths._marker_placement(root) == paths.STEALTH or (
        stealth.marker_tracking(root) is not None
    )
    try:
        state = state_path(root)
        if state.is_file() and json.loads(state.read_text()).get("to") == paths.STEALTH:
            bound = True
    except (SettingsError, ValueError, OSError):
        bound = True  # an unreadable move state is no evidence the repo is not stealth
    if bound:
        raise SettingsError(
            f"{COMMAND}: refused: this repo is bound to stealth (a stealth workspace, or a "
            "move to stealth in progress), and no fr artifact reaches a stealth target's "
            "branch (R24); nothing was written"
        )


def _into_repo(root: Path, branch: str, emit: Callable[[str], None]) -> None:
    """The branch's quiet feature root back into its tree (repo layout), and off `fr`:
    one commit on each side, the placement recorded last (so a crash re-runs), pushed.
    The placement is recorded only once nothing is left unpushed (review p7-r2)."""
    from fr.git_policy.push import PushRefusedError, atomic_push, fr_pending, push
    from fr.placement import quiet
    from fr.placement.move import META, _files, inside, record_placement, refuse_foreign

    _refuse_stealth_bound(root)
    frwt = quiet.worktree_path(root)
    fid = paths.checked_feature_id(branch)
    prefix = f"{paths.FEATURES_DIR}/{fid}"
    froot = frwt / prefix
    remote = _remote(root)
    moved = 0
    if (frwt / ".git").exists() and froot.is_dir():
        quiet.fast_forward(root)
        # From git (the fr worktree's HEAD), never the working tree: a symlink refuses.
        got = _files(frwt, "HEAD", f"{prefix}/")
        files = {
            p.removeprefix(f"{prefix}/"): data
            for p, (_, data) in got.items()
            if p.removeprefix(f"{prefix}/").split("/", 1)[0] not in META
        }
        # Only fr artifacts reach the product branch (review p7-r5): anyone who can push
        # to `fr` could otherwise plant `.github/workflows/x.yml` here.
        refuse_foreign(files, f"{prefix}/ on `fr`")
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
                 f"{_INTO_SUBJECT.format(branch=branch)} (R28)", "--", *written)  # fmt: skip
        with quiet.fr_worktree_lock(frwt):
            _run(frwt, "rm", "-r", "-q", "--", prefix)
            _run(frwt, "commit", "-q", "--no-verify", "-m",
                 f"chore(fr): {fid} migrated to placement repo (R28)", "--", prefix)  # fmt: skip
        moved = len(files)
    code = moved > 0 or _migration_pending(root, branch, remote)
    fr_side = (frwt / ".git").exists() and fr_pending(root, remote)
    if code or fr_side:
        try:
            if code:
                push(root, remote, branch)
            if fr_side:
                atomic_push(root, frwt, remote, branch, code=False)
        except PushRefusedError as e:
            raise SettingsError(f"{COMMAND}: the commits are made; push them: {e}") from e
        what = f"migrated {moved} artifact(s) of {branch}" if moved else (
            f"pushed the migration of {branch} an earlier run committed"
        )  # fmt: skip
        emit(f"{what} back to placement repo; pushed")
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
