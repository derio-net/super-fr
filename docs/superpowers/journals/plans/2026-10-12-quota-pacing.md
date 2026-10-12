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
