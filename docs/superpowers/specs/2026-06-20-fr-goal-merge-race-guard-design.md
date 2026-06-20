# fr-goal merge-race guard — design

**Issue:** [#320](https://github.com/derio-net/super-fr/issues/320) ·
**Date:** 2026-06-20 · **Slug:** `fr-goal-merge-race-guard`

## Problem

When an fr-goal run **delegates the build (and PR creation) to a subagent**,
the subagent opens the PR as its final action — so the PR is open and
mergeable *before* fr-goal's review-and-fix pass (step 7) runs. If the
operator merges during that window, the later fix commits push onto an
**already-merged branch** and silently never reach `main`.

This has recurred **3×**. The most recent occurrence (brain-fr PR #4) shipped
two **critical** fixes to a merged branch ~19h before the fix commit existed;
they were recovered only because brain-fr had auto-delete-on-merge **off**.

**super-fr itself has `deleteBranchOnMerge: true`** — so here an orphaned fix
commit would be near-unrecoverable. The stakes for the repo that *owns this
skill* are higher than the repo where the bug was first seen.

### Root cause

fr-goal's written order — implement (6) → review-and-fix (7) → deliver one
PR (8) — is safe only when one inline agent runs it (the PR is genuinely
last). The bug appears when PR creation is **delegated to the implementing
subagent**, reordering step 8 ahead of step 7. Nothing in the skill currently
forbids "implement AND open the PR" as one delegated unit.

`fr-execute` step 5 ("Open the PR") is the concrete trigger: fr-goal step 6
invokes `fr-execute` per phase, and its step-5 PR-open fires before fr-goal's
review.

## Decisions (operator Q&A, 2026-06-20)

1. **Enforcement = Hybrid (hook + prose).** Code-enforce the high-frequency
   pre-push guard (#2) as a new PreToolUse(Bash) hook; keep close-out
   verification (#3) and the ordering/wording changes (#1, #4) as skill prose.
   Tight blast radius, the dangerous action is physically blocked, and the
   once-per-run interactive close-out stays squash-aware prose.
2. **PR visibility = Draft from start.** The build only pushes the branch; the
   orchestrator opens a **draft** PR for visibility, and runs `gh pr ready`
   **only after** the review-fix pass lands. GitHub blocks merging a draft, so
   the operator physically cannot merge during review — and the "Draft" label
   is itself the "review pending — do not merge yet" signal (fix #4).

## Squash-merge correctness (affects fix #3)

The issue proposed `git merge-base --is-ancestor <fix-sha> origin/main` for
close-out verification. super-fr has **squash merge enabled** (confirmed:
`squashMergeAllowed: true`), and squash rewrites SHAs — so the branch tip is
**not** an ancestor of `main` after a squash merge, and the proposed check
**false-negatives**. The close-out verification must instead be
**content-based**: confirm the PR is `MERGED` *and* the branch's changes are
present in `origin/main` (e.g. `git fetch origin main` then
`git diff --quiet origin/main -- <changed paths>` shows nothing missing).

## Design

### A. New hook — `fr-merged-pr-push-guard.sh` (fix #2, code-enforced)

A second `PreToolUse(Bash)` hook, registered alongside `fr-isolation-guard.sh`
in `plugins/super-fr/hooks/hooks.json`.

**Behaviour:**

- Acts only when (a) the tool is `Bash`, (b) a pipeline **sentinel exists for
  the session** (same `$FR_SENTINEL_DIR/$session_id.json` the isolation guard
  uses — scopes the guard to active fr pipelines, matching blast radius), and
  (c) the command contains a `git push` subcommand.
- When those hold, it `cd`s to the command's declared `.cwd` and reads the
  **current branch's** PR state: `gh pr view --json state,mergedAt`.
  - PR `state` is `MERGED` or `CLOSED` → **deny** with a reason explaining the
    orphan risk and pointing at cherry-pick-onto-main / fresh-branch recovery.
  - Any other state (`OPEN`, draft) → **allow**.
- **Fail-open** on every ambiguity: no sentinel, no `git push` in the command,
  no PR for the branch (first push), `gh`/`jq` absent, network/auth failure,
  unparseable output → `exit 0` (allow). The hook is a discipline backstop,
  not a security boundary (same contract as `fr-isolation-guard.sh`); failing
  closed would block legitimate first pushes and all offline work.
- Scope note in the script: it checks the **checked-out** branch's PR, the
  near-universal case for `git push`; an explicit cross-branch
  `git push origin HEAD:other` is out of scope (documented, not handled).

**Why a separate hook, not an extension of `fr-isolation-guard.sh`:** that
guard exits 0 for worktree-cwd commands — and pushes run *from* the worktree —
so it never sees pushes. The new concern (PR state, regardless of cwd) is
orthogonal; a separate, independently-tested hook keeps both single-purpose.

### B. fr-goal SKILL.md prose (fixes #1, #3, #4)

- **Step 6 (Implement):** the implementing layer — inline agent *or* a
  delegated subagent (multi-repo step 3) — **pushes the branch only; it never
  opens the PR.** A subagent's mandate ends at "branch pushed." PR creation is
  the orchestrator's, at step 8, after step 7.
- **Bridge (after build, before review):** for visibility, the orchestrator
  opens a **draft** PR now. Drafts are GitHub-unmergeable, so the review
  window stays closed and the "Draft" badge signals "review pending."
- **Step 7 (Review):** unchanged in intent; fixes push to the draft branch.
  The pre-push guard (hook A) protects these pushes.
- **Step 8 (Deliver):** the PR becomes mergeable **only after** step 7's fixes
  are committed — run `gh pr ready` now (and only now). Finalize the body
  (summary, spec/plan paths, findings+fixes, back-loaded manual phase, Test
  Plan if any). **Hand-off wording (#4):** never announce "PR is up / ready to
  merge" until fixes are in; say "review pending — do not merge yet" while the
  PR is a draft, and only "reviewed and ready to merge" after `gh pr ready`.
- **Step 9 (Post-merge close-out):** after the operator reports the merge,
  **verify the fix reached `main`** before declaring done — squash-aware (see
  above): confirm PR `MERGED` and the branch's changes are present in
  `origin/main`. If anything is missing → **stop**, surface it, recover
  (cherry-pick onto `main` / fresh PR). Only then `fr archive` / `fr isolation
  down`.

### C. fr-isolation SKILL.md prose (documents fix #2's enforcement)

In the exec-bridge "Push and PR creation default to the HOST" area: before
pushing to a feature branch, the branch's PR must not be `MERGED`/`CLOSED`
(pushing there orphans the commit). A `PreToolUse` hook
(`fr-merged-pr-push-guard.sh`) now enforces this during fr pipelines — document
it so a denied push is understood, not worked around.

### D. fr-execute SKILL.md prose (closes the concrete trigger)

Step 5 ("Open the PR") gets a caveat: **under fr-goal LOCAL mode, do not open
a per-phase PR** — push the branch only; the single PR is fr-goal's step 8,
opened (as a draft) by the orchestrator post-review. Per-phase PRs remain the
behaviour for the standalone **dispatched** (Issue/VK) flow.

## Scope / out of scope

- **In:** `fr-goal`, `fr-isolation`, `fr-execute` SKILL.md; new hook +
  `hooks.json`; hook unit tests; version bump 3.4.0 → **3.4.1** (patch — a
  bugfix tightening an existing workflow; touches `skills/**` + a new hook =
  user-observable, bump required).
- **Out:** the dispatched VK/Issue flow's per-phase-PR model (unchanged);
  willikins postmortem (read-only reference, not modified); operator-side
  `~/.claude/rules/fr-plan-override.md` (mirrors override-routing, not step
  bodies — no mirror needed).
- **No Test Plan section:** this deliverable is skill/hook code, not a
  deployment; correctness is proven by the pytest hook tests, not a post-merge
  operator-driven run.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-06-20-fr-goal-merge-race-guard | `derio-net/super-fr` | `2026-06-20-fr-goal-merge-race-guard` | — |
