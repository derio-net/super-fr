# Auto-archive merged fr plans — design

**Issue:** derio-net/super-fr#334
**Date:** 2026-07-03
**Status:** design

## Problem

The fr lifecycle convention is: a plan lives in
`docs/superpowers/plans/<plan>/` while active, then moves to
`docs/superpowers/implemented/plans/<plan>/` once its work merges. Nothing
**enforces** the archive step, so it gets skipped — fully-implemented plans sit
in `plans/` indefinitely (twice in brain-fr; and *right now* in this repo:
`2026-07-02-cncd-phase1-integration` is 13/13 complete but unarchived).

The tell is always the same: a plan dir in `plans/` whose every phase is
complete. A human has to notice this manually today, because:

- The **mover** exists (`fr archive --all` sweeps `plans/*/`, gate-checks each,
  `git mv`s it, sweeps the spec, runs `repair_repo`) but someone must *know to
  run it*.
- The **per-plan detector** exists (`fr status <dir>` prints "plan complete —
  run `fr archive`") but requires a specific `PLAN_DIR` argument — there is no
  repo-wide, unprompted sweep and no automatic backstop.

This is a detection/enforcement gap, not a mechanism gap. It maps onto issue
#334 option 2 and the repo's own #328 principle: *invariants get a hook/CI
gate, not prose.*

## Goal

Make "merged-but-unarchived" **impossible to silently accumulate**:

1. **Detect** archivable plans repo-wide, on demand (read-only).
2. **Auto-archive** them in one step (the existing bulk mover).
3. **Enforce** via a hard-fail CI tripwire so drift can never reach `main`
   unnoticed.

Non-goal: option 1's "auto-open a housekeeping PR when the final phase merges."
There is no reliable local merge trigger (no webhook in this flow), so that tier
is explicitly out of scope.

## The shared signal (one source of truth)

A **new pure predicate** is the spine of the whole feature:

```python
# packages/fr/src/fr/archive.py
def completed_unarchived_plans(repo_root: Path) -> list[str]:
    """Plan-dir names under docs/superpowers/plans/ that are fully
    locally complete and should be archived. gh-free / offline."""
```

- **Signal:** a plan counts iff every phase satisfies
  `render.plan_locally_complete(phase)` — i.e. `completion.at` is set OR all its
  steps are ticked, for *all* phases. This is the gh-free ("locally complete")
  arm the archive gate already uses for never-dispatched plans, and it is
  exactly what `fr status <dir>` reports as "plan complete."
- **Why gh-free:** plain `pytest` runs offline and cannot observe merged PRs for
  *dispatched* plans. The locally-complete signal is deterministic, offline, and
  conservative (it only flags plans whose every phase is marked done), so it
  never false-positives on in-progress work.
- **Discovery:** glob `docs/superpowers/plans/*/` dirs containing `_meta.yaml`
  (same target selection as `archive_cmd.py`), `parser.parse()` each, apply the
  predicate. Parse failures are skipped (not flagged) — a malformed plan is a
  different problem.

Both the `fr status` repo sweep and the CI tripwire call this one function.
There is no second definition of "merged-but-unarchived."

## Changes

### 1. Pure predicate — `fr.archive.completed_unarchived_plans` (new)

As above. Lives beside the existing archive helpers so it's importable by both
the CLI and the tripwire test. Reuses `render.plan_locally_complete` and
`parser.parse`; no new plan-model logic.

### 2. Repo-wide detection — extend `fr status` (read-only)

`fr status` currently *requires* `PLAN_DIR`. Make it **optional**:

- `fr status` (no arg) → **repo-wide sweep**: lists every plan under
  `docs/superpowers/plans/`, marking each `archivable` (via
  `completed_unarchived_plans`) or `in progress`. When any are archivable, it
  prints the one-step fix: `run \`fr archive --all\` to archive N plan(s)`.
- `fr status <dir>` → unchanged (existing per-plan gh-aware report).
- `--format json` on the no-arg form emits
  `{"archivable": [...], "in_progress": [...]}`.

`fr status` stays **read-only / allowlist-safe** — the sweep never mutates. It
only *detects* and *points at* the mover.

### 3. Auto-archive — `fr archive --all` (existing; the one-step move)

No new mutating command. `fr archive --all` already is the auto-archiver:
gate-checked bulk `git mv` + spec sweep + `repair_repo`, all staged for one
operator commit. The `fr status` sweep's nudge points here. This satisfies the
"auto-archive" scope: detection surfaces the drift, one command clears it.

(If `fr archive --all` needs any hardening to archive the never-dispatched
locally-complete cncd plan cleanly, that is done here — but the existing gate's
`plan_locally_complete` arm already covers never-dispatched plans, so no change
is expected.)

### 4. Hard-fail CI tripwire (new)

`tests/unit/test_tripwire_unarchived_plans.py`, following the shape of
`test_tripwire_isolation_marker.py` / `test_tripwire_claude_p.py`:

- **Unit tests** on `completed_unarchived_plans` against fixture plan dirs: a
  fully-complete plan is flagged; an in-progress plan is not.
- **Repo-level integration test** — the backstop. The signal is
  **complete on `origin/main`** ∩ **still present in the working-tree
  `plans/`**:
  - the *origin/main* arm materializes `origin/main`'s `plans/` subtree and runs
    the same `completed_unarchived_plans` predicate on it, so it fires only on a
    plan that **actually merged complete**. This excludes both a brand-new plan
    (not on main) and the PR that **finishes** a multi-PR plan whose dir landed
    on main incomplete (main is still incomplete there);
  - the *working-tree* arm lets the PR that **archives/removes** a stale plan
    pass (the dir is gone from the tree → not an offender).
  So it fires only on a plan that merged complete and was then left unarchived —
  exactly issue #334's tell — making the post-merge archive non-skippable, while
  never blocking the PR doing the completing or the archiving. Checking
  *completeness* on main (not mere presence) is what avoids red-flagging the
  finishing PR of an incrementally-executed plan.
- `REPO_ROOT = Path(__file__).resolve().parents[2]`. Reads only the local
  `origin/main` ref; the `test` CI job gains `fetch-depth: 0` so the ref is
  present, and the test skips cleanly if it isn't.

### 5. Archive the lingering cncd plan (delivery, not code)

`2026-07-02-cncd-phase1-integration` is 13/13 complete, never dispatched, still
in `plans/` — a live instance of exactly this bug. Archive it (`fr archive
docs/superpowers/plans/2026-07-02-cncd-phase1-integration`) so the new repo-level
tripwire ships **green**. This doubles as the feature's live end-to-end proof.

### 6. Version bump

User-observable CLI + behavior change → patch bump via `scripts/bump-version.py`
(per CLAUDE.md release rule). `fr status`/`packages/*/src` changed.

## Files touched

| File | Change |
|---|---|
| `packages/fr/src/fr/archive.py` | + `completed_unarchived_plans(repo_root)` |
| `packages/fr/src/fr/commands/status_cmd.py` | make `PLAN_DIR` optional; repo-wide sweep (text + json) |
| `packages/fr/src/fr/cli.py` | adjust `status` command signature if needed |
| `tests/unit/test_tripwire_unarchived_plans.py` | new: unit + repo-level tripwire |
| `tests/unit/test_status_cmd.py` (or existing) | repo-wide sweep tests |
| `docs/superpowers/plans/2026-07-02-cncd-phase1-integration/` | archived → `implemented/plans/` |
| version files (4) via `bump-version.py` | patch bump |

## Testing strategy (TDD)

Each unit of behavior is red→green→(refactor):

1. `completed_unarchived_plans` — fixtures for complete / in-progress / malformed
   → predicate. **This is the core; write its tests first.**
2. `fr status` no-arg sweep — text output lists archivable plans + nudge; json
   shape; single-plan path unchanged.
3. Tripwire — unit tests on fixtures + the live repo-level assertion (goes green
   only after step 5 archives cncd).

## Test Plan

None — pure code + CI (CLI command, a pure predicate, a pytest tripwire, and a
docs move). No service/bot/infra deploy, so no post-merge operator-driven test
plan. Verification is the full `uv run pytest` suite (including the new
tripwire) + `fr status` / `fr archive --all` exercised locally against the cncd
plan.

## Implementation Plans

| Plan | Target repo | Slug | Status |
|------|-------------|------|--------|
| 2026-07-03-auto-archive-merged-plans | `derio-net/super-fr` | `2026-07-03-auto-archive-merged-plans` | — |

## Risks / edge cases

- **False positives on in-progress plans.** Mitigated: the predicate requires
  *every* phase locally complete; a plan mid-flight has un-ticked steps / unset
  `completion.at` and is not flagged.
- **A plan legitimately kept in `plans/` while its archive-PR is pending.** The
  hard-fail is intentional here — #334's whole point is that the follow-up
  archive gets forgotten. CI red is the forcing function; the fix is to archive,
  which is one command. Enforcement is **post-merge**: the plan must be complete
  on `origin/main` (the origin/main arm above), so the feature PR that finishes
  it is never blocked — the guard fires on the next CI run after merge.
- **Forcing-red lands on parallel PRs during the archive window.** By design (CI
  red is the forcing function): once a complete plan merges to `main`, every
  *other* open PR is red until the archive PR lands (the archive PR itself is
  green — it removes the dir from `plans/`). The assertion message names the
  unarchived plan and the one-command fix so a contributor hit by a red they
  didn't cause understands why.
- **Botched archive (copy left in `plans/`).** Surfaced live: the cncd plan was
  copied to `implemented/plans/` but never removed from `plans/`, so `fr archive`
  would `git mv` it *into* the existing dir (`implemented/plans/X/X`).
  `archive_plan_dir` now refuses when the destination already exists
  (`test_archive_dest_guard.py`), and the stale copy is removed with `git rm`.
- **Malformed / partially-migrated plan dirs.** Skipped by the predicate (parse
  failure ≠ complete), so they can't wedge CI red for the wrong reason.
- **gh-observation drift.** The tripwire deliberately uses the offline signal,
  not merged-PR observation, so it's a conservative subset of `fr archive --all`'s
  gate — it never flags a plan the mover would refuse.
