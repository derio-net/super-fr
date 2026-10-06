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

<!-- fr:journal kind=decision scope=plan id=p2-phase-rows-phases-from-cursor-and-units created=2026-10-06T20:19:04+00:00 phase=2 -->
### p2-phase-rows-phases-from-cursor-and-units · decision · phase_rows lists every phase found in the cursor's phase/<n>/{implement,review}-phase units or in a usage entry's units (phase 2)

A phase with usage figures but no cursor unit (or the reverse) still gets a row, with `—` for what is missing,
so a figure is never dropped from the per-phase table. Phases are matched by the unit key
`phase/<n>/<member>` under any step (real cursors nest them under `implement`).

<!-- fr:journal kind=decision scope=plan id=p2-mismatch-mark created=2026-10-06T20:19:04+00:00 phase=2 -->
### p2-mismatch-mark · decision · the mismatch mark is a trailing `≠` on the ran cell, in both the CLI and the PR body (phase 2)

`ran_text` renders `<model> ≠` when ran and bound differ by `fr.models.model_family`; an unobserved ran is `—`
and never marked. The PR body's per-phase table carries a one-line legend for it.

<!-- fr:journal kind=discovery scope=plan id=p2-step-table-keeps-old-columns created=2026-10-06T20:19:04+00:00 phase=2 -->
### p2-step-table-keeps-old-columns · discovery · the step table keeps its leading `step | turns | cost` columns and appends main/subagent columns (phase 2)

Existing PR-body assertions and readers rely on `| <step> | <turns> | <cost> |` as the row prefix, so the role
split is appended as six columns (`main|subagent` x `turns, cache-read / output, cost`) rather than replacing them.

<!-- fr:journal kind=discovery scope=plan id=p2-synth-tier-red-was-green created=2026-10-06T20:19:04+00:00 phase=2 -->
### p2-synth-tier-red-was-green · discovery · the "synthesized attempt carrying tier/bound is refused" test passed before GREEN (phase 2)

Before the fields existed, `Attempt(extra="forbid")` already refused `tier`/`bound` with a message naming the
field, so that one RED test was not observed failing; after GREEN the refusal comes from the synthesized-attempt
validator's list. The other P2.T1 tests were observed red.

<!-- fr:journal kind=discovery scope=plan id=p2-live-cursors-at-v9 created=2026-10-06T20:19:04+00:00 phase=2 -->
### p2-live-cursors-at-v9 · discovery · this repo's two live run cursors are migrated to run v9; an fr older than this branch cannot read them (phase 2)

`uv run fr migrate artifacts --yes` stamped 2026-10-06-feat-batch-cost-evidence.yaml and
2026-10-06-feat-batch-verification-kinds.yaml at 9 (stamp only). Hooks running the base clone's installed fr
(5.10.3) read a newer stamp than they know; drive this run with `uv run fr` from the worktree.

<!-- fr:journal kind=discovery scope=plan id=p2-explainer-updated created=2026-10-06T20:19:04+00:00 phase=2 -->
### p2-explainer-updated · discovery · 01-fr-goal explainer updated for fr run cost's two tables and the tier/bound record; HTML regenerated (phase 2)

The unmodified re-render with the --isolated renderer was byte-identical to the committed .html first; the
regenerated page differs only by the two edited paragraphs.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-06T20:19:04+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

moving _model_family to fr.models.model_family was the only cleanup; _observed_model's one comparison now picks bound-or-model, nothing else duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-06T20:19:04+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

a stamp-only migration module mirroring run_driver.py, plus a one-line _already_v8 delegating to _already_v7; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-06T20:19:04+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

the shared cell formatters (usd_text, count_text, compact_tokens, figure_cells, ran_text) were written into fr.run.cost in GREEN, so the CLI had no local copies left to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-10-06T20:19:04+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

pr_body renders through the same fr.run.cost formatters as the CLI (cost_markdown), so no duplicate remained; T5's tidy covered the old local usd/n helpers
