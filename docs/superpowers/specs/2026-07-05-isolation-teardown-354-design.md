# fr isolation teardown: verified `down()` + host-wide `gc` reconciliation

**Date:** 2026-07-05
**Status:** Design (brainstormed with operator via `/fr-goal`) — ready for `fr-plan`.
**Issue:** derio-net/super-fr#354
**Target repo:** derio-net/super-fr (package `fr`, module `fr.isolation`)
**Supersedes:** `docs/superpowers/specs/2026-06-15-isolation-gc-design.md` (never
built; that branch carried only the spec). This consolidates its Task-B design
with #354's new, high-severity Task A, and drops its item 5 (`up` off
`origin/<default>`) — **already shipped as #322**.

## Problem

Two independent leaks, both found 2026-07-05 while investigating 22+ Docker
containers on the operator's Mac (6 leaked devcontainers across 6 repos):

### Task A — `down()` deletes its bookkeeping without verifying teardown (severity: high)

`LocalWorktreeDevcontainerTarget.down()` (`packages/fr/src/fr/isolation/local.py:295-311`)
runs `docker stop`, `docker rm`, and `git worktree remove` **without checking a
single return code**, then calls `delete_state()` unconditionally:

```python
self._remove_isolation_marker(state.worktree)
container = self._container_id(state)
if container:
    self.run(["docker", "stop", container])   # rc ignored
    self.run(["docker", "rm", container])     # rc ignored
self.run(["git", "worktree", "remove", "--force", str(state.worktree)], cwd=self.repo_root)  # rc ignored
delete_state(state.repo_root, state.branch)   # runs no matter what
```

**Observed:** `derio-net/frank`, branch `feat/repo-blog-authoring-overview`.
The worktree was removed and the state file deleted, but the devcontainer kept
running (a transient docker hiccup at teardown time — a manual `docker stop`/`rm`
later worked fine). Because `delete_state()` ran anyway, `fr isolation status`
reported *"no isolation workspaces"* — the container went **invisible to `fr`**,
findable only by cross-referencing `docker ps` labels against
`~/.cache/fr/worktrees/*` by hand. A silent leak with no in-CLI signal is worse
than a loud failure.

This contrasts with `up`/`restart`/`_git_worktree_add`, which already check
`result.returncode` and raise `IsolationError` (`local.py:170-171, 216-220, 333-335`).
`down` is the one destructive path that doesn't.

### Task B — nothing tears a workspace down when its PR merges (severity: medium)

`fr isolation down` is **never called by code** — the only call site is the CLI
handler. Every other reference is prose ("after the PR is MERGED, run `down`")
in `fr-isolation` / `fr-goal` step 9 / `fr-debugging`. That instruction is
**structurally unfollowable**: the completion signal (terminal PR merged)
reliably arrives *after* every in-session opportunity has passed — the operator
merges later, elsewhere, via the GitHub UI, or another agent, and never circles
back to the originating session to trigger close-out. This produced 5 of the 6
leaked containers this session (cnc-fr ×2, cnc-frd, cnc-fru, runs-fr — all
MERGED PRs, containers still up 2–5 h post-merge).

The dispatch/phase-based path is immune — the `fr_vk` bridge tick already
observes PR-merge and reaps its **VK cloud** workspaces (`fr_vk.workspaces.reap_orphans`,
a disjoint resource space: MCP `list_workspaces`, not local docker). End-to-end
(worktree + devcontainer) workflows have **no equivalent observer**, so they
leak ~100%.

### Residue neither fix reclaims today: images

`down` does `docker stop`+`rm` (container) but never `docker rmi`. The
`vsc-<branch>-…-features` image layers (~1 GB each) accumulate — 10+ observed,
including (ironically) `feat__isolation-gc`.

## Requirements

1. **Task A:** `down()` verifies each destructive step's post-condition before
   deleting state; on failure it raises `IsolationError` and **leaves the state
   file + marker in place**, so the workspace stays visible to
   `fr isolation status` and a retry finishes the job.
2. **Task B:** `fr isolation gc` — a host-wide, substrate-neutral reconciliation
   sweep that classifies every tracked workspace and tears down MERGED ones —
   **runnable standalone** (human or scheduler) **and fired opportunistically**
   from every `up`/`down` (operator's chosen primary trigger; no daemon).
3. **Images:** `down()` reclaims its own image; `gc` sweeps dangling `vsc-*`
   images (operator opted this into this PR).
4. **Docs:** the "remember to run `down`" prose is reconciled to "gc reconciles
   merged workspaces; `down` is still the lever for immediate teardown."

### Operator constraint (carried from 2026-06-15)

*"I don't want another scheduler on each host that runs fr workloads. I'm ok
with ONE stale workspace."* Firing gc on every `up`/`down` bounds the
steady-state leak to **≤1** workspace (host-wide sweep, so an `up` in repo A
also reaps completed work in repos B…F) with no launchd/cron/daemon.

## Design

### Task A — verified `down()`

Re-query is the **authoritative post-condition check**, not the return code:
`docker rm` on an already-gone container returns non-zero while the
post-condition (container gone) holds, and a `rm` can return 0 yet leave a
wedged container. Ground truth is "is it still there?", via the existing
`_container_id` / `state.worktree.exists()`:

```python
def down(self, state, force=False):
    pr = self._pr(state)
    if pr and pr.get("state") == "OPEN" and not force:
        raise IsolationError(...)                       # open-PR guard — UNCHANGED
    container = self._container_id(state)
    image = self._image_for(container) if container else None
    if container:
        self.run(["docker", "stop", container])
        self.run(["docker", "rm", container])
        if self._container_id(state) is not None:       # re-query: still there?
            raise IsolationError(
                f"container for {state.branch} still present after docker stop/rm — "
                "workspace left intact (still visible to `fr isolation status`); retry `down`."
            )
    self._reclaim_image(image)                           # best-effort, non-fatal (see Images)
    wt = self.run(["git", "worktree", "remove", "--force", str(state.worktree)], cwd=self.repo_root)
    if wt.returncode != 0 and state.worktree.exists():   # re-query: dir gone?
        raise IsolationError(
            f"git worktree remove failed for {state.worktree}: {wt.stderr or wt.stdout} — "
            "state left intact; retry `down`."
        )
    self._remove_isolation_marker(state.worktree)        # moved AFTER wt removal
    delete_state(state.repo_root, state.branch)
```

Changes from today:
- **Marker removal moves to the end.** If worktree removal fails and we raise,
  the marker stays inside the still-present worktree → the workspace remains a
  valid isolation workspace and stays visible. (When the worktree *is* removed,
  the marker goes with it; the explicit unlink is then an idempotent no-op.)
- **Orphan-down still works:** for a workspace whose worktree is already gone,
  `git worktree remove` fails but `state.worktree.exists()` is False → the guard
  does not fire → teardown completes. "Already gone" == success.
- **`--force` semantics are NOT widened.** `force` bypasses the open-PR guard
  only — it does **not** skip post-condition verification. Letting force delete
  state while a live container remains would re-introduce exactly the
  invisible-leak bug. The escape for a genuinely wedged container is
  `fr isolation restart --force` then `down`, or manual docker + re-run; the
  workspace staying visible is the feature, not a bug.

### Images

`down()` reclaims the container's image, best-effort:
- Capture the image id **before** `docker rm` (need the container to inspect):
  `_image_for(container)` → `docker inspect --format '{{.Image}}' <container>`.
- After `docker rm`, `_reclaim_image(image)` runs `docker rmi <image>`. A
  shared / in-use image failing `rmi` is **logged, never fatal** — image
  reclamation must never block or fail a teardown whose container is already
  gone. It is off the verification path.

`gc` additionally sweeps **dangling** `vsc-*` images with no container
(`docker images` filtered to `vsc-*`, minus any still referenced by a live
container), each `rmi` best-effort.

### Task B — `fr isolation gc`

**Host-wide discovery** (state is per-repo, so gc reconstructs the set from two
substrate-visible sources and unions them):

1. **Docker labels** (survives state loss):
   `docker ps -a --filter label=devcontainer.local_folder --format '{{.ID}}\t{{.Label "devcontainer.local_folder"}}'`
   → `(container_id, worktree_path)`.
2. **Worktree dirs** under `~/.cache/fr/worktrees/*/*` (catches workspaces whose
   container is stopped/gone but whose worktree + state linger).

For each discovered worktree path, gc git-resolves it back to its owning repo
(`git -C <wt> rev-parse --git-common-dir` → `<main-repo>/.git` → `load_state`),
reconstructing the `IsolationState` **without a prior registry**. `gh pr view`
runs from the worktree itself (the branch is checked out there).

**Classification, then action** — gc must classify before acting (a blind
`down()` would reap in-progress no-PR work):

| State | Signal | Action |
| --- | --- | --- |
| **Terminal PR merged** | `_pr` state == `MERGED` | `Target.down()` (container + worktree + state + image) |
| **Open PR** | `_pr` state == `OPEN` | **skip** (operator may still push — matches `down`'s guard) |
| **Orphan — worktree gone** | worktree dir absent, container found by label | reap by label directly (`stop`+`rm`+`rmi`) + delete any dangling state; no PR check (worktree gone ⇒ done) |
| **No PR yet** | `_pr` returns none | **warn only** — never auto-reap (protects live no-PR design work, e.g. a multi-day `secrets-injection` brainstorm) |
| **No state, worktree present** | label-discovered, no state file, worktree exists | **warn, don't reap** (ambiguous) |

- gc reuses `Target.down(state, force=False)` for the MERGED case — merged isn't
  open, so the guard passes; if Task A's verification raises on a transient
  failure, gc **catches per-workspace, logs, and continues** (one bad workspace
  never aborts the sweep; the next sweep retries).
- `--dry-run` classifies + reports, mutates nothing. `--format json` emits the
  per-workspace verdict+action for scripting.

**Concurrency:** gc takes a host-wide `flock(LOCK_EX | LOCK_NB)` on
`~/.cache/fr/isolation-gc.lock` (idiom mirrored from `fr_vk.bridge_cli._acquire_lock`
— `/tmp` fallback, `BlockingIOError` if held; reimplemented locally, **not**
imported, since `fr` must not depend on `fr_vk`, which is being dropped). A
second concurrent sweep exits immediately; the sweep is idempotent, so a missed
overlap is harmless — the next `up`/`down` re-runs it.

### Opportunistic background spawn (primary auto-trigger)

`up()` and `down()`, **after their own work completes**, spawn a detached,
non-interactive `fr isolation gc`:

- Routed through an injectable **`GcSpawner`** seam (constructor arg, like
  `runner`), default `_detached_gc_spawn`:
  `subprocess.Popen([sys.executable, "-m", "fr", "isolation", "gc"], start_new_session=True, stdin/stdout/stderr → ~/.cache/fr/isolation-gc.log)`,
  then return immediately. It must not block the caller, raise into the agentic
  flow, or print to the agent's stream (any spawn error is swallowed + logged).
- The seam keeps the flow **testable**: tests inject a recording spawner and
  assert (a) `up`/`down` request exactly one spawn, (b) a spawner that raises
  does not propagate into `up`/`down`. A rotating `isolation-gc.log` captures
  what was reaped, for audit.

Why a seam and not the `runner`: a detached `Popen` is a different shape than
`subprocess.run` (the `runner` signature) — folding it into `runner` would
misrepresent the fire-and-forget semantics and make the non-blocking/non-raising
contract untestable.

### Substrate neutrality

All teardown flows through `Target.down()`; discovery (docker label) and the
reap primitive live in `LocalWorktreeDevcontainerTarget`. gc's **classification
is substrate-agnostic**; only discovery + reap are docker-specific. A future
k8s `Target` (pods; `derio-net/runs-fr`) implements pod discovery/reap behind
the same seam — out of scope here, but not foreclosed.

## Doc reconciliation

Within the 120-line SKILL cap (compress to add):
- `fr-isolation` — add `fr isolation gc` to the Lifecycle block; rewrite the
  **Cleanup contract** so it reads "gc reconciles merged workspaces
  automatically (fired on every `up`/`down`, host-wide, ≤1 stale); `down` is the
  lever for immediate teardown and still refuses an open PR without `--force`."
- `fr-goal` step 9 / `fr-debugging` line 98 — soften "human must remember `down`
  per-branch in the originating session" to "gc reconciles merged workspaces
  even if the session never resumes; the explicit `down` remains for immediate
  close-out."

## Non-goals

- No per-host daemon / launchd / cron.
- No auto-reap of no-PR workspaces (warn only).
- VK / phase-based reaping unchanged (disjoint resource space — VK cloud MCP
  workspaces, not local docker).
- k8s/pod `Target` out of scope; the seam is preserved for it.
- `--force` is **not** extended to skip teardown verification.

## Test Plan

**Post-merge, operator-driven (real Docker on the Mac — the fake-runner seam
cannot prove real teardown).** Run after this PR merges:

1. **Verified `down` (Task A):** `up` a throwaway workspace; with the container
   running, simulate a transient failure (e.g. `docker pause` the container so
   `rm` can't complete, or stop the docker daemon mid-`down`) and run
   `fr isolation down --branch <b>`. Confirm it **exits non-zero with an
   `IsolationError`**, the state file + `.fr-isolation` marker **survive**, and
   `fr isolation status` **still lists the workspace**. Un-pause / restart
   docker, re-run `down`, confirm clean teardown.
2. **Image reclamation:** note the workspace's `vsc-*` image
   (`docker images | grep vsc-`) before a normal `down`; after, confirm the
   image is gone (or, if shared, that `down` still succeeded and logged the skip).
3. **gc classification:** create three workspaces — one whose PR you merge, one
   whose PR stays OPEN, one with no PR. Run `fr isolation gc --dry-run` and
   confirm the verdicts (merged→reap, open→skip, no-PR→warn); run
   `fr isolation gc` and confirm `docker ps` shows the merged one **reaped**, the
   open-PR and no-PR ones **untouched**, and `docker images` shows the merged
   one's image gone.
4. **Opportunistic trigger + ≤1 invariant:** with a merged-PR workspace present,
   run `fr isolation up` for a *new, unrelated* branch; confirm the background
   gc reaped the merged one (check `~/.cache/fr/isolation-gc.log`) and
   `docker ps` shows ≤1 stale workspace without you running gc by hand.

## Acceptance rows

New rows registered against this spec (business claims → matrix; see
`## Test Plan`):
- `isolation-down-verified` — teardown that can't complete leaves the workspace
  visible to `fr isolation status` (never a silent state delete).
- `isolation-gc-reconciles-merged` — a merged-PR workspace is torn down without
  the originating session, host-wide, bounded to ≤1 stale.

## Implementation Plans

| Plan | Target repo | Slug | Status |
|------|-------------|------|--------|
| 2026-07-05-isolation-teardown-354 | `derio-net/super-fr` | `2026-07-05-isolation-teardown-354` | — |
