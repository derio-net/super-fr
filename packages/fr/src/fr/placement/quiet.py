"""The quiet placement (spec 2026-11-04-repo-feature-settings R2, R23; §3.E).

**The switch.** A repo is quiet when its remote has an orphan branch `fr` whose root
`settings.yaml` says `placement: quiet`. fr reads it from `refs/remotes/origin/fr`, by
the commit that ref names, never a working tree, and fetches that ref at `fr isolation
up` and `fr run start` (`fetch_switch`), refusing both when `origin` is unreachable. A
repo with no `origin` is `repo`, whatever local branches it has.

**The worktree.** Under quiet every artifact lives in a second worktree of `fr`, at
`~/.cache/fr/worktrees/<repo>/fr`, below `features/<feature-id>/` (the layout rule of
`fr.artifacts.paths`). It is created on demand from `origin/fr` (`ensure_worktree`),
never with a force flag, and only ever moves by fast-forward or by appending fr's own
commits.

**The feature id** is the branch slug, which is not injective (`feat/a__b` and
`feat__a/b` share `feat__a__b`, gh#1419). Since the slug is a feature's PATH here, a
branch whose id another branch already holds is refused, naming both: otherwise two
features would write one path, and R23's "each commit touches one feature's path" would
be false without anything noticing.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from fr.artifacts import paths
from fr.settings import SettingsError

QUIET_BRANCH: Final = "fr"
"""The orphan branch, local and on origin, that holds a quiet repo's artifacts."""
QUIET_REF: Final = f"refs/heads/{QUIET_BRANCH}"
FETCH_REFSPEC: Final = f"+{QUIET_REF}:{paths.SWITCH_REF}"
"""The one fetch `up` and `run start` make: it moves only the remote-tracking ref."""

_NETWORK_TIMEOUT_S: Final = 60
_SOURCE: Final = f"{paths.SWITCH_REF}:{paths.SWITCH_SETTINGS}"

Network = Callable[[list[str]], "subprocess.CompletedProcess[str]"]
"""Runs one git argv against origin (bounded, never prompting)."""


@dataclass(frozen=True)
class Switch:
    """A valid quiet switch: its settings, the raw mapping they came from (for per-key
    provenance), and the commit read."""

    settings: Any  # fr.settings.model.Settings (kept loose: no import cycle at load)
    data: object
    sha: str


_CACHE: dict[tuple[str, str], Switch | None] = {}
"""(common dir, switch sha) -> the parsed switch. The sha is read from the filesystem
on every call, so a moved ref is a new key: the cache can never serve stale settings."""


def _git_dir(root: Path) -> Path | None:
    dot = root / ".git"
    if dot.is_dir():
        return dot
    if dot.is_file():
        try:
            line = dot.read_text().strip()
        except OSError:
            return None
        if line.startswith("gitdir:"):
            return (root / line.removeprefix("gitdir:").strip()).resolve()
    return None


def _ref_sha(common: Path, ref: str) -> str | None:
    """The sha a ref holds, read from the filesystem (loose, then packed-refs)."""
    loose = common / ref
    try:
        if loose.is_file():
            value = loose.read_text().strip()
            return value or None
        packed = common / "packed-refs"
        if not packed.is_file():
            return None
        for line in packed.read_text().splitlines():
            if line.startswith(("#", "^")):
                continue
            sha, _, name = line.partition(" ")
            if name == ref:
                return sha
    except OSError:
        return None
    return None


def _has_origin(root: Path) -> bool:
    """An `origin` remote is configured. Not a git repo (or no such directory) is no:
    the caller's own repo check names that problem."""
    from fr.git import GitUnavailableError, git_answer

    if not Path(root).is_dir():
        return False
    try:
        return git_answer(root, "config", "--get", "remote.origin.url").returncode == 0
    except GitUnavailableError:
        return False


def _read(root: Path) -> Switch | None:
    common = paths._common_dir(root)
    if common is None:
        return None
    sha = _ref_sha(common, paths.SWITCH_REF)
    if sha is None:
        return None
    key = (str(common), sha)
    if key in _CACHE:
        return _CACHE[key]
    if not _has_origin(root):
        return None  # R23: no origin is `repo`; a stale tracking ref speaks for nobody
    from fr.settings.load import parse_settings_text, show_at_commit, yaml_of

    text = show_at_commit(root, sha, paths.SWITCH_SETTINGS)
    result: Switch | None = None
    if text is not None:
        settings = parse_settings_text(text, source=_SOURCE, servable=False)
        if settings.placement == paths.QUIET:
            result = Switch(settings, yaml_of(text, _SOURCE), sha)
        elif settings.placement != paths.REPO:
            raise SettingsError(
                f"{_SOURCE}: placement: {settings.placement} cannot be set on the `fr` switch: "
                "stealth is chosen per run, never by repo settings (R24); the switch says "
                "`placement: quiet`"
            )
    _CACHE[key] = result
    return result


def read_switch(root: Path) -> Any:
    """The quiet settings `origin/fr` carries (`fr.settings.model.Settings`), or None
    when there is no switch: no origin, no `origin/fr`, no root `settings.yaml`, or one
    saying `placement: repo`. A file that is there but unreadable or invalid refuses
    (`SettingsError`, R2): it is never read as absent."""
    switch = _read(Path(root))
    return None if switch is None else switch.settings


def switch(root: Path) -> Switch | None:
    """`read_switch` with the raw mapping and the commit, for the settings loader."""
    return _read(Path(root))


def refuse_under_quiet(root: Path, command: str, why: str) -> None:
    """Refuse *command* BEFORE it writes anything when the repo is quiet (review p3-r1):
    a writer that cannot yet put its files on the `fr` branch must not leave them in the
    product checkout, where a plain `git add -A` carries them to the feature branch.
    Reads the switch alone (no fr worktree is created to refuse); a stealth workspace
    refuses the same way (R24: no fr file reaches the target)."""
    from fr.artifacts.paths import outside_repo

    placement = outside_repo(Path(root))
    if placement is not None:
        raise SettingsError(
            f"`{command}` is not available under placement {placement} yet: {why}. Nothing "
            "was written (R23, R24: no fr file reaches a product branch)"
        )


def worktree_path(root: Path) -> Path:
    """`~/.cache/fr/worktrees/<repo>/fr`, beside isolation's own worktrees (same `<repo>`
    as `fr.isolation.types.repo_cache_name`, read without a subprocess). A relative *root*
    (`.`) is resolved first: its name would otherwise be empty."""
    root = Path(root).resolve()
    common = paths._common_dir(root)
    name = common.parent.name if common is not None and common.name == ".git" else root.name
    home = Path(os.environ.get("HOME", str(Path.home())))
    return home / ".cache" / "fr" / "worktrees" / name / QUIET_BRANCH


def head_branch(root: Path) -> str | None:
    """The branch checked out at *root*, from its HEAD file; None when detached."""
    git_dir = _git_dir(Path(root))
    if git_dir is None:
        return None
    try:
        head = (git_dir / "HEAD").read_text().strip()
    except OSError:
        return None
    return head.removeprefix("ref: refs/heads/") if head.startswith("ref: refs/heads/") else None


def _branch_names(common: Path) -> set[str]:
    """Every local and `origin` branch name, from the filesystem."""
    prefixes = ("refs/heads/", "refs/remotes/origin/")
    names: set[str] = set()
    for prefix in prefixes:
        base = common / prefix
        if base.is_dir():
            names.update(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file())
    packed = common / "packed-refs"
    try:
        lines = packed.read_text().splitlines() if packed.is_file() else []
    except OSError:
        lines = []
    for line in lines:
        name = line.partition(" ")[2]
        for prefix in prefixes:
            if name.startswith(prefix):
                names.add(name.removeprefix(prefix))
    names.discard("HEAD")
    names.discard(QUIET_BRANCH)
    return names


def _where(placement: str) -> tuple[str, str]:
    """(refusal prefix, where a feature path lives) for the shared quiet/stealth checks."""
    if placement == "stealth":
        return "placement stealth", "the tracking repo's directory for this target"
    return "placement quiet", f"the `{QUIET_BRANCH}` branch"


def check_feature_id(root: Path, branch: str, placement: str = "quiet") -> str:
    """*branch*'s feature id, refusing one another branch already holds (gh#1419)."""
    if branch == QUIET_BRANCH:
        raise SettingsError(
            f"placement quiet: a feature branch cannot be named `{QUIET_BRANCH}`, the branch "
            "that holds the artifacts"
        )
    fid = paths.feature_id(branch)
    common = paths._common_dir(Path(root))
    others = (
        sorted(n for n in _branch_names(common) if n != branch and paths.feature_id(n) == fid)
        if common is not None
        else []
    )
    if others:
        raise SettingsError(
            f"{_where(placement)[0]}: branch {branch!r} and {', '.join(map(repr, others))} "
            f"share the feature id {fid!r} (the branch name with `/` as `__`), which is one "
            f"path in {_where(placement)[1]}. Rename one of them"
        )
    return fid


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    from fr.git import GitUnavailableError, git_answer

    try:
        return git_answer(root, *args)
    except GitUnavailableError as e:
        raise SettingsError(f"placement quiet: {e}") from e


_OWNED: set[tuple[str, str]] = set()
"""(common dir, worktree path) pairs already verified this process."""


def _check_owner(root: Path, path: Path) -> None:
    """The worktree at *path* must be THIS repo's, on `fr`. The path is keyed by the
    repo's directory name only, so two repos of the same name share it: reusing another
    repo's worktree would commit this repo's artifacts to that repo's `fr` branch and
    push them to its origin."""
    mine = paths._common_dir(Path(root))
    if mine is not None and (str(mine), str(path)) in _OWNED:
        return
    theirs = _git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    owner = Path(theirs.stdout.strip()).resolve() if theirs.returncode == 0 else None
    if mine is None or owner is None or owner != mine.resolve():
        owner_repo = owner.parent if owner is not None and owner.name == ".git" else owner
        raise SettingsError(
            f"placement quiet: {path} is the `{QUIET_BRANCH}` worktree of another repository "
            f"({owner_repo or 'unknown'}), not of {Path(root).resolve()}: two repos with the "
            "same directory name share that path. Move one of them (or that worktree) "
            "away and retry"
        )
    head = _git(path, "symbolic-ref", "--quiet", "HEAD")
    if head.returncode != 0 or head.stdout.strip() != QUIET_REF:
        raise SettingsError(
            f"placement quiet: {path} is a worktree of {Path(root).resolve()} but its HEAD is "
            f"{head.stdout.strip() or 'detached'}, not {QUIET_REF}; fr writes artifacts only "
            f"on `{QUIET_BRANCH}`. Switch it back (`git -C {path} switch {QUIET_BRANCH}`)"
        )
    _OWNED.add((str(mine), str(path)))


def _refuse_unrelated_local(root: Path) -> None:
    """A local `fr` branch is adopted only when it is an ancestor or a descendant of
    `origin/fr` (review p3-r9): any other one is somebody else's history, and committing
    on it would push a second, unrelated root to origin's append-only `fr`."""
    remote = _git(root, "rev-parse", "--verify", "--quiet", f"{paths.SWITCH_REF}^{{commit}}")
    if remote.returncode != 0:
        return
    for older, newer in ((QUIET_REF, paths.SWITCH_REF), (paths.SWITCH_REF, QUIET_REF)):
        if _git(root, "merge-base", "--is-ancestor", older, newer).returncode == 0:
            return
    raise SettingsError(
        f"placement quiet: the local `{QUIET_BRANCH}` branch is neither an ancestor nor a "
        f"descendant of origin/{QUIET_BRANCH}, so it is not this repo's artifact history; "
        f"fr will not adopt it. Rename or delete it (`git branch -m {QUIET_BRANCH} "
        f"{QUIET_BRANCH}-old`) and retry"
    )


def ensure_worktree(root: Path) -> Path:
    """The fr worktree, created on demand from `origin/fr` (a local `fr` branch tracking
    it), never with a force flag. Refuses a path that is there but is not it."""
    path = worktree_path(root)
    if (path / ".git").exists():
        _check_owner(root, path)
        return path
    if path.exists() and any(path.iterdir()):
        raise SettingsError(
            f"placement quiet: {path} exists and is not the `{QUIET_BRANCH}` worktree; "
            "move it away and retry"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(root, "worktree", "prune")
    local = _git(root, "rev-parse", "--verify", "--quiet", f"{QUIET_REF}^{{commit}}")
    if local.returncode == 0:
        _refuse_unrelated_local(root)
        argv = ["worktree", "add", str(path), QUIET_BRANCH]
    else:
        argv = ["worktree", "add", "--no-track", "-b", QUIET_BRANCH, str(path), paths.SWITCH_REF]
    done = _git(root, *argv)
    if done.returncode != 0 and not (path / ".git").exists():
        raise SettingsError(
            f"placement quiet: cannot create the `{QUIET_BRANCH}` worktree at {path}: "
            f"{done.stderr.strip()}"
        )
    if local.returncode != 0:
        _git(root, "config", f"branch.{QUIET_BRANCH}.remote", "origin")
        _git(root, "config", f"branch.{QUIET_BRANCH}.merge", QUIET_REF)
    return path


def fast_forward(root: Path) -> None:
    """Move the fr worktree up to `origin/fr` when it is strictly behind (never a reset:
    a local `fr` that diverged keeps its commits, and `fr push` replays them)."""
    path = worktree_path(root)
    if not (path / ".git").exists():
        return
    _check_owner(root, path)
    behind = _git(path, "merge-base", "--is-ancestor", "HEAD", paths.SWITCH_REF)
    if behind.returncode == 0:
        _git(path, "merge", "--ff-only", "--quiet", paths.SWITCH_REF)


def owner_of(fr_root: Path, fid: str) -> str | None:
    """The branch the feature root *fid* records as its owner, or None when unrecorded."""
    try:
        text = (fr_root / paths.FEATURES_DIR / fid / paths.FEATURE_OWNER).read_text()
    except OSError:
        return None
    return text.strip() or None


def check_owner(fr_root: Path, fid: str, branch: str, placement: str = "quiet") -> None:
    """Refuse when *fid*'s feature root is owned by a branch other than *branch*: the id
    is not injective, and the other branch may live only in another clone (p3-r6)."""
    owner = owner_of(fr_root, fid)
    if owner is not None and owner != branch:
        raise SettingsError(
            f"{_where(placement)[0]}: branch {branch!r} has the feature id {fid!r}, whose path "
            f"in {_where(placement)[1]} is owned by {owner!r} "
            f"({paths.FEATURES_DIR}/{fid}/{paths.FEATURE_OWNER}). Rename the branch"
        )


def branch_of(root: Path) -> str | None:
    """The branch a checkout works on: its HEAD, or the marker's branch when detached."""
    branch = head_branch(root)
    if branch is None:
        from fr.isolation.marker import marker_at

        marker = marker_at(root)
        recorded = marker.get("branch") if marker else None
        branch = recorded if isinstance(recorded, str) else None
    return branch


def quiet_space(root: Path) -> paths.ArtifactSpace:
    """The quiet `ArtifactSpace` of the checkout at *root*: the fr worktree, and the
    feature its branch names (none in the fr worktree itself)."""
    root = Path(root)
    path = worktree_path(root)
    branch = branch_of(root)
    if branch == QUIET_BRANCH or root.resolve() == path.resolve():
        return paths.ArtifactSpace(paths.QUIET, path, None)
    if branch is None:
        raise SettingsError(
            f"placement quiet: {root} has a detached HEAD and no workspace marker naming "
            "its branch; a quiet feature is named by its branch"
        )
    fid = check_feature_id(root, branch)
    ensure_worktree(root)
    check_owner(path, fid, branch)
    return paths.ArtifactSpace(paths.QUIET, path, fid)


LOCK_NAME: Final = "fr-worktree.lock"
"""The fr worktree's lock, in ITS git dir: every workspace of a repo shares one fr
worktree and one index there, so its commits, replays and pushes are serialised."""
LOCK_WAIT_SECONDS: float = 10.0
_LOCK_POLL_S: Final = 0.05


def _fr_git_dir(fr_root: Path) -> Path:
    done = _git(fr_root, "rev-parse", "--absolute-git-dir")
    if done.returncode != 0 or not done.stdout.strip():
        raise SettingsError(
            f"placement quiet: git cannot name the git dir of the `{QUIET_BRANCH}` worktree "
            f"at {fr_root}: {done.stderr.strip()}"
        )
    return Path(done.stdout.strip())


@contextmanager
def fr_worktree_lock(fr_root: Path) -> Iterator[None]:
    """Hold the fr worktree's exclusive lock (review p3-r8), waiting a bounded
    `LOCK_WAIT_SECONDS` for another fr command to release it, then refusing, named."""
    path = _fr_git_dir(fr_root) / LOCK_NAME
    with path.open("a") as handle:
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SettingsError(
                        f"placement quiet: another fr command holds {path} (it is committing "
                        f"or pushing on the shared `{QUIET_BRANCH}` worktree); retry when it "
                        "is done"
                    ) from None
                time.sleep(_LOCK_POLL_S)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def fr_worktree_problem(fr_root: Path, *, dirty: bool = True) -> str | None:
    """Why fr cannot commit or replay on the fr worktree right now, or None: a rebase or
    merge someone left in progress there, or (with *dirty*, for a replay) uncommitted
    changes to tracked files. A pathspec commit is not blocked by unrelated edits."""
    git_dir = _fr_git_dir(fr_root)
    for name, what in (
        ("rebase-merge", "a rebase in progress"),
        ("rebase-apply", "a rebase in progress"),
        ("MERGE_HEAD", "a merge in progress"),
        ("CHERRY_PICK_HEAD", "a cherry-pick in progress"),
    ):
        if (git_dir / name).exists():
            return (
                f"the `{QUIET_BRANCH}` worktree at {fr_root} has {what}; finish or abort it "
                f"there (`git -C {fr_root} rebase --abort`) and retry"
            )
    if not dirty:
        return None
    status = _git(fr_root, "status", "--porcelain", "--untracked-files=no")
    if status.returncode == 0 and status.stdout.strip():
        first = status.stdout.strip().splitlines()[0][3:]
        return (
            f"the `{QUIET_BRANCH}` worktree at {fr_root} has uncommitted changes to tracked "
            f"files ({first}); commit or discard them there and retry"
        )
    return None


def _default_network(root: Path) -> Network:
    def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        try:
            return subprocess.run(
                argv,
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=_NETWORK_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(argv, 124, "", "timed out")
        except OSError as e:
            return subprocess.CompletedProcess(argv, 127, "", str(e))

    return run


def unreachable(why: str, command: str | None = "fr isolation up") -> SettingsError:
    """The R23 reachability refusal. *command* is the one that refused, whose own
    `--no-fetch` is the remedy; None for a command that has no such flag."""
    remedy = (
        f"; `{command} --no-fetch` reads the last fetched origin/{QUIET_BRANCH} instead"
        if command is not None
        else ""
    )
    return SettingsError(
        f"origin is unreachable ({why}): fr reads the quiet switch (origin/{QUIET_BRANCH}) at "
        "`fr isolation up` and `fr run start` and will not guess the placement without it "
        f"(R23). Check the remote with `git remote -v`{remedy}"
    )


def fetch_switch(
    root: Path,
    *,
    no_fetch: bool = False,
    network: Network | None = None,
    command: str = "fr isolation up",
) -> str:
    """Fetch `origin/fr` and return the placement it names (`quiet` or `repo`).

    No `origin` is `repo`, with nothing fetched. `--no-fetch` reads the last fetched ref
    and says so (it is not a reachability check). Otherwise an origin that cannot be
    reached refuses; an `fr` branch origin does not have deletes the stale tracking ref,
    so a deleted switch is noticed (the sticky check then refuses in a quiet workspace).
    """
    root = Path(root)
    if not _has_origin(root):
        return paths.REPO
    if no_fetch:
        print(
            f"fr: --no-fetch: reading the last fetched origin/{QUIET_BRANCH} for the placement "
            "(not a reachability check)",
            file=sys.stderr,
        )
    else:
        net = network or _default_network(root)
        probe = net(["git", "ls-remote", "--exit-code", "origin", QUIET_REF])
        if probe.returncode == 2:
            if _git(root, "rev-parse", "--verify", "--quiet", paths.SWITCH_REF).returncode == 0:
                _git(root, "update-ref", "-d", paths.SWITCH_REF)
        elif probe.returncode != 0:
            raise unreachable(
                (probe.stderr or probe.stdout or "git ls-remote failed").strip(), command
            )
        else:
            fetched = net(["git", "fetch", "--no-tags", "origin", FETCH_REFSPEC])
            if fetched.returncode != 0:
                raise unreachable((fetched.stderr or "git fetch failed").strip(), command)
    placement = paths.QUIET if read_switch(root) is not None else paths.REPO
    if placement == paths.QUIET:
        fast_forward(root)
    return placement
