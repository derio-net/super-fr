"""LocalWorktreeDevcontainerTarget — worktree + devcontainer over a Runner seam.

Every external call (git, devcontainer, docker, gh) goes through `runner` so
the lifecycle is unit-testable without Docker. The devcontainer CLI labels
containers with `devcontainer.local_folder=<workspace>`, which is how status
and down re-find the container.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fr.isolation.types import (
    IsolationError,
    IsolationState,
    _git_common_dir,
    _warn_legacy,
    delete_state,
    resolve_profile,
    save_state,
)

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


def subprocess_runner(
    argv: list[str], cwd: Path | None = None, check: bool = False, capture: bool = True
) -> subprocess.CompletedProcess[str]:
    """capture=False inherits stdio — exec passthrough must stream the
    container's output live (long builds/test runs), not swallow it."""
    return subprocess.run(argv, cwd=cwd, check=check, capture_output=capture, text=True)


def _home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


@dataclass
class MergeVerification:
    """Whether a branch's changes are present on a base ref (#320 close-out)."""

    changed: list[str]  # files the branch changed since its merge-base
    missing: list[str]  # changed files NOT yet present on the base ref
    changes_present: bool


def branch_changes_present(
    run: Runner, repo_root: Path, branch: str, base_ref: str
) -> MergeVerification:
    """Are the branch's changes present on `base_ref` (e.g. origin/main)?

    Compares FINAL FILE CONTENT, not commit identity / ancestry — so it is
    correct across squash, merge-commit, and rebase merges alike (an
    ancestry/patch-id check would false-negative on squash). A commit pushed to
    the branch AFTER the merge (the #320 orphan) shows up as a changed path that
    still differs from the base → reported missing. Conservative: if the base
    later changed the same paths, those read as missing (a safe "STOP and
    check", never a false "verified").
    """
    mb = run(["git", "merge-base", base_ref, branch], cwd=repo_root)
    if mb.returncode != 0:
        raise IsolationError(f"no merge-base for {base_ref} and {branch} — unrelated histories?")
    merge_base = mb.stdout.strip()
    names = run(["git", "diff", "--name-only", merge_base, branch], cwd=repo_root)
    changed = [ln for ln in names.stdout.splitlines() if ln]
    if not changed:
        return MergeVerification(changed=[], missing=[], changes_present=True)
    diff = run(
        ["git", "diff", "--name-only", branch, base_ref, "--", *changed],
        cwd=repo_root,
    )
    missing = [ln for ln in diff.stdout.splitlines() if ln]
    return MergeVerification(changed=changed, missing=missing, changes_present=not missing)


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


class LocalWorktreeDevcontainerTarget:
    def __init__(self, repo_root: Path, runner: Runner = subprocess_runner):
        # resolve() — the mount target must match the realpath git bakes
        # into the worktree's gitdir pointer (symlinked /tmp on macOS etc.).
        # Then normalize to the main toplevel so a worktree-launched run keys
        # off the durable main checkout (#292).
        self.repo_root = _main_worktree_root(Path(repo_root).resolve())
        self.run = runner

    # ---------- lifecycle ----------

    def up(
        self,
        profile: str | None,
        branch: str,
        path: Path | None = None,
        base: str | None = None,
        no_fetch: bool = False,
    ) -> IsolationState:
        if not (self.repo_root / ".git").exists():
            raise IsolationError(
                f"{self.repo_root} is not a git repo — fr isolation only runs inside one."
            )
        name = resolve_profile(self.repo_root, profile)

        worktree = path or (
            _home()
            / ".cache"
            / "fr"
            / "worktrees"
            / self.repo_root.name
            / branch.replace("/", "__")
        )
        worktree.parent.mkdir(parents=True, exist_ok=True)
        self._git_worktree_add(worktree, branch, base=base, no_fetch=no_fetch)

        config = worktree / ".devcontainer" / name / "devcontainer.json"
        # super-fr#299 part 2: the worktree is cut from the committed tree. If
        # the profile exists only as an UNCOMMITTED file in the base repo, the
        # worktree won't have it — explain the fix instead of letting
        # `devcontainer up` fail with a cryptic "config not found". Gate on the
        # base copy being GENUINELY uncommitted (porcelain non-empty): a profile
        # that is committed but merely absent on an older target branch is a
        # different situation, so we must not misreport it as "not committed".
        if not config.exists():
            rel = f".devcontainer/{name}/devcontainer.json"
            base_status = self.run(
                ["git", "-C", str(self.repo_root), "status", "--porcelain", "--", rel]
            )
            if base_status.stdout.strip():
                raise IsolationError(
                    f"profile {name!r} is written in the base repo but not committed, so the "
                    f"worktree can't see it — run `fr init scaffold --profile {name}` (which now "
                    "commits) or commit .devcontainer/ yourself, then retry `fr isolation up`."
                )
        self._ensure_mounted_env_file(config)
        # Resolve the shared common dir, not <repo_root>/.git: correct even if
        # repo_root is a worktree (a gitfile), independent of normalization (#292).
        git_dir = _git_common_dir(self.repo_root)
        result = self.run(
            [
                "devcontainer",
                "up",
                f"--workspace-folder={worktree}",
                f"--config={config}",
                f"--mount=type=bind,source={git_dir},target={git_dir}",
            ],
            cwd=worktree,
        )
        if result.returncode != 0:
            raise IsolationError(f"devcontainer up failed: {result.stderr or result.stdout}")

        state = IsolationState(
            repo_root=self.repo_root,
            branch=branch,
            worktree=worktree,
            profile=name,
            created_at=datetime.now(UTC).isoformat(),
        )
        save_state(state)
        self._write_isolation_marker(worktree, branch)
        return state

    def exec(self, state: IsolationState, argv: list[str]) -> int:
        config = state.worktree / ".devcontainer" / state.profile / "devcontainer.json"
        result = self.run(
            [
                "devcontainer",
                "exec",
                f"--workspace-folder={state.worktree}",
                f"--config={config}",
                *argv,
            ],
            cwd=state.worktree,
            capture=False,
        )
        return result.returncode

    def restart(self, state: IsolationState, force: bool = False) -> str:
        """Bounce the devcontainer without dropping the worktree (#341 Task 3).

        `docker restart` cycles only the process tree — the container filesystem
        and the bind-mounted worktree survive, so node_modules / local DB stacks
        / in-container installs are kept (unlike down+up). `force` uses
        `--time=0` (immediate SIGKILL then start) for a container too wedged to
        stop gracefully. Returns the restarted container id.
        """
        container = self._container_id(state)
        if not container:
            raise IsolationError(
                f"no container for {state.branch} — nothing to restart "
                "(run `fr isolation up` first)."
            )
        argv = ["docker", "restart", *(["--time=0"] if force else []), container]
        result = self.run(argv)
        if result.returncode != 0:
            raise IsolationError(
                f"docker restart failed: {result.stderr or result.stdout}. If the container "
                "is too wedged to stop gracefully, retry with --force."
            )
        return container

    def stats(self, state: IsolationState) -> dict[str, str] | None:
        """Host-side `docker stats --no-stream` for a RUNNING container (#341
        Task 3B), so an agent can detect a thrashing container instead of
        inferring it from hung execs. Returns None (never raises) for a missing,
        non-running, or unreadable container — the caller renders `n/a`."""
        # One `docker ps` for both id and state (id state, space-joined).
        parts = self._docker_ps(state).split()
        if len(parts) < 2 or parts[1] != "running":
            return None
        container = parts[0]
        # Pipe-delimited: MemUsage ("1.2GiB / 4GiB") itself contains spaces.
        result = self.run(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}",
                container,
            ]
        )
        line = (result.stdout or "").strip()
        if result.returncode != 0 or line.count("|") != 2:
            return None
        cpu, mem, mem_perc = line.split("|")
        return {"cpu": cpu, "mem": mem, "mem_perc": mem_perc}

    def status(self, state: IsolationState) -> dict[str, Any]:
        return {
            "repo": str(state.repo_root),
            "branch": state.branch,
            "profile": state.profile,
            "worktree": str(state.worktree),
            "worktree_exists": state.worktree.is_dir(),
            "container": self._container_state(state) or "not running",
            "pr": self._pr(state),
        }

    def verify_merge(
        self,
        state: IsolationState,
        default_branch: str = "main",
        remote: str = "origin",
    ) -> dict[str, Any]:
        """Confirm the branch's changes reached `<remote>/<default_branch>`.

        Squash/rebase/merge-safe (content-based, not ancestry). `verified`
        requires ALL THREE positive confirmations — content present AND the PR
        is `MERGED` AND the `<remote>/<default_branch>` ref is fresh (fetch
        succeeded). The content check alone can be fooled by genuinely
        convergent content (the same fix landing twice), so the MERGED PR is the
        load-bearing tiebreak; an unknown PR state or a failed fetch is
        conservatively NOT verified, never a silent pass. The close-out (#320)
        STOPs (and the caller inspects which signal is missing) when not
        verified.
        """
        base_ref = f"{remote}/{default_branch}"
        fetch = self.run(["git", "fetch", remote, default_branch], cwd=state.worktree)
        fetched = fetch.returncode == 0
        res = branch_changes_present(self.run, state.worktree, state.branch, base_ref)
        pr = self._pr(state)
        pr_state = pr.get("state") if pr else None
        verified = res.changes_present and pr_state == "MERGED" and fetched
        return {
            "branch": state.branch,
            "verified": verified,
            "changes_present": res.changes_present,
            "missing": res.missing,
            "pr_state": pr_state,
            "fetched": fetched,
        }

    def down(self, state: IsolationState, force: bool = False) -> None:
        pr = self._pr(state)
        if pr and pr.get("state") == "OPEN" and not force:
            raise IsolationError(
                f"PR for {state.branch} is still open ({pr.get('url', '?')}) — "
                "the operator may push to it. Re-run with --force to tear down anyway."
            )
        self._remove_isolation_marker(state.worktree)
        container = self._container_id(state)
        if container:
            self.run(["docker", "stop", container])
            self.run(["docker", "rm", container])
        self.run(
            ["git", "worktree", "remove", "--force", str(state.worktree)],
            cwd=self.repo_root,
        )
        delete_state(state.repo_root, state.branch)

    # ---------- helpers ----------

    def _git_worktree_add(
        self, worktree: Path, branch: str, base: str | None = None, no_fetch: bool = False
    ) -> None:
        if worktree.exists():
            return  # already provisioned — up() is idempotent on the worktree
        branches = self.run(["git", "branch", "--list", branch], cwd=self.repo_root)
        if branches.stdout.strip():
            # Reuse: check the existing branch out as-is. Never fetch or rebase —
            # continuation/reuse must inherit the branch's own tip (#322 corner 1).
            argv = ["git", "worktree", "add", str(worktree), branch]
        else:
            # Genuine cold-start: a brand-new branch. Default to freshly-fetched
            # origin/<default> instead of the base repo's current HEAD (#322).
            start_point, log_line = self._cold_start_base(branch, base, no_fetch)
            print(log_line, file=sys.stderr if log_line.startswith("WARNING") else sys.stdout)
            argv = ["git", "worktree", "add", str(worktree), "-b", branch]
            if start_point is not None:
                argv.append(start_point)
        result = self.run(argv, cwd=self.repo_root)
        if result.returncode != 0:
            raise IsolationError(f"git worktree add failed: {result.stderr}")

    # ----- .fr-isolation marker lifecycle (#328 Task 3) -----

    def _write_isolation_marker(self, worktree: Path, branch: str, mode: str = "worktree") -> None:
        """Write the `.fr-isolation` identity marker and git-exclude it.

        The marker is what the `fr-isolation-required` PreToolUse hook reads to
        decide whether an edit is inside a real isolation workspace (#328 Task
        3). Identity = the resolved worktree toplevel + branch + mode; the hook
        blocks when the recorded toplevel does not match the file's actual
        toplevel (a stale / copied marker) or when the toplevel is not a linked
        worktree. `up` also appends it to the shared `info/exclude`, so the
        marker can never be staged into a PR — backed by a committed
        `.gitignore` entry and a CI tripwire.
        """
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".fr-isolation").write_text(
            json.dumps(
                {
                    "toplevel": str(worktree.resolve()),
                    "branch": branch,
                    "mode": mode,
                    "created_at": datetime.now(UTC).isoformat(),
                },
                indent=2,
            )
            + "\n"
        )
        exclude = _git_common_dir(self.repo_root) / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude.read_text().splitlines() if exclude.is_file() else []
        if ".fr-isolation" not in existing:
            with exclude.open("a") as fh:
                fh.write(".fr-isolation\n")

    def _remove_isolation_marker(self, worktree: Path) -> None:
        """Retire the marker on `down` (idempotent — absent is fine)."""
        (worktree / ".fr-isolation").unlink(missing_ok=True)

    # ----- cold-start base resolution (#322) -----

    def _cold_start_base(
        self, branch: str, base: str | None, no_fetch: bool
    ) -> tuple[str | None, str]:
        """Resolve the start-point for a NEW branch per the spec matrix.

        Returns (start_point, log_line). start_point is the ref to append after
        `-b <branch>`, or None meaning "append nothing" — git then defaults to
        the current HEAD (byte-identical to the legacy behaviour). The log_line
        is printed by the caller; a `WARNING`-prefixed line goes to stderr.
        """
        # Operator named an explicit start-point — use it verbatim, no fetch, no
        # default-branch resolution. `--base HEAD` is the documented opt-in to the
        # old "fork from current checkout" behaviour (stacking / current-branch).
        if base is not None:
            if base == "HEAD":
                return None, f"isolation: basing new branch {branch} on HEAD (--base)"
            return base, f"isolation: basing new branch {branch} on {base} (--base)"

        if no_fetch:
            default = self._resolve_default_branch()
            ref = f"origin/{default}"
            if self._ref_exists(ref):
                return ref, f"isolation: basing new branch {branch} on {ref} (local, --no-fetch)"
            return None, (
                f"WARNING: --no-fetch but no local {ref} tracking ref — "
                f"basing {branch} on local HEAD"
            )

        if not self._has_origin_remote():
            return None, f"WARNING: no origin remote — basing {branch} on local HEAD"

        if not self._fetch_origin():
            return None, f"WARNING: git fetch origin failed — basing {branch} on local HEAD"

        default = self._resolve_default_branch()
        ref = f"origin/{default}"
        if self._ref_exists(ref):
            return ref, f"isolation: basing new branch {branch} on {ref} (fetched)"
        return None, f"WARNING: {ref} not found after fetch — basing {branch} on local HEAD"

    def _has_origin_remote(self) -> bool:
        result = self.run(["git", "remote"], cwd=self.repo_root)
        return "origin" in (result.stdout or "").split()

    def _fetch_origin(self) -> bool:
        """git fetch origin; return success. Never raises — a fetch problem
        degrades to the local-HEAD fallback, it does not abort the run."""
        result = self.run(["git", "fetch", "origin"], cwd=self.repo_root)
        if result.returncode != 0:
            return False
        # Refresh origin/HEAD so _resolve_default_branch's symbolic-ref hits.
        # Best-effort: a failure here just falls through to the gh/main chain.
        self.run(["git", "remote", "set-head", "origin", "--auto"], cwd=self.repo_root)
        return True

    def _resolve_default_branch(self) -> str:
        """symbolic-ref refs/remotes/origin/HEAD → gh defaultBranchRef → main."""
        sym = self.run(
            ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=self.repo_root
        )
        name = (sym.stdout or "").strip()
        if sym.returncode == 0 and name:
            # --short yields "origin/main"; strip to the bare branch name.
            return name.removeprefix("origin/")
        gh = self.run(
            ["gh", "repo", "view", "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"],
            cwd=self.repo_root,
        )
        gh_name = (gh.stdout or "").strip()
        if gh.returncode == 0 and gh_name:
            return gh_name  # gh returns a bare branch name — no origin/ prefix to strip
        return "main"

    def _ref_exists(self, ref: str) -> bool:
        result = self.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=self.repo_root
        )
        return result.returncode == 0

    def _ensure_mounted_env_file(self, config: Path) -> None:
        """Ensure the env-file the profile's devcontainer.json mounts exists.

        Mount-following (#272): the committed config is the source of truth —
        an unmigrated repo still mounts the legacy vk path, so creating the
        fr file would not help docker. Warn on the legacy spelling; no
        --env-file in runArgs → nothing to ensure.
        """
        try:
            run_args = json.loads(config.read_text()).get("runArgs", [])
        except (OSError, json.JSONDecodeError):
            return
        for flag, value in zip(run_args, run_args[1:]):
            if flag != "--env-file":
                continue
            env_file = Path(value.replace("${localEnv:HOME}", str(_home())))
            if "/.config/vk/secrets/" in str(env_file):
                _warn_legacy("secrets env-file mount", env_file)
            if not env_file.is_file():
                env_file.parent.mkdir(parents=True, exist_ok=True)
                env_file.write_text(f"# fr isolation secrets — {self.repo_root.name}\n")

    def _docker_ps(self, state: IsolationState) -> str:
        result = self.run(
            [
                "docker",
                "ps",
                "--all",
                f"--filter=label=devcontainer.local_folder={state.worktree}",
                "--format={{.ID}} {{.State}}",
            ]
        )
        return (result.stdout or "").strip()

    def _container_id(self, state: IsolationState) -> str | None:
        line = self._docker_ps(state)
        return line.split()[0] if line else None

    def _container_state(self, state: IsolationState) -> str | None:
        line = self._docker_ps(state)
        return line.split()[1] if line and len(line.split()) > 1 else None

    def _pr(self, state: IsolationState) -> dict[str, Any] | None:
        result = self.run(
            ["gh", "pr", "view", state.branch, "--json", "state,url"],
            cwd=self.repo_root,
        )
        if result.returncode != 0 or not (result.stdout or "").strip():
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
