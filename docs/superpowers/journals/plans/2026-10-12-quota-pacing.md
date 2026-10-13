<!-- fr:journal-schema=2 -->
# Journal: 2026-10-12-quota-pacing

<!-- fr:journal kind=decision scope=plan id=p1-pacing-loop-only created=2026-10-12T06:55:45+00:00 phase=1 -->
### p1-pacing-loop-only · decision · Pacing applies to a looping drive and the cloud pass, not --once or plan mode (phase 1)

`--once` and a plan-only run keep today's behaviour (a rate limit exits with the read error's code); a loop waits, and the cloud pass exits 3. `essential` (below the floor) is decided by `quota.decide` but the loops ignore it until phase 2 builds the essential-only pass, so the quota line never claims a pass that does not exist.

<!-- fr:journal kind=discovery scope=plan id=p1-stale-exhausted-reading created=2026-10-12T06:55:45+00:00 phase=1 -->
### p1-stale-exhausted-reading · discovery · An exhausted /rate_limit reading whose reset has passed must not be waited on (phase 1)

A wait whose end is already past sleeps 0 s, and the loop would re-read and re-run forever, spending the budget it was meant to spare (found by a test whose clock was the real one). `decide` runs the pass, and `after_rate_limit` backs off as a secondary limit, when the reading's reset plus 30 s is not ahead of now.

<!-- fr:journal kind=discovery scope=plan id=p1-collect-fakes-returned-none created=2026-10-12T06:55:45+00:00 phase=1 -->
### p1-collect-fakes-returned-none · discovery · Three existing tests faked collect_into with None for the facts (phase 1)

recollect now reads facts.skipped and facts.unviewed (R2), so the fakes in test_triage_batch_drive_cmd and test_triage_batch_drive_disruption return the world's facts, as the real function does.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-12T06:55:45+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the floor reader shared the host file's mapping loader with api: in the same change (one reader of forge.yaml); nothing else to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-12T06:55:45+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the seam is one method on each adapter plus one pass-through; nothing to extract

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-10-12T07:05:53+00:00 phase=1 -->
### p1-review · review · code review of phase 1 (d7266583..816f1164) (phase 1)

Independent reviewer raised 7 findings: p1-r1..p1-r7 (6 in, 1 out). R3, R4, R5, R6 confirmed correct as written. In-scope findings fixed in 06eb3626 with tests; p1-r4 out of scope (closed by phase 3, R12).

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-12T07:05:53+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · after_rate_limit computes interval*2**backoff before the cap; unbounded backoff overflows (quota.py:158) (phase 1)

after_rate_limit computes interval*2**backoff before the cap; unbounded backoff overflows (quota.py:158)

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-12T07:05:53+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · rate limits surfacing as VisibilityUnreadable or failed writes were not recognised (no backoff, no wait_until, counted clean) (phase 1)

rate limits surfacing as VisibilityUnreadable or failed writes were not recognised (no backoff, no wait_until, counted clean)

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-12T07:05:53+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · cloud wait branch lease renewal exited 2 on an unreadable visibility instead of 3 (phase 1)

cloud wait branch lease renewal exited 2 on an unreadable visibility instead of 3

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-12T07:05:53+00:00 phase=1 state=open review_scope=out -->
### p1-r4 · finding [open] (reviewer: out of scope) · host wait_out renewal retries a GraphQL visibility read every 60s inside the exhausted window until R12 lands (phase 1)

host wait_out renewal retries a GraphQL visibility read every 60s inside the exhausted window until R12 lands

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-12T07:05:53+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · cloud pass renewal ignored R16's 5-minute margin (phase 1)

cloud pass renewal ignored R16's 5-minute margin

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-12T07:05:53+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · a binary pacing.json crashed Pacer construction (UnicodeDecodeError uncaught) (phase 1)

a binary pacing.json crashed Pacer construction (UnicodeDecodeError uncaught)

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-12T07:05:53+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · loop tests stubbed one_pass/take_lease and the conftest stub was conditional (phase 1)

loop tests stubbed one_pass/take_lease and the conftest stub was conditional

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-12T07:05:53+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: after_rate_limit computes interval*2**backoff before the cap; unbounded backoff overflows (quota.py:158) (phase 1)

Exponent clamped to 10, backoff count bounded at 32, a negative backoff treated as 0 and rejected on load. Tests test_a_huge_backoff_neither_overflows_nor_grows_past_the_cap, test_a_negative_backoff_is_treated_as_zero, test_a_negative_backoff_is_not_usable.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-12T07:05:53+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: rate limits surfacing as VisibilityUnreadable or failed writes were not recognised (no backoff, no wait_until, counted clean) (phase 1)

Pacer.limited reads the free /rate_limit after any ForgeReadError and after a failed-write pass; text match OR exhausted budget is a rate limit; such a pass is never clean. Tests test_an_unreadable_visibility_on_an_exhausted_budget_is_a_rate_limit, test_a_failed_write_on_an_exhausted_budget_is_not_a_clean_pass (+ ample-budget controls).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-12T07:05:53+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: cloud wait branch lease renewal exited 2 on an unreadable visibility instead of 3 (phase 1)

Renewal failure warns once and the pass still prints the quota line and exits 3. Test test_a_failed_renewal_while_waiting_warns_and_still_exits_3.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-12T07:05:53+00:00 phase=1 state=open resolves=p1-r4 out_of_scope=true -->
### p1-r4-resolved · finding [out-of-scope] · resolves p1-r4: host wait_out renewal retries a GraphQL visibility read every 60s inside the exhausted window until R12 lands (phase 1)

Closed by phase 3 (R12: visibility read over conditional REST, which an exhausted GraphQL budget does not touch). Phase 1 alone ships with the GraphQL read; the plan already orders R12 into phase 3, so no separate change here.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-12T07:05:53+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: cloud pass renewal ignored R16's 5-minute margin (phase 1)

Condition now subtracts batch.LEASE_MARGIN. Tests test_the_cloud_pass_renews_a_lease_expiring_just_inside_the_margin, test_the_cloud_pass_leaves_a_lease_with_room_to_spare_alone.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-12T07:05:53+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: a binary pacing.json crashed Pacer construction (UnicodeDecodeError uncaught) (phase 1)

load catches (OSError, ValueError) on the read. Test test_a_binary_file_is_an_empty_state_and_a_warning.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-12T07:05:53+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: loop tests stubbed one_pass/take_lease and the conftest stub was conditional (phase 1)

Conftest stub unconditional; real _Driver/one_pass/_host_loop integration cases (rate limit raised from take_lease and from save_pass) assert one reset+30s wait with no forge call in between; real _pace_forge wiring reaches ClientForge.rate_limit. Tests in test_triage_quota_loop.py.

<!-- fr:journal kind=discovery scope=plan id=p2-visibility-never-carried created=2026-10-12T07:56:06+00:00 phase=2 -->
### p2-visibility-never-carried · discovery · A partial collect must not carry a repo's visibility (orchestrator correction to R10) (phase 2)

The privacy guard (fr/triage/privacy.py) trusts facts.visibility and reads a missing repo live. A carried, stale "public" would let a repo made private since the last full pass pass the leak check for up to 15 minutes. Carried repos are left out of facts.visibility; read repos get it exactly as before. Test test_a_carried_repo_s_visibility_is_left_out_for_the_guard_to_read_live.

<!-- fr:journal kind=discovery scope=plan id=p2-conftest-circular-import created=2026-10-12T07:56:06+00:00 phase=2 -->
### p2-conftest-circular-import · discovery · Phase 1's autouse rate-limit stub errored any test file that never imported the CLI (phase 2)

tests/conftest.py's stub imports fr.commands.triage_batch_cmd directly, which on its own is a circular import (triage_kanban_cmd <-> triage_claim_cmd); test_real_ghclient.py alone errored on every test. The fixture now imports fr.cli first. Masked in the full suite.

<!-- fr:journal kind=decision scope=plan id=p2-probes-in-run-pass created=2026-10-12T07:56:06+00:00 phase=2 -->
### p2-probes-in-run-pass · decision · Probes run in the drive's run_pass; collect_into owns the facts-then-pacing order (phase 2)

The pass kind must be known before any collect (a quiet pass collects nothing), so the probes run in _Driver._pass_plan through a _probe_forge seam. collect_into takes only= and an after_write callback invoked once facts.json is written, in which the Pacer promotes pending ETags; the ordering guarantee lives in collect_into. Unpaced (--once, plan mode, fr triage collect) passes no new arguments at all.

<!-- fr:journal kind=decision scope=plan id=p2-quiet-needs-recorded-summary created=2026-10-12T07:56:06+00:00 phase=2 -->
### p2-quiet-needs-recorded-summary · decision · pacing.json records the last planned pass's summary, and a quiet pass reports it (phase 2)

A quiet pass plans nothing, yet the loop and the cloud exit code read a Summary. The planned pass stores its summary counts in pacing.json (new optional `summary`); a quiet pass is possible only when one is on record, so a cloud wake (one process each) can be quiet too. Below the floor a pass with nothing changed is quiet rather than essential. A full pass narrowed by the floor does not move full_at, so the next pass above the floor is a real full one.

<!-- fr:journal kind=discovery scope=plan id=p2-carried-landed-batches-unverified created=2026-10-12T07:56:06+00:00 phase=2 -->
### p2-carried-landed-batches-unverified · discovery · A carried repo's landed batches are marked unverified, so no close-out is planned (phase 2)

The snapshot skips every live read for a carried repo (queue, merge commit, hand close-out, archive PRs, claim and export reads); its landed batches without a close-out event go to `unverified`, which drive_pass already treats as closing with no action. run_pass additionally drops merge/update/closeout/archive/adopt actions for carried repos.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-12T07:56:06+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

one shared parser (fr.gh.probe) serves both adapters from the start; nothing duplicated to extract

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-12T07:56:06+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

probe.py was written pure around PacingState with PassPlan as its one output; nothing left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-12T07:56:06+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

the carry is three small helpers beside collect_facts_counted (_carry_set, _kept_links, _carried_judgement); the full path is untouched

<!-- fr:journal kind=review scope=plan id=p2-review created=2026-10-12T08:13:59+00:00 phase=2 -->
### p2-review · review · code review of phase 2 (06eb3626..5d297a01) (phase 2)

Independent reviewer raised 8 findings, all in scope: p2-r1..p2-r8. Confirmed sound: probe-before-collect ordering, failed-repo ETag drop, visibility never carried, cross-repo links both ways, only=None unchanged, quota-held dispatch counted pending. All fixed in 630f6a92 plus follow-up ffd287ae, each with a test.

<!-- fr:journal kind=discovery scope=plan id=p2-ci-conftest created=2026-10-12T08:13:59+00:00 phase=2 -->
### p2-ci-conftest · discovery · CI caught a conftest import the targeted runs could not (phase 2)

The phase-2 head failed two suite-isolation tests: tests/conftest.py imported tests.unit.triage_fixtures, and those tests run the conftest in a subprocess from a temp dir. Fixed in 5d297a01 by inlining the stub.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-12T08:13:59+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · after_collect stored judgements_digest before the pass planned; a pass failing after collect made the next one quiet (phase 2)

after_collect stored judgements_digest before the pass planned; a pass failing after collect made the next one quiet

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-12T08:13:59+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · rate-limited Unviewed keys were carried and their repo's ETags kept (phase 2)

rate-limited Unviewed keys were carried and their repo's ETags kept

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-12T08:13:59+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · after an essential (dispatch-held) pass an above-floor pass could be quiet (phase 2)

after an essential (dispatch-held) pass an above-floor pass could be quiet

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-12T08:13:59+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · an essential --yes pass printed 'nothing done; re-run with --yes to act' (phase 2)

an essential --yes pass printed 'nothing done; re-run with --yes to act'

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-12T08:13:59+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · no previous facts below the floor carried every repo while collect read all (phase 2)

no previous facts below the floor carried every repo while collect read all

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-10-12T08:13:59+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · carried repos were unread for _claim_plan, so a carried batch could dispatch without owed claims (phase 2)

carried repos were unread for _claim_plan, so a carried batch could dispatch without owed claims

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-10-12T08:13:59+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · quiet pass built Summary(**pacing.json summary) unchecked (phase 2)

quiet pass built Summary(**pacing.json summary) unchecked

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-10-12T08:13:59+00:00 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · forced-full-below-floor test inspected private _pass_plan (phase 2)

forced-full-below-floor test inspected private _pass_plan

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-12T08:13:59+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: after_collect stored judgements_digest before the pass planned; a pass failing after collect made the next one quiet (phase 2)

after_collect clears summary and digest; record_summary writes them once the pass planned (630f6a92). Follow-up ffd287ae: a pass after one that never planned carries nothing, so its owed merges are not deferred. Tests test_a_pass_that_fails_after_writing_its_facts_is_never_followed_by_a_quiet_one (now asserts the owed merge), test_a_written_facts_json_is_no_planned_pass.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-12T08:13:59+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: rate-limited Unviewed keys were carried and their repo's ETags kept (phase 2)

Unviewed never carried; a repo with a rate-limited unviewed key counts as failed and drops its ETags. Tests test_a_carried_repo_s_unviewed_key_is_viewed_again, test_a_rate_limited_unviewed_key_fails_its_repo.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-12T08:13:59+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: after an essential (dispatch-held) pass an above-floor pass could be quiet (phase 2)

PacingState.held_for_quota; pass_kind is never quiet above the floor while set. Tests test_dispatch_resumes_once_the_budget_is_back_above_the_floor (recent full_at), test_pass_kinds, test_held_for_quota_round_trips_and_a_bad_value_is_false.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-12T08:13:59+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: an essential --yes pass printed 'nothing done; re-run with --yes to act' (phase 2)

Board skip no longer falls into the plan-mode branch; test (d) asserts the line is absent.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-12T08:13:59+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: no previous facts below the floor carried every repo while collect read all (phase 2)

collect reports the set it actually carried (CollectStats.carried_repos), used for both snapshot and ETag promotion; no previous facts plans only=None. Test test_a_paced_drive_with_no_previous_facts_below_the_floor_reads_and_merges.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-10-12T08:13:59+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: carried repos were unread for _claim_plan, so a carried batch could dispatch without owed claims (phase 2)

_claim_plan's unread set is collect-skipped repos only. Test test_a_carried_repo_s_batch_claims_its_members_before_it_dispatches.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-10-12T08:13:59+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: quiet pass built Summary(**pacing.json summary) unchecked (phase 2)

pacing_state drops a summary whose keys do not match Summary's fields. Test test_a_summary_with_a_key_the_summary_does_not_have_is_no_summary.

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-10-12T08:13:59+00:00 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: forced-full-below-floor test inspected private _pass_plan (phase 2)

Driven through Rig with a two-repo scope; asserts collects, OTHER's unconditional probe and no live read for OTHER.

<!-- fr:journal kind=decision scope=plan id=p3-d1 created=2026-10-12T08:51:40+00:00 phase=3 -->
### p3-d1 · decision · Watch pacing shares the drive's functions via triage_cmd (phase 3)

triage_kanban_cmd may not import triage_batch_cmd, so make_pacer, plan_paced_pass and rate_limit_reason now live in triage_cmd and the drive calls them. The watch plans with board=True (Pacer.plan): it has no drive summary, so a placeholder stands for it in the planning copy only, and record_digest stores the digest without a summary, so a drive that follows still plans rather than standing quiet on the watch's collect.

<!-- fr:journal kind=discovery scope=plan id=p3-x1 created=2026-10-12T08:51:40+00:00 phase=3 -->
### p3-x1 · discovery · Captured REST fixtures carry no headers (phase 3)

FixtureGh answers bodies captured without -i. fr.gh.repo_visibility therefore accepts a body with no status line (no ETag cached); a real gh api -i answer always has the status line. parse_api in the test support now skips -i.

<!-- fr:journal kind=decision scope=plan id=p3-d2 created=2026-10-12T08:51:40+00:00 phase=3 -->
### p3-d2 · decision · Visibility ETag map is cleared per test (phase 3)

fr.gh._VISIBILITY is module state (R12); an autouse fixture in tests/conftest.py clears it so one test's cached answer is never another's 304.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-12T08:51:40+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

the visibility read became one shared function in fr.gh used by both adapters; nothing left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-12T08:51:40+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

the refactor was the work itself: make_pacer, plan_paced_pass and rate_limit_reason moved into triage_cmd so the drive and the watch share them; nothing further

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-10-12T08:51:40+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

a single optional render argument and one footer clause; nothing to clean

<!-- fr:journal kind=review scope=plan id=p3-review created=2026-10-12T08:56:54+00:00 phase=3 -->
### p3-review · review · code review of phase 3 (ffd287ae..080abd7f) (phase 3)

Independent reviewer found no correctness or privacy defect in R12, R17 or R14 (R12 traced fail-closed on every path). Raised 5 findings: p3-r1..p3-r4 in (tests, docstring, footer UTC), fixed in c235ea3f; p3-r5 out of scope.

<!-- fr:journal kind=discovery scope=plan id=p3-ci-scenarios created=2026-10-12T08:56:54+00:00 phase=3 -->
### p3-ci-scenarios · discovery · CI caught three scenario fakes missing the visibility read's -i (phase 3)

The cloud-triage scenario fakes matched `gh api repos/...` exactly; the R12 read sends `-i`. The privacy guard correctly refused (fail closed). Fixed in 080abd7f by letting the fakes accept -i.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-12T08:56:54+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · no test for the quiet-pass-with-no-board.html render-once behaviour (phase 3)

no test for the quiet-pass-with-no-board.html render-once behaviour

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-10-12T08:56:54+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · repo_visibility fail-closed branches and an end-to-end live_visibility None case were untested (phase 3)

repo_visibility fail-closed branches and an end-to-end live_visibility None case were untested

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-10-12T08:56:54+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · recollect docstring said 'no carry-over' though only= carries (phase 3)

recollect docstring said 'no carry-over' though only= carries

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-10-12T08:56:54+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · footer printed reset %H:%MZ without normalising to UTC (phase 3)

footer printed reset %H:%MZ without normalising to UTC

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-10-12T08:56:54+00:00 phase=3 state=open review_scope=out -->
### p3-r5 · finding [open] (reviewer: out of scope) · drive lock is checked only at the start of each watch iteration (phase 3)

drive lock is checked only at the start of each watch iteration

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-12T08:56:54+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: no test for the quiet-pass-with-no-board.html render-once behaviour (phase 3)

Test test_a_quiet_pass_with_no_board_yet_renders_it_once (c235ea3f).

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-10-12T08:56:54+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: repo_visibility fail-closed branches and an end-to-end live_visibility None case were untested (phase 3)

TestConditionalVisibility gained every fail-closed case (non-304 error keeps entry, exit-0 304 raises, unusable 200 raises, no-ETag 200 drops the entry, status-less body caches nothing, other repo same host); test_a_5xx_after_a_cached_200_makes_the_visibility_unreadable. All passed against the existing code: it already failed closed.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-10-12T08:56:54+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: recollect docstring said 'no carry-over' though only= carries (phase 3)

Docstring reworded (c235ea3f).

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-10-12T08:56:54+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: footer printed reset %H:%MZ without normalising to UTC (phase 3)

budget_from_json normalises naive to UTC and aware to astimezone(UTC). Tests test_the_footer_names_the_reset_in_utc_whatever_offset_the_record_carried, test_the_footer_escapes_the_resource_name.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-10-12T08:56:54+00:00 phase=3 state=open resolves=p3-r5 out_of_scope=true -->
### p3-r5-resolved · finding [out-of-scope] · resolves p3-r5: drive lock is checked only at the start of each watch iteration (phase 3)

Existing lock design (triage_kanban_cmd _watch predates this change); pacing.json writes are atomic and advisory, so an interleave is bounded. Not caused by this change.
