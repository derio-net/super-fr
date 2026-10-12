# Journal: 2026-10-12-board-truth

<!-- fr:journal kind=discovery scope=plan id=p1-closed-listing-failure-is-stderr created=2026-10-12T06:43:21+00:00 phase=1 -->
### p1-closed-listing-failure-is-stderr · discovery · Closed-in-progress listing failure is a stderr warning, not a facts warning (phase 1)

Facts.warnings holds only Truncation (list-limit hits), so a failed closed fr:in-progress listing is printed to stderr and yields an empty set; the repo is never skipped. The limit hit adds a Truncation(source=issues).

<!-- fr:journal kind=discovery scope=plan id=p1-test-forge-fakes-ignore-state created=2026-10-12T06:43:21+00:00 phase=1 -->
### p1-test-forge-fakes-ignore-state · discovery · Triage test forge fakes returned open issues for any state (phase 1)

FakeForge, test_triage_cli and test_triage_skeleton list_issues fakes ignored `state`; the new closed listing would have returned the open set. They now answer [] for state != open (FakeForge takes closed_in_progress / closed_listing_failing) and record labels.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-12T06:43:21+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

Task 3 only threaded an optional labels argument through existing signatures and added model fields; the new collect helper (_closed_in_progress) was written once, nothing duplicated to clean.
