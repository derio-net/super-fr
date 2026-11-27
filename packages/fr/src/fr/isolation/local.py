"""LocalWorktreeDevcontainerTarget — worktree + devcontainer over a Runner seam.

Every external call (git, devcontainer, docker, gh) goes through `runner` so
the lifecycle is unit-testable without Docker. The devcontainer CLI labels
containers with `devcontainer.local_folder=<workspace>`, which is how status
and down re-find the container.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from fr._hosts import detect_backend
from fr.artifacts.paths import KIND_DIRS, below
from fr.hostclient import FORGE_ERRORS, client_for
from fr.isolation import preserve as _preserve
from fr.isolation.branchrefs import (
    RemoteView,
    _forge_runner,
    _main_worktree_root,
    _short,
    _why,
    classify_branch,
    fetch_placement,
    network_env,
    resolve_branch_refs,
    run_network,
)
from fr.isolation.gc import GcSweeper
from fr.isolation.landing import branch_changes_present, recorded_start
from fr.isolation.preserve import TeardownReport
from fr.isolation.reap import (
    GcAction,
    ReapHazard,
    ReapRefused,
    _forge_refused,
    _hazard_detail,
)
from fr.isolation.runner import (
    GcSpawner,
    Runner,
    _home,
    _missing_binary,
    _noop_gc_spawn,
    devcontainer_id,
    subprocess_runner,
)
from fr.isolation.types import (
    IsolationError,
    IsolationState,
    _git_common_dir,
    carried_state,
    check_slug_free,
    default_worktree_path,
    delete_state,
    harden_secret_file,
    repo_cache_name,
    resolve_profile,
    save_state,
)
from fr.plan_validator_wrapper import REPAIR_COMMAND

# The one remedy every "no workspace" message offers (`--branch` is required).
_UP_REMEDY = "`fr isolation up --branch <branch>`"


# Files only fr's own tooling writes into a workspace, appended to the shared
# `info/exclude` on `up` so they never make a worktree dirty — which would make
# `down`'s reap-hazard check refuse at close-out. `devcontainer-lock.json` is
# what the devcontainer CLI writes beside each profile's config (gh#824);
# anchored, so a lock file the repo keeps elsewhere stays the repo's business.
_FR_OWNED_EXCLUDES = (".fr-isolation", "/.devcontainer/*/devcontainer-lock.json")


# A profile scaffolded before VK support was removed installs this package; its
# postCreateCommand would fail on every container start (spec 2026-11-14 R4,
# retiring the VK runner).
_VK_PROFILE_NEEDLE = "subdirectory=packages/fr-vk"


class StaleProfileError(IsolationError):
    """The profile itself is wrong, so no container was touched. Exec's resume
    and `rebuild` re-raise it as-is: their hints (rebuild recreates it, the old
    container may be gone) would mislead. `up` keeps its own wrapper (R4)."""


def _refuse_vk_profile(config: Path) -> None:
    """Refuse a devcontainer config that still installs fr-vk, before any
    container starts. A config that is absent or unreadable is `devcontainer
    up`'s to report."""
    try:
        text = config.read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return
    if _VK_PROFILE_NEEDLE in text:
        raise StaleProfileError(
            f"{config} installs fr-vk, but VK support was removed: delete the "
            f"`--with '…#{_VK_PROFILE_NEEDLE}'` segment from its postCreateCommand. "
            "Fix the profile on the default branch too, because every new branch "
            "is cut from it."
        )


class LocalWorktreeDevcontainerTarget:
    # The mode this class implements — pinned on the background gc it spawns
    # (gh#569). HostWorktreeTarget overrides it.
    _MODE: ClassVar[str] = "devcontainer"

    def __init__(
        self,
        repo_root: Path,
        runner: Runner = subprocess_runner,
        gc_spawner: GcSpawner = _noop_gc_spawn,
    ):
        # resolve() — the mount target must match the realpath git bakes
        # into the worktree's gitdir pointer (symlinked /tmp on macOS etc.).
        # Then normalize to the main toplevel so a worktree-launched run keys
        # off the durable main checkout (#292).
        self.repo_root = _main_worktree_root(Path(repo_root).resolve())
        self.run = runner
        self._gc_spawner = gc_spawner

    # ---------- lifecycle ----------

    def _worktree_up_core(self, branch: str, path: Path | None) -> Path:
        """Shared worktree prelude for the linked-worktree modes: the git-repo
        guard + the default worktree-path computation + parent mkdir. Extracted
        so `HostWorktreeTarget.up` reuses it verbatim instead of duplicating ~15
        lines (isolation host modes). Callers append their own mode-specific
        steps (profile/devcontainer for the local target; none for host)."""
        if not (self.repo_root / ".git").exists():
            raise IsolationError(
                f"{self.repo_root} is not a git repo — fr isolation only runs inside one."
            )
        # Before anything is created: another branch may hold this one's slug (gh#1419).
        check_slug_free(self.repo_root, branch)
        # Keyed on the MAIN checkout's basename (spec 2026-09-04 §5.C): an `up`
        # from inside a linked worktree files under the repo, never `agent-…`.
        worktree = path or default_worktree_path(self.repo_root, branch)
        worktree.parent.mkdir(parents=True, exist_ok=True)
        return worktree

    def up(
        self,
        profile: str | None,
        branch: str,
        path: Path | None = None,
        base: str | None = None,
        no_fetch: bool = False,
        stealth: Any = None,
    ) -> IsolationState:
        placement = self._fetch_placement(branch, no_fetch, stealth)
        worktree = self._worktree_up_core(branch, path)
        name = resolve_profile(self.repo_root, profile)
        base_sha = self._git_worktree_add(worktree, branch, base=base, no_fetch=no_fetch)

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
                    f"worktree can't see it — run `fr init scaffold --profile {name} --force` "
                    "(which commits; add `--tracking none` if the repo has no recognised "
                    f"remote) or commit .devcontainer/ yourself, then retry {_UP_REMEDY}."
                )
        # Record BEFORE the side effect that can fail (gh#578): a failing
        # postCreate used to leave a worktree and a container that neither
        # `status` nor `down` could address. With the record saved first, a
        # failed `up` is a listed workspace — retry `up`, or `down` it.
        state = carried_state(
            self.repo_root,
            branch,
            worktree,
            name,
            "devcontainer",
            base_sha=base_sha,
            placement=placement,
            tracking=stealth.text if stealth is not None else None,
        )
        save_state(state)
        self._write_isolation_marker(
            worktree,
            branch,
            created_at=state.created_at,
            placement=state.placement,
            tracking=self._tracking_entry(state),
        )
        try:
            self._devcontainer_up(worktree, name)
        except IsolationError as err:
            raise IsolationError(
                f"{err}\nThe workspace for {branch} is recorded: fix the cause and re-run "
                f"`fr isolation up --branch {branch}`, or remove it with "
                f"`fr isolation down --branch {branch}`."
            ) from err
        self._spawn_gc()
        return state

    @staticmethod
    def _config_path(worktree: Path, profile: str) -> Path:
        """The BRANCH's own profile config — `<worktree>/.devcontainer/<profile>/
        devcontainer.json`, never the base clone's."""
        return worktree / ".devcontainer" / profile / "devcontainer.json"

    def _devcontainer_argv(self, worktree: Path, profile: str, *sub: str) -> list[str]:
        """`devcontainer <sub…> --workspace-folder=<wt> --config=<cfg>`: the
        addressing every devcontainer call shares (up, exec, the ssh probe)."""
        return [
            "devcontainer",
            *sub,
            f"--workspace-folder={worktree}",
            f"--config={self._config_path(worktree, profile)}",
        ]

    def _devcontainer_up(
        self,
        worktree: Path,
        profile: str,
        *,
        remove_existing: bool = False,
        no_cache: bool = False,
    ) -> None:
        """The one `devcontainer up` — shared by `up`, `rebuild` and exec's
        resume, so the mount and config rules cannot drift between them."""
        _refuse_vk_profile(self._config_path(worktree, profile))
        self._ensure_mounted_env_file(self._config_path(worktree, profile))
        # Resolve the shared common dir, not <repo_root>/.git: correct even if
        # repo_root is a worktree (a gitfile), independent of normalization (#292).
        git_dir = _git_common_dir(self.repo_root)
        argv = [
            *self._devcontainer_argv(worktree, profile, "up"),
            f"--mount=type=bind,source={git_dir},target={git_dir}",
        ]
        if remove_existing:
            argv.append("--remove-existing-container")
        if no_cache:
            argv.append("--build-no-cache")
        try:
            result = self.run(argv, cwd=worktree)
        except FileNotFoundError as err:
            raise IsolationError(_missing_binary(err, "cannot run `devcontainer up`")) from err
        if result.returncode != 0:
            raise IsolationError(f"devcontainer up failed: {result.stderr or result.stdout}")
        probe = self.run(
            [*self._devcontainer_argv(worktree, profile, "exec"), "fr", "--version"],
            cwd=worktree,
        )
        if probe.returncode != 0:
            detail = (probe.stderr or probe.stdout or "fr is not executable").strip()
            raise IsolationError(
                "devcontainer is missing the required `fr` runtime: "
                f"`fr --version` failed: {detail}\n"
                f"Update {self._config_path(worktree, profile)} so postCreateCommand installs "
                "fr without suppressing failures, then run `fr isolation rebuild`."
            )

    def exec(self, state: IsolationState, argv: list[str]) -> int:
        """Run `argv` in the workspace's container, resuming a stopped one first
        (`_ensure_running`, spec §3.B). A missing binary is an IsolationError,
        never a traceback."""
        if not state.worktree.is_dir():
            raise IsolationError(
                f"worktree {state.worktree} for {state.branch} is gone — "
                f"run `fr isolation up --branch {state.branch}`."
            )
        self._ensure_running(state)
        try:
            result = self.run(
                [*self._devcontainer_argv(state.worktree, state.profile, "exec"), *argv],
                cwd=state.worktree,
                capture=False,
            )
        except FileNotFoundError as err:
            raise IsolationError(_missing_binary(err, f"cannot run in {state.branch}")) from err
        return result.returncode

    # Docker states `exec` runs in directly, and the ones it resumes with
    # `devcontainer up` (which re-runs postStartCommand; a bare `docker start`
    # would skip it).
    _RUNNING: ClassVar[frozenset[str]] = frozenset({"running", "restarting"})
    _RESUMABLE: ClassVar[frozenset[str]] = frozenset({"exited", "created"})

    def _ensure_running(self, state: IsolationState) -> None:
        """Bring the workspace's container to a state `devcontainer exec` can
        use, or raise (spec §3.B). A failed `docker ps` raises `docker is
        unreachable` via `_ps_pairs_strict` — never read as absence (#354).
        Absent or dead is never recreated silently: that is a build, not a
        resume, so the error names `rebuild`."""
        branch = state.branch
        rebuild = f"`fr isolation rebuild --branch {branch}` recreates it (worktree kept)."
        pairs = self._ps_pairs_strict(state)
        if any(current in self._RUNNING for _, current in pairs):
            return
        # Several containers can share the label: the first usable one wins,
        # a resumable one before a paused one; only none usable raises.
        resumable = next((cid for cid, cur in pairs if cur in self._RESUMABLE), None)
        paused = next((cid for cid, cur in pairs if cur == "paused"), None)
        if resumable is not None:
            print(
                f"isolation: container for {branch} was stopped — resuming (devcontainer up)",
                file=sys.stderr,
            )
            try:
                self._devcontainer_up(state.worktree, state.profile)
            except StaleProfileError:
                raise
            except IsolationError as err:
                # The hint leads: devcontainer's output is multi-line (p2-f6).
                raise IsolationError(
                    f"could not resume the container for {branch} — {rebuild}\n{err}"
                ) from err
            return
        if paused is not None:
            result = self.run(["docker", "unpause", paused])
            if result.returncode != 0:
                raise IsolationError(
                    f"could not unpause the container for {branch} ({paused}) — {rebuild}\n"
                    f"{(result.stderr or result.stdout or '').strip()}"
                )
            return
        if not pairs:
            raise IsolationError(f"no usable container for {branch} — {rebuild}")
        container, current = pairs[0]
        raise IsolationError(
            f"no usable container for {branch} ({container}, docker state {current}) — {rebuild}"
        )

    def rebuild(self, state: IsolationState, no_cache: bool = False) -> str:
        """Recreate the container against the existing worktree and the
        branch's own profile config (#577, spec §3.A). The state record,
        worktree, marker, bindings and run cursor are never touched.

        On success the old image is reclaimed if the rebuild changed it: the
        rebuild retags the same `vsc-…` name, so the old image becomes `<none>`
        and gc's `vsc-`-prefix sweep would never reach it. On failure nothing
        is reclaimed — `--remove-existing-container` may already have removed
        the old container, and the retry needs its image."""
        branch = state.branch
        if not state.worktree.is_dir():
            raise IsolationError(
                f"worktree {state.worktree} for {branch} is gone — there is nothing to "
                f"rebuild against; run `fr isolation up --branch {branch}`."
            )
        config = self._config_path(state.worktree, state.profile)
        before = self._ps_pairs_strict(state)
        old = before[0][0] if before else None
        old_image = self._image_for(old) if old else None
        try:
            self._devcontainer_up(
                state.worktree, state.profile, remove_existing=True, no_cache=no_cache
            )
        except StaleProfileError:
            raise
        except IsolationError as err:
            raise IsolationError(
                f"rebuild of {branch} failed: {err}\n"
                f"The old container ({old or 'none'}) may already have been removed; the "
                "worktree and run are intact. Fix the profile and retry with "
                f"`fr isolation rebuild --branch {branch}`."
            ) from err
        # The container WAS recreated: a failed re-query must not report the
        # rebuild as failed (p2-f1). Without the new id, skip the reclaim.
        new: str | None = None
        try:
            after = self._ps_pairs_strict(state)
        except IsolationError as err:
            print(
                f"warning: {branch} was rebuilt, but the new container could not be "
                f"queried ({err}); the old image was not reclaimed.",
                file=sys.stderr,
            )
        else:
            known = {cid for cid, _ in before}
            new = next((cid for cid, _ in after if cid not in known), None)
            if new is None and after:
                new = after[0][0]
        new_image = self._image_for(new) if new else None
        if old_image and new_image and new_image != old_image:
            self._reclaim_image(old_image)
        return (
            f"{branch} recreated ({old or 'none'} → {new or 'unknown'}) from {config}; "
            "worktree untouched"
        )

    def restart(self, state: IsolationState, force: bool = False) -> str:
        """Bounce the devcontainer without dropping the worktree (#341 Task 3).

        `docker restart` cycles only the process tree — the container filesystem
        and the bind-mounted worktree survive, so node_modules / local DB stacks
        / in-container installs are kept (unlike down+up). `force` uses
        `--time=0` (immediate SIGKILL then start) for a container too wedged to
        stop gracefully. Returns the restarted container id.
        """
        container, _ = self._require_container(state, "nothing to restart")
        argv = ["docker", "restart", *(["--time=0"] if force else []), container]
        result = self.run(argv)
        if result.returncode != 0:
            raise IsolationError(
                f"docker restart failed: {result.stderr or result.stdout}. If the container "
                "is too wedged to stop gracefully, retry with --force."
            )
        return container

    # Docker states in which the container's process tree is not running —
    # `stop` has nothing to do for these (#471).
    _NOT_RUNNING: ClassVar[frozenset[str]] = frozenset({"exited", "created", "dead"})

    def stop(self, state: IsolationState) -> str:
        """Halt the devcontainer, keeping the worktree, state, marker and
        bindings (#471, spec §3.B). `up`, `restart` or the next `exec` resumes it.

        The stop is verified by re-querying `docker ps --all`, never inferred
        from `docker stop`'s exit code; a query that FAILS is an error, never
        read as 'no container' (the #354 rule). An already-stopped container is
        a no-op success whose message says so."""
        container, current = self._require_container(state, "nothing to stop")
        if current == "dead":
            # Not resumable: `up`/`restart`/`exec` cannot bring a dead container
            # back, so do not promise they will (phase-1 review f4).
            return (
                f"{state.branch}'s container {container} is dead — "
                f"`fr isolation rebuild --branch {state.branch}` recreates it (worktree kept)."
            )
        if current in self._NOT_RUNNING:
            return f"{state.branch} already stopped ({container}, docker state {current})."
        result = self.run(["docker", "stop", container])
        if result.returncode != 0:
            raise IsolationError(
                f"docker stop failed for {state.branch} ({container}): "
                f"{(result.stderr or result.stdout or '').strip()}"
            )
        # Verify THIS container by id, not whatever line comes first: the label
        # filter can list several containers for one worktree (phase-1 review
        # f1). Absent from the re-query means it was removed (`--rm`) — stopped.
        after = dict(self._ps_pairs_strict(state)).get(container)
        if after is not None and after not in self._NOT_RUNNING:
            raise IsolationError(
                f"container {container} for {state.branch} is still running "
                f"(docker state {after}) after `docker stop`."
            )
        return (
            f"{state.branch} stopped ({container}) — worktree, state and bindings kept; "
            f"{_UP_REMEDY}, `restart` or the next `exec` resumes it."
        )

    def _ps_parts_strict(self, state: IsolationState) -> list[str]:
        """`[id, state]` of the first container from `docker ps --all`, `[]`
        when there is none. Raises like `_ps_pairs_strict`."""
        pairs = self._ps_pairs_strict(state)
        return list(pairs[0]) if pairs else []

    def _ps_pairs_strict(self, state: IsolationState) -> list[tuple[str, str]]:
        """Every `(id, state)` from `docker ps --all` for this worktree. Unlike
        `_docker_ps_line`, a failed query — or a missing docker binary — raises
        instead of reading as absence (#354)."""
        try:
            result = self._docker_ps(state)
        except FileNotFoundError as err:
            raise IsolationError(
                f"docker is unreachable — cannot query the container for {state.branch}."
            ) from err
        if result.returncode != 0:
            raise IsolationError(
                f"docker is unreachable — `docker ps` failed for {state.branch}: "
                f"{(result.stderr or result.stdout or '').strip()}"
            )
        pairs = []
        for line in (result.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 2:
                pairs.append((parts[0], parts[1]))
        return pairs

    def _require_container(self, state: IsolationState, nothing: str) -> tuple[str, str]:
        """The workspace's `(container id, docker state)`; raise with the `up`
        hint when there is none. Shared by `restart` and `stop`."""
        parts = self._ps_parts_strict(state)
        if not parts:
            raise IsolationError(
                f"no container for {state.branch} — {nothing} (run {_UP_REMEDY} first)."
            )
        return parts[0], parts[1]

    def stats(self, state: IsolationState) -> dict[str, str] | None:
        """Host-side `docker stats --no-stream` for a RUNNING container (#341
        Task 3B), so an agent can detect a thrashing container instead of
        inferring it from hung execs. Returns None (never raises) for a missing,
        non-running, or unreadable container — the caller renders `n/a`."""
        # One `docker ps` for both id and state (id state, space-joined).
        parts = self._docker_ps_line(state).split()
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
            "container": self._shown_container_state(state),
            "pr": self._status_pr(state),
        }

    def _status_pr(self, state: IsolationState) -> dict[str, Any] | None:
        """`status`'s PR column: a refused forge lookup is reported on stderr and
        shown as no PR, never a traceback over every row (review p2-r1)."""
        try:
            return self._pr(state)
        except IsolationError as exc:
            print(f"warning: {state.branch}: {exc}", file=sys.stderr)
            return None

    # Backend CLI name + PR/MR label for push_check's guidance line —
    # shares the gh/glab/tea vocabulary `fr._hosts.TAG_FOR_BACKEND` already
    # uses elsewhere, kept local (not imported) since that map's values are
    # the short issue-reference tags ("gh"/"gl"/"gt"), not the CLI binary names.
    _CLI_FOR_BACKEND: ClassVar[dict[str, str]] = {
        "github": "gh",
        "gitlab": "glab",
        "gitea": "tea",
    }
    _PR_LABEL: ClassVar[dict[str, str]] = {
        "github": "PR",
        "gitlab": "MR",
        "gitea": "PR",
    }

    def push_check(self, state: IsolationState) -> dict[str, Any]:
        """Read-only preflight diagnostic for #377: worktree remotes,
        whether an SSH agent socket is visible IN-CONTAINER (informational
        only — expected to be ABSENT, that is not a failure), and a
        backend-aware pointer at the correct host-side push workflow. Never
        prints key material, tokens, or ssh-agent socket contents/paths —
        presence/absence only (see `_ssh_agent_probe`)."""
        remote = self.run(["git", "-C", str(state.worktree), "remote", "-v"])
        remotes = [ln for ln in (remote.stdout or "").splitlines() if ln.strip()]
        backend = detect_backend(self.repo_root)
        cli = self._CLI_FOR_BACKEND.get(backend, "gh")
        pr_label = self._PR_LABEL.get(backend, "PR")
        guidance = (
            f"push and {cli} {pr_label} creation must run on the HOST from the worktree "
            f"(cd {state.worktree} && git push ...) — the container has no SSH agent "
            "or git-host credentials by design; see fr-isolation SKILL.md's "
            "Exec-bridge discipline."
        )
        return {
            "branch": state.branch,
            "remotes": remotes,
            "backend": backend,
            "ssh_agent_in_container": self._ssh_agent_probe(state),
            "guidance": guidance,
        }

    def _ssh_agent_probe(self, state: IsolationState) -> dict[str, Any]:
        """In-container SSH_AUTH_SOCK presence check ONLY — reports whether
        the env var is set and, if set, whether the socket path exists, never
        the path itself or any key material (no `ssh-add -l`, no reading the
        socket)."""
        probe_script = (
            'if [ -n "$SSH_AUTH_SOCK" ]; then '
            'if [ -S "$SSH_AUTH_SOCK" ]; then echo set:socket-exists; '
            "else echo set:socket-missing; fi; "
            "else echo unset; fi"
        )
        result = self.run(
            [
                *self._devcontainer_argv(state.worktree, state.profile, "exec"),
                "sh",
                "-c",
                probe_script,
            ],
            cwd=state.worktree,
        )
        detail = (result.stdout or "").strip() or "unknown"
        return {"present": detail.startswith("set:"), "detail": detail}

    def verify_merge(
        self,
        state: IsolationState,
        default_branch: str,
        remote: str = "origin",
    ) -> dict[str, Any]:
        """Confirm the branch's changes reached `<remote>/<default_branch>`.

        Squash/rebase/merge-safe (content-based, not ancestry). `verified`
        requires ALL FOUR positive confirmations — content present AND the PR
        is `MERGED` AND the `<remote>/<default_branch>` ref is fresh (fetch
        succeeded) AND the branch's own remote state is known
        (`branch_fetched`: fetched, or confirmed deleted by `ls-remote`). Every
        ref of the branch that resolves — the fetched `<remote>/<branch>` and
        the local branch — must have its changes on the base. The content check
        alone can be fooled by genuinely convergent content (the same fix
        landing twice), so the MERGED PR is the load-bearing tiebreak; an
        unknown PR state or a failed fetch is
        conservatively NOT verified, never a silent pass. The close-out (#320)
        STOPs (and the caller inspects which signal is missing) when not
        verified.

        The branch is checked at EVERY ref that resolves — `<remote>/<branch>`
        after a fresh fetch of it, and the local branch — so a stale local ref
        cannot decide alone and an unpushed local commit still refuses. Raises
        IsolationError naming the branch when neither resolves.
        """
        refs, branch_fetched = self._branch_refs(state.branch, remote)
        return self._verdict(
            state.worktree,
            state.branch,
            default_branch,
            remote,
            pr=self._pr(state),
            refs=refs,
            branch_fetched=branch_fetched,
            start=state.base_sha,
        )

    def verify_merge_reaped(
        self,
        branch: str,
        default_branch: str,
        remote: str = "origin",
    ) -> dict[str, Any]:
        """`verify_merge` for a branch whose workspace gc already reaped.

        No state file and no worktree, so the same fetch + content check +
        PR-state verdict runs from the repo root, against EVERY ref of the
        branch that still resolves — `<remote>/<branch>` after a fresh fetch of
        it, and the local branch gc keeps. Each must have its changes on the
        base: a post-merge push from another clone lives only on the remote
        ref, an unpushed commit only on the local one, and either is work that
        did not land (adversarial review M1). Raises IsolationError naming the
        ref when neither resolves. `verified` still needs all four signals."""
        refs, branch_fetched = self._branch_refs(branch, remote)
        pr = self._pr_from(self.repo_root, branch)
        res = self._verdict(
            self.repo_root,
            branch,
            default_branch,
            remote,
            pr=pr,
            refs=refs,
            branch_fetched=branch_fetched,
            start=recorded_start(self.repo_root, branch),
        )
        res["reaped"] = True
        return res

    def _branch_refs(self, branch: str, remote: str) -> tuple[list[str], bool]:
        """`resolve_branch_refs`, raising IsolationError when neither ref
        resolves (verify-merge has nothing to check)."""
        refs, branch_fetched = resolve_branch_refs(self.run, self.repo_root, branch, remote)
        if not refs:
            raise IsolationError(
                f"cannot resolve branch ref {branch!r} (neither local nor {remote}/{branch})."
            )
        return refs, branch_fetched

    def _verdict(
        self,
        cwd: Path,
        branch: str,
        default_branch: str,
        remote: str,
        pr: dict[str, Any] | None,
        refs: list[str] | None = None,
        *,
        branch_fetched: bool,
        start: str | None = None,
    ) -> dict[str, Any]:
        base_ref = f"{remote}/{default_branch}"
        fetch = self._run_network(["git", "fetch", remote, default_branch], cwd=cwd)
        fetched = fetch.returncode == 0
        results = [
            branch_changes_present(self.run, cwd, r, base_ref, start) for r in refs or [branch]
        ]
        missing = sorted({m for r in results for m in r.missing})
        changes_present = all(r.changes_present for r in results)
        pr_state = pr.get("state") if pr else None
        # `branch_fetched` (C2 review, #665/#598): a failed branch fetch whose
        # remote state is unknown (not confirmed gone via ls-remote) must not
        # let a possibly-stale ref decide `verified`.
        verified = changes_present and pr_state == "MERGED" and fetched and branch_fetched
        return {
            "branch": branch,
            "verified": verified,
            "changes_present": changes_present,
            "missing": missing,
            "pr_state": pr_state,
            "fetched": fetched,
            "branch_fetched": branch_fetched,
        }

    def _reap_hazard(self, state: IsolationState) -> ReapHazard | None:
        """PURE QUERY — runs no destructive command — so `gc --dry-run` (phase 3)
        can ask exactly the question the live reap path enforces, instead of
        predicting a different answer. `git fetch` is the one exception to
        "no command that writes": it only advances remote-tracking refs, never
        a workspace, branch, or working tree (spec §3.4).

        The exits are ordered LOCAL-FIRST, NETWORK-SECOND, and the ordering is
        load-bearing, not incidental: the free local check must short-circuit
        before any candidate pays for a fetch.

        1. Worktree directory already gone (removed out-of-band) → None, not a
           hazard — the `_down_worktree_tail` post-condition check further down
           treats that as already-torn-down. Nothing left to query, nothing
           left to lose.
        2. DIRTY WORKTREE (#435, phase 1): `git status --porcelain` in
           `state.worktree`. Non-empty output is a hazard — tracked AND
           untracked alike (decision d1: #435's own lost work was a newly
           authored, therefore untracked, file). A NON-ZERO return code is
           also a hazard (`kind="unverifiable"`) rather than being read as
           clean — the #354 invariant ("a failed query is not evidence of
           absence") applied to the working tree. Ignored paths (`.venv/`,
           `.fr-isolation`, `__pycache__/`) never appear in `--porcelain`, so
           routine workspace clutter cannot wedge the guard.
        3. UNLANDED CONTENT (#467, phase 2): the worktree is clean, but the
           branch may hold content that never reached `origin/<default>` — a
           local-only commit, or one pushed to the branch after its PR merged
           (the #320 orphan, caught for free). Fetches `origin/<default>`
           first (a stale local ref would misread a genuinely-merged workspace
           as unlanded), then compares content with `branch_changes_present`.
           A failed fetch is `kind="unverifiable"`, the same #354 invariant
           applied to the network call: offline defers a reap, never permits a
           wrong one.
        """
        if not state.worktree.is_dir():
            return None
        # DRIFTED CHECKOUT (gh#553): every later check speaks for
        # `state.branch`, but the worktree may have another branch checked
        # out (a `git checkout -b` inside the workspace). That branch's
        # commits are checked by nothing below, so refuse rather than reap
        # on the registered branch's verdict. A detached HEAD (mid-rebase,
        # bisect) is not a different branch and falls through.
        head = self.run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=state.worktree)
        checked_out = (head.stdout or "").strip() if head.returncode == 0 else ""
        if checked_out and checked_out != state.branch:
            return ReapHazard(
                kind="drifted-checkout",
                detail=_hazard_detail(
                    state.branch,
                    f"has {checked_out} checked out, not the branch fr registered",
                    [],
                    f"Switch back with `git switch {state.branch}`; to keep working on "
                    f"{checked_out}, then give it its own workspace with "
                    f"`fr isolation up --branch {checked_out}`.",
                ),
            )
        status = self.run(["git", "status", "--porcelain"], cwd=state.worktree)
        if status.returncode != 0:
            return ReapHazard(
                kind="unverifiable",
                detail=_hazard_detail(
                    state.branch,
                    "could not be checked for uncommitted changes (git status failed)",
                    [],
                    "Fix the worktree so `git status` runs there, then re-run `fr isolation down`.",
                ),
            )
        paths = [line[3:] for line in (status.stdout or "").splitlines() if line.strip()]
        if paths:
            return ReapHazard(
                kind="dirty-worktree",
                detail=_hazard_detail(
                    state.branch,
                    f"has {len(paths)} uncommitted change(s)",
                    paths,
                    "Commit or stash them.",
                ),
            )

        # Phase 2 (#467): the worktree is clean, but the BRANCH may still hold
        # content that never reached origin/<default> — a local-only commit,
        # or one pushed to the branch after its PR merged (the #320 orphan).
        # Fetch first, using the RESOLVED default branch (never the literal
        # "main" `verify_merge` defaults to — that default is a latent bug for
        # a repo on master) — a stale local origin/<default> would read every
        # genuinely-merged workspace as unlanded (spec §3.4). A failed fetch is
        # itself a hazard, not a pass: the #354 invariant ("a failed query is
        # not evidence of absence") applied to the network call — offline
        # defers a reap, it never permits a wrong one.
        # A repo with NO `origin` remote at all is a different thing from a
        # fetch that failed, and conflating them made `down` unusable there
        # (phase-2 review f3). There is no remote for the branch to be behind,
        # so the content question is unanswerable AND meaningless; and nothing
        # unrecoverable is at stake, because `git worktree remove` leaves the
        # branch and its commits in the repo (phase-1 review f2) while guard 2
        # above still covers the uncommitted work that genuinely has no object.
        # Refusing here would mean a local-only repo could only ever be reaped
        # with --force — the one lever an agent may not reach for on its own
        # (decision d3). Local check, no network.
        if self.run(["git", "remote", "get-url", "origin"], cwd=state.worktree).returncode != 0:
            return None
        default = self._resolve_default_branch()
        fetch = self._run_network(["git", "fetch", "origin", default], cwd=state.worktree)
        if fetch.returncode != 0:
            return ReapHazard(
                kind="unverifiable",
                detail=_hazard_detail(
                    state.branch,
                    f"could not be checked against origin/{default} (git fetch failed)",
                    [],
                    "Check connectivity to origin (or that the remote still exists), "
                    "then re-run `fr isolation down`.",
                ),
            )
        # Deliberately NOT `self.verify_merge(state)` — the tempting reuse and
        # the wrong one (spec §3.3). verify_merge is fetch + branch_changes_present
        # + `self._pr(state)`, and that third call shells out to gh/glab/tea; gc
        # has already made exactly that call one line earlier (`_gc_one`) to
        # classify the workspace, so reusing verify_merge would buy a SECOND
        # host-CLI round trip per reap candidate on a host-wide sweep, only to
        # recompute a PR state the caller is already holding — and then discard
        # `verified`, which the PR-less merged-by-content path can never
        # satisfy anyway. Do the two steps this guard actually needs directly.
        # TOTAL, never raising (phase-2 review f4): `branch_changes_present`
        # raises IsolationError when `git merge-base` fails (unrelated
        # histories, a base ref that vanished between the fetch and here).
        # A guard that raises is worse than one that refuses — `_gc_one`'s
        # `if dry_run:` arms sit OUTSIDE their `try`, so an exception escaping
        # here aborts the whole host-wide sweep, breaking gc's documented
        # "one failed workspace never aborts the sweep" invariant. Unknown
        # state is not "safe to reap"; it is `unverifiable`, which phase 3
        # classifies as a skip. Mirrors `_merged_by_content`'s own
        # `except Exception: return False`.
        try:
            result = branch_changes_present(
                self.run, state.worktree, state.branch, f"origin/{default}", state.base_sha
            )
        except Exception as e:
            return ReapHazard(
                kind="unverifiable",
                detail=_hazard_detail(
                    state.branch,
                    f"could not be compared with origin/{default} ({e})",
                    [],
                    "Check that the branch and origin/"
                    f"{default} share history, then re-run `fr isolation down`.",
                ),
            )
        if result.missing:
            return ReapHazard(
                kind="unlanded-content",
                detail=_hazard_detail(
                    state.branch,
                    f"has {len(result.missing)} changed file(s) that are not on origin/{default}",
                    result.missing,
                    "Push the branch.",
                ),
            )
        return None

    def down(
        self, state: IsolationState, force: bool = False, preserve: bool = True
    ) -> TeardownReport:
        """Tear down the workspace, verifying each destructive step's
        POST-CONDITION before deleting the bookkeeping (#354 Task A).

        Historically `down` ran `docker stop`/`rm` and `git worktree remove`
        with their return codes ignored, then `delete_state()` unconditionally —
        so a transient docker hiccup left a running container that `fr isolation
        status` could no longer see (state gone). Now: re-query the container /
        worktree AFTER the teardown call and, if it survived, raise
        `IsolationError` while LEAVING the state file + `.fr-isolation` marker in
        place, so the workspace stays visible and a retry (or `--force`, for a
        refused-guard case) can finish the job.

        Re-query — not the return code — is authoritative: `docker rm` on an
        already-gone container returns non-zero while the post-condition (gone)
        holds, and a `rm` can return 0 yet leave a wedged container. `--force`
        bypasses all three refusal guards — the open-PR check AND the
        reap-hazard guard (#467 phase 3: dirty worktree, unlanded content,
        unverifiable) — but it never skips THIS verification (that would
        re-introduce the invisible-leak bug).

        Before destroying anything it preserves fr's own records under
        `docs/superpowers/` (#575, spec §3.D) — `preserve=False` discards them,
        and is accepted only together with `force`. Returns what it ended.
        """
        report = self._down_worktree_tail(state, force, preserve=preserve)
        self._spawn_gc()
        return report

    def _open_pr_refusal(self, state: IsolationState) -> str | None:
        """The open-PR guard's refusal text, or None when no PR is open."""
        pr = self._pr(state)
        if pr and pr.get("state") == "OPEN":
            return (
                f"PR for {state.branch} is still open ({pr.get('url', '?')}) — "
                "the operator may push to it. Re-run with --force to tear down anyway."
            )
        return None

    def down_refusal(self, state: IsolationState) -> str | None:
        """PURE QUERY (#533): the reason a non-forced `down` would refuse this
        workspace, or None if it would proceed. Asks the SAME two guards, in
        the same order, that `_down_worktree_tail` enforces — so `down --all`'s
        blast-radius listing predicts rather than guesses — including the
        `isolation: <b> holds active run <id> …` prefix (#575, spec §3.D.1)."""
        runs = _preserve.branch_runs(state.worktree, state.branch)
        open_pr = self._open_pr_refusal(state)
        if open_pr is not None:
            return _preserve.name_runs(runs, open_pr, state.branch)
        hazard = self._reap_hazard(state)
        return (
            _preserve.name_runs(runs, hazard.detail, state.branch) if hazard is not None else None
        )

    def held_runs(self, state: IsolationState) -> str:
        """PURE QUERY: the `holds run <id> at step <cursor>` line(s) for the
        branch's active runs ('' when none) — `down --all` shows it for every
        workspace, even under `--force`, where no refusal carries it."""
        return _preserve.runs_line(_preserve.branch_runs(state.worktree, state.branch))

    def _down_worktree_tail(
        self, state: IsolationState, force: bool, preserve: bool = True
    ) -> TeardownReport:
        """PR guard → reap-hazard guard → STAGE fr's records → environment
        teardown → verified worktree removal → COMMIT the tombstone → marker +
        state retirement. Shared with `HostWorktreeTarget` (#... isolation host
        modes): the ONLY per-mode difference is `_teardown_container`, which the
        host-worktree mode overrides to a no-op (no docker), so both guards, the
        post-condition verification, and the marker/state cleanup stay identical
        across modes.

        #575 (spec §3.D): the branch's runs are computed ONCE and name every
        refusal. Preservation is two-phase — staged after the guards (a copy
        failure raises here, with the workspace intact), committed only after
        the removal is verified — and keyed on `state.repo_root`, so gc's
        host-wide sweep files each record under the workspace's own repo."""
        if not preserve and not force:
            raise IsolationError(
                "--no-preserve is only valid with --force — it discards fr's records "
                f"under {KIND_DIRS['superpowers']}/, an explicit per-call decision."
            )
        runs = _preserve.branch_runs(state.worktree, state.branch)
        open_pr = self._open_pr_refusal(state)
        if open_pr is not None and not force:
            raise IsolationError(_preserve.name_runs(runs, open_pr, state.branch))
        if not force:
            hazard = self._reap_hazard(state)
            if hazard is not None:
                raise ReapRefused(
                    ReapHazard(hazard.kind, _preserve.name_runs(runs, hazard.detail, state.branch))
                )
        record = _preserve.stage(state, self.run, runs=runs) if preserve else None
        self._teardown_container(state)
        if record is not None:
            # From here staging/ may be the only copy: protect it (p4-f2).
            _preserve.mark_removal_attempted(record)
        wt = self.run(
            ["git", "worktree", "remove", "--force", str(state.worktree)],
            cwd=self.repo_root,
        )
        if wt.returncode != 0 and state.worktree.exists():
            raise IsolationError(
                f"git worktree remove failed for {state.worktree}: "
                f"{wt.stderr or wt.stdout} — state left intact; retry `fr isolation down`."
            )
        # Marker removal is LAST: a raise above leaves the marker inside the
        # still-present worktree, so the workspace stays a valid isolation
        # workspace. When the worktree is gone the marker went with it — the
        # unlink is then an idempotent no-op.
        preserved: Path | None = None
        reason: str | None = None if preserve else _preserve.NO_PRESERVE
        if record is not None:
            try:
                preserved = _preserve.commit(record, forced=force, run=self.run)
            except Exception as e:
                # The worktree is already gone: failing now would strand the
                # state record of a workspace that no longer exists. The
                # staged copies are protected (removal_attempted) and the next
                # down merges them; the report says where they are (p4-f4).
                reason = (
                    f"could not record the teardown ({e}); the staged copies are at "
                    f"{record.staging}"
                )
        self._remove_isolation_marker(state.worktree)
        delete_state(state.repo_root, state.branch)
        # A retry's record carries the first attempt's runs too (p4-f2).
        ended = record.runs if record is not None else runs
        return TeardownReport(
            branch=state.branch,
            preserved_dir=preserved,
            ended_runs=[(r.id, r.cursor) for r in ended if r.active],
            reason=reason,
            preserved_files=len(record.files) if record is not None and preserved else 0,
            skipped=list(record.skipped) if record is not None else [],
            unpreserved_runs=record.unpreserved_runs() if record is not None else [],
        )

    def _teardown_container(self, state: IsolationState) -> None:
        """Stop + rm the devcontainer and reclaim its image, verifying the
        post-condition. Overridden to a no-op by docker-less modes."""
        # A FAILED `docker ps` (daemon unreachable) must NOT be read as "no
        # container" — that path would `delete_state()` while a container may
        # still be running once the daemon recovers, the exact #354 leak. So the
        # probe raises on query failure, only a successful-but-empty result means
        # "genuinely absent".
        probe = self._docker_ps(state)
        if probe.returncode != 0:
            raise IsolationError(
                f"docker ps failed while tearing down {state.branch} "
                f"({(probe.stderr or probe.stdout or '').strip()}) — cannot verify teardown; "
                "state left intact, retry `fr isolation down` once docker recovers."
            )
        line = (probe.stdout or "").strip()
        container = line.split()[0] if line else None
        # Capture the image id BEFORE `docker rm` (the container must still exist
        # to inspect it); reclaim it AFTER the container is confirmed gone.
        image = self._image_for(container) if container else None
        volumes = self._workspace_volumes(container) if container else []
        if container:
            self.run(["docker", "stop", container])
            self.run(["docker", "rm", container])
            verify = self._docker_ps(state)
            if verify.returncode != 0 or (verify.stdout or "").strip():
                raise IsolationError(
                    f"container for {state.branch} still present (or unverifiable) after "
                    "docker stop/rm — workspace left intact (still visible to `fr isolation "
                    "status`); retry `fr isolation down` once docker recovers."
                )
            self._reclaim_image(image)
            self._reclaim_volumes(volumes)

    def _spawn_gc(self) -> None:
        """Fire the opportunistic background sweep — best-effort, never raises
        into up()/down().

        Every spawner is handed this target's mode (gh#569), so the background
        sweep runs in the mode of the workspace that fired it."""
        try:
            self._gc_spawner(self.repo_root, self._MODE)
        except Exception:
            pass

    # ---------- gc: host-wide reconciliation (#354 Task B) ----------

    def gc(self, dry_run: bool = False) -> list[GcAction]:
        """Reconcile every isolation workspace on the host: tear down the ones
        whose PR merged, leave open-PR and no-PR work alone, and reap orphaned
        containers. Host-wide (an `up` in repo A reaps completed work in B…F),
        so end-to-end workflows no longer depend on a human remembering to run
        `down` in the originating session.

        Classification is authoritative BEFORE any action — a blind `down()`
        would reap in-progress no-PR work (its guard only blocks OPEN PRs). Each
        workspace is handled in isolation: one failed teardown is recorded and
        the sweep continues.

        A host-wide flock serializes concurrent sweeps (two near-simultaneous
        up/down each fork a gc): the second gets `EWOULDBLOCK` and short-circuits
        to an empty report. The sweep is idempotent, so a skipped overlap is
        harmless — the next up/down re-runs it.
        """
        return GcSweeper(self).gc(dry_run)

    def _stale_state_reapable(self) -> bool:
        """May a state record whose worktree is gone be retired right now?

        Only when the container view is TRUSTWORTHY: a healthy `docker ps`
        (returncode 0) means `_labelled_containers()` genuinely saw every
        container, so a record with none really is stale. A broken or absent
        daemon defers the reap to a later sweep rather than dropping the state
        file that is the only pointer to a container that may still be running
        (#354). Docker-less modes override this to an unconditional True — they
        have no containers by construction.
        """
        try:
            return self.run(["docker", "ps", "-q"]).returncode == 0
        except Exception:
            return False

    def _labelled_containers(self) -> list[tuple[str, Path]]:
        result = self.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "label=devcontainer.local_folder",
                "--format",
                '{{.ID}}\t{{.Label "devcontainer.local_folder"}}',
            ]
        )
        out: list[tuple[str, Path]] = []
        for line in (result.stdout or "").splitlines():
            parts = line.split("\t")
            if len(parts) == 2 and parts[0] and parts[1]:
                out.append((parts[0], Path(parts[1])))
        return out

    def _label_reap(self, container_id: str) -> None:
        """Reap a container found only by docker label (worktree already gone):
        stop + rm + best-effort image rmi."""
        image = self._image_for(container_id)
        volumes = self._workspace_volumes(container_id)
        self.run(["docker", "stop", container_id])
        self.run(["docker", "rm", container_id])
        self._reclaim_image(image)
        self._reclaim_volumes(volumes)

    def _sweep_dangling_images(self, dry_run: bool) -> list[GcAction]:
        """rmi `vsc-*` devcontainer images no live container references — the
        ~1 GB layers that accumulate as workspaces come and go (#354). Each rmi
        is best-effort: a still-referenced image failing is recorded, never
        raised."""
        referenced = self._referenced_images()
        out: list[GcAction] = []
        for image_id, repo, tag in self._vsc_images():
            ref = f"{repo}:{tag}"
            if image_id in referenced or repo in referenced or ref in referenced:
                continue
            if dry_run:
                out.append(GcAction(repo, None, "dangling-image", "would-reap", image_id))
                continue
            # Reap by the TAGGED ref, not the image id: a dangling image carrying
            # more than one tag makes `docker rmi <id>` fail ("referenced in
            # multiple repositories"). Removing each `repo:tag` untags cleanly and
            # frees the layers on the last tag — no --force, no multi-tag conflict.
            r = self.run(["docker", "rmi", ref])
            out.append(
                GcAction(
                    repo,
                    None,
                    "dangling-image",
                    "reaped" if r.returncode == 0 else "reap-failed",
                    image_id,
                )
            )
        return out

    def _vsc_images(self) -> list[tuple[str, str, str]]:
        result = self.run(["docker", "images", "--format", "{{.ID}}\t{{.Repository}}\t{{.Tag}}"])
        out: list[tuple[str, str, str]] = []
        for line in (result.stdout or "").splitlines():
            parts = line.split("\t")
            if len(parts) == 3 and parts[1].startswith("vsc-"):
                out.append((parts[0], parts[1], parts[2]))
        return out

    def _referenced_images(self) -> set[str]:
        result = self.run(["docker", "ps", "-a", "--format", "{{.Image}}"])
        return {ln.strip() for ln in (result.stdout or "").splitlines() if ln.strip()}

    # ---------- helpers ----------

    def _ensure_validator_wrapper_in_ref(self, ref: str) -> None:
        """Plan repos need the wrapper in the ref used for worktree add.

        `fr isolation up --branch <branch>` creates/reuses a linked worktree from git state, not
        the base checkout's uncommitted files. A filesystem-only wrapper check
        would let an untracked wrapper pass, then the isolated worktree would
        still lack the validator entry point.
        """
        plans = self.run(
            ["git", "ls-tree", ref, "--", KIND_DIRS["plan"]],
            cwd=self.repo_root,
        )
        if plans.returncode != 0 or not plans.stdout.strip():
            return
        result = self.run(
            ["git", "ls-tree", ref, "--", "scripts/validate-plans.sh"],
            cwd=self.repo_root,
        )
        line = result.stdout.strip()
        if result.returncode != 0 or not line:
            raise IsolationError(
                f"plan repo has {KIND_DIRS['plan']} in {ref} but no "
                f"scripts/validate-plans.sh there; run `{REPAIR_COMMAND}` from the repo "
                f"root, commit it to the isolation start ref, then retry {_UP_REMEDY}."
            )
        mode = line.split(maxsplit=1)[0]
        if mode != "100755":
            raise IsolationError(
                f"plan repo has scripts/validate-plans.sh in {ref} but it is not executable; "
                "run `chmod +x scripts/validate-plans.sh`, commit it to the isolation "
                f"start ref, then retry {_UP_REMEDY}."
            )

    def _ensure_validator_wrapper_in_worktree(self, worktree: Path) -> None:
        # The wrapper is owed by a product branch that holds plans. Under quiet or stealth
        # the plans live on `fr` or in the tracking repo (review p4-r4), so only plans in
        # the product tree itself count, as in `_ensure_validator_wrapper_in_ref`.
        plans = below(worktree, "plan")  # the product checkout's own tree
        if not plans.is_dir():
            return
        wrapper = worktree / "scripts" / "validate-plans.sh"
        if not wrapper.is_file() or not (wrapper.stat().st_mode & 0o111):
            raise IsolationError(
                f"existing isolation worktree {worktree} is missing executable "
                f"scripts/validate-plans.sh; run `{REPAIR_COMMAND}`, commit it on the worktree "
                f"branch, then retry {_UP_REMEDY}."
            )

    def _git_worktree_add(
        self, worktree: Path, branch: str, base: str | None = None, no_fetch: bool = False
    ) -> str | None:
        """Provision `worktree` on `branch`; the commit a NEW branch was cut
        from, or None when the branch or worktree already existed (gh#768)."""
        if worktree.exists():
            self._ensure_validator_wrapper_in_worktree(worktree)
            return None  # already provisioned — up() is idempotent on the worktree
        # Classify <B> against origin/<B> (#438, spec §3.E). The probe runs
        # for the local rows too, best-effort: an unknown origin never blocks
        # a reuse, and a local branch is never fetched into or rebased (#322
        # corner 1) — only the remote-tracking ref moves.
        local_sha = self._rev(f"refs/heads/{branch}")
        remote = self._remote_view(branch, no_fetch)
        decision = classify_branch(
            branch,
            local_sha=local_sha,
            remote=remote,
            relation=self._relation(local_sha, remote.sha),
            base=base,
            worktree=worktree,
        )
        # stderr, always: `--print-path` and `fr run start` own stdout (§3.C).
        for line in decision.lines:
            print(line, file=sys.stderr)
        track = False
        start_sha: str | None = None
        if decision.action == "local":
            checkout = branch
            argv = ["git", "worktree", "add", str(worktree), branch]
        elif decision.action == "remote":
            checkout = f"origin/{branch}"
            # --no-track + explicit upstream config: git's --track refuses a
            # remote-tracking ref no fetch refspec maps (a --single-branch or
            # narrow-refspec clone — exactly where pods and CI live).
            argv = ["git", "worktree", "add", "--no-track", "-b", branch, str(worktree), checkout]
            track = True
        else:
            # Genuine cold-start: a brand-new branch. Default to freshly-fetched
            # origin/<default> instead of the base repo's current HEAD (#322).
            # An unknown probe already failed to reach origin: no second fetch.
            start_point, log_line = self._cold_start_base(
                branch, base, no_fetch, origin_reachable=remote.state != "unknown"
            )
            checkout = start_point or "HEAD"
            sha = start_sha = self._rev(checkout)
            print(f"{log_line} ({_short(sha)})" if sha else log_line, file=sys.stderr)
            argv = ["git", "worktree", "add", str(worktree), "-b", branch]
            if start_point is not None:
                argv.append(start_point)
        self._ensure_validator_wrapper_in_ref(checkout)
        result = self.run(argv, cwd=self.repo_root)
        if result.returncode != 0:
            raise IsolationError(f"git worktree add failed: {result.stderr}")
        if track:
            self._set_upstream(branch)
        # #575 (spec §3.D.4): only a worktree this call CREATED gets the
        # branch's preserved records back — a reuse returned above. A restore
        # problem never fails the `up`: the worktree is already correct.
        # A cold start is a NEW branch that merely reuses the name: its restore
        # only points at the old records, never applies them (p4-f5).
        try:
            _preserve.restore(
                self.repo_root,
                branch,
                worktree,
                self.run,
                new_branch=decision.action not in ("local", "remote"),
            )
        except Exception as e:
            print(
                f"WARNING: could not restore {branch}'s preserved records ({e}) — they stay "
                f"at {_preserve.preserved_dir(self.repo_root, branch)}",
                file=sys.stderr,
            )
        return start_sha

    def _set_upstream(self, branch: str) -> None:
        """branch.<B>.{remote,merge} — what --track would have written. A
        failure is reported, never fatal: the worktree is already correct."""
        for key, value in (("remote", "origin"), ("merge", f"refs/heads/{branch}")):
            res = self.run(["git", "config", f"branch.{branch}.{key}", value], cwd=self.repo_root)
            if res.returncode != 0:
                print(
                    f"WARNING: could not set {branch}'s upstream to origin/{branch} "
                    f"({_why('git config', res)}) — set branch.{branch}.remote=origin and "
                    f"branch.{branch}.merge=refs/heads/{branch} yourself",
                    file=sys.stderr,
                )
                return

    def _rev(self, ref: str) -> str | None:
        """The commit `ref` names, or None when it names none."""
        result = self.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=self.repo_root
        )
        sha = (result.stdout or "").strip()
        return sha if result.returncode == 0 and sha else None

    def _network_env(self) -> dict[str, str]:
        return network_env(self.run, self.repo_root)

    def _run_network(
        self, argv: list[str], cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        """A bounded, non-interactive git call against origin. A timeout comes
        back as a non-zero, non-2 exit — `unknown`, never `absent`."""
        return run_network(self.run, self.repo_root, argv, cwd=cwd)

    def _fetch_placement(self, branch: str, no_fetch: bool, stealth: Any = None) -> str:
        """R23 "the switch": fetch `origin/fr` (absent is fine) and return the placement
        it names, refusing an unreachable origin before anything is provisioned; under
        quiet, also refuse a branch whose feature id another branch holds (gh#1419).
        With *stealth*, R24's checks instead (`fetch_placement`)."""
        return fetch_placement(
            self.repo_root, branch, no_fetch, lambda argv: self._run_network(argv), stealth
        )

    def _tracking_entry(self, state: IsolationState) -> dict[str, str] | None:
        """The marker's `tracking` record under stealth (R24 "the local record")."""
        if state.placement != "stealth" or state.tracking is None:
            return None
        from fr.placement.stealth import marker_entry, parse_ref, target_dir

        return marker_entry(parse_ref(state.tracking), target_dir(self.repo_root))

    def _remote_view(self, branch: str, no_fetch: bool) -> RemoteView:
        """Probe `origin/<B>`: `ls-remote --exit-code` (0 exists, 2 absent,
        anything else unknown — never absence, #354), then an explicit-refspec
        fetch so `origin/<B>` updates even in a --single-branch clone."""
        tracking = f"refs/remotes/origin/{branch}"
        if not self._has_origin_remote():
            return RemoteView("absent", None, "no origin remote")
        if no_fetch:
            sha = self._rev(tracking)
            return RemoteView("exists", sha) if sha else RemoteView("unchecked", None, "--no-fetch")
        probe = self._run_network(
            ["git", "ls-remote", "--exit-code", "origin", f"refs/heads/{branch}"]
        )
        if probe.returncode == 2:
            return RemoteView("absent")
        if probe.returncode != 0:
            return RemoteView("unknown", self._rev(tracking), _why("git ls-remote", probe))
        fetch = self._run_network(["git", "fetch", "origin", f"+refs/heads/{branch}:{tracking}"])
        sha = self._rev(tracking)
        if fetch.returncode != 0:
            return RemoteView("unfetched", sha, _why("git fetch", fetch))
        if sha is None:
            return RemoteView("unfetched", None, f"no origin/{branch} after the fetch")
        return RemoteView("exists", sha)

    def _relation(self, local_sha: str | None, remote_sha: str | None) -> tuple[int, int] | None:
        """(ahead, behind) of local `<B>` against `origin/<B>`; None when
        either is missing, they agree, or git cannot count."""
        if local_sha is None or remote_sha is None or local_sha == remote_sha:
            return None
        result = self.run(
            ["git", "rev-list", "--left-right", "--count", f"{local_sha}...{remote_sha}"],
            cwd=self.repo_root,
        )
        parts = (result.stdout or "").split()
        if result.returncode != 0 or len(parts) != 2 or not all(p.isdigit() for p in parts):
            return None
        return int(parts[0]), int(parts[1])

    # ----- .fr-isolation marker lifecycle (#328 Task 3) -----

    def _write_isolation_marker(
        self,
        worktree: Path,
        branch: str,
        mode: str = "worktree",
        created_at: str | None = None,
        target: str = "devcontainer",
        placement: str | None = None,
        tracking: dict[str, str] | None = None,
    ) -> None:
        """Write the `.fr-isolation` identity marker and git-exclude it.

        `target` (`devcontainer | worktree`) records which isolation `up`
        chose, beside the unchanged `mode` the edit gate reads: both targets
        write `mode: worktree`, and only `target` tells `fr run`'s host-side
        check a devcontainer from a host-worktree pod (spec
        2026-09-25-lean-cost-aware-process §5.B.6, p2-r20).

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
                    "target": target,
                    # the state record's own created_at, so an `up` that
                    # carries the record forward does not restamp the marker
                    "created_at": created_at or datetime.now(UTC).isoformat(),
                    # R23 "sticky": the placement `up` found; `space_for` refuses a
                    # later switch that disagrees. Omitted only by a caller with none.
                    **({"placement": placement} if placement is not None else {}),
                    # R24 "the local record": under stealth, the tracking ref and the
                    # target's directory in the tracking worktree.
                    **({"tracking": tracking} if tracking is not None else {}),
                },
                indent=2,
            )
            + "\n"
        )
        exclude = _git_common_dir(self.repo_root) / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        text = exclude.read_text() if exclude.is_file() else ""
        missing = [p for p in _FR_OWNED_EXCLUDES if p not in text.splitlines()]
        if missing:
            with exclude.open("a") as fh:
                # The file is shared and may be hand-edited: a last line with no
                # trailing newline would otherwise absorb our first pattern
                # (`*.log` + `.fr-isolation` → `*.log.fr-isolation`, gh#843).
                if text and not text.endswith("\n"):
                    fh.write("\n")
                fh.writelines(f"{p}\n" for p in missing)

    def _remove_isolation_marker(self, worktree: Path) -> None:
        """Retire the marker on `down` (idempotent — absent is fine)."""
        (worktree / ".fr-isolation").unlink(missing_ok=True)

    # ----- cold-start base resolution (#322) -----

    def _cold_start_base(
        self, branch: str, base: str | None, no_fetch: bool, origin_reachable: bool = True
    ) -> tuple[str | None, str]:
        """Resolve the start-point for a NEW branch per the spec matrix.

        Returns (start_point, log_line). start_point is the ref to append after
        `-b <branch>`, or None meaning "append nothing" — git then defaults to
        the current HEAD (byte-identical to the legacy behaviour). The log_line
        is printed by the caller, to stderr (every line `up` prints does).
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

        if not origin_reachable:
            # The <B> probe just failed to reach origin; a second, full fetch
            # would only repeat that wait (#438 review).
            return None, f"WARNING: origin unreachable — basing {branch} on local HEAD"

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
        result = self._run_network(["git", "fetch", "origin"])
        if result.returncode != 0:
            return False
        # Refresh origin/HEAD so _resolve_default_branch's symbolic-ref hits.
        # Best-effort: a failure here just falls through to the gh/main chain.
        self._run_network(["git", "remote", "set-head", "origin", "--auto"])
        return True

    def _resolve_default_branch(self) -> str:
        """symbolic-ref refs/remotes/origin/HEAD → the forge's own answer → main.

        The forge step is the adapter's `default_branch` (`fr.hostclient.
        client_for`), which picks gh / glab / tea for this checkout's backend;
        a failed lookup reads as `None`, hence "main".
        """
        sym = self.run(
            ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=self.repo_root
        )
        name = (sym.stdout or "").strip()
        if sym.returncode == 0 and name:
            # --short yields "origin/main"; strip to the bare branch name.
            return name.removeprefix("origin/")

        # The forge step runs on this lifecycle's own runner, with the
        # non-interactive network env and timeout (spec
        # 2026-10-06-forge-remainder §4.B), plus the adapter's host (gh#1015).
        try:
            branch = client_for(self.repo_root).default_branch(
                cwd=self.repo_root,
                run=lambda argv, *, cwd, env=None: run_network(
                    self.run, self.repo_root, argv, cwd, extra_env=env
                ),
            )
        except FORGE_ERRORS as exc:  # the lookup soft-fails all else: the host refusal
            raise _forge_refused(exc) from exc
        return branch or "main"

    def _ref_exists(self, ref: str) -> bool:
        return self._rev(ref) is not None

    def _ensure_mounted_env_file(self, config: Path) -> None:
        """Ensure the env-file the profile's devcontainer.json mounts exists.

        Mount-following (#272): the committed config is the source of truth —
        the file is created so docker can read it. No --env-file in runArgs →
        nothing to ensure.
        """
        try:
            run_args = json.loads(config.read_text()).get("runArgs", [])
        except OSError, UnicodeDecodeError, json.JSONDecodeError:
            return
        for flag, value in zip(run_args, run_args[1:]):
            if flag != "--env-file":
                continue
            env_file = Path(value.replace("${localEnv:HOME}", str(_home())))
            if not env_file.is_file():
                env_file.parent.mkdir(parents=True, exist_ok=True)
                env_file.write_text(f"# fr isolation secrets — {repo_cache_name(self.repo_root)}\n")
            harden_secret_file(env_file)  # 0600 file / 0700 dirs — self-heals loose perms

    def _docker_ps(self, state: IsolationState) -> subprocess.CompletedProcess[str]:
        return self.run(
            [
                "docker",
                "ps",
                "--all",
                f"--filter=label=devcontainer.local_folder={state.worktree}",
                "--format={{.ID}} {{.State}}",
            ]
        )

    def _docker_ps_line(self, state: IsolationState) -> str:
        """Tolerant read for status/stats — empty on absent OR query failure.
        `down()` uses the raw `_docker_ps` so it can tell those two apart: a
        FAILED query must never be read as 'container gone' (that would re-open
        the #354 leak under a down daemon), only a successful-but-empty one."""
        return (self._docker_ps(state).stdout or "").strip()

    def _image_for(self, container: str) -> str | None:
        """The image id backing a container (for post-teardown reclamation)."""
        result = self.run(["docker", "inspect", "--format", "{{.Image}}", container])
        img = (result.stdout or "").strip()
        return img if result.returncode == 0 and img else None

    def _reclaim_image(self, image: str | None) -> None:
        """Best-effort `docker rmi` — #354. A devcontainer's `vsc-*` image is
        ~1 GB and leaks today (down never removed it). Reclamation is OFF the
        verification path: a shared / in-use image failing `rmi` is logged, never
        fatal — image cleanup must not block a teardown whose container is
        already gone."""
        if not image:
            return
        result = self.run(["docker", "rmi", image])
        detail = (result.stderr or result.stdout or "").strip()
        # Already gone is reclaimed, not a failure: a features profile's rebuild
        # can leave the old image id removed before fr gets to it (live walk,
        # phase-6 p6-f1). Only an image that is still there earns the warning.
        if result.returncode != 0 and "No such image" not in detail:
            print(
                f"warning: could not remove image {image} (shared or in use?): {detail}",
                file=sys.stderr,
            )

    def _workspace_volumes(self, container: str) -> list[str]:
        """Named volumes this container's workspace owns, read BEFORE `docker rm`.

        `docker rm` never removes a named volume, and docker-in-docker keeps the
        inner dockerd's whole /var/lib/docker in `dind-var-lib-docker-<id>` — a
        leak of many GB per torn-down workspace. Ownership is the
        `${devcontainerId}` in the volume name: a shared volume (a cache mounted
        by every workspace) carries no id and is never touched."""
        result = self.run(
            [
                "docker",
                "inspect",
                "--format",
                '{{index .Config.Labels "devcontainer.local_folder"}}\t'
                '{{index .Config.Labels "devcontainer.config_file"}}\n'
                '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}} {{end}}{{end}}',
                container,
            ]
        )
        lines = (result.stdout or "").splitlines()
        if result.returncode != 0 or len(lines) < 2:
            return []
        folder, _, config = lines[0].partition("\t")
        if not folder or not config:
            return []
        dc_id = devcontainer_id(folder, config)
        return [v for v in lines[1].split() if dc_id in v]

    def _reclaim_volumes(self, volumes: list[str]) -> None:
        """Best-effort `docker volume rm`, after the container is gone (a mounted
        volume cannot be removed). Like image reclaim, never fatal."""
        for volume in volumes:
            result = self.run(["docker", "volume", "rm", volume])
            detail = (result.stderr or result.stdout or "").strip()
            if result.returncode != 0 and "no such volume" not in detail.lower():
                print(f"warning: could not remove volume {volume}: {detail}", file=sys.stderr)

    def _shown_container_state(self, state: IsolationState) -> str:
        """`status`'s rendering of the docker state: `exited` reads as `stopped`
        (the state `fr isolation stop` leaves, #471); every other state passes
        through; no container is `not running`. A FAILED query is not absence
        (#354, phase-1 review f7): it reads `unknown (docker unreachable)`."""
        try:
            pairs = self._ps_pairs_strict(state)
        except IsolationError:
            return "unknown (docker unreachable)"
        current = pairs[0][1] if pairs else None
        if current is None:
            return "not running"
        return "stopped" if current == "exited" else current

    def _pr(self, state: IsolationState) -> dict[str, Any] | None:
        return self._pr_from(self.repo_root, state.branch)

    def _pr_from(self, cwd: Path, branch: str) -> dict[str, Any] | None:
        """PR/MR-for-branch lookup from an arbitrary repo cwd — gc reconciles
        workspaces across repos, so it can't assume `self.repo_root`. Uses
        host auth (gh/glab) or the CLI's own login (tea).

        The adapter's `pr_for_branch` (`fr.hostclient.client_for(cwd)`) runs
        it on this lifecycle's runner and returns the one shape callers
        depend on: `{"state": "OPEN"|"MERGED"|"CLOSED", "url": str,
        "mergedAt": str|None}` (the merge time where the forge reports one —
        gc's #844 check), or None.
        """
        try:
            return client_for(cwd).pr_for_branch(branch, cwd=cwd, run=_forge_runner(self.run))
        except FORGE_ERRORS as exc:  # the lookup soft-fails all else: the host refusal
            raise _forge_refused(exc) from exc
