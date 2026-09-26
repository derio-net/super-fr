# verify-merge survives later rewrites and checks the fetched branch

## Problem

`branch_changes_present` (`packages/fr/src/fr/isolation/local.py:287`) reports a
file as landed only when every non-blank line the branch ADDED still appears in
`<base_ref>:<path>` (`_branch_change_present_in_file`, `:259`). A merge that
lands AFTER the branch's own merge and rewrites those same lines makes the file
read as `missing`, so `fr isolation verify-merge` says NOT verified for a PR
that is genuinely merged. It fails safe (a STOP), but it blocks every closeout
in a batch queue merged back to back (super-fr#665, #598).

With `.changes/` fragments (#666) a PR no longer edits version lines, so that
half of the repro is mostly gone. The generated acceptance reports
(`docs/acceptance/report_*.{html,md}`) are rewritten by nearly every PR, so that
half still reproduces.

Second half: `LocalWorktreeDevcontainerTarget.verify_merge` (`:992`) passes
`refs=None` to `_verdict`, which then checks only the local `branch` ref
(`refs or [branch]`, `:1068`). A local branch can be stale relative to what was
pushed and merged. `verify_merge_reaped` already resolves and checks the fetched
`origin/<branch>` plus the local one via `_branch_refs` (`:1036`); the
non-reaped path does not.

## Design

### A. A rewritten file counts as landed if the branch's blob was once on the base

In `_branch_change_present_in_file`, when the per-line containment check fails,
fall back to a blob-equality check (option 1 of #598). The fallback runs on EVERY path that would otherwise return False, including the two early returns (path absent on `base_ref`, i.e. deleted later; no added lines) provided the branch itself still has the file. A branch that DELETED the file has no blob to compare, so a pure-deletion file that differs stays a STOP, as today. The file counts as landed
when `git rev-parse <branch>:<path>` equals `git rev-parse <c>:<path>` for some
commit `c` in `merge_base..base_ref` (restricted to commits touching `<path>`,
via `git rev-list <merge_base>..<base_ref> -- <path>`). That is: the branch's
exact content of the file existed on the base after the merge and was later
rewritten by another change.

Properties, all kept:

- **Fails safe.** A blob that never appeared on the base (an orphan commit
  pushed after the merge, a line that never landed) matches no `c` and stays
  `missing`. A commit that deleted the path, an unresolvable rev, or a failed
  git call reads as "no match", never as a pass.
- **Content-based, not ancestry-based**, so squash, rebase and merge-commit all
  behave the same.
- The existing whole-file fast path and per-line containment run first and are
  unchanged; the fallback only adds passes for files they reject.
- Cost is bounded to commits touching the one differing path.

### B. `verify_merge` checks the fetched remote branch too

`verify_merge` resolves refs with `_branch_refs(state.branch, remote)`: fetch the
branch, then check `<remote>/<branch>` AND the local branch (both, as the reaped
path does). Consequences, per the operator's answers:

- A stale local ref can no longer decide alone; the fetched remote ref is
  checked as well.
- Unpushed local commits still refuse (the local ref is still checked), and dirty
  worktrees are unaffected (that is `_reap_hazard`, not touched here).
- `_branch_refs` runs at `repo_root` (refs are shared across linked worktrees) and raises `IsolationError` naming the branch when neither ref resolves.
- A failed fetch of the branch (e.g. GitHub deleted the merged branch) is not a
  verdict: fall back to whichever refs still resolve, as `_branch_refs` does. The
  overall `verified` still requires content present, PR `MERGED` and a successful
  default-branch fetch.

### Non-goals

- Known limit (out of scope, fails safe): if a concurrent merge edited the file elsewhere BEFORE the branch landed and a later merge then rewrote the branch's lines, no base blob equals the branch's blob and the file still reads missing (STOP).
- `isolation/scaffold.py` and `artifacts/commit.py` are being edited by another
  batch (container-git-ownership) and are not touched.
- `_reap_hazard` and the `down`-time check call `branch_changes_present`, so they
  gain fix A (a widened, safety-relevant pass, hence tested below); their own ref selection is unchanged.
- The verdict is not weakened: nothing turns a STOP into a pass except positive
  blob-equality evidence from the base's own history.

## Acceptance

`fr isolation verify-merge` reports a merged branch as verified when a later
merge to the default branch rewrote lines the branch added, provided the
branch's exact file content was present on the base at some point after the
merge; and it checks the fetched remote branch as well as the local one.

## Test Plan

- Unit (real throwaway repos): a branch adds lines to a file, is squash-merged,
  and a later commit rewrites those same lines. `branch_changes_present` reports
  present (red before the fix).
- Unit: an orphan branch content that never landed, plus a later rewrite of the
  file, still reports missing.
- Unit: a file deleted from the base after the merge counts as landed; a branch-side pure deletion stays missing.
- Unit: `_reap_hazard` reports no hazard for a branch whose lines a later merge rewrote, and still reports one for unlanded content.
- Unit: `verify_merge` raises `IsolationError` when neither ref resolves.
- Unit: `verify_merge` with a stale local ref and an advanced fetched
  `origin/<branch>`, and with an unpushed local commit, refuses; a deleted remote
  branch falls back to the local ref.
- Update the acceptance matrix with one row for this behaviour, status `ci`.
- Full test suite, `ruff`, `mypy`.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-26-verify-merge-rewrites | `derio-net/super-fr` | `2026-09-26-verify-merge-rewrites` | — |
