# Journal: 2026-10-02-batch-forge-honesty

<!-- fr:journal kind=ruled-out scope=debug id=e4fc50219a6f created=2026-10-02T18:05:55+00:00 -->
### e4fc50219a6f · ruled-out · The four members do not share one root cause

Batch premise: one root cause. Investigation of the code each issue names finds four independent defects in four modules:
- #803: tracking gate (`_tracking_gate`, triage_batch_cmd.py:473) is called only by dispatch (:801); cancel (:380-406), merge and `fr undispatch` (undispatch_cmd.py) write labels/comments ungated. Cause: #794 placed the gate per-verb, not at the forge-write seam.
- #490: fr_vk/pr_state.py closer seam is `Callable[[str, str, str], None]` (repo, issue, backend); the host derived from pr_url in `_close_linked_gh_issue` (:121) never reaches `_default_close_gh_issue` (:76). Cause: a backend string travels where a resolved client is needed.
- #804: apply_cmd.py:265 reads require_tracker(plan repo). Not a defect yet: the spec does not say whose setting governs; needs an operator decision.
- #800: gitseam.py:186 merge passes `-c rerere.enabled=false` but not `merge.directoryRenames=false`; git infers a directory rename when an archive empties runs/ or journals/plans/. Cause: git default config, unrelated to forge writes.
Shared theme (forge/tracker honesty) only for #803/#804; #490 and #800 are separate. Per the batch's debugging rules, stopping to ask before fixing any.

<!-- fr:journal kind=decision scope=debug id=2f7b0b916b2d created=2026-10-02T18:08:51+00:00 -->
### 2f7b0b916b2d · decision · Operator: fix all four in one PR; #804 — the plan repo's tracking setting governs

Asked after the split finding. Answer: keep the one-PR contract, one failing test + one fix per cause. #804: the plan repo's `tracking` governs `fr apply --yes` for a cross-repo plan (fr has no checkout of target_repo; the plan repo declared intent). Pin it with a test and state it in the spec + code.

<!-- fr:journal kind=repro scope=debug id=b6486b64443f created=2026-10-02T18:10:12+00:00 -->
### b6486b64443f · repro · #800 reproduced: emptied docs/runs/ makes the scratch merge report a phantom path

tests/unit/test_triage_gitseam.py::test_an_archive_that_empties_a_live_directory_is_not_a_rename — main moves the last file of docs/runs/ into docs/implemented/runs/; the PR adds docs/runs/new.yaml. `Worktree.merge('origin/main')` returns ['docs/implemented/runs/new.yaml'] (exists on neither side), with merge.directoryRenames=conflict (git's default).

<!-- fr:journal kind=root-cause scope=debug id=ec7d0d7c107f created=2026-10-02T18:10:59+00:00 -->
### ec7d0d7c107f · root-cause · #800: the scratch merge inherits git's directory-rename detection

gitseam.Worktree.merge overrode rerere only. With merge.directoryRenames at git's default (conflict), an archive that empties docs/runs/ reads as a rename of the directory, so the PR's new cursor is relocated to implemented/runs/ and reported as a conflict on a path neither side has.
