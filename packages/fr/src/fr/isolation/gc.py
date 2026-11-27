"""GcSweeper — host-wide isolation gc, run for one target.

gc used to be fifteen methods on `LocalWorktreeDevcontainerTarget`. It lives
here as a collaborator that holds its target: every step that differs by mode
(`_labelled_containers`, `_sweep_dangling_images`, `_label_reap`, `_pr_from`,
`run`, `repo_root`) is the target's, and the sweeper calls it through
`self._target`, so a `HostWorktreeTarget` sweep still runs no docker (spec
2026-11-27-isolation-gc-sweeper).

`fr.isolation.local` imports this module, so the target type is imported for
type checking only.
"""

from __future__ import annotations

import errno
import fcntl
import shutil
from pathlib import Path
from typing import IO, TYPE_CHECKING, cast

from fr.isolation import preserve as _preserve
from fr.isolation.branchrefs import _realpath
from fr.isolation.landing import branch_changes_present
from fr.isolation.reap import GcAction, GcWorkspace, ReapRefused, _merged_before
from fr.isolation.runner import _home, _noop_gc_spawn
from fr.isolation.types import (
    IsolationError,
    IsolationState,
    _git_common_dir,
    delete_state,
    list_states,
    recorded_mode,
)

if TYPE_CHECKING:
    from fr.isolation.local import LocalWorktreeDevcontainerTarget


class GcSweeper:
    """Runs `gc` for one target, calling the target's own overrides."""

    def __init__(self, target: LocalWorktreeDevcontainerTarget) -> None:
        self._target = target

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
        try:
            lock = self._acquire_gc_lock()
        except BlockingIOError:
            return []
        try:
            actions = [self._gc_one_guarded(rec, dry_run) for rec in self._discover_workspaces()]
            actions.extend(self._target._sweep_dangling_images(dry_run))
            actions.extend(self._sweep_empty_repo_dirs(dry_run))
            actions.extend(self._sweep_stale_sessions(dry_run))
            actions.extend(self._sweep_agent_worktrees(dry_run))
            return actions
        finally:
            lock.close()

    def _acquire_gc_lock(self) -> IO[str]:
        """flock(LOCK_EX | LOCK_NB) on the host-wide gc lock; BlockingIOError if
        another sweep holds it. The same non-blocking flock idiom as
        `fr.artifacts.atomic`'s migration lock."""
        lock_path = _home() / ".cache" / "fr" / "isolation-gc.lock"
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            lock_path = Path("/tmp/fr-isolation-gc.lock")  # noqa: S108 — unprivileged fallback
        fh = open(lock_path, "w")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            fh.close()
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise BlockingIOError("gc sweep already in progress") from e
            raise
        return fh

    def _gc_one_guarded(self, rec: GcWorkspace, dry_run: bool) -> GcAction:
        """`_gc_one`, but an `IsolationError` that escapes it (a refused forge
        lookup, review p2-r1) skips THAT workspace instead of aborting the
        host-wide sweep. Skipped is the safe verdict: nothing is reaped."""
        try:
            return self._gc_one(rec, dry_run)
        except IsolationError as exc:
            branch = rec.state.branch if rec.state is not None else None
            return GcAction(str(rec.worktree), branch, "unverifiable", "skipped", str(exc))

    def _gc_one(self, rec: GcWorkspace, dry_run: bool) -> GcAction:
        wt = str(rec.worktree)
        if not rec.worktree.is_dir():
            # Orphan: worktree gone. If a container lingers (found by label),
            # reap it directly — no PR check needed (worktree gone ⇒ done).
            if not rec.container_id:
                return self._gc_stale_state(rec, dry_run)
            if dry_run:
                return GcAction(wt, None, "orphan", "would-reap")
            try:
                self._target._label_reap(rec.container_id)
                if rec.state is not None:  # dangling state file, if any
                    delete_state(rec.state.repo_root, rec.state.branch)
                return GcAction(wt, None, "orphan", "reaped", rec.container_id)
            except Exception as e:  # reap is best-effort; never abort the sweep
                return GcAction(wt, None, "orphan", "reap-failed", str(e))
        state = rec.state
        if state is None:
            return GcAction(wt, None, "no-state", "warned", "worktree present, no fr state")
        pr = self._target._pr_from(state.worktree, state.branch)
        pr_state = pr.get("state") if pr else None
        if pr is not None and pr_state == "MERGED" and _merged_before(pr, state.created_at):
            # gh#844: the lookup is by branch NAME, so a re-used name answers
            # with an earlier PR that merged before this workspace existed —
            # not this workspace's work. Fall through to the content check,
            # which judges the branch itself.
            pr_state = None
        if pr_state == "MERGED":
            return self._reap_or_classify(wt, state, "merged", dry_run)
        if pr_state == "OPEN":
            return GcAction(wt, state.branch, "open", "skipped")
        # No MERGED/OPEN PR. Before warning forever, check whether the branch's
        # CHANGES already landed on origin/<default> — a PR-less merge (work
        # squash-merged, rebased, or re-authored under another PR) is invisible
        # to gc's PR-only view, so the workspace would warn forever. Reap only
        # when provably safe (see _merged_by_content).
        if self._merged_by_content(state):
            return self._reap_or_classify(wt, state, "merged-by-content", dry_run)
        return GcAction(
            wt, state.branch, "no-pr", "warned", "no PR — `fr isolation down` when done"
        )

    def _reap_or_classify(
        self, wt: str, state: IsolationState, verdict: str, dry_run: bool
    ) -> GcAction:
        """Shared tail for both reap-eligible verdicts (MERGED-by-PR and
        merged-by-content, phase 3, #467 spec §3.5): the classification that
        gets here differs (PR state vs. content comparison), but what to DO
        once classified — preview or reap, and how a refusal reads — is
        identical, so it lives once.

        `_down_worktree_tail`'s hazard guard (force=False, unconditional) can
        still refuse a workspace gc has already classified as reap-eligible —
        e.g. a MERGED PR with an uncommitted change in the worktree. That
        refusal is a DECISION, not a teardown failure: caught here as
        `ReapRefused`, BEFORE the broad `except Exception`, and reported as
        "skipped" with the hazard's own detail — never "reap-failed", which
        reads as breakage and trains the operator to ignore the row. The
        broad handler still catches genuine teardown errors (IsolationError,
        a missing binary, an OSError from delete_state) so one workspace's
        failure never aborts the host-wide sweep.

        dry-run asks `_reap_hazard` the SAME question the live reap enforces
        before promising "would-reap" — a preview that predicts an action the
        live run would refuse is not a preview.

        Both the preview probe and the live teardown go through a sibling built
        from the WORKSPACE's recorded mode (gh#569), not `type(self)`. gc is
        host-wide and `self` is whatever mode the triggering command ran in: a
        host-worktree sweep reaping a devcontainer workspace through
        `type(self)` ran the docker-less `_teardown_container` no-op and leaked
        the container — the #354 leak by another route. Function-local import:
        `routing` imports `hostworktree`, which imports this module.
        """
        from fr.isolation.external import GC_EXTERNAL_DETAIL
        from fr.isolation.routing import target_for_state

        if recorded_mode(state) == "external":
            # An adopted checkout is the preparer's to clean up — classified,
            # never reaped, by a worktree sweep (same verdict ExternalTarget.gc
            # reports).
            return GcAction(wt, state.branch, "external", "skipped", GC_EXTERNAL_DETAIL)
        hold = _preserve.gc_run_hold(Path(wt), state.branch)
        if hold is not None:  # R9: a running or unreadable cursor, at the placement's root
            return GcAction(wt, state.branch, verdict, "skipped", f"kept: {hold}")
        # Rooted at the WORKSPACE's repo (see the dry-run note below) and built
        # with the NO-OP spawner so a reap never re-triggers a sweep. The cast
        # is sound: with external excluded above, routing only ever returns
        # this class or HostWorktreeTarget.
        sibling = cast(
            "LocalWorktreeDevcontainerTarget",
            target_for_state(state, runner=self._target.run, gc_spawner=_noop_gc_spawn),
        )
        if dry_run:
            # Ask through a sibling rooted at the WORKSPACE's repo, exactly as
            # the live path below does — `_reap_hazard` calls
            # `_resolve_default_branch()`, which reads `self.repo_root`, and gc
            # is host-wide: `self` here is whichever repo happened to trigger
            # the sweep, not this workspace's. Asking `self` would resolve
            # repo A's default branch while comparing repo B's worktree, so a
            # `master` repo swept from a `main` one would preview "would-skip"
            # for a workspace the live run then reaps — the preview/live
            # divergence this dry-run change exists to remove (phase-3 review
            # f5). Same sibling idiom as `_merged_by_content`.
            hazard = sibling._reap_hazard(state)
            if hazard is not None:
                return GcAction(wt, state.branch, verdict, "would-skip", hazard.detail)
            return GcAction(wt, state.branch, verdict, "would-reap")
        try:
            # Tear down through a Target rooted at the workspace's OWN repo
            # (down() keys git/gh off its repo_root) — substrate-neutral: gc
            # orchestrates Targets, it doesn't reach past them.
            report = sibling.down(state, force=False)
            ended = "; ".join(f"ended run {i} at step {c}" for i, c in report.ended_runs)
            if ended and report.preserved_dir is not None:
                ended += f" — record preserved at {report.preserved_dir}"
            return GcAction(wt, state.branch, verdict, "reaped", ended)
        except ReapRefused as e:
            return GcAction(wt, state.branch, verdict, "skipped", e.hazard.detail)
        except Exception as e:
            # Broad by design (matches the orphan branch): one workspace's
            # teardown — IsolationError, a missing binary, an OSError from
            # delete_state — must NEVER abort the host-wide sweep.
            return GcAction(wt, state.branch, verdict, "reap-failed", str(e))

    def _gc_stale_state(self, rec: GcWorkspace, dry_run: bool) -> GcAction:
        """Worktree gone, no container: retire the dangling fr state RECORD.

        A worktree removed out of band (`rm -rf`, a runner reaping its own
        workspace, a `git worktree remove` outside fr) leaves the state JSON at
        `<git-common-dir>/fr/isolation/<branch>.json` behind. Nothing discovered
        it before this (#423) — discovery was directory/container-driven — so
        `fr isolation status` reported a workspace that no longer exists, forever.

        Only bookkeeping is retired: the branch, its commits, and git's own
        worktree registration are left exactly as they are. Reaping is gated on
        `_stale_state_reapable()` so #354's invariant holds — a FAILED docker
        query must never be read as "no container".
        """
        wt = str(rec.worktree)
        state = rec.state
        if state is None:
            return GcAction(wt, None, "orphan", "skipped", "no container")
        from fr.isolation.external import GC_EXTERNAL_DETAIL
        from fr.isolation.routing import target_for_state

        if recorded_mode(state) == "external":
            return GcAction(wt, state.branch, "external", "skipped", GC_EXTERNAL_DETAIL)
        # Ask the WORKSPACE's mode, not the sweeper's (review p2-f1): a
        # host-worktree sweeper's own answer is an unconditional True, so a
        # devcontainer record whose worktree is gone would be dropped without
        # asking docker whether its container still runs — the #354 leak.
        try:
            owner = cast(
                "LocalWorktreeDevcontainerTarget",
                target_for_state(state, runner=self._target.run, gc_spawner=_noop_gc_spawn),
            )
        except Exception as e:  # unknown owner ⇒ never reap; never abort the sweep
            return GcAction(wt, state.branch, "orphan", "skipped", f"cannot route: {e}")
        if not owner._stale_state_reapable():
            return GcAction(
                wt, state.branch, "orphan", "skipped", "docker unavailable — reap deferred"
            )
        if dry_run:
            return GcAction(wt, state.branch, "orphan", "would-reap", "stale state record")
        try:
            delete_state(state.repo_root, state.branch)
            return GcAction(wt, state.branch, "orphan", "reaped", "stale state record")
        except Exception as e:  # per-workspace; never abort the host-wide sweep
            return GcAction(wt, state.branch, "orphan", "reap-failed", str(e))

    def _merged_by_content(self, state: IsolationState) -> bool:
        """True when a PR-less workspace's changes are ALL already present on
        origin/<default> — a merge gc's PR-only classifier can't see — and
        reaping is provably safe.

        CONTENT-based, not ancestry-based, so it recognizes SQUASH merges — the
        dominant org pattern. A squash lands the branch's net content as a new
        commit, leaving the branch NOT an ancestor of the default branch; an
        `is-ancestor` check would false-negative exactly there. Comparing final
        file content (`branch_changes_present` — squash/rebase/merge-commit safe)
        still sees the work as landed.

        ALL must hold (conservative on every unknown ⇒ False ⇒ warn, never reap):
        - `origin/<default>` resolves and exists;
        - the branch actually CHANGED files since its merge-base — a pristine or
          idle branch that merely fell behind main changed nothing, so it is not
          a merge and is never reaped (this protects the fresh workspace `up`
          creates at, or just behind, the tip);
        - every changed file's final content is already on `origin/<default>`;
        - the worktree is CLEAN (no uncommitted work to lose).

        A stale local `origin/<default>` ref only DEFERS a reap to a later sweep,
        never causes a wrong one. Documented residual (clean-worktree-guarded):
        genuinely convergent content — the identical change landing independently
        on main — reads as merged.
        """
        try:
            wt = state.worktree
            sibling = type(self._target)(
                state.repo_root, runner=self._target.run, gc_spawner=_noop_gc_spawn
            )
            base = f"origin/{sibling._resolve_default_branch()}"
            if (
                self._target.run(
                    ["git", "rev-parse", "--verify", "--quiet", base], cwd=wt
                ).returncode
                != 0
            ):
                return False
            status = self._target.run(["git", "status", "--porcelain"], cwd=wt)
            if status.returncode != 0 or (status.stdout or "").strip():
                return False
            result = branch_changes_present(
                self._target.run, wt, state.branch, base, state.base_sha
            )
            return bool(result.changed) and result.changes_present
        except Exception:
            return False

    def _discover_workspaces(self) -> list[GcWorkspace]:
        """Union THREE ownership-proving sources, then resolve each to its fr
        state. Every source is evidence that fr owns the workspace; nothing here
        enumerates `git worktree list`, so a plain `git worktree add` made by
        other automation is never seen and never reaped (#423 non-goal).

        1. docker-label containers (`devcontainer.local_folder`) — devcontainer
           mode only; docker-less modes override it to an empty list;
        2. directories under the fr worktree cache `~/.cache/fr/worktrees`;
        3. the invoking repo's own fr state records (#423) — the ONLY source
           that finds a workspace created at a custom `--path` (the shape
           runners use) or a record whose worktree has since vanished.

        Sources 1–2 are host-wide; source 3 is necessarily per-repo (state is
        per-repo, there is no host registry), which is why the cache scan stays.
        """
        by_path: dict[Path, GcWorkspace] = {}
        for cid, path in self._target._labelled_containers():
            by_path[path] = GcWorkspace(worktree=path, container_id=cid, state=None)
        for path in self._worktree_dirs():
            by_path.setdefault(path, GcWorkspace(worktree=path, container_id=None, state=None))
        recorded: dict[Path, IsolationState] = {}
        seen = {_realpath(p) for p in by_path}
        for st in self._repo_states():
            recorded[st.worktree] = st
            key = _realpath(st.worktree)
            if key in seen:
                continue  # already discovered by label/cache — don't double-classify
            seen.add(key)
            by_path[st.worktree] = GcWorkspace(worktree=st.worktree, container_id=None, state=None)
        for path, rec in by_path.items():
            if path.is_dir():
                try:
                    rec.state = self._resolve_state(path)
                except Exception:
                    # A single corrupt/unreadable state JSON must not abort the
                    # host-wide sweep — treat as no-state (the workspace is then
                    # warned, never blindly reaped).
                    rec.state = None
            else:
                # Worktree gone. Carry the state record through so the sweep can
                # retire the dangling bookkeeping (`_gc_stale_state`) instead of
                # leaving `fr isolation status` reporting a phantom workspace.
                rec.state = recorded.get(path)
        return list(by_path.values())

    def _repo_states(self) -> list[IsolationState]:
        """The invoking repo's fr state records — discovery source 3.

        Best-effort: a missing/corrupt state dir yields nothing rather than
        aborting the host-wide sweep (the other two sources still report)."""
        try:
            return list_states(self._target.repo_root)
        except Exception:
            return []

    def _worktree_dirs(self) -> list[Path]:
        root = _home() / ".cache" / "fr" / "worktrees"
        if not root.is_dir():
            return []
        return [
            child
            for repo in root.iterdir()
            if repo.is_dir()
            for child in repo.iterdir()
            if child.is_dir()
        ]

    def _resolve_state(self, worktree: Path) -> IsolationState | None:
        common = _git_common_dir(worktree)
        repo_root = common.parent if common.name == ".git" else common
        for st in list_states(repo_root):
            if st.worktree == worktree or st.worktree.resolve() == worktree.resolve():
                return st
        return None

    # ---------- gc: cache + session-index hygiene (spec 2026-09-04 §5.A/§5.C) ----------
    #
    # Substrate-neutral (no docker, no git), so every worktree mode inherits
    # them verbatim; ExternalTarget has its own read-only gc and is untouched.

    def _empty_repo_dirs(self) -> list[Path]:
        """Children of `~/.cache/fr/worktrees` with NO subdirectories — the
        `agent-…` / branch-slug folders an `up` from inside a linked worktree
        used to create before the cache was keyed on the main checkout, plus any
        repo folder whose last workspace was torn down. Stray files (`.DS_Store`)
        do not make a folder live: a workspace is always a subdirectory."""
        root = _home() / ".cache" / "fr" / "worktrees"
        if not root.is_dir():
            return []
        return [
            d
            for d in sorted(root.iterdir())
            if d.is_dir() and not any(c.is_dir() for c in d.iterdir())
        ]

    def _sweep_empty_repo_dirs(self, dry_run: bool) -> list[GcAction]:
        out: list[GcAction] = []
        for d in self._empty_repo_dirs():
            if dry_run:
                out.append(GcAction(str(d), None, "empty-repo-dir", "would-remove"))
                continue
            try:
                shutil.rmtree(d)
                out.append(GcAction(str(d), None, "empty-repo-dir", "removed"))
            except OSError as e:  # per-dir; never abort the host-wide sweep
                out.append(GcAction(str(d), None, "empty-repo-dir", "reap-failed", str(e)))
        return out

    def _sweep_stale_sessions(self, dry_run: bool) -> list[GcAction]:
        """Unlink per-session index files whose worktree is gone or whose
        workspace state no longer lists the session (state wins — the index is
        derived). Classification lives in `sessions.stale_session_indexes`, which
        is pure; only the unlink happens here. `detail` carries the index path."""
        from .sessions import stale_session_indexes

        out: list[GcAction] = []
        for p, data in stale_session_indexes():
            wt, br = data.get("worktree", "?"), data.get("branch")
            if dry_run:
                out.append(GcAction(wt, br, "stale-session", "would-remove", str(p)))
                continue
            p.unlink(missing_ok=True)
            out.append(GcAction(wt, br, "stale-session", "removed", str(p)))
        return out

    def _sweep_agent_worktrees(self, dry_run: bool) -> list[GcAction]:
        """Reap finished, clean `agent-*` subagent worktrees, which Claude Code
        never removes once fr's WorktreeCreate hook made them (gh#1270). The
        rules live in `agent_worktrees`; a failure there costs this step only,
        never the rest of the host-wide sweep."""
        from .agent_worktrees import sweep_agent_worktrees

        try:
            return sweep_agent_worktrees(self._target.repo_root, dry_run=dry_run)
        except Exception as e:  # noqa: BLE001 — one step of a best-effort sweep
            return [
                GcAction(str(self._target.repo_root), None, "agent-worktree", "reap-failed", str(e))
            ]
