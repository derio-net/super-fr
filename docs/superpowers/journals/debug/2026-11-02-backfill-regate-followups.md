<!-- fr:journal-schema=3 -->
# Journal: 2026-11-02-backfill-regate-followups

<!-- fr:journal kind=repro scope=debug id=8de1aeab0731 created=2026-11-02T20:41:11+00:00 -->
### 8de1aeab0731 · repro · independent review of #1324: untested cross-gate decision, transitions, unclosed tracked-only trackers

Source: ~/.cache/fr/coord/goals/review-1324/findings.md (F1 major, F2/F3 minor, F4-F6 nits). Repro for F3/F4: test_gh1322_tracked_only_texts_tell_the_operator_to_close_the_issue (last prose line was the discharge fence) and test_gh1322_a_mismatched_tracked_only_tracker_is_named_in_its_passed_form (skip said gate:devops pr:41). F1/F2 behaviour was already correct; tests added to pin it.
