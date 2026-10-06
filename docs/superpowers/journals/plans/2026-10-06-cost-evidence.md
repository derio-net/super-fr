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
