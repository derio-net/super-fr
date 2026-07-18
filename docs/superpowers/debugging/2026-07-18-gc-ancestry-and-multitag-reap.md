# gc leaves merged-but-PR-less workspaces (and multi-tagged images) unreaped

Date: 2026-07-18 · Repo: derio-net/super-fr · Branch: `fix/gc-ancestry-and-multitag-reap`

## Symptom & reproduction

Cleaning up isolation workspaces on the Mac, `fr isolation gc` had reaped only
1 of many stale containers; 17 workspaces were tracked, and four `vsc-*`
devcontainers (`feat/fr-dispatch-seam`, `feat/shutdown-degraded-mode`,
`feat/nut-shutdown-corrections`, `feat/openapi-client`) had run for days-to-weeks
despite their work being fully merged. `fr isolation gc --dry-run` classified all
four `no-pr → warned`. A second, smaller symptom: two dangling images sharing one
image id reported `dangling-image → reap-failed`.

Repro of defect 1 (per branch): the branch is 0 commits ahead of `origin/main`
yet `gh pr view <branch>` returns "no pull requests found":

```
$ git merge-base --is-ancestor feat/fr-dispatch-seam origin/main && echo ANCESTOR
ANCESTOR
$ gh pr view feat/fr-dispatch-seam --json state
no pull requests found for branch "feat/fr-dispatch-seam"
```

Repro of defect 2:

```
$ docker image inspect d2034d4d1669 --format '{{.RepoTags}}'
[vsc-fix__…-cwd-…-features:latest vsc-fix__…-pwd-env-…-features:latest]
$ docker rmi d2034d4d1669
Error response from daemon: conflict: unable to delete d2034d4d1669
  (must be forced) - image is referenced in multiple repositories
```

## Evidence

- `_gc_one` (`packages/fr/src/fr/isolation/local.py`) classifies purely on
  `_pr_from` state: `MERGED → reap`, `OPEN → skip`, else → `no-pr → warned`.
  It never asks git whether the branch's commits already reached the default
  branch.
- **Refuted** hypothesis H1 ("`gh pr view` can't resolve a deleted remote
  branch"): `gh pr view <branch>` returns `MERGED` correctly even after the
  remote branch is deleted. So merged *PRs* are still found.
- **Confirmed** hypothesis H2: the four branches genuinely have **no PR** — the
  work reached `main` under a different PR/branch (rebased / re-authored), so
  there is no PR object for `_pr_from` to find, while the commits *are* ancestors
  of `origin/main`.
- `_sweep_dangling_images` reaps via `docker rmi <image_id>`; `_vsc_images`
  yields one row per tag, so a multi-tagged image is asked to `rmi <id>` — the
  exact call Docker rejects for images referenced in multiple repositories.

## Root cause

1. **gc is blind to PR-less merges.** A workspace whose branch's changes have all
   reached `origin/<default>` but has no discoverable PR hits the `no-pr`
   catch-all and warns *forever*, because classification is PR-state-only and
   never consults whether the work already landed. The `#354` "≤1 stale"
   invariant only ever bounded the *merged-PR* class; the no-PR bucket is
   unbounded.
2. **Image reap keys off the image id, not the tag.** `docker rmi <id>` fails on
   any image carrying more than one repo tag.

## Fix

1. Before the `no-pr` return, reap as **`merged-by-content`** iff *all* hold
   (conservative — any git failure ⇒ False ⇒ warn, never reap):
   - `origin/<default>` resolves and exists, AND
   - the branch **changed files** since its merge-base (a pristine or idle branch
     that merely fell behind main changed nothing → not a merge → never reaped;
     this protects the fresh workspace `up` creates at/behind the tip), AND
   - every changed file's **final content is already on** `origin/<default>`
     (`branch_changes_present`, local.py:119 — content comparison, **squash /
     rebase / merge-commit safe**), AND
   - the worktree is **clean** (`git status --porcelain` empty — no uncommitted
     work to lose).
   Teardown reuses the same sibling-`down()` path as the merged-PR case.
   Documented residual (clean-worktree-guarded): genuinely convergent content —
   the identical change landing independently on main — reads as merged. A stale
   local `origin/<default>` ref only *defers* a reap, never causes a wrong one.
2. Reap dangling images by the tagged ref `repo:tag`, not the image id, so each
   tag is untagged and the last one frees the layers — no `--force`, no multi-tag
   conflict.

## Rejected hypotheses

- H1 (deleted remote branch hides a merged PR) — refuted empirically; `gh pr
  view <branch>` still returns `MERGED`.
- **`git merge-base --is-ancestor` for the merge check** — rejected after review
  feedback: the org **squash-merges** as its enduring pattern, and a squash lands
  a *new* commit on main, leaving the branch **not** an ancestor. An is-ancestor
  check would false-negative on exactly the dominant case, and worse, would reap a
  pristine-but-behind idle workspace (ancestor + strictly-behind + clean, yet no
  merge ever happened). Switched to **content comparison**
  (`branch_changes_present`), which the codebase already provides precisely
  because "an ancestry/patch-id check would false-negative on squash." The
  "branch changed files" guard distinguishes a real merge from a branch that only
  fell behind.
- "Reap any ancestor" — rejected: `up` bases new branches on `origin/<default>`,
  so a fresh workspace is trivially an ancestor; reaping on ancestry alone would
  nuke pristine new workspaces.
