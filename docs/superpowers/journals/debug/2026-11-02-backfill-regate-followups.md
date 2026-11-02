<!-- fr:journal-schema=3 -->
# Journal: 2026-11-02-backfill-regate-followups

<!-- fr:journal kind=repro scope=debug id=8de1aeab0731 created=2026-11-02T20:41:11+00:00 -->
### 8de1aeab0731 · repro · independent review of #1324: untested cross-gate decision, transitions, unclosed tracked-only trackers

Source: ~/.cache/fr/coord/goals/review-1324/findings.md (F1 major, F2/F3 minor, F4-F6 nits). Repro for F3/F4: test_gh1322_tracked_only_texts_tell_the_operator_to_close_the_issue (last prose line was the discharge fence) and test_gh1322_a_mismatched_tracked_only_tracker_is_named_in_its_passed_form (skip said gate:devops pr:41). F1/F2 behaviour was already correct; tests added to pin it.

<!-- fr:journal kind=root-cause scope=debug id=6434af8bcf6d created=2026-11-02T20:41:23+00:00 -->
### 6434af8bcf6d · root-cause · tracked-only form added text and a marker read without updating the operator-facing strings

#1324 introduced the passed tracker form but kept the held form's skip wording and gave the body no closing step, while no fr path ever closes it (§H skips it by design).

<!-- fr:journal kind=finding scope=debug id=f3-f4 created=2026-11-02T20:41:34+00:00 state=fixed -->
### f3-f4 · finding [fixed] · close line on tracked-only texts; passed-form mismatch skip

trackers._CLOSE_LINE appended before the markers (owed marker stays last, so owned_owed_key is unchanged); apply._apply names a passed marker as gate:<g>-passed pr:<n> (tracked only). F1 tests: test_gh1322_another_gate_passed_still_gates_this_one (both directions) + test_gate_cmd test_gh1322_the_dry_run_does_not_call_another_gates_pass_this_ones. F2: test_gh1322_both_labels_present_is_tracked_only_with_no_label_write, test_gh1322_passed_removed_later_rewrites_to_held. Auto-close filed as #1328. F5/F6 reviewed, deferred (no change).

<!-- fr:journal kind=discovery scope=debug id=post-merge-review created=2026-11-02T20:42:59+00:00 -->
### post-merge-review · discovery · independent post-merge review of #1324 ran; recorded here because its journal is archived

A cold, read-only reviewer reviewed #1324 after merge: no blocker, F1 major, F2/F3 minor, F4-F6 nits (findings file host-local at ~/.cache/fr/coord/goals/review-1324/findings.md). #1324's own journal (implemented/journals/debug/2026-11-02-backfill-regate.md) was archived by close-out PR #1326 before this entry could be written there, and archived artifacts are frozen, so the record lives in this follow-up's journal. This branch's PR is the follow-up.
