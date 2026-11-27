"""Network environment and `up --branch` classification of the isolation lifecycle (#1517).

`network_env`, `fetch_placement`, `run_network`, `resolve_branch_refs`,
`classify_branch` and the value types they return. Split out of `local.py`; it
never imports `fr.isolation.local`.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fr.ghclient import CommandRunner
from fr.isolation.runner import Runner
from fr.isolation.types import IsolationError, _git_common_dir


def _realpath(p: Path) -> Path:
    """Symlink-resolved identity for gc's discovery keys. The three sources
    spell the same workspace differently (a docker label is whatever string was
    recorded at `up`; the cache scan builds from `$HOME`; a state record carries
    its own copy), and on macOS `/tmp` is a symlink — so raw path equality would
    classify one workspace twice. Never raises: a path that cannot be resolved
    keys as itself."""
    try:
        return p.resolve()
    except OSError:
        return p


def _main_worktree_root(repo_root: Path) -> Path:
    """The MAIN checkout's toplevel, even when launched from a linked worktree.

    The common dir is <main>/.git; its parent is the main toplevel. Keying
    isolation off the durable main checkout (not the possibly-ephemeral launch
    worktree, e.g. an Agent(isolation:"worktree")) means the persisted state and
    the spawned worktree survive that launch worktree being reaped. No-op for a
    main checkout. #292

    `--separate-git-dir` / non-".git"-named git dirs are out of scope: the
    guard falls back to repo_root (the bind-mount still resolves correctly via
    _git_common_dir; only this normalization is skipped).
    """
    common = _git_common_dir(repo_root)
    return common.parent if common.name == ".git" else repo_root


# ----- `up --branch <B>` classification (#438, spec 2026-09-23 §3.E) -----


@dataclass(frozen=True)
class RemoteView:
    """What fr knows about `origin/<B>`.

    `state` is one of:
    - `exists` — probed and fetched (or, under `--no-fetch`, a local ref);
    - `unfetched` — ls-remote says it exists but the explicit fetch failed;
    - `absent` — ls-remote exit 2, or no origin remote at all;
    - `unknown` — any other probe failure (never read as absence, #354);
    - `unchecked` — `--no-fetch` with no local `origin/<B>` ref.

    `sha` is the local `origin/<B>` ref's commit when one exists: freshly
    fetched for `exists`, the last-fetched value otherwise.
    """

    state: str
    sha: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class BranchDecision:
    """`local` checks `<B>` out as-is; `remote` creates `<B>` from `ref`
    (`origin/<B>`); `cold` hands off to the cold-start base resolution.
    `lines` go to stderr before the worktree is added."""

    action: str
    ref: str | None
    lines: tuple[str, ...]


# A git call that talks to origin is bounded and never prompts (#438 review).
_NETWORK_TIMEOUT_S = 60.0
_BATCH_SSH = "ssh -o BatchMode=yes -o ConnectTimeout=15"


def network_env(run: Runner, repo_root: Path) -> dict[str, str]:
    """The environment for a git call that talks to origin: never prompt
    (no terminal credential prompt; ssh in BatchMode with a connect
    timeout) — unless the operator already chose an ssh command, which a
    GIT_SSH_COMMAND of ours would silently override."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    if not env.get("GIT_SSH_COMMAND") and not env.get("GIT_SSH"):
        configured = run(["git", "config", "--get", "core.sshCommand"], cwd=repo_root)
        if configured.returncode != 0 or not (configured.stdout or "").strip():
            env["GIT_SSH_COMMAND"] = _BATCH_SSH
    return env


def fetch_placement(
    repo_root: Path,
    branch: str,
    no_fetch: bool,
    network: Callable[[list[str]], subprocess.CompletedProcess[str]],
    stealth: Any = None,
) -> str:
    """The placement `up` records for *branch* (every target's one call): with *stealth*
    (a `fr.placement.stealth.StealthRef`, chosen per run, R24) the tracking repo's
    reachability, privacy and worktree, before anything is written; otherwise fetch the
    quiet switch through *network* and, under quiet, check the branch's feature id. A
    refusal is an `IsolationError` (exit 2)."""
    from fr.placement.quiet import check_feature_id, ensure_worktree, fetch_switch
    from fr.settings import SettingsError

    if stealth is not None:
        from fr.placement.stealth import enter

        try:
            enter(repo_root, branch, stealth)
        except SettingsError as e:
            raise IsolationError(str(e)) from e
        return "stealth"
    try:
        placement = fetch_switch(repo_root, no_fetch=no_fetch, network=network)
        if placement == "quiet":
            check_feature_id(repo_root, branch)
            ensure_worktree(repo_root)
    except SettingsError as e:
        raise IsolationError(str(e)) from e
    return placement


def run_network(
    run: Runner,
    repo_root: Path,
    argv: list[str],
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """A bounded, non-interactive git call against origin. A timeout comes
    back as a non-zero, non-2 exit — `unknown`, never `absent`. `extra_env`
    is a forge adapter's host overlay, set on top of the network env
    (gh#1015)."""
    env = {**network_env(run, repo_root), **(extra_env or {})}
    return run(argv, cwd=cwd or repo_root, env=env, timeout=_NETWORK_TIMEOUT_S)


def _forge_runner(run: Runner) -> CommandRunner:
    """This lifecycle's runner as a forge adapter's `CommandRunner`: the
    adapter's host overlay (`GH_HOST` / `GITLAB_HOST`) is applied on top of
    this process's environment, never dropped (gh#1015). With no host the
    call is exactly what it was before the overlay existed."""

    def call(
        argv: list[str], *, cwd: Path, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        if not env:
            return run(argv, cwd=cwd)
        return run(argv, cwd=cwd, env={**os.environ, **env})

    return call


def resolve_branch_refs(
    run: Runner, repo_root: Path, branch: str, remote: str
) -> tuple[list[str], bool]:
    """Fetch `<branch>` from `<remote>`, and report whether that fetch is
    trustworthy as `branch_fetched`.

    The fetch uses an EXPLICIT refspec (`+refs/heads/<b>:refs/remotes/
    <remote>/<b>`, like `_remote_view`), not a bare `git fetch <remote>
    <branch>` (C2 review, #665/#598): in a `--single-branch` clone the
    configured fetch refspec only covers the default branch, so a bare
    fetch of another branch updates FETCH_HEAD only, never the
    remote-tracking ref — leaving `<remote>/<branch>` stale or entirely
    absent and hiding a commit pushed to the real remote branch (from a
    different clone) after the merge.

    A failed fetch is not automatically a fallback: GitHub deletes a
    merged branch by default, and THAT case — `git ls-remote --heads`
    confirms exit 2 for the EXACT `refs/heads/<b>` (a bare name
    pattern-matches `foo/<b>` too) — is the one situation where the
    refs this clone still has (typically the local branch) are still
    trustworthy. Any other outcome (`ls-remote` finds the branch, or
    `ls-remote` itself fails) means the branch's true remote state is
    unknown, so `branch_fetched` is False and the caller must not verify
    off a possibly-stale ref alone.

    Module-level (not bound to a workspace's ops object) so a caller with no
    state file — `fr archive --branch` (2026-09-28-closeout-always §B.2) —
    resolves refs exactly as verify-merge does. Returns every ref among
    `<remote>/<branch>` and the local `<branch>` that resolves; an empty list
    means neither does, and the caller decides how to refuse.
    """
    tracking = f"refs/remotes/{remote}/{branch}"
    fetch = run_network(
        run, repo_root, ["git", "fetch", remote, f"+refs/heads/{branch}:{tracking}"]
    )
    branch_fetched = fetch.returncode == 0
    if not branch_fetched:
        ls = run_network(
            run, repo_root, ["git", "ls-remote", "--exit-code", remote, f"refs/heads/{branch}"]
        )
        branch_fetched = ls.returncode == 2
    refs = [
        cand
        for cand in (f"{remote}/{branch}", branch)
        if run(
            ["git", "rev-parse", "--verify", "--quiet", f"{cand}^{{commit}}"],
            cwd=repo_root,
        ).returncode
        == 0
    ]
    return refs, branch_fetched


def _why(what: str, result: subprocess.CompletedProcess[str]) -> str:
    """`<what> exited <rc>`, plus the last stderr line git printed."""
    lines = [ln for ln in (result.stderr or "").splitlines() if ln.strip()]
    head = f"{what} exited {result.returncode}"
    return f"{head}: {lines[-1].strip()}" if lines else head


def _short(sha: str | None) -> str:
    return (sha or "")[:12]


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _local_row(
    branch: str,
    local_sha: str,
    remote: RemoteView,
    relation: tuple[int, int] | None,
    worktree: Path,
) -> BranchDecision:
    """The `local <B> exists` rows. #322 corner 1: always reuse as-is."""
    remote_ref = f"origin/{branch}"
    line = f"isolation: reusing local branch {branch} at {_short(local_sha)}"
    if remote.state in ("unknown", "unfetched", "unchecked"):
        return BranchDecision("local", branch, (f"{line} (origin not checked: {remote.reason})",))
    if remote.state != "exists" or remote.sha is None or remote.sha == local_sha:
        return BranchDecision("local", branch, (line,))
    if relation is None:
        return BranchDecision(
            "local",
            branch,
            (f"{line} (differs from {remote_ref} at {_short(remote.sha)}; relation unknown)",),
        )
    ahead, behind = relation
    if behind == 0:
        return BranchDecision(
            "local", branch, (f"{line} ({_plural(ahead, 'commit')} ahead of {remote_ref})",)
        )
    if ahead == 0:
        relation_text, catch_up = "is behind", f"merge --ff-only {remote_ref}"
    else:
        relation_text, catch_up = "has diverged from", f"merge {remote_ref}"
    return BranchDecision(
        "local",
        branch,
        (
            f"WARNING: local {branch} ({_short(local_sha)}) {relation_text} {remote_ref} "
            f"({_short(remote.sha)}, +{ahead}/−{behind}) — using local; "
            f"`git -C {worktree} {catch_up}` to catch up",
        ),
    )


def classify_branch(
    branch: str,
    *,
    local_sha: str | None,
    remote: RemoteView,
    relation: tuple[int, int] | None,
    base: str | None,
    worktree: Path,
) -> BranchDecision:
    """The §3.E table as a pure function — no git, no I/O.

    `relation` is (ahead, behind) of local `<B>` against `origin/<B>`, or None
    when it could not be counted; it is only read when both exist and differ.
    Raises IsolationError for the refused rows: `--base` beside a known
    `origin/<B>` (it would fork a second history under one name), and an
    `origin/<B>` that exists but could neither be fetched nor found locally
    (a cold start there is #438 itself).
    """
    if local_sha is not None:
        return _local_row(branch, local_sha, remote, relation, worktree)

    remote_ref = f"origin/{branch}"
    fetch_hint = f"`git fetch origin +refs/heads/{branch}:refs/remotes/origin/{branch}`"
    if remote.state == "unfetched" and remote.sha is None:
        raise IsolationError(
            f"{remote_ref} exists but could not be fetched ({remote.reason}) — retry, "
            f"or {fetch_hint}"
        )
    known = remote.state == "exists" or (
        remote.state in ("unknown", "unfetched") and remote.sha is not None
    )
    if known and base is not None:
        seen = {
            "exists": "exists",
            "unfetched": "exists (fetch failed)",
            "unknown": "was last fetched (origin unreachable)",
        }[remote.state]
        raise IsolationError(
            f"{remote_ref} {seen} — --base would fork a second history under the same "
            "name; drop --base to reuse it, or choose another branch name"
        )
    if remote.state == "exists":
        return BranchDecision(
            "remote",
            remote_ref,
            (f"isolation: reusing remote branch {branch} at {remote_ref} ({_short(remote.sha)})",),
        )
    if remote.sha is not None:  # unknown / unfetched with a last-fetched ref
        why = (
            f"fetch of {remote_ref} failed" if remote.state == "unfetched" else "origin unreachable"
        )
        return BranchDecision(
            "remote",
            remote_ref,
            (
                f"WARNING: {why} — reusing the last-fetched {remote_ref} "
                f"({_short(remote.sha)}); it may be stale",
            ),
        )
    if remote.state == "unknown":
        return BranchDecision(
            "cold",
            None,
            (
                f"WARNING: origin could not be checked for {branch} ({remote.reason}) — "
                "cold-starting it; if it exists on origin this forks a second history",
            ),
        )
    if remote.state == "unchecked":
        return BranchDecision(
            "cold",
            None,
            (
                f"isolation: {remote_ref} not checked (--no-fetch, no local ref) — "
                "starting a new branch",
            ),
        )
    return BranchDecision("cold", None, ())
