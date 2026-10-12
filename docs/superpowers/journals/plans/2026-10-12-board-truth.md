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

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-12T06:50:48+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Race restore re-added fr:in-progress even when it was never on the issue, in two edits (phase 1)

claim_writes.py _remove_label restored the whole removed set after a foreign claim raced in, without checking presence.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-12T06:50:48+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · collect computed scope_id per repo unconditionally, outside any try (phase 1)

A broken host id aborted the whole collect and could mint the host-id file during a read (collect.py _closed_in_progress).

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-12T06:50:48+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · Closed-list truncation reused Truncation(source=issues) (phase 1)

Turned off closed-issue carry (extra view_issue per judged key) and was worded as the open backlog.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-12T06:50:48+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · clean-labels never refused glab/tea; refusal test was a tautology (phase 1)

Both real clients implement view_issue/edit_issue_labels; the test monkeypatched view_issue to raise.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-12T06:50:48+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · check text printed closed-in-progress after stale dispatch (phase 1)

Spec §B: the new sections come first in the text report.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-12T06:50:48+00:00 phase=1 state=open review_scope=out -->
### p1-r6 · finding [open] (reviewer: out of scope) · Test gaps: claim_sync unlabel via one release, no untrusted-author closed-hit case, board note only as a function (phase 1)

Main paths are covered; these are extra cases, not a defect of the change.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-12T06:50:48+00:00 phase=1 state=open review_scope=out -->
### p1-r7 · finding [open] (reviewer: out of scope) · release-pending also covers an own claim a still-running batch owes (phase 1)

Follows the spec's three-state definition; the page copy 'next claim sync clears it' can be false for such a claim.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-12T06:50:48+00:00 phase=1 -->
### p1-review-1 · review · Phase 1 code review (phase 1)

Dispatched read-only reviewer over fa1301fa..93428a1b raised p1-r1..p1-r7 (5 in, 2 out). All five in-scope fixed in a777bee4 with tests.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-12T06:50:48+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Race restore re-added fr:in-progress even when it was never on the issue, in two edits (phase 1)

Pre-read labels; restore only those present, in one edit_issue_labels(add=). Test test_a_race_restores_only_labels_that_were_present_in_one_edit.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-12T06:50:48+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: collect computed scope_id per repo unconditionally, outside any try (phase 1)

scope_id computed lazily only for claimed closed hits, guarded; failure warns and classifies them held. Tests test_a_broken_scope_id_makes_claimed_closed_hits_held_not_a_failed_collect, test_scope_id_is_never_computed_when_no_closed_hit_is_claimed.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-12T06:50:48+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: Closed-list truncation reused Truncation(source=issues) (phase 1)

Truncation source closed-in-progress with its own wording; carry keys only on the open list. Test test_a_closed_list_at_its_limit_names_itself_and_leaves_the_carry_active.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-12T06:50:48+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: clean-labels never refused glab/tea; refusal test was a tautology (phase 1)

clean-labels refuses UnsupportedBatchOps clients (glab/tea) before any read or write. Test test_glab_and_tea_are_refused_before_any_read_or_write builds real clients and asserts zero calls.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-12T06:50:48+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: check text printed closed-in-progress after stale dispatch (phase 1)

Section moved first. Test test_the_closed_in_progress_section_comes_first_in_the_text_report.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-12T06:50:48+00:00 phase=1 state=open resolves=p1-r6 out_of_scope=true -->
### p1-r6-resolved · finding [out-of-scope] · resolves p1-r6: Test gaps: claim_sync unlabel via one release, no untrusted-author closed-hit case, board note only as a function (phase 1)

Additional test cases for paths already covered; not a defect this change introduced.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-12T06:50:48+00:00 phase=1 state=open resolves=p1-r7 out_of_scope=true -->
### p1-r7-resolved · finding [out-of-scope] · resolves p1-r7: release-pending also covers an own claim a still-running batch owes (phase 1)

The state follows the spec's own definition (operator-approved three states); refining the release-pending wording is a separate change.
