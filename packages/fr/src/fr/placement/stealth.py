"""The stealth placement (spec 2026-11-04-repo-feature-settings R2, R24; §3.E).

**Chosen per run.** Stealth is never read from repo settings: `fr isolation up` or `fr
run start` is given `--stealth <tracking-repo>@<branch>` (or, run from the tracking repo,
`--target <path>`), and the workspace's isolation state and `.fr-isolation` marker record
`placement: stealth` and the tracking ref. Every fr command run there reads the marker
(`fr.artifacts.paths.space_for`), so none falls back to `repo`.

**The tracking worktree.** A clone of the tracking repo on its branch, at
`~/.cache/fr/worktrees/<repo>/stealth--<tracking-slug>`. Each target has its own
directory there, `<host>--<owner>--<repo>/` (a target with a local-path origin, or none,
is `local--<dirname>`), and a feature's artifacts sit below
`<target-dir>/features/<feature-id>/` in the repo layout (`fr.artifacts.paths`).

**Fail-fast and fatal.** An unreachable tracking repo, or a missing branch, refuses
before anything is written; every state write commits in the tracking worktree and is
pushed compare-and-swap (`fr.triage.gitseam.push_ref_cas`), and a push that does not
land refuses the command, with the tracking worktree put back as it was
(`commit_and_push`). It is never only a warning.

**Privacy.** A tracking repo more visible than the target is refused
(`fr.triage.privacy.more_visible`); a visibility that cannot be read refuses too.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urlparse

from fr.artifacts import paths
from fr.settings import SettingsError

if TYPE_CHECKING:
    from fr.artifacts.commit import CommitOutcome

STEALTH: Final = "stealth"
WORKTREE_PREFIX: Final = "stealth--"
TARGET_SETTINGS: Final = "settings.yaml"
"""`<target-dir>/settings.yaml` on the tracking branch: the target's policy (R2)."""
QUIET_FORGE: Final = {"labels": "off", "comments": "off", "issues": "off", "pr_body": "minimal"}
"""The forge values stealth sets itself (R5, R24 "what reaches the target")."""
PLACEMENT_SUFFIX: Final = ".stealth.json"
"""`<runs dir>/<run-id>.stealth.json`: the target's remote and branch and the product head
the state describes (R24 "resume"). Not a cursor field: the run kind does not change."""
_NETWORK_TIMEOUT_S: Final = 60
_PUSH_ATTEMPTS: Final = 3

Network = Callable[[list[str], Path], "subprocess.CompletedProcess[str]"]
"""Runs one git argv (cwd given) that talks to the tracking repo, bounded, never
prompting."""
Visibility = Callable[[str, "Path | None"], "str | None"]
"""A repo (URL or local path), and a checkout of it when fr has one -> `private` |
`internal` | `public`, or None unreadable."""


@dataclass(frozen=True)
class StealthRef:
    """A tracking ref: the tracking repo (URL or local path) and its branch."""

    repo: str
    branch: str

    @property
    def text(self) -> str:
        return f"{self.repo}@{self.branch}"


def parse_ref(text: str) -> StealthRef:
    """`<repo>@<branch>`, split at the LAST `@` (an scp-like URL has one of its own)."""
    repo, sep, branch = text.strip().rpartition("@")
    if not sep or not repo or not branch or ":" in branch or branch.startswith("-"):
        raise SettingsError(
            f"--stealth {text!r}: name the tracking repo and its branch as "
            "`<repo>@<branch>` (e.g. `git@example.com:me/track.git@main`)"
        )
    return StealthRef(repo, branch)


def is_local(repo: str) -> bool:
    """A local path (or `file://`), not a forge URL."""
    if repo.startswith(("/", "./", "../", "~", "file://")):
        return True
    return ":" not in repo


def _strip_git(name: str) -> str:
    return name[: -len(".git")] if name.endswith(".git") else name


def dir_name(repo: str | None, fallback: Path) -> str:
    """`<host>--<owner>--<repo>` for a forge URL, `local--<dirname>` for a local path (or
    no remote at all: *fallback* is the checkout whose name is used)."""
    from fr._hosts import _REMOTE_HOST_RE, slug_from_url

    if repo is None or is_local(repo):
        base = Path(repo.removeprefix("file://")).name if repo else Path(fallback).name
        return f"local--{_strip_git(base) or 'repo'}"
    host = urlparse(repo).hostname if "://" in repo else None
    if host is None:
        match = _REMOTE_HOST_RE.match(repo)
        host = match.group(1) if match else "host"
    slug = slug_from_url(repo) or _strip_git(repo.rstrip("/").rsplit("/", 1)[-1])
    return "--".join([host, *(_strip_git(s) for s in slug.split("/") if s)])


def tracking_slug(ref: StealthRef) -> str:
    """The tracking worktree's name below `stealth--`: the tracking repo and its branch."""
    return f"{dir_name(ref.repo, Path(ref.repo))}--{paths.feature_id(ref.branch)}"


def origin_url(root: Path) -> str | None:
    from fr.git import GitUnavailableError, git_answer

    try:
        done = git_answer(root, "config", "--get", "remote.origin.url")
    except GitUnavailableError:
        return None
    return done.stdout.strip() or None if done.returncode == 0 else None


def target_dir(root: Path) -> str:
    """The target checkout's directory name in the tracking worktree."""
    from fr.isolation.types import _git_common_dir

    common = _git_common_dir(Path(root).resolve())
    main = common.parent if common.name == ".git" else Path(root).resolve()
    return dir_name(origin_url(root), main)


def worktree_path(root: Path, ref: StealthRef) -> Path:
    """`~/.cache/fr/worktrees/<repo>/stealth--<tracking-slug>`, beside the target's own
    worktrees (the same `<repo>` as the quiet `fr` worktree)."""
    from fr.placement.quiet import worktree_path as quiet_path

    return quiet_path(Path(root).resolve()).parent / f"{WORKTREE_PREFIX}{tracking_slug(ref)}"


def _default_network(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
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


network: Network = _default_network
"""The seam tests replace; every git call that talks to the tracking repo goes through it."""


def _url_arg(repo: str) -> str:
    return str(Path(repo).expanduser()) if is_local(repo) and not repo.startswith("file:") else repo


def check_reachable(ref: StealthRef, cwd: Path) -> None:
    """R24 fail-fast: the tracking repo answers and has the branch, or refuse."""
    probe = network(
        ["git", "ls-remote", "--exit-code", _url_arg(ref.repo), f"refs/heads/{ref.branch}"],
        cwd,
    )
    if probe.returncode == 0:
        return
    if probe.returncode == 2:
        raise SettingsError(
            f"placement stealth: the tracking repo {ref.repo} has no branch {ref.branch!r}; "
            "fr refuses before writing anything (R24 fail-fast). Create the branch there "
            "and retry"
        )
    why = (probe.stderr or probe.stdout or "git ls-remote failed").strip()
    raise SettingsError(
        f"placement stealth: the tracking repo {ref.repo} is unreachable ({why}); fr "
        "refuses before writing anything (R24 fail-fast)"
    )


_REACHED: set[str] = set()
"""Tracking refs found reachable this process: `space_for` checks each once."""


_PRIVACY_OK: set[tuple[str, str]] = set()
"""(tracking ref, target remote) pairs `check_privacy` passed this process. The push seam
refuses a pair that is not here without asking first, so no caller can skip the guard."""


def reset_caches() -> None:
    """Forget every per-process answer (tests, a long-lived process)."""
    _REACHED.clear()
    _PRIVACY_OK.clear()


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    from fr.git import GitUnavailableError, git_answer

    try:
        return git_answer(cwd, *args)
    except GitUnavailableError as e:
        raise SettingsError(f"placement stealth: {e}") from e


def _same_repo(a: str, b: str) -> bool:
    if is_local(a) and is_local(b):
        return Path(_url_arg(a)).resolve() == Path(_url_arg(b)).resolve()
    return a.rstrip("/") == b.rstrip("/")


def _fetch(path: Path, ref: StealthRef) -> None:
    done = network(
        ["git", "fetch", "--quiet", "--no-tags", "origin", _refspec(ref)],
        path,
    )
    if done.returncode != 0:
        raise SettingsError(
            f"placement stealth: cannot fetch {ref.text} into {path}: "
            f"{(done.stderr or 'git fetch failed').strip()} (R24 fail-fast)"
        )


def _refspec(ref: StealthRef) -> str:
    return f"+refs/heads/{ref.branch}:{_remote_ref(ref)}"


def _remote_ref(ref: StealthRef) -> str:
    return f"refs/remotes/origin/{ref.branch}"


def _copy_identity(root: Path, path: Path) -> None:
    """fr's commits in the tracking clone use the target checkout's git identity, when it
    has one of its own (a CI runner may have no global identity)."""
    for key in ("user.name", "user.email"):
        value = _git(root, "config", "--get", key)
        if value.returncode == 0 and value.stdout.strip():
            _git(path, "config", key, value.stdout.strip())


def _is_ancestor(path: Path, a: str, b: str) -> bool:
    return _git(path, "merge-base", "--is-ancestor", a, b).returncode == 0


def _replay(path: Path, onto: str) -> bool:
    """Rebase this clone's unpushed commits onto *onto* (features' paths are disjoint, so
    a conflict means something is wrong); a rebase that fails is aborted. Whether it
    landed."""
    if _git(path, "rebase", "--quiet", "--autostash", onto).returncode == 0:
        return True
    _git(path, "rebase", "--abort")
    return False


def sync(path: Path, ref: StealthRef) -> None:
    """Bring the tracking clone at *path* to the tracking ref's tip (review p4-r1), the
    caller holding its lock: fetch, then fast-forward a clone that is behind, keep one
    that is only ahead (its unpushed commits ride the next push, a fast-forward), and
    replay unpushed commits onto a tip that moved meanwhile. A fast-forward or a replay
    that cannot run refuses: a stale clone is never read, or pushed, as the state."""
    _fetch(path, ref)
    remote = _remote_ref(ref)
    if _is_ancestor(path, "HEAD", remote):
        done = _git(path, "merge", "--ff-only", "--quiet", remote)
        if done.returncode != 0:
            raise SettingsError(
                f"placement stealth: cannot bring the tracking worktree {path} to the tip of "
                f"{ref.text}: {(done.stderr or done.stdout or 'git merge failed').strip()}. "
                "Resolve it there (fr will not read a stale clone as the state) and retry"
            )
        return
    if _is_ancestor(path, remote, "HEAD"):
        return
    if not _replay(path, remote):
        raise SettingsError(
            f"placement stealth: the tracking worktree {path} holds unpushed commits that "
            f"do not replay on the tip of {ref.text} (another host pushed meanwhile). fr "
            "refuses rather than read or push them as the state: inspect them there "
            f"(`git log {remote}..HEAD`), then drop or rebase them and retry"
        )


def ensure_worktree(root: Path, ref: StealthRef) -> Path:
    """The tracking worktree for *ref*: cloned on demand, else checked (it is a clone of
    the tracking repo, on the branch), fetched and fast-forwarded. Never a force flag."""
    path = worktree_path(root, ref)
    if (path / ".git").exists():
        url = origin_url(path)
        head = _git(path, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
        if url is None or not _same_repo(url, ref.repo) or head != ref.branch:
            raise SettingsError(
                f"placement stealth: {path} is not the tracking worktree of {ref.text} (its "
                f"origin is {url or 'unset'}, its branch {head or 'detached'}). Move it away "
                "and retry"
            )
        from fr.placement.quiet import fr_worktree_lock

        with fr_worktree_lock(path):
            sync(path, ref)
        return path
    if path.exists() and any(path.iterdir()):
        raise SettingsError(
            f"placement stealth: {path} exists and is not the tracking worktree; move it "
            "away and retry"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    done = network(
        [
            "git",
            "clone",
            "--quiet",
            "--no-tags",
            "--single-branch",
            "--branch",
            ref.branch,
            _url_arg(ref.repo),
            str(path),
        ],
        path.parent,
    )
    if done.returncode != 0:
        raise SettingsError(
            f"placement stealth: cannot clone {ref.text} to {path}: "
            f"{(done.stderr or 'git clone failed').strip()} (R24 fail-fast)"
        )
    _copy_identity(root, path)
    return path


# --- the local record ---------------------------------------------------------------


def marker_tracking(root: Path) -> tuple[StealthRef, str] | None:
    """The tracking ref and target directory a stealth marker at *root* records, or None
    when the checkout is not a stealth workspace."""
    from fr.isolation.marker import marker_at

    marker = marker_at(Path(root))
    if not marker or marker.get("placement") != STEALTH:
        return None
    tracking = marker.get("tracking")
    if not isinstance(tracking, dict) or not isinstance(tracking.get("ref"), str):
        raise SettingsError(
            f"{Path(root) / '.fr-isolation'}: placement: stealth without its `tracking` ref; "
            "re-run `fr isolation up --stealth <repo>@<branch>`"
        )
    target = tracking.get("target")
    return parse_ref(tracking["ref"]), (
        target if isinstance(target, str) and target else target_dir(root)
    )


def marker_entry(ref: StealthRef, target: str) -> dict[str, str]:
    """The marker's (and the state's) record of the tracking ref."""
    return {"ref": ref.text, "target": target}


def stealth_space(root: Path) -> paths.ArtifactSpace:
    """The stealth `ArtifactSpace` of the workspace at *root*: `<tracking worktree>/
    <target-dir>`, and the feature its branch names. The tracking repo is checked
    reachable once per process (R24 fail-fast), before any caller writes."""
    from fr.placement.quiet import branch_of, check_feature_id, check_owner

    root = Path(root)
    found = marker_tracking(root)
    assert found is not None
    ref, target = found
    wt = worktree_path(root, ref)
    if not (wt / ".git").exists():
        raise SettingsError(
            f"placement stealth: the tracking worktree {wt} is gone; re-create it with "
            f"`fr isolation up --stealth {ref.text}` (R24 fail-fast)"
        )
    if ref.text not in _REACHED:
        from fr.placement.quiet import fr_worktree_lock

        check_reachable(ref, wt)
        with fr_worktree_lock(wt):
            sync(wt, ref)  # p4-r1: never read an unpushed or stale clone as the state
        _REACHED.add(ref.text)
    branch = branch_of(root)
    if branch is None:
        raise SettingsError(
            f"placement stealth: {root} has a detached HEAD and no marker branch; a stealth "
            "feature is named by its branch"
        )
    fid = check_feature_id(root, branch, STEALTH)
    check_owner(wt / target, fid, branch, STEALTH)
    return paths.ArtifactSpace(STEALTH, wt / target, fid)


def tracking_root(space: paths.ArtifactSpace) -> Path:
    """The tracking worktree of a stealth space (its root is `<worktree>/<target-dir>`)."""
    return space.root.parent


# --- what reaches the target -----------------------------------------------------------

FR_OWNED_PATHS: Final = (
    *(f"{d}/" for d in paths.ARTIFACT_TREES),
    ".fr/",
    ".fr-isolation",
    ".claude/agents/fr-",
    ".claude/rules/acceptance-matrix.md",
    ".devcontainer/fr-profiles.yaml",
    "scripts/validate-plans.sh",
)
"""Path prefixes only fr writes in a repo: its artifact trees and the repository
configuration it scaffolds (decision quiet-placement-bound-vs-repo-config). A stealth
push refuses a commit that touches one (R24 "no fr file reaches the target")."""


def refuse_repo_config(repo_root: Path, command: str, what: str) -> None:
    """R24 "what reaches the target": under stealth no fr file reaches the target, so a
    command that writes repository configuration INTO the target (*what*) refuses, exit
    2, before it writes anything (review p4-r3). Under quiet the same files are written
    for the operator to commit (decision quiet-placement-bound-vs-repo-config)."""
    if paths.outside_repo(Path(repo_root)) != STEALTH:
        return
    raise SettingsError(
        f"{command} is not available under placement stealth: it writes {what} into the "
        "target, and no fr file reaches a stealth target (R24). Nothing was written"
    )


def refuse_forge_writes(repo_root: Path, command: str) -> None:
    """R24 "what reaches the target": only the code and one minimal draft PR. A command
    that writes issues, labels or comments to the target's forge refuses under stealth,
    exit 2, before any forge call (review p4-r5). The forge clients refuse the same
    writes underneath (`fr.placement.forge_guard`); this names the command."""
    from fr.placement.forge_guard import StealthForgeWriteError, in_stealth

    if not in_stealth(Path(repo_root)):
        return
    raise StealthForgeWriteError(
        f"{command} is not available under placement stealth: it writes to the target's "
        "forge, which receives only the code and one minimal draft PR (R24). Nothing was "
        "written"
    )


def _is_fr_owned(rel: str) -> bool:
    """Case-folded: on a case-insensitive filesystem `Docs/Superpowers/` IS fr's tree, and a
    case-sensitive one gains nothing from telling them apart here."""
    folded = rel.casefold()
    return folded.startswith(tuple(p.casefold() for p in FR_OWNED_PATHS))


def fr_paths_in(root: Path, commits: Sequence[str]) -> list[str]:
    """The paths among *commits*' changes that only fr writes (`FR_OWNED_PATHS`). Read
    NUL-separated with quoting off, so no path is C-quoted or split at a newline in it."""
    from fr.git import git_argv

    found: list[str] = []
    for sha in commits:
        argv = git_argv(
            Path(root),
            "-c", "core.quotePath=false", "diff-tree", "-z", "--no-commit-id", "--name-only",
            "-r", "-m", "--root", sha,
        )  # fmt: skip
        done = subprocess.run(argv, cwd=root, capture_output=True, check=False)
        if done.returncode != 0:  # fail closed: a commit fr cannot read is not pushed
            raise SettingsError(
                f"placement stealth: cannot list the paths of commit {sha}: "
                f"{done.stderr.decode(errors='replace').strip()}"
            )
        for raw in done.stdout.split(b"\0"):
            rel = raw.decode("utf-8", "surrogateescape")
            if rel and _is_fr_owned(rel) and rel not in found:
                found.append(rel)
    return found


# --- privacy ------------------------------------------------------------------------


def https_form(repo: str) -> str | None:
    """The `https://<host>/<path>` form of a forge remote: a URL (any scheme, its user and
    port dropped) or an scp-like `user@host:path` (review p4-r7); None when no host."""
    if "://" in repo:
        parsed = urlparse(repo)
        if not parsed.hostname:
            return None
        return f"https://{parsed.hostname}/{parsed.path.lstrip('/')}"
    hostpart, sep, path = repo.partition(":")
    host = hostpart.rsplit("@", 1)[-1]
    if not sep or not host or not path:
        return None
    return f"https://{host}/{path.lstrip('/')}"


_PINNABLE_BACKENDS: Final = frozenset({"github", "gitlab"})
"""Backends whose client fr can point at a given host (`gh` GH_HOST, `glab` --hostname).
`tea` resolves its own login, so a gitea visibility is unreadable here (fail closed)."""


def _bare_host(host: str) -> str:
    """Lowercased, any `user@` and `:port` dropped."""
    host = host.strip().lower().rsplit("@", 1)[-1]
    if host.startswith("["):
        return host.split("]", 1)[0] + "]"
    return host.split(":", 1)[0]


def _forge_visibility(repo: str, checkout: Path | None = None) -> str | None:
    """*repo*'s visibility from its forge, always asked on the host of *repo*'s own URL
    (the slug's host). With a *checkout* of it, its declared forge type picks the client
    (review p4-r7), and a checkout whose forge names a different host is unreadable.
    None when it cannot be read (which refuses)."""
    from fr._hosts import slug_from_url
    from fr.triage.privacy import live_visibility

    if is_local(repo):
        return "private"
    slug = slug_from_url(repo)
    if slug is None:
        return None
    url = https_form(repo)
    url_host = (urlparse(url).hostname or "").lower() if url else ""
    if url is None or not url_host:
        return None
    try:
        from fr import _hosts, hostclient

        if checkout is None:
            backend = _hosts.backend_for_url(url)
        else:
            # The slug is the remote's, so the host asked must be the remote's too: a
            # checkout whose forge names another host would answer for another repo of
            # the same name (review p4-r7). Raw hostnames, never the SaaS-filtered ones.
            root = Path(checkout)
            raw = _hosts.declared_host(root) or _hosts.origin_hostname(root) or ""
            if _bare_host(raw) != url_host:
                return None
            backend = _hosts.detect_backend(root)
        saas = _hosts.DEFAULT_HOST_BACKENDS.get(url_host)
        if saas is not None and saas != backend:
            return None  # a SaaS host has one forge: any other client answers wrongly
        if backend not in _PINNABLE_BACKENDS:
            return None  # its client cannot be pinned to url_host (tea asks its own login)
        client = hostclient.client_for_backend(backend, host=url_host)
    except Exception:  # noqa: BLE001 - an unbuildable client is "unreadable", which refuses
        return None
    return live_visibility(client, slug)


visibility: Visibility = _forge_visibility
"""The visibility port (tests replace it; nothing here calls a forge in a test)."""


def check_privacy(
    ref: StealthRef, target_remote: str | None, *, target_root: Path | None = None
) -> None:
    """R24 privacy: refuse a tracking repo more visible than the target, and either
    visibility unreadable (fail closed, naming the repo). A local path is private, so a
    local pair passes. *target_root*, the target's checkout, has its visibility read by
    its own forge client (review p4-r7)."""
    from fr.triage.privacy import more_visible

    target = target_remote or "."
    if (ref.text, target) in _PRIVACY_OK:
        return
    seen: dict[str, str] = {}
    for repo in (ref.repo, target):
        checkout = target_root if repo == target and repo != ref.repo else None
        answer = "private" if repo == "." else visibility(repo, checkout)
        if answer is None:
            raise SettingsError(
                f"placement stealth: cannot read the visibility of {repo}; fr refuses to put "
                "a target's state in a tracking repo it cannot place (R24 privacy)"
            )
        seen[repo] = answer
    if more_visible(seen[ref.repo], seen[target]):
        raise SettingsError(
            f"placement stealth: the tracking repo {ref.repo} is {seen[ref.repo]} and the "
            f"target {target} is {seen[target]}: its state would be more visible than its "
            "code (R24 privacy). Use a tracking repo no more visible than the target"
        )
    _PRIVACY_OK.add((ref.text, target))


# --- entering stealth -----------------------------------------------------------------


def enter(root: Path, branch: str, ref: StealthRef) -> dict[str, str]:
    """Everything `up` and `run start` do under stealth before anything is written in the
    target: the tracking repo reachable with its branch, privacy, the feature id free,
    then the tracking worktree. Returns the marker's `tracking` entry."""
    from fr.placement.quiet import check_feature_id, check_owner

    root = Path(root)
    check_reachable(ref, root)
    check_privacy(ref, origin_url(root), target_root=root)
    fid = check_feature_id(root, branch, STEALTH)
    target = target_dir(root)
    wt = ensure_worktree(root, ref)
    check_owner(wt / target, fid, branch, STEALTH)
    _REACHED.add(ref.text)
    return marker_entry(ref, target)


def from_tracking_repo(cwd: Path) -> StealthRef:
    """The tracking ref of the checkout at *cwd*, for a run started FROM the tracking repo:
    its origin (or its own path) and its current branch."""
    from fr.placement.quiet import head_branch

    shown = _git(Path(cwd), "rev-parse", "--show-toplevel")
    top = (
        Path(shown.stdout.strip()) if shown.returncode == 0 and shown.stdout.strip() else Path(cwd)
    )
    branch = head_branch(top)
    if branch is None:
        raise SettingsError(
            f"placement stealth: the tracking checkout {top} has a detached HEAD; name the "
            "tracking ref with --stealth <repo>@<branch>"
        )
    return StealthRef(origin_url(top) or str(top.resolve()), branch)


# --- the fatal state push ---------------------------------------------------------


def restore_files(wt: Path, files: Sequence[Path]) -> None:
    """Put each of *files* (written by THIS operation, in the tracking worktree *wt*) back
    to its bytes at HEAD, deleting one HEAD does not hold, with its index entry; empty
    directories it leaves are removed. Nothing else in *wt* is touched (review p4-r2: a
    concurrent workspace's pending file is not fr's to reset)."""
    top = wt.resolve()
    for f in files:
        path = Path(f).resolve()
        try:
            rel = path.relative_to(top).as_posix()
        except ValueError:
            continue
        if _git(wt, "cat-file", "-e", f"HEAD:{rel}").returncode == 0:
            _git(wt, "checkout", "HEAD", "--", rel)
            continue
        _git(wt, "rm", "--cached", "--quiet", "--ignore-unmatch", "--", rel)
        path.unlink(missing_ok=True)
        parent = path.parent
        while parent != top and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent


def _rollback(wt: Path, old: str, files: Sequence[Path]) -> None:
    """Drop the one commit this operation made (when it made one) and put *files* back as
    they were: a soft reset moves only the branch, so no other path's bytes or index entry
    move (review p4-r2: never `reset --hard`, which wiped a concurrent workspace's pending
    file). A commit already replayed on a newer tip keeps that tip under it."""
    if _git(wt, "rebase", "--abort").returncode != 0:
        pass  # no rebase in progress: the common case
    if _git(wt, "rev-parse", "HEAD").stdout.strip() != old:
        _git(wt, "reset", "--quiet", "--soft", "HEAD~1")
    restore_files(wt, files)


def _push(wt: Path, ref: StealthRef) -> None:
    """Push HEAD to the tracking branch compare-and-swap, and only as a fast-forward of
    the tip fr last saw (a HEAD beside that tip is replayed onto it first, p4-r1); on a
    lost race fetch, replay this commit on the new tip (features' paths are disjoint)
    and retry, bounded. Any other failure raises `StealthPushError`."""
    from fr.artifacts.commit import StealthPushError
    from fr.triage.gitseam import GitError, PushRefusedError, push_ref_cas

    for _ in range(_PUSH_ATTEMPTS):
        old = _git(wt, "rev-parse", "--verify", "--quiet", _remote_ref(ref)).stdout.strip()
        if old and not _is_ancestor(wt, old, "HEAD") and not _replay(wt, old):
            # p4-r1: the lease alone would force HEAD over a tip it does not descend from
            raise StealthPushError(
                f"placement stealth: cannot replay this state commit on the tip of "
                f"{ref.text}; the step is NOT recorded (R24)"
            )
        head = _git(wt, "rev-parse", "HEAD").stdout.strip()
        try:
            landed = push_ref_cas(
                wt, "origin", head, f"refs/heads/{ref.branch}", expected_old=old or None
            )
        except (PushRefusedError, GitError) as e:
            raise StealthPushError(
                f"placement stealth: the tracking repo {ref.repo} refused the state push "
                f"({str(e).strip()}); the step is NOT recorded and nothing moved (R24)"
            ) from e
        if landed:
            _git(wt, "update-ref", _remote_ref(ref), head)
            return
        try:
            _fetch(wt, ref)
        except SettingsError as e:
            raise StealthPushError(f"{e}; the step is NOT recorded (R24)") from e
        if not _replay(wt, _remote_ref(ref)):
            raise StealthPushError(
                f"placement stealth: cannot replay this state commit on the new tip of "
                f"{ref.text}; the step is NOT recorded (R24)"
            )
    raise StealthPushError(
        f"placement stealth: {ref.text} kept moving ({_PUSH_ATTEMPTS} attempts); the step is "
        "NOT recorded (R24)"
    )


def _dirty_elsewhere(wt: Path, mine: Sequence[Path]) -> list[str]:
    """Uncommitted changes in *wt* fr did not write: anything outside a feature's path.
    A change below `<target>/features/<id>/` is another workspace's pending write (it
    commits under this lock next), never in the way of a pathspec commit, and left alone
    (review p4-r2)."""
    status = _git(wt, "status", "--porcelain", "--untracked-files=no")
    owned = {p.resolve() for p in mine}
    out = []
    for line in status.stdout.splitlines():
        rel = line[3:].split(" -> ")[-1]
        parts = Path(rel).parts
        if len(parts) >= 3 and parts[1] == paths.FEATURES_DIR:
            continue
        if (wt / rel).resolve() not in owned:
            out.append(rel)
    return out


def commit_and_push(
    ref: StealthRef,
    wt: Path,
    files: Sequence[Path],
    message: str,
    commit: Callable[[Path, Sequence[Path], str], CommitOutcome],
    *,
    target_remote: str | None,
    target_root: Path | None = None,
) -> CommitOutcome:
    """R24: commit *files* in the tracking worktree *wt*, then push that commit
    compare-and-swap. A push that does not land rolls the worktree back to its bytes
    before this commit and raises `StealthPushError` (exit 2): the cursor never moves
    locally while the tracking ref did not.

    The privacy guard is held HERE, at the one push seam: a tracking repo more visible
    than *target_remote* (the target's origin) refuses before anything is committed,
    whichever caller got this far (R24 "privacy")."""
    from fr.artifacts.commit import CommitOutcome
    from fr.placement.quiet import fr_worktree_lock

    check_privacy(ref, target_remote, target_root=target_root)
    with fr_worktree_lock(wt):
        stray = _dirty_elsewhere(wt, files)
        if stray:
            return CommitOutcome(
                committed=False,
                reason=(
                    f"refusing to commit: the tracking worktree {wt} has uncommitted changes "
                    f"to {stray[0]}, which fr did not write; commit or discard them there"
                ),
            )
        old = _git(wt, "rev-parse", "HEAD").stdout.strip()
        outcome = commit(wt, files, message)
        if not outcome.committed:
            return outcome
        try:
            _push(wt, ref)
        except BaseException:
            _rollback(wt, old, files)
            raise
    return outcome


def plain_commit(wt: Path, files: Sequence[Path], message: str) -> CommitOutcome:
    """Commit exactly *files* in the tracking worktree (no product-branch policy applies:
    this is the tracking repo's branch, which may be its default)."""
    from fr.artifacts.commit import CommitOutcome

    rels = [str(Path(f).resolve().relative_to(wt.resolve())) for f in files]
    added = _git(wt, "add", "--", *rels)
    if added.returncode != 0:
        return CommitOutcome(committed=False, reason=added.stderr.strip())
    if not _git(wt, "diff", "--cached", "--name-only", "--", *rels).stdout.strip():
        return CommitOutcome(committed=False, reason="nothing to commit", unchanged=True)
    done = _git(wt, "commit", "--quiet", "--no-verify", "-m", message, "--", *rels)
    if done.returncode != 0:
        return CommitOutcome(committed=False, reason=done.stderr.strip())
    sha = _git(wt, "rev-parse", "HEAD").stdout.strip()
    return CommitOutcome(
        committed=True, reason="committed", paths=tuple(files), message=message, sha=sha
    )


# --- the product head (R24 "resume") ----------------------------------------------


def placement_file(runs_dir: Path, run_id: str) -> Path:
    return runs_dir / f"{run_id}{PLACEMENT_SUFFIX}"


def product_head(root: Path, branch: str) -> str | None:
    """The pushed head of the product branch (`refs/remotes/origin/<branch>`): the state
    only ever describes code that is already pushed (R24: code before state)."""
    done = _git(Path(root), "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}")
    return done.stdout.strip() or None if done.returncode == 0 else None


def write_placement_file(root: Path, runs_dir: Path, run_id: str, branch: str) -> Path:
    """Write `<run-id>.stealth.json`: the target's remote and branch and the product head
    this state describes. The caller commits it with the step."""
    path = placement_file(runs_dir, run_id)
    body = {
        "target_remote": origin_url(root),
        "target_branch": branch,
        "product_head": product_head(root, branch),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(body, indent=2, sort_keys=True) + "\n"
    if not path.is_file() or path.read_text() != text:
        path.write_text(text)
    return path


def read_placement_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise SettingsError(f"{path}: unreadable stealth placement file: {e}") from e
    if not isinstance(data, dict):
        raise SettingsError(f"{path}: unreadable stealth placement file: not an object")
    return data


@dataclass(frozen=True)
class Reconciled:
    """What resume found: `equal`, `branch-ahead` (the last step's bookkeeping is redone)
    or `state-ahead` (refused)."""

    verdict: str
    recorded: str | None
    branch_head: str | None


def reconcile(root: Path, recorded: str | None, branch: str) -> Reconciled:
    """R24 "resume": compare the product head the state recorded with the branch's pushed
    head. A state describing a commit the branch does not hold refuses, naming it."""
    head = product_head(root, branch)
    if recorded == head:
        return Reconciled("equal", recorded, head)
    if recorded is None:
        return Reconciled("branch-ahead", recorded, head)
    have = _git(Path(root), "cat-file", "-e", f"{recorded}^{{commit}}").returncode == 0
    if (
        head is not None
        and have
        and _git(Path(root), "merge-base", "--is-ancestor", recorded, head).returncode == 0
    ):
        return Reconciled("branch-ahead", recorded, head)
    raise SettingsError(
        f"placement stealth: the state describes product commit {recorded}, which "
        f"origin/{branch} does not hold (its head is {head or 'absent'}): the state is ahead "
        "of the code. Push that commit to the target, or resume on a host that has it (R24)"
    )


def note(message: str) -> None:
    print(f"fr: placement stealth: {message}", file=sys.stderr)


@dataclass(frozen=True)
class Resume:
    """What `fr isolation up --stealth … --resume <run-id>` found in the tracking repo."""

    branch: str
    placement_file: Path
    reconciled: Reconciled


def find_run(root: Path, ref: StealthRef, run_id: str) -> Path:
    """The `<run-id>.stealth.json` of *run_id* in this target's directory of the tracking
    worktree (any feature), or refuse naming where fr looked."""
    wt = worktree_path(root, ref)
    base = wt / target_dir(root) / paths.FEATURES_DIR
    found = sorted(base.glob(f"*/{paths.KIND_DIRS['run']}/{run_id}{PLACEMENT_SUFFIX}"))
    if len(found) != 1:
        raise SettingsError(
            f"placement stealth: {ref.text} holds {len(found) or 'no'} run {run_id!r} for "
            f"this target (looked below {base}); nothing to resume"
        )
    return found[0]


def prepare_resume(root: Path, ref: StealthRef, run_id: str) -> Resume:
    """R24 "resume", before any worktree of the target is made: the tracking repo checked
    (reachable, private enough), the run found, the product branch fetched from the
    target's remote, and the recorded product head reconciled with it. A state that is
    ahead of the code refuses here, naming the missing commit."""
    root = Path(root)
    check_reachable(ref, root)
    check_privacy(ref, origin_url(root), target_root=root)
    ensure_worktree(root, ref)
    _REACHED.add(ref.text)
    path = find_run(root, ref, run_id)
    data = read_placement_file(path)
    branch = data.get("target_branch")
    if not isinstance(branch, str) or not branch:
        raise SettingsError(f"{path}: records no target_branch; cannot resume {run_id}")
    fetched = network(
        ["git", "fetch", "--quiet", "--no-tags", "origin", f"+refs/heads/{branch}:"
         f"refs/remotes/origin/{branch}"],
        root,
    )  # fmt: skip
    if fetched.returncode != 0:
        raise SettingsError(
            f"placement stealth: cannot fetch {branch!r} from the target's origin "
            f"({(fetched.stderr or 'git fetch failed').strip()}); resume needs the code"
        )
    recorded = data.get("product_head")
    verdict = reconcile(root, recorded if isinstance(recorded, str) else None, branch)
    return Resume(branch, path, verdict)
