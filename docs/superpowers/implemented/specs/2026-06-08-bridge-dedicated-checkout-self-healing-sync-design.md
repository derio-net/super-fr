# Bridge dedicated-checkout + self-healing sync — design

**Issue:** #286 — Bridge `_pull_managed_repo` can't recover from an
out-of-band `main` ref move (VK force-update) → dispatch silently wedges.

**Date:** 2026-06-08
**Status:** approved (fr-goal batched Q&A, 2026-06-08)

## Problem

The bridge's per-tick managed-repo sync
(`_pull_managed_repo`, `packages/fr-vk/src/fr_vk/bridge_cli.py`) runs
`git fetch && git checkout main && git pull --ff-only`, best-effort with
errors swallowed. It is **not idempotent against an out-of-band branch ref
move** and silently wedges dispatch when one happens.

### Root cause (observed 2026-06-08 on `derio-net/runs-fr`)

The bridge keeps a long-lived checkout with `main` checked out and reads
plan/phase state from that **working tree** (`discover_plans`,
`packages/fr-dispatch/src/fr_dispatch/__init__.py`).

VibeKanban manages the **same repo** via worktrees. On PR merge + card→Done
it runs `git fetch origin --quiet` + `git branch -f main origin/main` from a
worktree (permitted because `main` isn't checked out *there*), force-moving
the local `main` ref to the merged commit **without touching the bridge's
index/working tree**.

Result: `HEAD/main == origin/main == <merged>` but index+worktree frozen at
the pre-merge parent → git reports staged deletions. `_pull_managed_repo`
can't recover: `checkout main` → main is a no-op, `pull --ff-only` is
"Already up to date". The bridge reads a stale plan (phase shows incomplete)
and never advances. Reflog signature:
`main@{...}: branch: Reset to origin/main` with **no** matching HEAD
pull/merge entry.

The deeper fault is a **single-source-of-truth violation**: the bridge and
VK share one checkout, with the bridge holding `main` checked out while VK
force-updates it from worktrees. Two independent writers, one working tree.

## Decision summary (batched Q&A, 2026-06-08)

| Decision | Choice |
|---|---|
| Scope | **Fix + architectural refactor together** — close the SSOT violation now, not just the surgical symptom |
| Desync metric channel | **Dedicated counter** `willikins_vk_bridge_repo_desync_total{repo="owner/name"}` (not `failure_total`, so a self-healed desync never reads as a tick failure) |
| Post-merge verification | **Live repro + self-heal proof** against a real managed checkout |

## Design

### 1. Dedicated bridge-owned checkout (the SSOT fix)

The bridge stops sharing VK's checkout. For each managed repo it maintains
its **own** checkout that nothing else writes to:

- **Location:** `<base>/<name>`, where `base` is `FR_BRIDGE_CHECKOUT_DIR`
  (read via `bridge_env("CHECKOUT_DIR")`, with the legacy
  `VK_BRIDGE_CHECKOUT_DIR` fallback) or, unset, `~/.cache/fr/bridge-checkouts`.
  `<name>` is the repo short name, so `discover_plans`'
  `_repo_checkout_root` (`FR_REPOS_DIR/<name>`) resolves to it when the loop
  sets `FR_REPOS_DIR = <bridge_checkout>.parent`.
- **Clone-if-missing:** if `<base>/<name>/.git` is absent, the bridge clones
  it from the configured repo's **origin URL** (`git -C <configured> remote
  get-url origin`). Cloning from the real GitHub origin — not the local
  shared checkout — guarantees `fetch origin` + `reset --hard origin/main`
  always reaches true head-of-main. First tick on a fresh pod clones; every
  later tick reuses.

VK keeps using its own `~/repos/<name>` (or wherever it manages worktrees);
the bridge no longer touches it. With the bridge as the **sole writer** of
its checkout, VK's out-of-band ref moves can never desync it. SSOT restored.

**Why a dedicated checkout, not "read plan state from git objects."** The
issue's architectural note lists both. Reading from git objects would
require rewriting `parse()` (`packages/fr/src/fr/parser.py`), which is
deeply filesystem-path-coupled — `Path.is_dir()`, `Path.iterdir()`,
`Path.read_text()`, `_find_repo_root` walking up for `.git`, and
`refs.resolve_spec_ref`. That parser is shared by the CLI, the test suite,
and dispatch; reimplementing its I/O against `git cat-file`/`git ls-tree`
is a large, high-risk blast radius. The dedicated checkout closes the same
root cause (the second writer) while leaving `parse()` / `discover_plans`
untouched — they keep reading a filesystem path; only *which* path, and
*who else writes to it*, changes.

### 2. Idempotent, self-healing sync

`_pull_managed_repo` is replaced with a sync that is idempotent against ref
state and self-heals any dirty tree, operating on the bridge-owned checkout:

```
git fetch origin
# detect desync BEFORE healing (drives the metric/log):
#   working tree dirty  =>  git status --porcelain non-empty
git checkout main          # ensure the correct branch is checked out
git reset --hard origin/main
```

`reset --hard origin/main` reconciles **any** out-of-band ref move or dirty
tree each tick — including the exact bug signature (HEAD already at the
merged commit, tree frozen at the parent). It is safe because the bridge
solely owns this checkout and only ever reads it; there are no genuine local
edits to lose (the "dirty" delta is always a lagging tree).

**Resilience preserved.** Every git command stays best-effort: a failure
logs a clear warning and the tick continues against the (possibly stale)
checkout — *a stale dispatch beats no dispatch*. The `--ff-only`
"Already up to date" trap is gone because reset is unconditional, not a
fast-forward that no-ops on an already-moved ref.

### 3. Desync observability metric

When the pre-reset working tree is **dirty** (the bug signature — a clean
tree merely behind `origin/main` is a normal fast-forward, not a desync),
the bridge:

- emits a **dedicated counter**
  `willikins_vk_bridge_repo_desync_total{repo="owner/name"}` via a new
  `MetricsPusher.push_repo_desync_total(repo=...)`, and
- logs a clear `WARNING` naming the repo and the dirty paths.

Kept distinct from `failure_total` so a self-healed desync never trips
failure dashboards/alerts. In the new architecture desync should be ~0
(the bridge is the sole writer), so any nonzero reading is a real anomaly —
e.g. someone manually touched the bridge checkout, or a deeper invariant
broke.

After the reset, a post-sync assertion (`HEAD == origin/main` and tree
clean) verifies the heal succeeded; failure logs loudly (heal-failed),
still best-effort.

## Components changed

- **`packages/fr-dispatch/src/fr_dispatch/metrics.py`** — add
  `push_repo_desync_total(self, *, repo: str)` to `MetricsPusher`
  (`<namespace>_repo_desync_total{repo="..."}` counter) and a no-op override
  on `NullMetrics`.
- **`packages/fr-vk/src/fr_vk/bridge_cli.py`**
  - `_bridge_checkout_base()` — resolves the base dir
    (`FR_BRIDGE_CHECKOUT_DIR` / `~/.cache/fr/bridge-checkouts`).
  - `_ensure_bridge_checkout(configured_repo, name)` — clone-if-missing the
    bridge-owned checkout from the configured repo's origin URL; returns the
    path or `None` on failure.
  - `_pull_managed_repo(checkout_path) -> bool` — rewritten to
    `fetch origin` → detect dirty tree → `checkout main` →
    `reset --hard origin/main`; returns whether a desync was detected.
    (Name retained so existing monkeypatch sites keep working; single
    positional arg preserved.)
  - `main()` loop — resolve `owner_name` first, ensure+sync the bridge
    checkout, push `repo_desync_total` (labelled with `owner_name`) when the
    sync reports a desync, point `FR_REPOS_DIR` at the bridge checkout's
    parent, then `discover_plans`.

## Tradeoffs

- A dedicated checkout per managed repo roughly doubles disk for those repos
  and adds a one-time clone on first tick. Acceptable: the managed-repo set
  is small, and the clone is amortized across all later ticks. (A
  `--reference`/`--shared` clone could save disk but would couple the
  bridge's object store back to the shared checkout — re-introducing a
  shared-state seam — so a plain clone from origin is preferred.)

## Test plan

### Automated (in the PR, TDD)

- **Self-heal unit/integration:** construct a bridge checkout whose tree is
  dirty while `HEAD == origin/main` (the bug signature); run the sync; assert
  the tree is reconciled to `origin/main`, `push_repo_desync_total` fired
  with the right `repo` label, and `discover_plans` then sees the correct
  (post-merge) plan state.
- **Normal advance is not flagged:** origin advances by a clean commit (the
  existing bare+clone fixture); assert the bridge checkout fast-forwards via
  reset, the new plan dir appears, and `push_repo_desync_total` is **not**
  called.
- **Clone-if-missing:** with the bridge checkout absent, assert the sync
  clones it from origin and discovery resolves against it.
- **Ordering preserved:** sync still precedes `discover_plans`.
- **Resilience:** a failing git command logs-and-continues; the tick still
  returns 0.

### Test Plan (post-merge — operator-driven)

The bug only surfaced live on `derio-net/runs-fr`. After merge + release,
verify in the deployed environment:

1. On the bridge's managed checkout, induce the out-of-band desync exactly
   as VK does: from a worktree, `git fetch origin && git branch -f main
   origin/main` so `HEAD == origin/main` but the bridge checkout's tree lags.
   (Or, in the dedicated-checkout world, dirty the bridge checkout directly
   to simulate drift.)
2. Run one bridge tick (`python -m fr_vk.bridge`).
3. Assert: the bridge checkout's tree now matches `origin/main` (clean,
   `HEAD == origin/main`); `willikins_vk_bridge_repo_desync_total{repo=...}`
   was pushed; the previously-wedged plan/phase advances (dispatch resumes).

## Version bump

Touches `src/` (`fr_dispatch`, `fr_vk`) → version bump required per
`CLAUDE.md`. Patch bump (`scripts/bump-version.py patch`).

## Implementation Plans

| Plan | Repo | File | Depends on |
| ---- | ---- | ---- | ---------- |
| 2026-06-08-bridge-dedicated-checkout-self-healing-sync | `derio-net/super-fr` | `2026-06-08-bridge-dedicated-checkout-self-healing-sync` | — |
