# Journal: 2026-10-03-verify-merge-false-landed

<!-- fr:journal kind=repro scope=debug id=d7aba9008c41 created=2026-10-03T19:52:44+00:00 -->
### d7aba9008c41 · repro · Three gaps in gc's landed checks (#757, #715, #700)

Batch verify-merge-false-landed. Investigation found three independent root causes. The operator chose to fix all three in one PR (2026-10-02).
- #757: a branch landed by `git merge --ff-only` and later reverted reads as landed. `_fork_point` keeps the tip, because no landing merge exists, so `merge_base..branch` is empty.
- #715: a squash whose blob combines a concurrent base edit, followed by a later rewrite of the branch's lines, reads as missing. This fails safe.
- #700: `fr/git.py` has two git seams. `_run_git` has no safe.directory handling, and `git_answer` trusts any enclosing ancestor repo.

<!-- fr:journal kind=root-cause scope=debug id=rc-757 created=2026-10-03T19:57:13+00:00 -->
### rc-757 · root-cause · #757: content alone cannot show where a fast-forwarded branch began

After an --ff-only landing the branch tip is on the base's first-parent line, so `_landing_fork` returns the tip itself. That makes the branch's diff empty, so every change reads as present, and a later revert reads as present too. Nothing in git separates this case from an empty branch. fr already records the evidence at `up`: `IsolationState.base_sha`.

<!-- fr:journal kind=finding scope=debug id=fix-757 created=2026-10-03T19:57:15+00:00 state=fixed -->
### fix-757 · finding [fixed] · #757 fixed: recorded start used as the fork point

`_fork_point(start=)` returns `start` when the walk ends at the tip and `start` is a strict ancestor of it. A `start` that is not an ancestor is ignored, and a failed ancestry check raises. verify_merge, verify_merge_reaped (via `recorded_start`), the gc reap hazard, `_merged_by_content` and `fr archive` all pass it. Tests: `test_branch_changes_present_reverted_fast_forward_with_recorded_start_is_missing`, `..._stays_present`, `test_verify_merge_reverted_fast_forward_uses_the_recorded_base_sha`. The tests were committed red before the fix. Limit: a branch with no surviving record (gc deleted the state, or the branch was not created by `up`) keeps the old behavior.

<!-- fr:journal kind=hypothesis scope=debug id=h-715 created=2026-10-03T20:00:09+00:00 -->
### h-715 · hypothesis · #715: the squash's patch carries the branch's lines when its blob cannot

A concurrent base edit makes the squash blob a combination of both edits, so blob equality can never match it. The squash commit's own first-parent patch, though, adds every non-blank line the branch added. Treating such a commit as the landing gives the same soundness as blob equality. The existing revert logic (held blobs, inverse patch) runs unchanged after it. Repro test committed red.

<!-- fr:journal kind=root-cause scope=debug id=rc-715 created=2026-10-03T20:01:04+00:00 -->
### rc-715 · root-cause · #715: the landing was recognised by its blob alone

`_branch_blob_was_on_base` matched only `new == blob`. A squash over a concurrent base edit never writes the branch's blob, so with the lines later rewritten nothing matched. Confirmed: `test_branch_changes_present_concurrent_edit_then_rewrite_counts_as_landed` was red on the parent commit.

<!-- fr:journal kind=finding scope=debug id=fix-715 created=2026-10-03T20:01:05+00:00 state=fixed -->
### fix-715 · finding [fixed] · #715 fixed: `_carries_patch` recognises the landing by its patch

A first-parent commit whose patch adds every non-blank line the branch added is the landing. Guards: `..._concurrent_edit_then_revert_is_missing` and `..._concurrent_edit_orphan_line_is_missing`. Every existing revert, three-way and side-branch test still passes. Remaining limit: if the concurrent edit touched the branch's own lines, the conflict resolution adds different lines, so it still reads as missing. That is the safe direction.

<!-- fr:journal kind=root-cause scope=debug id=rc-700 created=2026-10-03T20:09:08+00:00 -->
### rc-700 · root-cause · #700: two git seams with different ownership rules

`_run_git` ran bare `git`, while `git_answer`/`git_argv` added `-c safe.directory=<enclosing repo>`. Red evidence: `fr.git.repo_root` exited 128 with dubious ownership in a foreign-owned linked worktree. The walk-up also ignored `GIT_CEILING_DIRECTORIES`, so it could name an ancestor repo that git's own discovery would never open. That same gap made the outside-any-repo test depend on `TMPDIR`.

<!-- fr:journal kind=finding scope=debug id=fix-700 created=2026-10-03T20:09:09+00:00 state=fixed -->
### fix-700 · finding [fixed] · #700 fixed: one seam, ceiling-aware, no opt-out

Decision: no opt-out parameter. All ~50 call sites pass the repo fr was invoked on or created, so none reads an untrusted tree. The contract is in `safe_directory_args`'s docstring, and any future caller that reads a foreign tree must stay off this seam. Tests: `test_the_plain_wrappers_answer_in_a_foreign_owned_worktree`, `test_run_git_places_the_override_before_the_subcommand`, `test_safe_directory_never_names_a_repo_beyond_a_ceiling`, and the now-hermetic `test_safe_directory_outside_any_repo_is_empty`. Full suite: 7686 passed, 97 skipped.
