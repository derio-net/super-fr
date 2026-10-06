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

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-06T20:40:28+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · fr run cost loaded the phase cursor only from docs/superpowers/runs/, so archived runs printed no per-phase table (phase 2)

run_cmd.py ~4905 load_run_state only; load_run_usage falls back to implemented/usage/.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-06T20:40:28+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · _observed_model returned early when observed == attempt.model, skipping the bound-vs-ran warning after a claim --model (phase 2)

run_cmd.py ~3730; OpenCode's in-child claim always passes --model (claim.ts:111).

<!-- fr:journal kind=review scope=plan id=p2-review-r1 created=2026-10-06T20:40:28+00:00 phase=2 -->
### p2-review-r1 · review · Phase 2 review (tier/bound, run kind 9, per-phase tables) (phase 2)

Independent review (feature-dev:code-reviewer, Opus) of 029e56003..64fed89d5 against R7-R9 / §D-§E: §D, run 8→9 (run_driver precedent, no cursor_guard), §E and the explainer check out; readers of attempt.model grepped repo-wide, only a cosmetic held-unit descriptor loss. Raised p2-r1 and p2-r2, both in scope, both fixed in 7d7727e1e with tests. No out-of-scope findings.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-06T20:40:28+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: fr run cost loaded the phase cursor only from docs/superpowers/runs/, so archived runs printed no per-phase table (phase 2)

7d7727e1e: _cost_cursor reads live then archived cursor, tolerating an unparseable one; test_a_closed_out_run_prints_its_per_phase_table_from_the_archive, test_an_unparseable_archived_cursor_still_prints_the_step_table.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-06T20:40:28+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: _observed_model returned early when observed == attempt.model, skipping the bound-vs-ran warning after a claim --model (phase 2)

7d7727e1e: early return only when unobserved; family compared against bound or model; test_a_claimed_model_equal_to_the_transcript_still_warns_against_bound, test_a_claimed_model_of_the_bound_family_does_not_warn.

<!-- fr:journal kind=discovery scope=plan id=p3-selector-timestamp created=2026-10-06T21:19:42+00:00 phase=3 -->
### p3-selector-timestamp · discovery · compare selectors take an ISO timestamp as well as a date (phase 3)

A bare date cuts at midnight UTC, so #514's merge (2026-09-20T16:47Z) would put a whole day's runs on one side. The selector therefore also accepts an ISO timestamp (a bare date is midnight UTC); the audit used timestamps for both cutoffs.

<!-- fr:journal kind=discovery scope=plan id=p3-no-archived-token-split created=2026-10-06T21:19:42+00:00 phase=3 -->
### p3-no-archived-token-split · discovery · no archived run carries the v2 main/subagent split (phase 3)

Only two live usage files (this run, an in-flight sibling, both unpriced) carry steps_by_role, so compare's token columns are dashes for every archived run. #593's rules were answered from v1 per-step dollars and turns of the main session instead, with the share-of-cost rule reported as not determined.

<!-- fr:journal kind=discovery scope=plan id=p3-zero-reopens-corpus created=2026-10-06T21:19:42+00:00 phase=3 -->
### p3-zero-reopens-corpus · discovery · no journal in the corpus re-opens a finding (phase 3)

Zero resolution records in the archived and live plan journals say open for a finding that was closed, so compare's re-opened column is 0 everywhere and does not discriminate; the audit says so.

<!-- fr:journal kind=discovery scope=plan id=p3-audit-conclusions created=2026-10-06T21:19:42+00:00 phase=3 -->
### p3-audit-conclusions · discovery · audit conclusions: #627 inconclusive, #793 item 5 inconclusive (leaning no change), #593 inconclusive with option 4 as the default (phase 3)

See docs/superpowers/audits/2026-10-06-cost-evidence-audit.md. The before set of #627 has no usage at all (0/13 priced); #793's after set has 5 priced runs of 15; #593's share-of-cost rule cannot be evaluated from v1 files.

<!-- fr:journal kind=discovery scope=plan id=p3-skill-line-cap created=2026-10-06T21:19:42+00:00 phase=3 -->
### p3-skill-line-cap · discovery · fr-audit SKILL.md sits at 119 lines under two line caps (phase 3)

test_skill_validation caps skills at 120 and test_fr_audit_skill requires fewer than 120; the compare mention was tightened to 119 to satisfy both.

<!-- fr:journal kind=discovery scope=plan id=p3-acceptance-row created=2026-10-06T21:19:42+00:00 phase=3 -->
### p3-acceptance-row · discovery · acceptance row cost-evidence-usage-compare moved to ci (phase 3)

set-status with refs to the compare unit tests; the engine committed that change itself.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-06T21:19:42+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

compare.py was written once against its tests; the only later change was widening the selector to timestamps, nothing left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-06T21:19:42+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

the audit is a document, there was no code to refactor

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-06T21:40:21+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · compare counted phases only from cursor phase/<n>/ keys; pre-v5 cursors list a subset and manual markers were missed (phase 3)

e.g. 2026-09-20-fix-isolation-reap-data-loss lists phase/1, its plan has 01-04.yaml; findings/phase and the #627 before median were wrong.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-10-06T21:40:21+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · findings/phase ignored the journal `phase` field and divided phaseless findings in (phase 3)

compare.py _journal_counts never read e.phase.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-10-06T21:40:21+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · audit claimed the #793 window was all Opus 5.5; the unbounded before set includes Opus 5 runs (phase 3)

Audit §2 and Data limit 4.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-10-06T21:40:21+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · audit omitted that per-run cost includes (outside run) and that a shared session counts under each run (phase 3)

fix-497 and fix-532 usage files share one session id.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-10-06T21:40:21+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · §3 (#593) figures came from an uncommitted ad hoc script, not fr usage compare as R11 requires (phase 3)

Spec R10/§F amended (246735304) to add --steps.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-10-06T21:40:21+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · fr-audit skill said 'Both are read-only … write only under the cache' over three rows (phase 3)

SKILL.md:26-28 and mirrors.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-10-06T21:40:21+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · _journal_counts re-implemented the journal fold via private _record_state (phase 3)

fr.journal.model._fold is the one walk.

<!-- fr:journal kind=review scope=plan id=p3-review-r1 created=2026-10-06T21:40:21+00:00 phase=3 -->
### p3-review-r1 · review · Phase 3 review (fr usage compare, cost-evidence audit) (phase 3)

Independent review (feature-dev:code-reviewer, Opus) of 081a20a85..8c7e543ac against R10-R11 / §F-§G, checked against real archived cursors, plans, journals and usage files. Re-open counting verified real (not 0 by construction); timestamp selectors accepted. Raised p3-r1..r7, all in scope, all fixed with tests and the audit re-quoted from corrected output. No out-of-scope findings.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-06T21:40:21+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: compare counted phases only from cursor phase/<n>/ keys; pre-v5 cursors list a subset and manual markers were missed (phase 3)

compare._plan_phase_count counts plan NN.yaml (live then archived), cursor fallback ^phase/(\d+)(/|$); test_pre_v5_cursor_reads_items_and_a_v1_usage_file, test_run_missing_its_usage_file_is_dashed_but_counted.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-10-06T21:40:21+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: findings/phase ignored the journal `phase` field and divided phaseless findings in (phase 3)

phased findings divided by phases, phaseless in an `unphased` column; test_v8_row_counts_phases_turns_split_findings_and_reopens.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-10-06T21:40:21+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: audit claimed the #793 window was all Opus 5.5; the unbounded before set includes Opus 5 runs (phase 3)

Audit §2 and Data limit 4 now say the #793 before median mixes Opus 5 and 5.5 runs; after set is Opus 5.5 only.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-10-06T21:40:21+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: audit omitted that per-run cost includes (outside run) and that a shared session counts under each run (phase 3)

compare.mark_shared: shared column, per-set count and footnote; audit data limit for §1/§2; test_a_session_shared_by_two_runs_of_a_set_is_marked, test_unshared_sets_carry_no_footnote.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-10-06T21:40:21+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: §3 (#593) figures came from an uncommitted ad hoc script, not fr usage compare as R11 requires (phase 3)

fr usage compare --steps (step_table/render_steps); audit §3 re-quoted from it, script removed; test_steps_* and test_cli_steps_prints_a_table_per_set.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-10-06T21:40:21+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: fr-audit skill said 'Both are read-only … write only under the cache' over three rows (phase 3)

fr-audit SKILL.md reworded (compare writes nothing, --steps listed); both mirrors resynced.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-10-06T21:40:21+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: _journal_counts re-implemented the journal fold via private _record_state (phase 3)

public fr.journal.model.finding_states_and_reopens on a shared _fold_full walk; test_the_journal_fold_reports_reopens_without_a_second_walk.
