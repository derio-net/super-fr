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

<!-- fr:journal kind=discovery scope=plan id=p2-drive-cmd-preexisting-failures created=2026-10-12T07:19:20+00:00 phase=2 -->
### p2-drive-cmd-preexisting-failures · discovery · three test_triage_batch_drive_cmd claim-release tests fail on a clean HEAD (phase 2)

test_a_cancelled_batchs_claims_are_released_and_recorded_once and two siblings (failed record of released claims; merged then archived batch) exit 1 on an unmodified checkout too, so they are not caused by phase 2. Also: test_triage_batch_drive_disruption.py alone hits a pre-existing triage_kanban_cmd import cycle; it collects when run beside another triage test.

<!-- fr:journal kind=decision scope=plan id=p2-board-banner-placement created=2026-10-12T07:19:20+00:00 phase=2 -->
### p2-board-banner-placement · decision · board.html has no nav, so the skew banner sits directly under its header (phase 2)

kanban_render has no page_header nav; render_board takes a banner string rendered after the header block. triage.html renders it directly after page_header.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-12T07:19:20+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

the task only deleted the lenient parameter along the call chain; nothing left to clean

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-12T07:43:14+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · fr triage collect never printed facts.config_ignored (phase 2)

_report printed skipped/unviewed/warnings only; a hand-run collect dropped typo keys silently.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-12T07:43:14+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · batch dispatch dropped ignored keys silently (phase 2)

check_config_fresh discarded the dropped-key tuple.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-12T07:43:14+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Strict read_config left in prod; stale docstrings (phase 2)

Only a test called read_config; read_config_lenient/parse_triage_config docstrings described strict collect.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-12T07:43:14+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · No test for the board.html skew banner (phase 2)

write_board wiring and placement untested; scenario checked triage.html only.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-12T07:43:14+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · Tautological shared-builder test; no ordering test (phase 2)

classify called skew_entries and was compared with itself.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-10-12T07:43:14+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · Leniency of _fresh_config/_reservation/collect_into only signature-tested (phase 2)

inspect.signature checks, no real calls.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-10-12T07:43:14+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · Config-skew fixture was an impossible repo-scope state (phase 2)

Repo scope with a skipped repo cannot be produced by collect.

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-10-12T07:43:14+00:00 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · Acceptance row lacked R4 unit and integration refs (phase 2)

Row cited banner/check tests only.

<!-- fr:journal kind=finding scope=plan id=p2-r9 created=2026-10-12T07:43:14+00:00 phase=2 state=open review_scope=in -->
### p2-r9 · finding [open] (reviewer: in scope) · check.py imported skew_entries from the HTML module (phase 2)

Classification depended on rendering.

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-10-12T07:43:14+00:00 phase=2 -->
### p2-review-1 · review · Phase 2 code review (phase 2)

Dispatched read-only reviewer over b7693b86..03ae60d9 raised p2-r1..p2-r9, all in scope; all fixed in 45c47f66 with tests.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-12T07:43:14+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: fr triage collect never printed facts.config_ignored (phase 2)

_report prints ignored <repo>: keys. Test test_fr_triage_collect_names_the_dropped_key.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-12T07:43:14+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: batch dispatch dropped ignored keys silently (phase 2)

check_config_fresh returns the ignored keys; _fresh_config warns naming repo and keys. Tests test_check_config_fresh_returns_the_origin_ignored_keys, test_fresh_config_accepts_an_unknown_origin_key_and_warns.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-12T07:43:14+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Strict read_config left in prod; stale docstrings (phase 2)

Removed read_config and the lenient parameter; docstrings rewritten.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-12T07:43:14+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: No test for the board.html skew banner (phase 2)

Tests test_write_board_passes_the_skew_banner_and_places_it_under_the_header, test_render_board_without_a_banner_has_no_alert; scenario asserts board.html too.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-12T07:43:14+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: Tautological shared-builder test; no ordering test (phase 2)

Replaced by test_the_shared_builder_orders_repos_and_keys_in_banner_and_check (red first: keys were unsorted; now sorted).

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-10-12T07:43:14+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: Leniency of _fresh_config/_reservation/collect_into only signature-tested (phase 2)

Real-call tests: test_collect_into_collects_an_unknown_key_and_names_it, test_fresh_config_accepts_an_unknown_origin_key_and_warns, test_reservation_accepts_an_unknown_origin_key.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-10-12T07:43:14+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: Config-skew fixture was an impossible repo-scope state (phase 2)

Fixture regenerated as org scope; scenario uses --org.

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-10-12T07:43:14+00:00 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: Acceptance row lacked R4 unit and integration refs (phase 2)

Row now cites the R4 unit test and int=tests/integration/test_scenarios.py#test_triage_config_skew.

<!-- fr:journal kind=finding scope=plan id=p2-r9-resolved created=2026-10-12T07:43:14+00:00 phase=2 state=fixed resolves=p2-r9 -->
### p2-r9-resolved · finding [fixed] · resolves p2-r9: check.py imported skew_entries from the HTML module (phase 2)

skew_entries moved to triage/check.py; components imports it.

<!-- fr:journal kind=discovery scope=plan id=p3-r8-already-green created=2026-10-12T08:03:16+00:00 phase=3 -->
### p3-r8-already-green · discovery · R8 dispatch/cancel/claims_released pin was green on first run (phase 3)

For wave and wave-less two-member batches, stage is cancelled, owed_claims/owed_releases are empty, the card is not Running and the hint never says session running, even with a runner still reporting the session working. No fix in batch.py/claims.py was needed.

<!-- fr:journal kind=discovery scope=plan id=p3-front-order-in-card created=2026-10-12T08:03:16+00:00 phase=3 -->
### p3-front-order-in-card · discovery · A closeout-front card now carries --closeout in its summary (phase 3)

test_every_r4_section_is_on_a_full_card compared first-occurrence indexes over the whole card; it now checks the order within the Timeline section. Existing jump-count tests moved from 1/2 to 2/3 jumps (front plus body pair).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-12T08:03:16+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

Card.front is one small derived property and the render change reuses _jump/_status; nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-12T08:03:16+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

Tests and a scenario only; no production code changed (R8 was already green).

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-12T08:08:08+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · No render-level test for closeout_status unknown/absent (phase 3)

Only Card.front was tested via replace().

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-10-12T08:08:08+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · Scenario's 'no release owed' check could never fail (phase 3)

check --json has no releases-owed field.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-10-12T08:08:08+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · Running-column refuse_grep passed silently if extraction matched nothing (phase 3)

No guard that the section was found.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-10-12T08:08:08+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · R8 says after a fresh collect and render, but no test ran collect (phase 3)

Scenario and unit tests were render-only.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-10-12T08:08:08+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · Close-out-fronted pill/Jump carry no cue that they are the close-out's (phase 3)

kanban_render.py:306-314 adds no label.

<!-- fr:journal kind=review scope=plan id=p3-review-1 created=2026-10-12T08:08:08+00:00 phase=3 -->
### p3-review-1 · review · Phase 3 code review (phase 3)

Dispatched read-only reviewer over 8f97d84c..f4e4f71b, which rendered and screenshotted its own boards, raised p3-r1..p3-r5; r1-r4 fixed in 7ba9875d, r5 refuted by operator decision q7.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-12T08:08:08+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: No render-level test for closeout_status unknown/absent (phase 3)

Added test_an_unknown_closeout_status_leaves_the_front_to_the_batch_session and test_an_absent_closeout_has_a_batch_front_and_no_closeout_jump_or_code.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-10-12T08:08:08+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: Scenario's 'no release owed' check could never fail (phase 3)

Scenario asserts only claims_owed:[] and says release-owed is pinned by test_triage_cancelled_terminal.py, whose test asserts owed_releases is empty.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-10-12T08:08:08+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: Running-column refuse_grep passed silently if extraction matched nothing (phase 3)

expect_grep data-column="running" before the refuse_grep.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-10-12T08:08:08+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: R8 says after a fresh collect and render, but no test ran collect (phase 3)

Added test_right_after_a_fresh_collect_and_render_it_is_still_cancelled (collect_facts over FakeForge, wave and wave-less); row ref added.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-10-12T08:08:08+00:00 phase=3 state=refuted resolves=p3-r5 -->
### p3-r5-resolved · finding [refuted] · resolves p3-r5: Close-out-fronted pill/Jump carry no cue that they are the close-out's (phase 3)

Operator decision q7-closeout-front chose 'Exactly the note' over the offered 'Note + label the pill' option; the unlabelled front is the decided design, not a defect.

<!-- fr:journal kind=discovery scope=plan id=p4-explainers-unaffected created=2026-10-12T08:26:47+00:00 phase=4 -->
### p4-explainers-unaffected · discovery · No explainer describes the triage pages or nav (phase 4)

grep of docs/explainers/ (01-fr-goal.md, the hand-authored index.html and fr-isolation.html) finds no mention of triage, the Board tab or the page nav, so nothing needs regenerating.

<!-- fr:journal kind=discovery scope=plan id=p4-phone-board-clipped-in-headless created=2026-10-12T08:26:47+00:00 phase=4 -->
### p4-phone-board-clipped-in-headless · discovery · Headless Chrome at --window-size=390 clips the Batches columns on the right (phase 4)

The nav wraps cleanly at 390px, but the Kanban card column in phone-width-nav.png runs past the right edge. Headless Chrome enforces a minimum layout width, so this may be a capture artifact; the board's own CSS was not changed in this phase.

<!-- fr:journal kind=discovery scope=plan id=p4-repo-scope-stub-pages created=2026-10-12T08:26:47+00:00 phase=4 -->
### p4-repo-scope-stub-pages · discovery · repo-scope-five-tabs used stub origins/architecture pages (phase 4)

Origins and Architecture need origins facts and a checkout of subsystem refs, so the visual run seeded two one-line stub pages carrying a nav block, then rendered history, board and triage with the real commands. All five navs agreed afterwards, which also exercised refresh_navs on foreign pages. The org-scope run used only real renders.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-10-12T08:26:47+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

components.py gained the registry, pages_present and page_header in one place; each renderer only passes the present keys, so there was no duplicated chrome to fold.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t3 created=2026-10-12T08:26:47+00:00 phase=4 -->
### no-refactor-p4-t3 · discovery · no-refactor-because P4.T3 (phase 4)

Skill text, mirrors, scenario and matrix row are new content with no prior duplication to clean.
