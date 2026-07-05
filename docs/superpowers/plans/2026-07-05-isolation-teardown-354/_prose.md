# Plan — verified isolation `down()` + host-wide `gc` reconciliation (#354)

Implements `docs/superpowers/specs/2026-07-05-isolation-teardown-354-design.md`.
Two independent teardown leaks, one plan, one PR against `fr.isolation`.

## Shape

All work rides the **Runner seam** (`local.py`, every git/docker/gh call goes
through `runner`), so classification and teardown are unit-testable without
Docker. Two things do NOT fit the existing static `FakeRunner` and get purpose-
built test infrastructure:

1. **State transitions** — Task A's re-query verification needs "container
   present, then gone after `docker rm`." A stateful docker fake that records
   `rm` removals (and drops them from later `docker ps`) models this faithfully;
   `fail_on` the `rm` and the container survives → re-query still sees it → raise.
2. **Detached spawn** — the opportunistic gc is a fire-and-forget `Popen`, a
   different shape than `subprocess.run`. It routes through its own injectable
   `GcSpawner` seam so the non-blocking / non-raising contract is testable.

## Phases

1. **Task A — verified `down()`.** Re-query is the authoritative post-condition
   (a `docker rm` on an already-gone container returns non-zero while the
   post-condition holds; a `rm` can return 0 yet leave a wedged container). On a
   surviving container or a surviving worktree, raise `IsolationError` and leave
   state + marker in place — the workspace stays visible to
   `fr isolation status`. Marker removal moves to the end. `--force` bypasses the
   open-PR guard only, never the teardown verification.
2. **Task A — image reclamation.** Capture the image before `docker rm`; `rmi`
   after, best-effort and off the verification path (shared/in-use image logs,
   never fatal).
3. **`fr isolation gc` core.** Host-wide discovery unions docker-label
   containers with on-disk worktree dirs under `~/.cache/fr/worktrees/*/*`,
   git-resolving each to its owning repo (state is per-repo, so there is no
   registry to read). Classify → act per the spec table: MERGED→`down()`,
   OPEN→skip, no-PR→warn, orphan(worktree gone)→label-reap, no-state→warn. A
   per-workspace `try/except` keeps one bad teardown from aborting the sweep.
   `--dry-run` and `--format json`.
4. **Dangling `vsc-*` image sweep** inside gc — `rmi` vsc-* images unreferenced
   by any live container, best-effort.
5. **Opportunistic spawn + flock.** `up`/`down` fork a detached
   `fr isolation gc` after their own work (primary auto-trigger; ≤1 stale
   workspace, no daemon). gc takes a host-wide `flock(LOCK_EX|LOCK_NB)`
   (idiom mirrored from `fr_vk.bridge_cli._acquire_lock`, reimplemented locally —
   `fr` must not depend on `fr_vk`); a second concurrent sweep no-ops.
6. **Docs + version bump.** Reconcile the "remember to run `down`" prose in
   fr-isolation / fr-goal / fr-debugging within the 120-line SKILL cap; minor
   version bump (new subcommand + new mandatory behavior).

## Substrate neutrality

Teardown flows through `Target.down()`; discovery + reap are docker-specific and
live in `LocalWorktreeDevcontainerTarget`. gc's classification is
substrate-agnostic. A future k8s `Target` (pods) implements discovery/reap behind
the same seam — out of scope, not foreclosed.

## Coexistence with the bridge

The `fr_vk` bridge already reaps its **VK cloud** workspaces (MCP
`list_workspaces`) on PR-merge — a disjoint resource space from local docker
devcontainers. gc's sweep and the bridge's reaping never touch the same
resources; the "VK/phase-based reaping unchanged" non-goal holds by construction.

## Acceptance

- `isolation-down-verified` — phases 1, 2 (real-docker leg: Test-Plan item 1).
- `isolation-gc-reconciles-merged` — phases 3, 4, 5 (real reap + opportunistic
  trigger: Test-Plan items 3–4).

The spec's `## Test Plan` is post-merge, operator-driven (real Docker on the
Mac — the fake-runner seam cannot prove real teardown).
