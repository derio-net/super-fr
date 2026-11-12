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

import os
import subprocess
import sys
from collections.abc import Callable
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
    from fr.git import git_answer

    return git_answer(root, "config", "--get", "remote.origin.url").returncode == 0


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


def worktree_path(root: Path) -> Path:
    """`~/.cache/fr/worktrees/<repo>/fr`, beside isolation's own worktrees (same `<repo>`
    as `fr.isolation.types.repo_cache_name`, read without a subprocess)."""
    common = paths._common_dir(Path(root))
    name = common.parent.name if common is not None and common.name == ".git" else Path(root).name
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


def check_feature_id(root: Path, branch: str) -> str:
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
            f"placement quiet: branch {branch!r} and {', '.join(map(repr, others))} share the "
            f"feature id {fid!r} (the branch name with `/` as `__`), which is one path on "
            f"the `{QUIET_BRANCH}` branch. Rename one of them"
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


def quiet_space(root: Path) -> paths.ArtifactSpace:
    """The quiet `ArtifactSpace` of the checkout at *root*: the fr worktree, and the
    feature its branch names (none in the fr worktree itself)."""
    root = Path(root)
    path = worktree_path(root)
    branch = head_branch(root)
    if branch is None:
        from fr.isolation.marker import marker_at

        marker = marker_at(root)
        recorded = marker.get("branch") if marker else None
        branch = recorded if isinstance(recorded, str) else None
    if branch == QUIET_BRANCH or root.resolve() == path.resolve():
        return paths.ArtifactSpace(paths.QUIET, path, None)
    if branch is None:
        raise SettingsError(
            f"placement quiet: {root} has a detached HEAD and no workspace marker naming "
            "its branch; a quiet feature is named by its branch"
        )
    fid = check_feature_id(root, branch)
    ensure_worktree(root)
    return paths.ArtifactSpace(paths.QUIET, path, fid)


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


def unreachable(why: str) -> SettingsError:
    return SettingsError(
        f"origin is unreachable ({why}): fr reads the quiet switch (origin/{QUIET_BRANCH}) at "
        "`fr isolation up` and `fr run start` and will not guess the placement without it "
        "(R23). Check the remote with `git remote -v`; `fr isolation up --no-fetch` reads "
        f"the last fetched origin/{QUIET_BRANCH} instead"
    )


def fetch_switch(root: Path, *, no_fetch: bool = False, network: Network | None = None) -> str:
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
            raise unreachable((probe.stderr or probe.stdout or "git ls-remote failed").strip())
        else:
            fetched = net(["git", "fetch", "--no-tags", "origin", FETCH_REFSPEC])
            if fetched.returncode != 0:
                raise unreachable((fetched.stderr or "git fetch failed").strip())
    placement = paths.QUIET if read_switch(root) is not None else paths.REPO
    if placement == paths.QUIET:
        fast_forward(root)
    return placement
