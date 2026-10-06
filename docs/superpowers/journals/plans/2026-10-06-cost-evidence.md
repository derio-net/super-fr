# Journal: 2026-10-06-cost-evidence

<!-- fr:journal kind=decision scope=plan id=p1-rekey-keyword created=2026-10-06T18:31:58+00:00 phase=1 -->
### p1-rekey-keyword · decision · session_entry takes a rekey keyword so backfill keeps brief re-keying while writing no split (phase 1)

Spec §B says backfill/refreshed_file pass index=None. Passing None alone would also drop the agent-id -> unit re-keying of briefs that backfill does today. session_entry therefore takes a keyword-only `rekey` (units_by_agent) used for briefs only; backfill and refreshed_file pass rekey and no index, so they write neither steps_by_role nor units and brief keys are unchanged.

<!-- fr:journal kind=discovery scope=plan id=p1-tdd-order-t3-t4 created=2026-10-06T18:31:58+00:00 phase=1 -->
### p1-tdd-order-t3-t4 · discovery · split.py and message_dollars were written before their RED tests in T3/T4 (phase 1)

The attribution module and the rollup extraction were drafted before the test file existed, so T3.S1/T4.S1 were not observed failing for those units (the session_entry and kind-bump tests were observed red). The tests assert the spec's invariants independently (sum-back to steps, half-open endpoints, retry counted once, unit total <= message total).

<!-- fr:journal kind=discovery scope=plan id=p1-refresh-drops-split created=2026-10-06T18:31:58+00:00 phase=1 -->
### p1-refresh-drops-split · discovery · refreshed_file replaces an entry that a live capture split, writing no split (phase 1)

Per spec §B refreshed_file passes no index, so an archived-time re-price of an unpriced session replaces that entry with one carrying no steps_by_role/units, even if the closeout capture had written them (unpriced there). Carrying the old split over would mix usd None with a re-priced entry, so it was left to the spec. The audit should expect archived re-priced sessions to read the split as not observed.

<!-- fr:journal kind=discovery scope=plan id=p1-opencode-agents-flaky-under-load created=2026-10-06T18:31:58+00:00 phase=1 -->
### p1-opencode-agents-flaky-under-load · discovery · tests/integration/test_install_opencode_agents.py two tests failed once under a loaded -n auto run, pass alone and in the final suite (phase 1)

test_a_resolved_binding_lands_as_model_on_each_tier_file_only and test_an_unbound_tier_inherits_rather_than_pinning_an_empty_model failed in one full run that overlapped other background pytest runs of mine, then passed alone (9 passed) and in the final full suite (9710 passed). Not caused by this phase (no opencode agent or models code touched).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-06T18:31:58+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the extraction of message_dollars out of rollup (rollup now calls it) was itself the refactor; nothing further to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-06T18:31:58+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

attribution lives in its own module (usage/split.py) and unit_index in file.py with units_by_agent as a thin view; nothing left to tidy

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-06T18:31:58+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

the migration is a small stamp-only module mirroring run_driver.py and the validator is one helper; nothing to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1-1 created=2026-10-06T19:23:48+00:00 phase=1 state=open review_scope=in -->
### p1-r1-1 · finding [open] (reviewer: in scope) · refreshed_file dropped a live capture's split on re-pricing; a test locked the loss in (phase 1)

backfill.py refreshed_file passed no index; test_usage_refresh_after_exit.py asserted no split. Spec §B amended (e7c1df5df).

<!-- fr:journal kind=finding scope=plan id=p1-r1-2 created=2026-10-06T19:23:48+00:00 phase=1 state=open review_scope=in -->
### p1-r1-2 · finding [open] (reviewer: in scope) · Cross-unit 'latest dispatched wins' overlap was untested (phase 1)

test_usage_split.py overlap fixture only overlapped one unit's own attempts.

<!-- fr:journal kind=finding scope=plan id=p1-r1-3 created=2026-10-06T19:23:48+00:00 phase=1 state=open review_scope=in -->
### p1-r1-3 · finding [open] (reviewer: in scope) · Per-unit dollars and per-message dollar shares were not pinned (phase 1)

Only turns and a <= total bound were asserted for by_unit_and_role.

<!-- fr:journal kind=finding scope=plan id=p1-r1-4 created=2026-10-06T19:23:48+00:00 phase=1 state=open review_scope=in -->
### p1-r1-4 · finding [open] (reviewer: in scope) · End-to-end capture assertion was a vacuous disjunction (phase 1)

test_usage_capture.py:185 accepted (unattributed) in place of the unit.

<!-- fr:journal kind=finding scope=plan id=p1-r1-5 created=2026-10-06T19:23:48+00:00 phase=1 state=open review_scope=in -->
### p1-r1-5 · finding [open] (reviewer: in scope) · steps figures carried no tokens, so the spec's token invariant was uncheckable (phase 1)

file.py session_entry built steps with usd/turns only. Spec §B amended to option (a).

<!-- fr:journal kind=discovery scope=plan id=p1-flaky-install-atomic created=2026-10-06T19:23:48+00:00 phase=1 -->
### p1-flaky-install-atomic · discovery · test_install_atomic::test_fr_stays_runnable_throughout_a_reinstall failed once under a loaded full run, passes alone (phase 1)

No install code touched by this branch; observed in the p1 fix suite (15 min wall clock, loaded host). Load-related flake, not caused here.

<!-- fr:journal kind=finding scope=plan id=p1b-r1 created=2026-10-06T19:23:48+00:00 phase=1 state=open review_scope=in -->
### p1b-r1 · finding [open] (reviewer: in scope) · unit_index took the role from the top-level step, so real phase units got role `agent`, never executor/reviewer (phase 1)

file.py:278 step_role_of(step) with step=`implement` (group); tests invented top-level implement-phase/review-phase steps.

<!-- fr:journal kind=finding scope=plan id=p1b-r2 created=2026-10-06T19:23:48+00:00 phase=1 state=open review_scope=in -->
### p1b-r2 · finding [open] (reviewer: in scope) · refreshed_file wrote v2-only token fields into archived files stamped schema_version 1 (phase 1)

Since p1-r1-5 steps always carry tokens; backfill.refreshed_file re-shaped archived v1 files.

<!-- fr:journal kind=review scope=plan id=p1-review-r1 created=2026-10-06T19:23:48+00:00 phase=1 -->
### p1-review-r1 · review · Phase 1 review (usage split, usage kind v2) (phase 1)

Two independent reviews (feature-dev:code-reviewer, Opus). Review a (af48ce7f4..cfc99b3d6): p1-r1-1..5, all in scope, fixed in 40c11189a; its return lacked the review-findings block, so a second reviewer was dispatched. Review b (af48ce7f4..40c11189a) verified those five fixes as real and raised p1b-r1 (critical: phase units got role `agent`) and p1b-r2 (refreshed v1 files re-shaped), both in scope, both fixed with tests. No out-of-scope findings.

<!-- fr:journal kind=finding scope=plan id=p1-r1-1-resolved created=2026-10-06T19:23:48+00:00 phase=1 state=fixed resolves=p1-r1-1 -->
### p1-r1-1-resolved · finding [fixed] · resolves p1-r1-1: refreshed_file dropped a live capture's split on re-pricing; a test locked the loss in (phase 1)

40c11189a: refreshed_file passes unit_index(raw) iff the old entry had a split; test_backfill_prices_an_archived_session_once_it_has_exited + test_a_refresh_reprices_an_existing_split_and_never_adds_one.

<!-- fr:journal kind=finding scope=plan id=p1-r1-2-resolved created=2026-10-06T19:23:48+00:00 phase=1 state=fixed resolves=p1-r1-2 -->
### p1-r1-2-resolved · finding [fixed] · resolves p1-r1-2: Cross-unit 'latest dispatched wins' overlap was untested (phase 1)

40c11189a: test_two_different_overlapping_units_attribute_to_the_latest_dispatch_in_any_order.

<!-- fr:journal kind=finding scope=plan id=p1-r1-3-resolved created=2026-10-06T19:23:48+00:00 phase=1 state=fixed resolves=p1-r1-3 -->
### p1-r1-3-resolved · finding [fixed] · resolves p1-r1-3: Per-unit dollars and per-message dollar shares were not pinned (phase 1)

40c11189a: test_each_unit_role_dollars_are_the_sum_of_its_messages_dollars; proportionality in the message_dollars test.

<!-- fr:journal kind=finding scope=plan id=p1-r1-4-resolved created=2026-10-06T19:23:48+00:00 phase=1 state=fixed resolves=p1-r1-4 -->
### p1-r1-4-resolved · finding [fixed] · resolves p1-r1-4: End-to-end capture assertion was a vacuous disjunction (phase 1)

40c11189a: asserts units[unit]['agent'].turns > 0 and no (unattributed), separately.

<!-- fr:journal kind=finding scope=plan id=p1-r1-5-resolved created=2026-10-06T19:23:48+00:00 phase=1 state=fixed resolves=p1-r1-5 -->
### p1-r1-5-resolved · finding [fixed] · resolves p1-r1-5: steps figures carried no tokens, so the spec's token invariant was uncheckable (phase 1)

40c11189a: steps figures carry token counts via split.tokens_by_step; step invariant test covers every token field.

<!-- fr:journal kind=finding scope=plan id=p1b-r1-resolved created=2026-10-06T19:23:48+00:00 phase=1 state=fixed resolves=p1b-r1 -->
### p1b-r1-resolved · finding [fixed] · resolves p1b-r1: unit_index took the role from the top-level step, so real phase units got role `agent`, never executor/reviewer (phase 1)

file.py:277-281 role from the phase/<n>/<member> segment; fixtures moved to the real `implement` group nesting; test_the_index_maps_agents_roles_and_open_ended_intervals, test_subagent_messages_go_to_executor_reviewer_and_flat_agent_roles.

<!-- fr:journal kind=finding scope=plan id=p1b-r2-resolved created=2026-10-06T19:23:48+00:00 phase=1 state=fixed resolves=p1b-r2 -->
### p1b-r2-resolved · finding [fixed] · resolves p1b-r2: refreshed_file wrote v2-only token fields into archived files stamped schema_version 1 (phase 1)

backfill._v1_steps: refreshed_file without an index writes usd/turns-only steps; test_a_refreshed_v1_file_validates_and_writes_no_token_fields_on_steps.
