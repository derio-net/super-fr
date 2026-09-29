# Journal: 2026-09-29-batch-plan-inputs

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-29T11:09:46+00:00 -->
### repro · repro · take 10 (#817): stray 'none.', question-worded unobservable message on reviewer gate, scratch .records/ yaml refused as 'must be migrated', unexplained tier: hard

Members #813 #812 #815, fr 4.35.0 on OpenCode + GitLab. See the issues for transcripts.

<!-- fr:journal kind=root-cause scope=debug id=rc-815-none created=2026-09-29T11:09:46+00:00 -->
### rc-815-none · root-cause · proportionality asks section: _bullets([]) returns ['none.'] when every phase has its own ask

packages/fr/src/fr/proportionality.py:222 reuses _bullets, whose empty sentinel suits list sections but dangles after the count line.

<!-- fr:journal kind=root-cause scope=debug id=rc-815-unobservable created=2026-09-29T11:09:47+00:00 -->
### rc-815-unobservable · root-cause · _why_unobservable() is gate-agnostic and hard-codes 'questions'

run_cmd.py:242; called by the operator-gate (:1233) and the reviewer gate (:2254).

<!-- fr:journal kind=root-cause scope=debug id=rc-812-records created=2026-09-29T11:09:48+00:00 -->
### rc-812-records · root-cause · record locator claims every *.records/*.yaml; trigger words an unreadable artifact as 'must be migrated'; fr-plan names no scratch home

registry.py:444 locator; trigger.py:581 _will_not_act_here shared wording; skills/fr-plan/SKILL.md.

<!-- fr:journal kind=root-cause scope=debug id=rc-813-tier created=2026-09-29T11:09:49+00:00 -->
### rc-813-tier · root-cause · fr-plan lists tiers without criteria and self-review asks no reason for tier above standard

skills/fr-plan/SKILL.md:80. A policy gap, not a code defect.

<!-- fr:journal kind=decision scope=debug id=batch-not-one-cause created=2026-09-29T11:09:49+00:00 -->
### batch-not-one-cause · decision · Batch spans four independent root causes; paused for operator direction before any fix

Per batch rule. Proposed: fix all four in one PR; #813's reason as a spec-journal decision (no plan shape change), so no artifact current_version moves.

<!-- fr:journal kind=finding scope=debug id=fix-815-none created=2026-09-29T11:56:05+00:00 state=fixed -->
### fix-815-none · finding [fixed] · Phases section lists only phases with no ask; no bare none.

proportionality.py; pinned by test_plan_proportionality::test_the_folded_shape_has_no_phase_without_an_ask (changed from pinning the bug).

<!-- fr:journal kind=finding scope=debug id=fix-815-unobservable created=2026-09-29T11:56:05+00:00 state=fixed -->
### fix-815-unobservable · finding [fixed] · _why_unobservable(what) — reviewer gate says subagent dispatches

run_cmd.py; test_run_evidence_separate_context::test_an_unobservable_reviewer_names_dispatches_not_questions.

<!-- fr:journal kind=finding scope=debug id=fix-812-unreadable created=2026-09-29T11:56:06+00:00 state=fixed -->
### fix-812-unreadable · finding [fixed] · Unreadable artifact named with its error; non-mapping body is a failure; scratch inputs to $TMPDIR

registry._yaml_read_key, runner.inspection_failures, trigger._will_not_act_here/_cannot_read; fr-plan SKILL. Locator NOT narrowed: silently skipping a stray .records/ file would let it be committed unseen; naming it loudly is the structural fix. test_migration_trigger::test_a_non_interactive_refusal_names_an_unreadable_file_not_a_migration.

<!-- fr:journal kind=finding scope=debug id=fix-813-tier created=2026-09-29T11:56:07+00:00 state=fixed -->
### fix-813-tier · finding [fixed] · Tier criteria in fr-plan; self-review errors on hard without a tier-<plan>-p<N> decision

plan_ops._tier_issues, phase_sizing.tier_reasons; tests/unit/test_plan_tier_reason.py.
