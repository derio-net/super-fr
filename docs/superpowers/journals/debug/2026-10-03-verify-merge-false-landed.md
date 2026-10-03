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
