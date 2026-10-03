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
