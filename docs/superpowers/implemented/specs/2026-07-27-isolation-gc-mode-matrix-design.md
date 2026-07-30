# Isolation GC across devcontainer, host-worktree, and external modes

**Issue:** derio-net/super-fr#423
**Status:** design
**Date:** 2026-07-27

## Problem

`fr isolation gc` is documented as *the* host-wide lifecycle reconciler —
runnable standalone or on a schedule, and fired opportunistically after every
`up`/`down`. That contract only holds in devcontainer mode. Today:

```console
$ FR_ISOLATION_TARGET=worktree fr isolation gc --dry-run --format json
error: gc requires docker; host-worktree gc is future work — …
$ fr isolation gc            # inside a prepared (external) container
error: gc not supported in external mode — externally managed.
```

Both are exit-2 hard failures with no machine-readable output, so a docker-less
pod or a prepared container has **no reconciler at all**: workspaces persist
until a human remembers `fr isolation down` in the originating session. The
observed failure (recurring bookmark-drain agent) is precisely that: a trace PR
merged asynchronously *after* its session exited, leaving the workspace forever.

Three further gaps surfaced while auditing the surface for this issue:

1. **Discovery misses fr-owned workspaces at custom paths.**
   `_discover_workspaces()` unions docker-labelled containers with directories
   under `~/.cache/fr/worktrees/<repo>/<branch>`. A workspace created with
   `fr isolation up --path /somewhere/else` — the shape VK and other runners
   use — is invisible to gc in *every* mode, including devcontainer.
2. **Stale state records are never reconciled.** If a worktree is removed out of
   band (`rm -rf`, a runner reaping its own workspace), the fr state JSON at
   `<git-common-dir>/fr/isolation/<branch>.json` survives forever. It is not
   discoverable (discovery is directory/container-driven), so `fr isolation
   status` keeps reporting a workspace that does not exist.
3. **Opportunistic triggers are mode-blind.** `HostWorktreeTarget._spawn_gc` is
   a deliberate no-op ("the sweep is docker-coupled") and `HostWorktreeTarget.up`
   never called it anyway; `ExternalTarget` has no spawn at all. Additionally the
   `gc` CLI resolves its target from `Path.cwd()` directly — after a `down` that
   removed the operator's cwd, that raises a bare `FileNotFoundError` traceback
   rather than the clean exit-2 every sibling command produces via `_resolve_repo`.

## Non-goals

- **fr does not reconcile arbitrary Git worktrees.** A plain `git worktree add`
  made by other automation is not fr-owned and must never be reaped. gc's
  discovery deliberately never calls `git worktree list`; ownership is proven by
  an fr state file, the fr worktree cache root, or a devcontainer label.
- No daemon, no host registry of repos. gc stays "sweep what this invocation can
  prove it owns".
- No new merge classifier. The existing conservative merged / merged-by-content /
  open / no-pr ladder is reused verbatim across modes.

## Decisions

Operator-owned decisions for this run were made autonomously (the session is
non-interactive) and are recorded here as the contract; each is a
smallest-safe-change choice consistent with the issue's "Desired outcome".

| # | Decision | Rationale |
|---|---|---|
| D1 | Host-worktree gc runs the **same reconciler** as devcontainer mode, with the docker-only steps (container discovery, container reap, `vsc-*` image sweep) skipped, not faked. | Issue outcome 1. The merge/content/cleanliness checks are substrate-neutral already; only discovery and teardown were docker-coupled. |
| D2 | External mode returns a **structured non-destructive verdict** (`verdict="external"`, `action="skipped"`) and exits 0, instead of refusing with exit 2. | Issue outcomes 2 + 3: `--format json` must be useful in every supported mode. fr cannot tear down a preparer-owned checkout, so it reports who owns cleanup instead of failing. |
| D3 | Discovery gains a third, ownership-proving source: **fr state files for the invoking repo** (`list_states(self.repo_root)`). | Fixes gap 1 (custom `--path` workspaces) and enables gap 2 in all modes without widening scope to unrelated worktrees. |
| D4 | A discovered workspace whose **worktree is gone and has no container** has its *state record* deleted (`verdict="orphan"`, `action="reaped"`, detail `stale state record`). In devcontainer mode this requires a **healthy docker probe** first; host-worktree mode is unconditionally eligible (no containers exist by construction). | Fixes gap 2 while preserving the #354 invariant that a *failed* docker query is never read as "no container". |
| D5 | `up`/`down` in host-worktree mode **do** spawn the detached sweep; external mode deliberately does **not**, and says so in its docstring + skill text. | Issue outcome 5. A prepared container's lifecycle belongs to its preparer; a host-wide sweep from inside it would be scope creep. |
| D6 | `fr isolation gc` gains `--repo` (default `.`) and resolves it through `_resolve_repo`. | Unattended cron/agent runs need to name the repo; a deleted cwd degrades to exit 2 with guidance instead of a traceback. |
| D7 | Version bump: **minor** (3.19.0). | A previously-refused command now works in two modes — a user-visible workflow addition per AGENTS.md. |

## Design

### Mode matrix (the contract this spec pins)

| Surface | devcontainer | host-worktree | external |
|---|---|---|---|
| `up` | worktree + container; spawns gc | worktree only; **spawns gc** (new) | adopts checkout; **no spawn**, by design |
| `status` | full (docker probe) | `container="n/a (host)"` | `mode=external`, `pr=None` |
| `restart` / `stats` | supported | refuse (externally managed) | refuse (externally managed) |
| `down` | container + worktree + state; spawns gc | worktree + state; **spawns gc** (new) | state + marker branch claim only |
| `gc` | full sweep | **full sweep minus docker** (new) | **structured `external` verdict** (new) |
| `verify-merge` | supported | supported (git + host `gh`, no docker) | refused |
| `status --push-check` | supported | refused (needs an in-container probe) | refused |

### Discovery and the ownership boundary

`_discover_workspaces()` unions three sources, each of which is *proof of fr
ownership*:

1. **docker labels** (`devcontainer.local_folder`) — devcontainer mode only;
   overridden to `[]` in host-worktree mode.
2. **the fr worktree cache** — `~/.cache/fr/worktrees/<repo>/<branch>`.
3. **fr state files for the invoking repo** — `list_states(self.repo_root)`
   (new). This is the only source that finds a workspace at a custom `--path`
   or a state record whose worktree has vanished.

Nothing enumerates `git worktree list`. A directory that is a git worktree but
has no fr state and lives outside the cache root is simply never seen; one that
lives *inside* the cache root but has no state is reported `no-state` /
`warned` — visible, never touched. Legacy automation that used plain
`git worktree add` cleans up with `git worktree remove` / `git worktree prune`;
that boundary is documented in the skill.

### Classification ladder (unchanged, now shared by both worktree modes)

```
worktree gone ─┬─ container present ────────────→ orphan / reaped   (docker only)
               └─ no container ─┬─ state present → orphan / reaped  (stale state record, D4)
                                └─ no state      → orphan / skipped
worktree present ─┬─ no fr state ───────────────→ no-state / warned
                  ├─ PR MERGED ─────────────────→ merged / reaped
                  ├─ PR OPEN ───────────────────→ open / skipped
                  ├─ no PR, changes on origin/<default>, clean tree
                  │                             → merged-by-content / reaped
                  └─ otherwise ─────────────────→ no-pr / warned
```

`--dry-run` maps every `reaped` to `would-reap` and mutates nothing, in every
mode. Per-workspace failure isolation and the host-wide `flock` are unchanged,
so a concurrent sweep still short-circuits to an empty report.

### Implementation seams

The reconciler stays on `LocalWorktreeDevcontainerTarget`; mode differences are
narrow overrides, so the two worktree modes cannot drift:

- `_labelled_containers()` → `[]` in `HostWorktreeTarget`.
- `_sweep_dangling_images(dry_run)` → `[]` in `HostWorktreeTarget`.
- `_stale_state_reapable()` — new predicate. Local: a `docker ps -q` probe must
  return 0 (a broken daemon defers, never mis-reaps). Host: `True`.
- `_spawn_gc()` — the `HostWorktreeTarget` no-op override is removed; `up`/`down`
  call it.
- `ExternalTarget.gc(dry_run)` — returns exactly one `GcAction` describing the
  adopted containment; never mutates.

CLI: `gc` drops the two `_refuse_*` guards, gains `--repo`, and dispatches
through a small structural cast (both targets expose `gc`).

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| isolation-gc-mode-matrix | `derio-net/super-fr` | `isolation-gc-mode-matrix` | — |

## Test Plan

Post-merge, operator-driven (a docker-less pod is the only honest venue for
step 1–2; CI covers the rest as unit/integration tests):

1. On a docker-less pod with `FR_ISOLATION_TARGET=worktree`, run
   `fr isolation gc --dry-run --format json` — exits 0 and emits a JSON array
   (empty or classified), with no docker invocation.
2. On the same pod: `fr isolation up --branch tmp/gc-check`, merge a trivial PR
   from it, then `fr isolation gc` — the workspace is reaped; a second workspace
   with an open PR and a third with a dirty tree survive.
3. Inside a prepared (`mode: external`) container, `fr isolation gc --format
   json` exits 0 with a single `external` / `skipped` entry and the checkout is
   untouched.
4. Create a plain `git worktree add ../scratch` outside the fr cache, run
   `fr isolation gc`, and confirm it is neither reported nor removed.
