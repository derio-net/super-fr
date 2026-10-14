<!-- fr:journal-schema=2 -->
# Journal: 2026-10-14-exit-gates

<!-- fr:journal kind=decision scope=plan id=plan-shape created=2026-10-13T23:06:47+00:00 -->
### plan-shape · decision · Eight agentic phases, one per ask, serial; no [manual] phase

The live verification (labels, routing, collected close-out, release) is post-merge Test Plan rows, not a phase. Skill and doc prose rides the phase that changes the behaviour it describes.

<!-- fr:journal kind=discovery scope=plan id=p1-r24-changes-existing-test created=2026-10-13T23:42:28+00:00 phase=1 -->
### p1-r24-changes-existing-test · discovery · R24 makes a section-less spec with a row verify live and no reason an error (phase 1)

test_plan_self_review_verification::test_a_spec_with_no_section_passes_unchanged asserted the opposite on a row with verify: live; it now uses a row with no verify: (the still-unchanged case). The brainstorm warning passes shape_default None, so it checks explicit strategies only, as before.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-13T23:42:28+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

Task 1 only adds a constants module and a fragment; there was nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-13T23:42:28+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

The spec_section and ExitBlock additions are each one new branch/field beside the existing ones; nothing duplicated to merge.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-10-13T23:42:28+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

Task 6 adds scenario scripts, their wiring, one prose sentence and matrix moves; nothing to clean.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-13T23:58:11+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · a gate: <row>= line naming a row id no row citing the spec has is silently ignored, so a typo drops a post-merge gate (phase 1)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-13T23:58:11+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · remap_problem is only a CLI stderr warning: missing from --json, UnicodeDecodeError not caught, later consumers need to fail closed (phase 1)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-13T23:58:11+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · a section with only gate: lines exists for this fr but not for a released fr, so effective strategies diverge under version skew (phase 1)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-13T23:58:11+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · the brainstorm warning passes shape_default=None, so rows on the shape default miss reason/scenario checks (phase 1)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-13T23:58:11+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · Exit.rank is a max over kinds, so R8's per-row downgrade guard cannot use it; expose per-row kinds (phase 1)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-13T23:58:11+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · the remap is read from the working tree while the driver reads the default branch; deliver and the driver could compute different exits (phase 1)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-13T23:58:11+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · exit.gates remap keys are unvalidated (a typo'd kind, or none) and ignored silently (phase 1)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-10-13T23:58:11+00:00 phase=1 state=open review_scope=out -->
### p1-r8 · finding [open] (reviewer: out of scope) · spec §A says an older collector refuses exit:; since gh#998 parse_triage_config drops unknown top-level keys (phase 1)

Reviewer tag: out (a spec accuracy point, not caused by the code change).

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-13T23:58:11+00:00 phase=1 -->
### p1-review-1 · review · phase 1 independent review: 8 findings (7 in, 1 out) (phase 1)

Dispatched reviewer read 3defb53b..58660915 against spec R1-R6, R24, §A, §H, §I; ran 9 targeted unit files, the shipped-verifications tripwire, mirror/skill tripwires and the two exit-gates scenarios green. Verdict: ready with fixes; no critical or important issues. Every in-scope finding verified against the code and fixed with a test in 2c89b761 (p1-r6 by a spec clarification); p1-r8 out of scope.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-13T23:58:11+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: a gate: <row>= line naming a row id no row citing the spec has is silently ignored, so a typo drops a post-merge gate (phase 1)

self-review reports the unknown id (gate line and bullet); test_p1_r1_a_gate_line_naming_an_unknown_row_is_an_error, test_p1_r1_a_bullet_naming_an_unknown_row_is_an_error (2c89b761).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-13T23:58:11+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: remap_problem is only a CLI stderr warning: missing from --json, UnicodeDecodeError not caught, later consumers need to fail closed (phase 1)

--json carries remap_problem, load_remap catches UnicodeDecodeError, Exit.remap_problem kept for phases 2-4 to fail closed on; test_p1_r2_json_carries_remap_problem, test_p1_r2_load_remap_survives_a_non_utf8_file (2c89b761).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-13T23:58:11+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: a section with only gate: lines exists for this fr but not for a released fr, so effective strategies diverge under version skew (phase 1)

a gate-only section is a self-review error asking for strategy: <name|none>; test_p1_r3_a_gate_only_section_is_an_error (2c89b761).

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-13T23:58:11+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: the brainstorm warning passes shape_default=None, so rows on the shape default miss reason/scenario checks (phase 1)

the warning threads the run state and passes shape_default(repo_root, state) on both resolve paths, still advisory; test_p1_r4_the_brainstorm_warning_sees_rows_on_the_shape_default (2c89b761).

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-13T23:58:11+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: Exit.rank is a max over kinds, so R8's per-row downgrade guard cannot use it; expose per-row kinds (phase 1)

Exit gains row_kinds and run_kind; test_p1_r5_exit_exposes_row_kinds_and_the_run_kind, test_p1_r5_a_run_without_strategy_has_run_kind_none (2c89b761).

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-13T23:58:11+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: the remap is read from the working tree while the driver reads the default branch; deliver and the driver could compute different exits (phase 1)

by design the driver never recomputes the exit: it reads the PR's verification:/gate: labels, which deliver computed from the PR's own tree; spec §A now says so (2c89b761).

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-13T23:58:11+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: exit.gates remap keys are unvalidated (a typo'd kind, or none) and ignored silently (phase 1)

self-review warns on a remap key that is none or names no strategy; test_p1_r7_a_remap_key_naming_no_strategy_warns, test_p1_r7_the_key_none_warns (2c89b761).

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-10-13T23:58:11+00:00 phase=1 state=open resolves=p1-r8 out_of_scope=true -->
### p1-r8-resolved · finding [out-of-scope] · resolves p1-r8: spec §A says an older collector refuses exit:; since gh#998 parse_triage_config drops unknown top-level keys (phase 1)

Not caused by phase 1's code: the claim was in the spec text. The stale sentence was corrected in spec §A in passing (2c89b761); the finding stays out of scope as the reviewer tagged it.

<!-- fr:journal kind=decision scope=plan id=p2-label-sync-seam created=2026-10-14T01:10:19+00:00 phase=2 -->
### p2-label-sync-seam · decision · sync_exit_labels reaches its forge through fr.verification.labels.client_for (phase 2)

A brainstorm/spec-review/deliver resolve now calls the forge, so tests/conftest.py gains an autouse fixture that points that one name at a client which cannot label a PR (a warning, as on GitLab); a test of the sync passes its own fake client. A missing origin or PR is PrNotFound, silent at the early points. A non-empty Exit.remap_problem refuses the sync (fail closed), so deliver refuses naming it.

<!-- fr:journal kind=decision scope=plan id=p2-downgrade-guard-per-row created=2026-10-14T01:10:19+00:00 phase=2 -->
### p2-downgrade-guard-per-row · decision · The R8 guard compares per row and for the run, not Exit.rank (phase 2)

weakened() compares run_kind/run_gate and each row's row_kinds/row_gates: a post-merge gate that leaves a row (or the run), or a kind of lower kind_rank, is a downgrade, once spec-review is done. A row lowered beside one that still holds the maximum rank is caught. The operator claim is verified by the same transcript reader journal resolve uses (journal.operator.verify_operator_answer, factored out of verify_operator_claim), windowed from the spec-review step's completion. A non-empty remap_problem before or after refuses the change.

<!-- fr:journal kind=discovery scope=plan id=p2-decision-answered-by-not-yet created=2026-10-14T01:10:19+00:00 phase=2 -->
### p2-decision-answered-by-not-yet · discovery · A journal decision cannot carry answered_by yet (R12 is a later phase) (phase 2)

JournalEntry.answered_by is valid only on a resolution record, so the exit-change decision states the operator answer in its body; phase 5's R12 header tokens can replace that.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-14T01:10:19+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

Two protocol methods, one implementation per client delegating to the issue methods, and the fake gained two methods; nothing duplicated to merge.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-14T01:10:19+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

Two label constructors beside spec_label and one module over run_exit; no second copy of a family or a sync loop.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-14T01:10:19+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

Two small helpers beside _deliver_pr_gate, each calling the one sync function; nothing to merge.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t5 created=2026-10-14T01:10:19+00:00 phase=2 -->
### no-refactor-p2-t5 · discovery · no-refactor-because P2.T5 (phase 2)

A scenario script, its wiring, two prose sentences and two matrix moves; nothing to clean.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · early label sync never fires: _emitted_pr finds only deliver's pr; tests monkeypatched it (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · guard/early sync keyed on literal step id spec-review; fr-goal-light's spec-plan-review leaves the R8 guard off (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · hand-editing ## Verification after spec-review lowers the exit unchecked (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · operator-answer window is since spec-review done (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · unverified advisory not persisted in the exit-change decision (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · unreadable exit only warns at deliver (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · deliver warns on any PrNotFound incl. GitHub no-open-PR (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · post-merge gate swapped for another is not a lowering (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p2-r9 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r9 · finding [open] (reviewer: in scope) · set accepts an unresolvable strategy (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p2-r10 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r10 · finding [open] (reviewer: in scope) · row change overwrites rationale; gate-only set inexpressible (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p2-r11 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r11 · finding [open] (reviewer: in scope) · labels created before the forge is known to support them (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p2-r12 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r12 · finding [open] (reviewer: in scope) · a no-op set still journals and commits (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p2-r13 created=2026-10-14T01:56:03+00:00 phase=2 state=open review_scope=in -->
### p2-r13 · finding [open] (reviewer: in scope) · set_cmd prints spec_rel with Rich markup (phase 2)

Reviewer tag: in.

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-10-14T01:56:03+00:00 phase=2 -->
### p2-review-1 · review · phase 2 independent review: 13 findings (13 in, 0 out) (phase 2)

Dispatched reviewer read 5dddc4d2..b07f6097 against R7, R8, §B, §I (fr-goal), ruled on four named concerns (hand-edit bypass: confirmed p2-r3; answer window: confirmed p2-r4; fail-open: kept per R8, advisory persisted p2-r5; unreadable exit at deliver: p2-r6), checked the last three tests fail on old code. Verdict: with fixes. All 13 verified and fixed with tests in 90ee2beb; CI green.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: early label sync never fires: _emitted_pr finds only deliver's pr; tests monkeypatched it (phase 2)

branch lookup restored at brainstorm/spec-review; test_p2_r1_the_early_sync_finds_the_pr_by_the_branch (no _emitted_pr patch). (90ee2beb, CI green)

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: guard/early sync keyed on literal step id spec-review; fr-goal-light's spec-plan-review leaves the R8 guard off (phase 2)

spec-reviewing step derived from the manifest's fr-spec-reviewer agent with literal fallback; test_p2_r2_the_guard_applies_on_fr_goal_light. (90ee2beb, CI green)

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: hand-editing ## Verification after spec-review lowers the exit unchecked (phase 2)

spec-review resolve journals an exit-baseline decision; deliver refuses a lowering not covered by an operator-answered exit-change decision (fr/verification/baseline.py); test_p2_r3_deliver_refuses_a_lowering_nothing_accounts_for. (90ee2beb, CI green)

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: operator-answer window is since spec-review done (phase 2)

window opens at the later of the review and the latest exit-change decision; test_p2_r4_the_answer_window_opens_at_the_later_of_review_and_last_change. (90ee2beb, CI green)

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: unverified advisory not persisted in the exit-change decision (phase 2)

advisory appended to the decision body; test_p2_r5_an_unverified_claim_is_marked_in_the_decision. (90ee2beb, CI green)

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: unreadable exit only warns at deliver (phase 2)

SyncOutcome.unknown refuses deliver, warns early; test_p2_r6_an_unreadable_exit_refuses_deliver_and_only_warns_early. (90ee2beb, CI green)

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: deliver warns on any PrNotFound incl. GitHub no-open-PR (phase 2)

no open PR refuses at deliver; only an undeterminable forge (no origin) warns; test_p2_r7_no_open_pr_refuses_deliver_but_an_unknown_forge_only_warns. (90ee2beb, CI green)

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: post-merge gate swapped for another is not a lowering (phase 2)

a swap needs the operator; test_p2_r8_replacing_one_post_merge_gate_with_another_needs_the_operator. (90ee2beb, CI green)

<!-- fr:journal kind=finding scope=plan id=p2-r9-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r9 -->
### p2-r9-resolved · finding [fixed] · resolves p2-r9: set accepts an unresolvable strategy (phase 2)

refused before any write; test_p2_r9_an_unknown_strategy_is_refused_before_anything_is_written. (90ee2beb, CI green)

<!-- fr:journal kind=finding scope=plan id=p2-r10-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r10 -->
### p2-r10-resolved · finding [fixed] · resolves p2-r10: row change overwrites rationale; gate-only set inexpressible (phase 2)

--strategy optional with --gate, rationale kept; test_p2_r10_a_gate_only_change_keeps_the_strategy_and_a_row_keeps_its_rationale. (90ee2beb, CI green)

<!-- fr:journal kind=finding scope=plan id=p2-r11-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r11 -->
### p2-r11-resolved · finding [fixed] · resolves p2-r11: labels created before the forge is known to support them (phase 2)

PR probed before ensure_labels; test_p2_r11_an_unsupported_forge_creates_no_labels. (90ee2beb, CI green)

<!-- fr:journal kind=finding scope=plan id=p2-r12-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r12 -->
### p2-r12-resolved · finding [fixed] · resolves p2-r12: a no-op set still journals and commits (phase 2)

unchanged, nothing written; test_p2_r12_a_no_op_writes_nothing. (90ee2beb, CI green)

<!-- fr:journal kind=finding scope=plan id=p2-r13-resolved created=2026-10-14T01:56:03+00:00 phase=2 state=fixed resolves=p2-r13 -->
### p2-r13-resolved · finding [fixed] · resolves p2-r13: set_cmd prints spec_rel with Rich markup (phase 2)

markup=False; test_p2_r13_the_success_line_is_printed_literally. (90ee2beb, CI green)

<!-- fr:journal kind=decision scope=plan id=p3-narrowing-filing created=2026-10-14T03:23:35+00:00 phase=3 -->
### p3-narrowing-filing · decision · Filing a narrowing decision appends a decision with the same narrows= and tracked_by= (phase 3)

The journal is append-only and a decision has no resolution record, so `fr journal file` appends `<id>-filed`: a decision carrying the original's `narrows=` (and `gate=`) plus `tracked_by=<issue>`. A narrowing decision is a decision with `narrows=` and no `tracked_by=`; it is accounted when a later decision with the same narrows set carries `tracked_by=` (fr.journal.file.narrowing_accounted). R11's operator check reads only narrowing decisions, never the filing.

<!-- fr:journal kind=decision scope=plan id=p3-brainstorm-operator-decisions created=2026-10-14T03:23:35+00:00 phase=3 -->
### p3-brainstorm-operator-decisions · decision · The brainstorm record writes answered_by=operator on its decisions when its gate is cleared by asking (phase 3)

apply_record marks a record operator_decisions when its step clears an operator gate, it is not no_questions, and evidence.answered_by is not agent. Its decisions with no answered_by are written answered_by=operator and skip the transcript check (the gate's own question-round check verifies it; a refusal restores every byte). An item saying agent is kept. Elsewhere a decision claiming operator is verified against the transcript since the journal's last entry (an empty journal: the whole session).

<!-- fr:journal kind=decision scope=plan id=p3-leftover-rules created=2026-10-14T03:23:35+00:00 phase=3 -->
### p3-leftover-rules · decision · Leftovers gate runs before the PR body; tracking none keeps only the gate route for rows; a walked gated row may close (phase 3)

`_deliver_leftovers_gate` runs before `_deliver_pr_gate`, so the body renders with the deferrals already recorded. An unreadable exit judges no row there (the label sync refuses it). Under tracking none the journal kinds are not leftovers and an owed row's only fix is `fr verification set --gate`. A gated row stops holding its issue once walk-verified (R14's rows-walked pass), as a post-merge row already did.

<!-- fr:journal kind=discovery scope=plan id=p3-journal-item-filed-as created=2026-10-14T03:23:35+00:00 phase=3 -->
### p3-journal-item-filed-as · discovery · JournalItem also gained filed_as, inside the same record 9 -> 10 hop (phase 3)

`fr journal file` writes through the record engine, and an owed entry's filing record carries filed_as=, which no record field expressed. JournalItem.filed_as rides the same kind-10 bump; the engine accepts a `resolves` naming an owed entry only when filed_as is set (discharge stays `fr journal resolve`'s).

<!-- fr:journal kind=discovery scope=plan id=p3-deliver-fixtures-account created=2026-10-14T03:23:35+00:00 phase=3 -->
### p3-deliver-fixtures-account · discovery · Deliver test fixtures now account for their leftovers (phase 3)

The shared `_at_deliver` fixture defers its out-of-scope finding to an issue and gives the seeded unwired row an issue (account_seeded_row); the fr-goal shape walk does the same before deliver. tests/integration/test_exit_gates_deliver.py keeps the unaccounted path end to end.

<!-- fr:journal kind=finding scope=plan id=p3-older-fr-refuses-decision-tokens created=2026-10-14T03:23:35+00:00 phase=3 state=open review_scope=in -->
### p3-older-fr-refuses-decision-tokens · finding [open] (reviewer: in scope) · A released fr refuses answered_by= and tracked_by= on a decision, so spec §C's "an older fr ignores them" holds only for gate= and narrows= (phase 3)

parse_journal reads tokens by name, so an unknown token (gate=, narrows=) is ignored by fr <= 5.26. But answered_by= and tracked_by= are tokens it already knows and validates: its JournalEntry refuses answered_by off a resolution record and tracked_by off an open one, so a journal holding an operator-answered or filed narrowing decision is a parse error for an older fr. Built as the spec and the brief name the tokens; the journal stamp was not moved. Options: move the journal kind (migration), or spell the decision tokens differently.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-14T03:23:35+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

Three header tokens beside the existing ones, one projection helper each; the serializer's tuple join is the only new branch, so nothing duplicated to merge.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-14T03:23:35+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

A stamp-only hop guarding with the live model (a superset of v9), three optional JournalItem fields and one context flag in the engine; nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-10-14T03:23:35+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

fr/journal/file.py only plans and builds one record over the archive's two filers and the record engine; no filer or journal fold was copied.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t5 created=2026-10-14T03:23:35+00:00 phase=3 -->
### no-refactor-p3-t5 · discovery · no-refactor-because P3.T5 (phase 3)

Prose, mirrors, a re-rendered explainer and one matrix move; nothing to clean.
