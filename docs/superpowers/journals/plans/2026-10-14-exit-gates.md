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

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-14T04:19:31+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · released fr refuses answered_by=/tracked_by= on a decision; every operator-answered spec journal would become unparseable (phase 3)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-10-14T04:19:31+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · brainstorm-gate stamp marks unasked narrows= decisions operator, waiving R11 (phase 3)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-10-14T04:19:31+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · stamp reads the claimed answered_by, not the derived provenance (phase 3)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-10-14T04:19:31+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · _journals silently drops an unparseable journal (phase 3)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-10-14T04:19:31+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · an owed row's tracking issue can be closed by Closes #n (phase 3)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-10-14T04:19:31+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · plan_filing defers in-scope open findings (phase 3)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-10-14T04:19:31+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · old-reader test never exercised answered_by/tracked_by (phase 3)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-10-14T04:19:31+00:00 phase=3 state=open review_scope=in -->
### p3-r8 · finding [open] (reviewer: in scope) · migration description omits filed_as (phase 3)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p3-r9 created=2026-10-14T04:19:31+00:00 phase=3 state=open review_scope=in -->
### p3-r9 · finding [open] (reviewer: in scope) · no e2e deliver under tracking none with an unfiled finding (phase 3)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p3-r10 created=2026-10-14T04:19:31+00:00 phase=3 state=open review_scope=out -->
### p3-r10 · finding [open] (reviewer: out of scope) · verify_operator_answer opens its window at 1970 on an empty journal and accepts any answer since the journal last moved (phase 3)

Reviewer tag: out (the existing resolution-claim verifier has the same weakness).

<!-- fr:journal kind=review scope=plan id=p3-review-1 created=2026-10-14T04:19:31+00:00 phase=3 -->
### p3-review-1 · review · phase 3 independent review: 10 findings (9 in, 1 out) (phase 3)

Dispatched reviewer read a7f81181..172aa3f0 against R9-R12, §C and the artifact-versioning and explainers rules; ruled on token compatibility (confirmed against origin/main, p3-r1), narrowing self-authorization (p3-r2), claimed vs derived provenance (p3-r3), leftover predicates (match; gaps p3-r4..r6), fixtures (justified) and the record kind 10 migration (compliant). A security review added exact ref matching to p3-r2. All 9 in-scope fixed with tests in 73cb6792; CI green.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-14T04:19:31+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: released fr refuses answered_by=/tracked_by= on a decision; every operator-answered spec journal would become unparseable (phase 3)

decision-only tokens decided_by= and remainder_tracked_by=, answered_by/tracked_by resolution-only as released, spec R9/R10/R12/§C amended (decision decision-token-names); test_p3_r7_the_released_reader_parses_every_new_token (vendored fr 5.26 reader), test_p3_r1_the_live_model_keeps_answered_by_and_tracked_by_resolution_only. (73cb6792, CI green)

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-10-14T04:19:31+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: brainstorm-gate stamp marks unasked narrows= decisions operator, waiving R11 (phase 3)

a narrowing is the operator's only when every narrowed ref, normalized like the Closes guard, appears in an answered round; test_p3_r2_narrowed_refs_match_answered_rounds_exactly (9 cases), test_p3_r2_a_narrowing_no_answered_round_names_stays_the_agents. (73cb6792, CI green)

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-10-14T04:19:31+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: stamp reads the claimed answered_by, not the derived provenance (phase 3)

stamp computed from the gate's derived provenance; unobserved never stamps a narrowing; test_p3_r3_an_unobserved_gate_never_stamps_a_narrowing_and_notes_the_rest. (73cb6792, CI green)

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-10-14T04:19:31+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: _journals silently drops an unparseable journal (phase 3)

deliver gates refuse naming it; test_p3_r4_an_unparseable_journal_refuses_the_deliver_gates_naming_it. (73cb6792, CI green)

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-10-14T04:19:31+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: an owed row's tracking issue can be closed by Closes #n (phase 3)

refused; test_p3_r5_a_close_over_an_owed_rows_tracking_issue_is_refused. (73cb6792, CI green)

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-10-14T04:19:31+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: plan_filing defers in-scope open findings (phase 3)

only out-of-scope findings file; test_an_unfileable_id_is_refused_and_nothing_is_filed_or_written. (73cb6792, CI green)

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-10-14T04:19:31+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: old-reader test never exercised answered_by/tracked_by (phase 3)

rewritten against a vendored released reader; test_p3_r7_the_released_reader_parses_every_new_token. (73cb6792, CI green)

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-10-14T04:19:31+00:00 phase=3 state=fixed resolves=p3-r8 -->
### p3-r8-resolved · finding [fixed] · resolves p3-r8: migration description omits filed_as (phase 3)

named; test_p3_r8_the_migration_names_every_field_it_adds. (73cb6792, CI green)

<!-- fr:journal kind=finding scope=plan id=p3-r9-resolved created=2026-10-14T04:19:31+00:00 phase=3 state=fixed resolves=p3-r9 -->
### p3-r9-resolved · finding [fixed] · resolves p3-r9: no e2e deliver under tracking none with an unfiled finding (phase 3)

test_p3_r9_under_tracking_none_an_unfiled_out_of_scope_finding_delivers_and_is_listed (guards pre-existing behaviour, so not red-first). (73cb6792, CI green)

<!-- fr:journal kind=finding scope=plan id=p3-r10-resolved created=2026-10-14T04:19:31+00:00 phase=3 state=open resolves=p3-r10 out_of_scope=true -->
### p3-r10-resolved · finding [out-of-scope] · resolves p3-r10: verify_operator_answer opens its window at 1970 on an empty journal and accepts any answer since the journal last moved (phase 3)

Pre-existing in the shared operator-claim verifier used by fr journal resolve --answered-by; this change reuses it unchanged.

<!-- fr:journal kind=finding scope=plan id=p3-older-fr-refuses-decision-tokens-resolved created=2026-10-14T04:19:31+00:00 phase=3 state=fixed resolves=p3-older-fr-refuses-decision-tokens -->
### p3-older-fr-refuses-decision-tokens-resolved · finding [fixed] · resolves p3-older-fr-refuses-decision-tokens: A released fr refuses answered_by= and tracked_by= on a decision, so spec §C's "an older fr ignores them" holds only for gate= and narrows= (phase 3)

Same defect as p3-r1, fixed by the decided_by=/remainder_tracked_by= tokens (73cb6792).

<!-- fr:journal kind=decision scope=plan id=p4-gated-never-keeps-a-drive-alive created=2026-10-14T05:10:19+00:00 phase=4 -->
### p4-gated-never-keeps-a-drive-alive · decision · A gated batch counts in Summary.gated and never keeps a drive alive (phase 4)

A post-merge gate waits on a person (a walk, or `fr gate pass`), possibly for days, so a gated landed batch is neither closing nor blocked: `Summary.gated` counts it, the summary line says `gated N`, and `done` ignores it, as a batch awaiting its live walk already was (AWAITING_LIVE_HOLD). The rows-walked pass is detected by the next drive pass that runs; a loop does not poll for it.

<!-- fr:journal kind=decision scope=plan id=p4-ledger-rows-in-a-worktree created=2026-10-14T05:10:19+00:00 phase=4 -->
### p4-ledger-rows-in-a-worktree · decision · The gated rows are read in a detached worktree of origin/<default>, cached per tip (phase 4)

`fr.triage.ledger.gated_rows_at` adds a detached worktree at the default branch's tip through `Checkout.add_worktree`, runs `run_exit` there and removes it. Not `snapshot_paths`: it drops file modes, and the exit's shape default is filtered by whether `.fr/candidate-install` is executable, so a snapshot could compute a different exit than the PR's tree. Which gates hold the batch is never recomputed (the merged PR's labels say it, `held_gates`); only which rows each gate gates, their `walked` status and their issues come from the tree. The driver caches rows per (repo, tip sha, branch). A run-level gate with no row is never passed by the driver.

<!-- fr:journal kind=decision scope=plan id=p4-cursor-position-raw created=2026-10-14T05:10:19+00:00 phase=4 -->
### p4-cursor-position-raw · decision · The cursor position is read from the raw cursor YAML at the PR head, per head sha (phase 4)

`fr.triage.cursor.cursor_position` reads a raw mapping (a cursor at a PR head may be written by an older or newer fr than the reader): deliver done, else the cursor step `blocked` (its gate), else a `manual` unit that is all that is left of the cursor step, else `none`. `read_cursor` reaches the head through `Checkout.reach_commit` (fetching origin's branch once) and `Checkout.list_dir`/`show`. Only an OPEN PR of an unfinished batch gets one; the driver caches it per (repo, head sha). Plain `fr triage collect` passes no reader, so its facts carry no cursor; the drive's do.

<!-- fr:journal kind=discovery scope=plan id=p4-merged-label-reads created=2026-10-14T05:10:19+00:00 phase=4 -->
### p4-merged-label-reads · discovery · The gate ledger costs one PR view per merged PR of an unfinished batch per collect (phase 4)

No list read carries a merged PR's labels, so collect reads them with one `pr_view` (`Forge.pr_labels`) per merged PR on a ledger branch: every dispatched, uncancelled batch without a close-out recorded archived. A finished batch costs nothing. A failed read leaves `labels` None (unread), which no reader takes as ungated evidence.

<!-- fr:journal kind=finding scope=plan id=p4-gated-post-merge-delayed created=2026-10-14T05:10:19+00:00 phase=4 state=open review_scope=out -->
### p4-gated-post-merge-delayed · finding [open] (reviewer: out of scope) · A gated batch's post_merge waits for its gate, yet the tester walks the merged build (phase 4)

The driver runs a repo's `post_merge` (e.g. `./scripts/install.sh`) only inside the close-out action. R13 skips the close-out of a gated batch, so the driver no longer installs a gated merge until its gate passes, while R14's walk is of exactly that merged build. The board's post-merge need now skips a gated batch (is_gated), so it does not report this either. Phase 6 restructures close-out (collected close-out, R15); running post_merge for a landed gated batch apart from its close-out belongs there or in its own issue.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-10-14T05:10:19+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

The ledger reads are one helper (_ledger_reads) applied once to every PR list collect builds; the cursor reader is one pure function plus one gitseam-only reader, and the schema pins moved with sed; nothing duplicated to merge.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t3 created=2026-10-14T05:10:19+00:00 phase=4 -->
### no-refactor-p4-t3 · discovery · no-refactor-because P4.T3 (phase 4)

gate_cmd is one command over pass_gate, the helper the driver's gate-pass executor already calls, so the swap and comment exist once; nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t4 created=2026-10-14T05:10:19+00:00 phase=4 -->
### no-refactor-p4-t4 · discovery · no-refactor-because P4.T4 (phase 4)

One fr acceptance set-status call; nothing to clean.

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-10-14T05:54:33+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · failed merged-PR label read leaves the batch ungated and closes it out (fail-open) (phase 4)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-10-14T05:54:33+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · gated batch's post_merge deferred until its gate passes; needs_you hid it (phase 4)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-10-14T05:54:33+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · run-level gate no row inherits auto-passed via an unrelated row gate (phase 4)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-10-14T05:54:33+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · pass_gate swaps labels before commenting; a failed comment is lost (phase 4)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-10-14T05:54:33+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · fr gate pass accepts an unmerged PR (phase 4)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p4-r6 created=2026-10-14T05:54:33+00:00 phase=4 state=open review_scope=in -->
### p4-r6 · finding [open] (reviewer: in scope) · fr gate pass --repo always builds a github.com client (phase 4)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p4-r7 created=2026-10-14T05:54:33+00:00 phase=4 state=open review_scope=in -->
### p4-r7 · finding [open] (reviewer: in scope) · per-pass cost: pr_view per batch, fetch per gated batch, worktree in plan mode (phase 4)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p4-r8 created=2026-10-14T05:54:33+00:00 phase=4 state=open review_scope=in -->
### p4-r8 · finding [open] (reviewer: in scope) · awaiting-live re-added every pass, spec said first pass (phase 4)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p4-r9 created=2026-10-14T05:54:33+00:00 phase=4 state=open review_scope=in -->
### p4-r9 · finding [open] (reviewer: in scope) · release command printed while other gates still hold (phase 4)

Reviewer tag: in.

<!-- fr:journal kind=review scope=plan id=p4-review-1 created=2026-10-14T05:54:33+00:00 phase=4 -->
### p4-review-1 · review · phase 4 independent review: 9 findings (9 in, 0 out) (phase 4)

Dispatched reviewer read b736af59..d735686c against R13, R14, §D; ruled drive_pass pure, gate rows from run_exit, swap idempotent, awaiting-live narrow, FACTS_SCHEMA 12 = main+1, fr gate pass refusals; found the fail-open ledger read (p4-r1) and the circular post_merge hold (p4-r2). All 9 fixed with tests in 9b543573; CI green.

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-10-14T05:54:33+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: failed merged-PR label read leaves the batch ungated and closes it out (fail-open) (phase 4)

ledger-unknown held: close-out skipped with a ledger-unread action; test_p4_r1_a_ledger_that_could_not_be_read_holds_the_closeout. (9b543573, CI green)

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-10-14T05:54:33+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: gated batch's post_merge deferred until its gate passes; needs_you hid it (phase 4)

post_merge is its own action at merge for every landed batch, close-out held until PostMergeEvent; views exemption dropped; test_p4_r2_a_gated_batch_gets_its_post_merge_at_merge_but_no_closeout, test_p4_r2_the_board_shows_a_gated_batchs_unfinished_post_merge. (9b543573, CI green)

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-10-14T05:54:33+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: run-level gate no row inherits auto-passed via an unrelated row gate (phase 4)

ledger carries run_gate/run_gate_inherited; test_p4_r3_a_run_gate_no_row_inherits_never_auto_passes. (9b543573, CI green)

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-10-14T05:54:33+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: pass_gate swaps labels before commenting; a failed comment is lost (phase 4)

comment first, never twice; test_p4_r4_pass_gate_comments_first_and_never_twice. (9b543573, CI green)

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-10-14T05:54:33+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: fr gate pass accepts an unmerged PR (phase 4)

refused; test_p4_r5_it_refuses_a_pr_that_is_not_merged. (9b543573, CI green)

<!-- fr:journal kind=finding scope=plan id=p4-r6-resolved created=2026-10-14T05:54:33+00:00 phase=4 state=fixed resolves=p4-r6 -->
### p4-r6-resolved · finding [fixed] · resolves p4-r6: fr gate pass --repo always builds a github.com client (phase 4)

host resolved; test_p4_r6_the_host_is_the_named_one_or_the_checkouts_origin. (9b543573, CI green)

<!-- fr:journal kind=finding scope=plan id=p4-r7-resolved created=2026-10-14T05:54:33+00:00 phase=4 state=fixed resolves=p4-r7 -->
### p4-r7-resolved · finding [fixed] · resolves p4-r7: per-pass cost: pr_view per batch, fetch per gated batch, worktree in plan mode (phase 4)

settled labels carried, one fetch per repo per pass, ledger read without a worktree; test_p4_r7_a_pass_fetches_each_repo_once_however_many_batches_are_gated, test_p4_r7_the_ledger_read_adds_no_worktree. (9b543573, CI green)

<!-- fr:journal kind=finding scope=plan id=p4-r8-resolved created=2026-10-14T05:54:33+00:00 phase=4 state=fixed resolves=p4-r8 -->
### p4-r8-resolved · finding [fixed] · resolves p4-r8: awaiting-live re-added every pass, spec said first pass (phase 4)

re-adding is intended; spec R13 amended; test_p4_r8_every_pass_re_adds_a_missing_awaiting_live_label pins it. (9b543573, CI green)

<!-- fr:journal kind=finding scope=plan id=p4-r9-resolved created=2026-10-14T05:54:33+00:00 phase=4 state=fixed resolves=p4-r9 -->
### p4-r9-resolved · finding [fixed] · resolves p4-r9: release command printed while other gates still hold (phase 4)

printed only when no held gate remains; test_p4_r9_no_release_command_while_another_gate_still_holds. (9b543573, CI green)

<!-- fr:journal kind=finding scope=plan id=p4-gated-post-merge-delayed-resolved created=2026-10-14T05:54:33+00:00 phase=4 state=open resolves=p4-gated-post-merge-delayed out_of_scope=true -->
### p4-gated-post-merge-delayed-resolved · finding [out-of-scope] · resolves p4-gated-post-merge-delayed: A gated batch's post_merge waits for its gate, yet the tester walks the merged build (phase 4)

The executor tagged it out of scope; the reviewer reclassified the same defect in scope as p4-r2, fixed in 9b543573. This entry stays as the executor recorded it.

<!-- fr:journal kind=discovery scope=plan id=p5-1107-salvage created=2026-10-14T06:16:40+00:00 phase=5 -->
### p5-1107-salvage · discovery · #1107 read: nothing salvaged (phase 5)

PR 1107 (batch-sweep-status-lanes) derives human lanes from a run cursor at the PR head too, but it is a parallel design (its own matrix row, gitseam reader, scenario) written against session-status-era kanban code. Phase 4 already put cursor_position/read_cursor (fr/triage/cursor.py, facts schema 12) in place, so nothing was copied; lane_of reads PullRequest.cursor. #1107 can be closed once this ships (spec F).

<!-- fr:journal kind=decision scope=plan id=p5-ledger-unknown-lane created=2026-10-14T06:16:40+00:00 phase=5 -->
### p5-ledger-unknown-lane · decision · A landed batch with an unread gate ledger sits in Needs you · Developer (phase 5)

Not Done and not Closing out, so an operator sees it: lane_of puts a landed, not closed-out batch whose merged-PR labels collect could not read in needs-developer, reason saying which gate holds it is unknown and the next collect retries. The card leaves the lane when a collect reads the labels.

<!-- fr:journal kind=decision scope=plan id=p5-lane-one-function created=2026-10-14T06:16:40+00:00 phase=5 -->
### p5-lane-one-function · decision · lane_of (triage/lanes.py) is the one lane function (phase 5)

column_of and needs_you both call it, from facts alone (cursor, approval_verdict on the PR labels and events, a live merge stop, held_gates on the merged PR labels). live_stops moved there from kanban to avoid a kanban/views cycle. needs_you gained an optional stops argument; render.py's caller passes none, so a recorded merge stop lane shows on the board only.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-10-14T06:16:40+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

mergeability.py is one two-line predicate and one string; the hint call site is a single branch in _card, nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t3 created=2026-10-14T06:16:40+00:00 phase=5 -->
### no-refactor-p5-t3 · discovery · no-refactor-because P5.T3 (phase 5)

prose and a matrix status move only; lane logic was already one function (P5.T2.S3)

<!-- fr:journal kind=decision scope=plan id=p5-ledger-unknown-lane-2 created=2026-10-14T06:22:28+00:00 phase=5 -->
### p5-ledger-unknown-lane-2 · decision · Supersedes p5-ledger-unknown-lane: an unread gate ledger stays in Closing out (phase 5)

lane_of no longer places a landed batch with unread gate labels in Needs you - Developer. It stays in Closing out with the driver's ledger-unread hint (gate labels unread; close-out waits), and needs_you lists it under a distinct ledger-unread kind (not a role lane) until the next collect reads them.

<!-- fr:journal kind=finding scope=plan id=p5-r1 created=2026-10-14T06:39:40+00:00 phase=5 state=open review_scope=in -->
### p5-r1 · finding [open] (reviewer: in scope) · merge stops never reach Needs you now; board lane and Needs-you disagree (§F) (phase 5)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p5-r2 created=2026-10-14T06:39:40+00:00 phase=5 state=open review_scope=in -->
### p5-r2 · finding [open] (reviewer: in scope) · ledger-unread batch placed in Needs you · Developer (phase 5)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p5-r3 created=2026-10-14T06:39:40+00:00 phase=5 state=open review_scope=in -->
### p5-r3 · finding [open] (reviewer: in scope) · duplicate approve-pr and needs-reviewer rows (phase 5)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p5-r4 created=2026-10-14T06:39:40+00:00 phase=5 state=open review_scope=in -->
### p5-r4 · finding [open] (reviewer: in scope) · reviewer lane hint outranks red-CI hints (phase 5)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p5-r5 created=2026-10-14T06:39:40+00:00 phase=5 state=open review_scope=in -->
### p5-r5 · finding [open] (reviewer: in scope) · stop vs gate precedence differs between hint and column (phase 5)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p5-r6 created=2026-10-14T06:39:40+00:00 phase=5 state=open review_scope=in -->
### p5-r6 · finding [open] (reviewer: in scope) · Tester/DevOps reason names one gate and not what is owed (phase 5)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p5-r7 created=2026-10-14T06:39:40+00:00 phase=5 state=open review_scope=in -->
### p5-r7 · finding [open] (reviewer: in scope) · conflicting hint covers only merge, not enqueue (phase 5)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p5-r8 created=2026-10-14T06:39:40+00:00 phase=5 state=open review_scope=in -->
### p5-r8 · finding [open] (reviewer: in scope) · matrix row cites one test for R17+R19 (phase 5)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p5-r9 created=2026-10-14T06:39:40+00:00 phase=5 state=open review_scope=in -->
### p5-r9 · finding [open] (reviewer: in scope) · SKILL lanes paragraph left the --refresh parenthetical dangling (phase 5)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p5-r10 created=2026-10-14T06:39:40+00:00 phase=5 state=open review_scope=in -->
### p5-r10 · finding [open] (reviewer: in scope) · Need.kind comment missing the lane kinds (phase 5)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p5-r11 created=2026-10-14T06:39:40+00:00 phase=5 state=open review_scope=out -->
### p5-r11 · finding [open] (reviewer: out of scope) · a run blocked on a gate before its batch PR exists cannot reach Needs you · Developer (phase 5)

Reviewer tag: out (the cursor is read only at a PR head, by R18's construction; mitigated because batch dispatch opens the PR).

<!-- fr:journal kind=review scope=plan id=p5-review-1 created=2026-10-14T06:39:40+00:00 phase=5 -->
### p5-review-1 · review · phase 5 independent review: 11 findings (10 in, 1 out) (phase 5)

Dispatched reviewer read b8dacdb3..33959e3f against R17-R19 and §F; confirmed lane_of is the one lane function, R18 and R19 hold, no batch lost; found merge stops missing from Needs you now (p5-r1) and the ledger-unread misplacement (p5-r2). All 10 in-scope fixed in 66336cf5; CI green.

<!-- fr:journal kind=finding scope=plan id=p5-r1-resolved created=2026-10-14T06:39:40+00:00 phase=5 state=fixed resolves=p5-r1 -->
### p5-r1-resolved · finding [fixed] · resolves p5-r1: merge stops never reach Needs you now; board lane and Needs-you disagree (§F) (phase 5)

stops threaded through triage_cmd/render/_needs_section/needs_you; test_p5_r1_a_recorded_merge_stop_reaches_the_rendered_needs_you_now. (66336cf5, CI green)

<!-- fr:journal kind=finding scope=plan id=p5-r2-resolved created=2026-10-14T06:39:40+00:00 phase=5 state=fixed resolves=p5-r2 -->
### p5-r2-resolved · finding [fixed] · resolves p5-r2: ledger-unread batch placed in Needs you · Developer (phase 5)

back to Closing out with the driver's hint plus a ledger-unread Need; test_an_unread_ledger_stays_closing_out_with_the_drivers_hint_and_a_need. (66336cf5, CI green)

<!-- fr:journal kind=finding scope=plan id=p5-r3-resolved created=2026-10-14T06:39:40+00:00 phase=5 state=fixed resolves=p5-r3 -->
### p5-r3-resolved · finding [fixed] · resolves p5-r3: duplicate approve-pr and needs-reviewer rows (phase 5)

one row per card; test_p5_r3_a_green_unapproved_delivered_pr_has_one_row. (66336cf5, CI green)

<!-- fr:journal kind=finding scope=plan id=p5-r4-resolved created=2026-10-14T06:39:40+00:00 phase=5 state=fixed resolves=p5-r4 -->
### p5-r4-resolved · finding [fixed] · resolves p5-r4: reviewer lane hint outranks red-CI hints (phase 5)

red outranks; test_p5_r4_a_red_delivered_pr_hint_is_the_red_one_not_approve_it. (66336cf5, CI green)

<!-- fr:journal kind=finding scope=plan id=p5-r5-resolved created=2026-10-14T06:39:40+00:00 phase=5 state=fixed resolves=p5-r5 -->
### p5-r5-resolved · finding [fixed] · resolves p5-r5: stop vs gate precedence differs between hint and column (phase 5)

hint uses lane.reason; test_p5_r5_hint_and_column_agree_when_a_stop_meets_a_gate. (66336cf5, CI green)

<!-- fr:journal kind=finding scope=plan id=p5-r6-resolved created=2026-10-14T06:39:40+00:00 phase=5 state=fixed resolves=p5-r6 -->
### p5-r6-resolved · finding [fixed] · resolves p5-r6: Tester/DevOps reason names one gate and not what is owed (phase 5)

every held gate and the owed act named; test_p5_r6_the_reason_names_every_held_gate_and_what_is_owed. (66336cf5, CI green)

<!-- fr:journal kind=finding scope=plan id=p5-r7-resolved created=2026-10-14T06:39:40+00:00 phase=5 state=fixed resolves=p5-r7 -->
### p5-r7-resolved · finding [fixed] · resolves p5-r7: conflicting hint covers only merge, not enqueue (phase 5)

both; test_p5_r7_the_conflicting_hint_replaces_merge_and_enqueue. (66336cf5, CI green)

<!-- fr:journal kind=finding scope=plan id=p5-r8-resolved created=2026-10-14T06:39:40+00:00 phase=5 state=fixed resolves=p5-r8 -->
### p5-r8-resolved · finding [fixed] · resolves p5-r8: matrix row cites one test for R17+R19 (phase 5)

conflicting and agreement tests added as levels. (66336cf5, CI green)

<!-- fr:journal kind=finding scope=plan id=p5-r9-resolved created=2026-10-14T06:39:40+00:00 phase=5 state=fixed resolves=p5-r9 -->
### p5-r9-resolved · finding [fixed] · resolves p5-r9: SKILL lanes paragraph left the --refresh parenthetical dangling (phase 5)

moved back; skill-validation tripwire green. (66336cf5, CI green)

<!-- fr:journal kind=finding scope=plan id=p5-r10-resolved created=2026-10-14T06:39:40+00:00 phase=5 state=fixed resolves=p5-r10 -->
### p5-r10-resolved · finding [fixed] · resolves p5-r10: Need.kind comment missing the lane kinds (phase 5)

comment updated. (66336cf5, CI green)

<!-- fr:journal kind=finding scope=plan id=p5-r11-resolved created=2026-10-14T06:39:40+00:00 phase=5 state=open resolves=p5-r11 out_of_scope=true -->
### p5-r11-resolved · finding [out-of-scope] · resolves p5-r11: a run blocked on a gate before its batch PR exists cannot reach Needs you · Developer (phase 5)

R18 reads the cursor at the batch PR's head by design; a pre-PR gated run is a separate design question, not caused by this phase's code.

<!-- fr:journal kind=decision scope=plan id=p6-driver-records-first created=2026-10-14T08:00:04+00:00 phase=6 -->
### p6-driver-records-first · decision · The driver records each member's close-out event before the collected session starts (phase 6)

gh#883's dedupe key stays the event: the driver writes one closeout event per member (archive = the collected branch, handle = the item, then the runner's handle once known) before runner.dispatch, and takes them all back if the dispatch fails. The verb reuses that branch, records nothing twice, and takes back a held member's pending event, so a held batch ends with no close-out event (R15). A hand-run verb records `runner: hand` events itself.

<!-- fr:journal kind=decision scope=plan id=p6-predicted-holds created=2026-10-14T08:00:04+00:00 phase=6 -->
### p6-predicted-holds · decision · The driver predicts an archive hold from the default branch and makes it a need, never a member (phase 6)

Before planning the collected close-out, the driver reads each due batch's run on origin/<default> (ledger.closeout_read): a Test Plan step with no outcome and no passed gate means `fr archive` would hold, so the batch gets a `closeout-held` action (counted blocked; Need kind closeout-held) and is left out. Without this a held batch would be re-collected every pass. The verb still names any hold the prediction missed (exit 1). The facts-only board cannot see this need (it reads no clone).

<!-- fr:journal kind=decision scope=plan id=p6-verify-merge-exit-2 created=2026-10-14T08:00:04+00:00 phase=6 -->
### p6-verify-merge-exit-2 · decision · verify-merge exit 2 (the merged branch is gone) does not hold a batch (phase 6)

A batch branch is deleted at merge, so `fr isolation verify-merge --branch <b>` in the scratch worktree usually exits 2 (unresolvable ref), which disproves nothing; the merged PR stands. Exit 1 (not verified) holds the batch.

<!-- fr:journal kind=decision scope=plan id=p6-attributed-collected-heads created=2026-10-14T08:00:04+00:00 phase=6 -->
### p6-attributed-collected-heads · decision · attributed accepts head == event.archive only for a collected head (phase 6)

§D's rule is applied to `chore/closeout-<date>-<n>` heads, a name only that close-out produces. A per-batch `chore/archive-<plan>` or `chore/closeout-<run>` head still needs the run file or plan journal in its files (rg-12, pinned by test_head_only_attribution_is_the_branch_named_closeout_alone).

<!-- fr:journal kind=decision scope=plan id=p6-handback-budget created=2026-10-14T08:00:04+00:00 phase=6 -->
### p6-handback-budget · decision · The collected close-out's hand-back budget counts distinct heads per item across members (phase 6)

closeout_handback_decision reads every member's closeout_handback events for the item: a hand-back at this head is skipped (or stuck when delivered none), one at an earlier head makes the next failure closeout-stuck. conflict_decision, red_decision and fresh_conflicts now share handbacks_since (per-dispatch count, semantics unchanged); the close-out's count is not per dispatch, so it counts heads instead.

<!-- fr:journal kind=discovery scope=plan id=p6-gitseam-runs-fr created=2026-10-14T08:00:04+00:00 phase=6 -->
### p6-gitseam-runs-fr · discovery · gitseam's closed set of commands now includes this fr itself (phase 6)

The collected close-out runs verify-merge, closeout outcome and archive as `python -m fr` (the running interpreter, never PATH) through Worktree.run_fr, which uses the one `_run` (coded=True for the exit code), so the seam still starts every process from its two subprocess.run calls and the batch modules stay subprocess-free.

<!-- fr:journal kind=discovery scope=plan id=p6-judgements-schema-10 created=2026-10-14T08:00:04+00:00 phase=6 -->
### p6-judgements-schema-10 · discovery · closeout_handback moves the judgements writer schema 9 to 10 (origin/main is 9) (phase 6)

Schemas 1-9 still load; a schema-9 file carrying closeout_handback is refused. Pinned tests moved to 10; the fr-triage skill example says `schema: 10`, and its `schema: 1` guard became a digit-aware regex. Parallel PRs collide on this number: recheck origin/main before merge.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t1 created=2026-10-14T08:00:04+00:00 phase=6 -->
### no-refactor-p6-t1 · discovery · no-refactor-because P6.T1 (phase 6)

batch_closeout.py was written as one engine module (Member/Step/execute) beside the gitseam Worktree methods it needs; the naming helpers moved into batch_drive during GREEN, so nothing was left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t2 created=2026-10-14T08:00:04+00:00 phase=6 -->
### no-refactor-p6-t2 · discovery · no-refactor-because P6.T2 (phase 6)

step 2's aggregation is one loop plus one per-repo planning block reusing next_collected/collected_name; attributed gained one guarded line; no duplication left to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t4 created=2026-10-14T08:00:04+00:00 phase=6 -->
### no-refactor-p6-t4 · discovery · no-refactor-because P6.T4 (phase 6)

prose, mirrors and a matrix status move only

<!-- fr:journal kind=finding scope=plan id=p6-r1 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6-r1 · finding [open] (reviewer: in scope) · undeclared holds taken back and re-collected every pass, no Needs-you row (phase 6)

Reviewer A tag: in.

<!-- fr:journal kind=finding scope=plan id=p6-r2 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6-r2 · finding [open] (reviewer: in scope) · take-back last-event-only and skipped on fail/crash; leftover event marks a held batch archived (phase 6)

Reviewer A tag: in.

<!-- fr:journal kind=finding scope=plan id=p6-r3 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6-r3 · finding [open] (reviewer: in scope) · closeout-held only in the driver Snapshot; board disagrees (phase 6)

Reviewer A tag: in.

<!-- fr:journal kind=finding scope=plan id=p6-r4 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6-r4 · finding [open] (reviewer: in scope) · one unreadable member fails the whole verb (phase 6)

Reviewer A tag: in.

<!-- fr:journal kind=finding scope=plan id=p6-r5 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6-r5 · finding [open] (reviewer: in scope) · collected PR closed unmerged wedges the repo (phase 6)

Reviewer A tag: in.

<!-- fr:journal kind=finding scope=plan id=p6-r6 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6-r6 · finding [open] (reviewer: in scope) · auto-merge with no file allowlist after a code-fixing hand-back (phase 6)

Reviewer A tag: in.

<!-- fr:journal kind=finding scope=plan id=p6-r7 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6-r7 · finding [open] (reviewer: in scope) · verify-merge exit 2 tolerance too broad (phase 6)

Reviewer A tag: in.

<!-- fr:journal kind=finding scope=plan id=p6-r8 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6-r8 · finding [open] (reviewer: in scope) · issues closed at PR open, not merge (phase 6)

Reviewer A tag: in.

<!-- fr:journal kind=finding scope=plan id=p6-r9 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6-r9 · finding [open] (reviewer: in scope) · re-run on a pushed branch fails non-ff with no recovery (phase 6)

Reviewer A tag: in.

<!-- fr:journal kind=finding scope=plan id=p6b-r1 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6b-r1 · finding [open] (reviewer: in scope) · review-free allowlist admitted workflows/verifications (code execution) and acceptance status (phase 6)

Reviewer B (security re-review of c818f3ba..a692922a) tag: in.

<!-- fr:journal kind=finding scope=plan id=p6b-r2 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6b-r2 · finding [open] (reviewer: in scope) · fabricated green CI with no check results (phase 6)

Reviewer B (security re-review of c818f3ba..a692922a) tag: in.

<!-- fr:journal kind=finding scope=plan id=p6b-r3 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6b-r3 · finding [open] (reviewer: in scope) · forge file list truncated, rename-blind, unbound to the merge head (phase 6)

Reviewer B (security re-review of c818f3ba..a692922a) tag: in.

<!-- fr:journal kind=finding scope=plan id=p6b-r4 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6b-r4 · finding [open] (reviewer: in scope) · membership and Closes from the editable PR body (phase 6)

Reviewer B (security re-review of c818f3ba..a692922a) tag: in.

<!-- fr:journal kind=finding scope=plan id=p6b-r5 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6b-r5 · finding [open] (reviewer: in scope) · resume trusted a fork PR on the branch name (phase 6)

Reviewer B (security re-review of c818f3ba..a692922a) tag: in.

<!-- fr:journal kind=finding scope=plan id=p6b-r6 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6b-r6 · finding [open] (reviewer: in scope) · a failed hand run leaves an open marker that wedges the repo (phase 6)

Reviewer B (security re-review of c818f3ba..a692922a) tag: in.

<!-- fr:journal kind=finding scope=plan id=p6b-r7 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6b-r7 · finding [open] (reviewer: in scope) · named or hand run while a close-out is in flight collides (phase 6)

Reviewer B (security re-review of c818f3ba..a692922a) tag: in.

<!-- fr:journal kind=finding scope=plan id=p6b-r8 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6b-r8 · finding [open] (reviewer: in scope) · --branch not validated (phase 6)

Reviewer B (security re-review of c818f3ba..a692922a) tag: in.

<!-- fr:journal kind=finding scope=plan id=p6b-r9 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6b-r9 · finding [open] (reviewer: in scope) · transient read error became a durable hold (phase 6)

Reviewer B (security re-review of c818f3ba..a692922a) tag: in.

<!-- fr:journal kind=finding scope=plan id=p6b-r10 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=in -->
### p6b-r10 · finding [open] (reviewer: in scope) · unbounded hand-backs with no members; reopened PR never re-observed (phase 6)

Reviewer B (security re-review of c818f3ba..a692922a) tag: in.

<!-- fr:journal kind=finding scope=plan id=p6b-r11 created=2026-10-14T09:22:53+00:00 phase=6 state=open review_scope=out -->
### p6b-r11 · finding [open] (reviewer: out of scope) · main has no required review or checks, so the auto-merge guards are the only barrier once approved-fr is bypassed (phase 6)

Reviewer B tag: out (repo ruleset predates this change).

<!-- fr:journal kind=review scope=plan id=p6-review-1 created=2026-10-14T09:22:53+00:00 phase=6 -->
### p6-review-1 · review · phase 6 independent review: 9 findings (9 in, 0 out) (phase 6)

Reviewer A read 97f2e29d..c818f3ba against R15, R16, R27, §D, §E; found holds/membership driven by guesses and take-back (p6-r1..r4), wedges and an unguarded no-approval merge. All 9 fixed by the a692922a redesign.

<!-- fr:journal kind=review scope=plan id=p6-review-2 created=2026-10-14T09:22:53+00:00 phase=6 -->
### p6-review-2 · review · phase 6 focused security re-review: 11 findings (10 in, 1 out) (phase 6)

Reviewer B read the fix range c818f3ba..a692922a on the security review's flags; confirmed the allowlist admitted executable config (p6b-r1, critical), fabricated green (p6b-r2), forge-file-list and PR-body trust (p6b-r3..r5). Fixed in aec72e4f by a verb-recorded trust anchor; CI green.

<!-- fr:journal kind=finding scope=plan id=p6-r1-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6-r1 -->
### p6-r1-resolved · finding [fixed] · resolves p6-r1: undeclared holds taken back and re-collected every pass, no Needs-you row (phase 6)

a692922a (redesign: start marker, durable closeout_hold, Closes at merge, docs-only merge, verify-merge --default-branch, resume/refuse), hardened by aec72e4f; tests in test_triage_collected_closeout_drive.py / test_triage_batch_closeout*.py named p6_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6-r2-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6-r2 -->
### p6-r2-resolved · finding [fixed] · resolves p6-r2: take-back last-event-only and skipped on fail/crash; leftover event marks a held batch archived (phase 6)

a692922a (redesign: start marker, durable closeout_hold, Closes at merge, docs-only merge, verify-merge --default-branch, resume/refuse), hardened by aec72e4f; tests in test_triage_collected_closeout_drive.py / test_triage_batch_closeout*.py named p6_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6-r3-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6-r3 -->
### p6-r3-resolved · finding [fixed] · resolves p6-r3: closeout-held only in the driver Snapshot; board disagrees (phase 6)

a692922a (redesign: start marker, durable closeout_hold, Closes at merge, docs-only merge, verify-merge --default-branch, resume/refuse), hardened by aec72e4f; tests in test_triage_collected_closeout_drive.py / test_triage_batch_closeout*.py named p6_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6-r4-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6-r4 -->
### p6-r4-resolved · finding [fixed] · resolves p6-r4: one unreadable member fails the whole verb (phase 6)

a692922a (redesign: start marker, durable closeout_hold, Closes at merge, docs-only merge, verify-merge --default-branch, resume/refuse), hardened by aec72e4f; tests in test_triage_collected_closeout_drive.py / test_triage_batch_closeout*.py named p6_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6-r5-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6-r5 -->
### p6-r5-resolved · finding [fixed] · resolves p6-r5: collected PR closed unmerged wedges the repo (phase 6)

a692922a (redesign: start marker, durable closeout_hold, Closes at merge, docs-only merge, verify-merge --default-branch, resume/refuse), hardened by aec72e4f; tests in test_triage_collected_closeout_drive.py / test_triage_batch_closeout*.py named p6_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6-r6-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6-r6 -->
### p6-r6-resolved · finding [fixed] · resolves p6-r6: auto-merge with no file allowlist after a code-fixing hand-back (phase 6)

a692922a (redesign: start marker, durable closeout_hold, Closes at merge, docs-only merge, verify-merge --default-branch, resume/refuse), hardened by aec72e4f; tests in test_triage_collected_closeout_drive.py / test_triage_batch_closeout*.py named p6_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6-r7-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6-r7 -->
### p6-r7-resolved · finding [fixed] · resolves p6-r7: verify-merge exit 2 tolerance too broad (phase 6)

a692922a (redesign: start marker, durable closeout_hold, Closes at merge, docs-only merge, verify-merge --default-branch, resume/refuse), hardened by aec72e4f; tests in test_triage_collected_closeout_drive.py / test_triage_batch_closeout*.py named p6_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6-r8-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6-r8 -->
### p6-r8-resolved · finding [fixed] · resolves p6-r8: issues closed at PR open, not merge (phase 6)

a692922a (redesign: start marker, durable closeout_hold, Closes at merge, docs-only merge, verify-merge --default-branch, resume/refuse), hardened by aec72e4f; tests in test_triage_collected_closeout_drive.py / test_triage_batch_closeout*.py named p6_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6-r9-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6-r9 -->
### p6-r9-resolved · finding [fixed] · resolves p6-r9: re-run on a pushed branch fails non-ff with no recovery (phase 6)

a692922a (redesign: start marker, durable closeout_hold, Closes at merge, docs-only merge, verify-merge --default-branch, resume/refuse), hardened by aec72e4f; tests in test_triage_collected_closeout_drive.py / test_triage_batch_closeout*.py named p6_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6b-r1-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6b-r1 -->
### p6b-r1-resolved · finding [fixed] · resolves p6b-r1: review-free allowlist admitted workflows/verifications (code execution) and acceptance status (phase 6)

aec72e4f: trust anchor — auto-merge only at the verb-recorded head, own git diff within the archive allowlist, trusted same-repo commits, recorded Closes; tests named p6b_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6b-r2-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6b-r2 -->
### p6b-r2-resolved · finding [fixed] · resolves p6b-r2: fabricated green CI with no check results (phase 6)

aec72e4f: trust anchor — auto-merge only at the verb-recorded head, own git diff within the archive allowlist, trusted same-repo commits, recorded Closes; tests named p6b_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6b-r3-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6b-r3 -->
### p6b-r3-resolved · finding [fixed] · resolves p6b-r3: forge file list truncated, rename-blind, unbound to the merge head (phase 6)

aec72e4f: trust anchor — auto-merge only at the verb-recorded head, own git diff within the archive allowlist, trusted same-repo commits, recorded Closes; tests named p6b_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6b-r4-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6b-r4 -->
### p6b-r4-resolved · finding [fixed] · resolves p6b-r4: membership and Closes from the editable PR body (phase 6)

aec72e4f: trust anchor — auto-merge only at the verb-recorded head, own git diff within the archive allowlist, trusted same-repo commits, recorded Closes; tests named p6b_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6b-r5-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6b-r5 -->
### p6b-r5-resolved · finding [fixed] · resolves p6b-r5: resume trusted a fork PR on the branch name (phase 6)

aec72e4f: trust anchor — auto-merge only at the verb-recorded head, own git diff within the archive allowlist, trusted same-repo commits, recorded Closes; tests named p6b_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6b-r6-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6b-r6 -->
### p6b-r6-resolved · finding [fixed] · resolves p6b-r6: a failed hand run leaves an open marker that wedges the repo (phase 6)

aec72e4f: trust anchor — auto-merge only at the verb-recorded head, own git diff within the archive allowlist, trusted same-repo commits, recorded Closes; tests named p6b_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6b-r7-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6b-r7 -->
### p6b-r7-resolved · finding [fixed] · resolves p6b-r7: named or hand run while a close-out is in flight collides (phase 6)

aec72e4f: trust anchor — auto-merge only at the verb-recorded head, own git diff within the archive allowlist, trusted same-repo commits, recorded Closes; tests named p6b_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6b-r8-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6b-r8 -->
### p6b-r8-resolved · finding [fixed] · resolves p6b-r8: --branch not validated (phase 6)

aec72e4f: trust anchor — auto-merge only at the verb-recorded head, own git diff within the archive allowlist, trusted same-repo commits, recorded Closes; tests named p6b_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6b-r9-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6b-r9 -->
### p6b-r9-resolved · finding [fixed] · resolves p6b-r9: transient read error became a durable hold (phase 6)

aec72e4f: trust anchor — auto-merge only at the verb-recorded head, own git diff within the archive allowlist, trusted same-repo commits, recorded Closes; tests named p6b_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6b-r10-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=fixed resolves=p6b-r10 -->
### p6b-r10-resolved · finding [fixed] · resolves p6b-r10: unbounded hand-backs with no members; reopened PR never re-observed (phase 6)

aec72e4f: trust anchor — auto-merge only at the verb-recorded head, own git diff within the archive allowlist, trusted same-repo commits, recorded Closes; tests named p6b_r*; CI green.

<!-- fr:journal kind=finding scope=plan id=p6b-r11-resolved created=2026-10-14T09:22:53+00:00 phase=6 state=open resolves=p6b-r11 out_of_scope=true -->
### p6b-r11-resolved · finding [out-of-scope] · resolves p6b-r11: main has no required review or checks, so the auto-merge guards are the only barrier once approved-fr is bypassed (phase 6)

The repo's ruleset (docs/merge-protection.md, configure-main-protection.sh stages) predates this change; raised to the operator in the PR body.

<!-- fr:journal kind=decision scope=plan id=p7-release-status-window created=2026-10-14T10:05:58+00:00 phase=7 -->
### p7-release-status-window · decision · fr release status counts PRs merged after the last final tag's commit time, and fails closed on a forge error (phase 7)

"Merged since the last final tag" is `mergedAt` later than the tag's commit time (`git log -1 --format=%cI`), from one bulk merged-PR list; only those PRs get a `pr_view` for their labels. The tag is the highest `^v\d+\.\d+\.\d+$` among the checkout's tags. A forge failure exits 1 (and in `release.py` a failed `gh` read or `--from-json` decision refuses), because an empty `waiting` would cut a final. Owed rows come from `fr.triage.ledger.gated_rows_at` on `origin/<default>` (HEAD when unresolvable); an unreadable exit reports `owed_rows: null`, never "none owed", and never changes whether the PR waits (the labels decide).

<!-- fr:journal kind=decision scope=plan id=p7-release-forge-split created=2026-10-14T10:05:58+00:00 phase=7 -->
### p7-release-forge-split · decision · release.py reads the forge itself; fr decides from its facts with no credential (phase 7)

A security review flagged the first design: `release.py` ran `uv run fr release status --json` with the release workflow's write-capable token in its environment, executing the repo's own fr package with a credential the staged suite is denied for exactly that reason (`_credential_free_env`). Now `release.py` does the one credentialed read itself (`Commands.gh_read`: `gh pr list --state merged --search merged:>=<last final tag time> --json number,title,url,mergedAt,headRefName,labels --limit 1000`; a read that hits the limit refuses as possibly truncated), writes those facts to a temp file, and runs `fr release status --from-json <file> --json` (`Commands.decide`) with `_credential_free_env()` plus an empty `GH_CONFIG_DIR`, so no token and no stored gh login is readable. In that mode fr never builds a forge client; the owed rows are read from local git at HEAD. Both modes call the one pure `fr.release_status.release_status`, so they cannot disagree (pinned by a test). Every other git command in release.py now runs credential-free too; only the two pushes authenticate. Spec R21 and §G are amended to match.

<!-- fr:journal kind=decision scope=plan id=p7-rc-bump-rule created=2026-10-14T10:05:58+00:00 phase=7 -->
### p7-rc-bump-rule · decision · An RC of X.Y.Z bumps from the last final it implies, read from its own shape (phase 7)

`Version.bumped` on an RC: X.0.0 implies a major, X.Y.0 a minor, else a patch. A bump no bigger than that lands on the final X.Y.Z; a bigger one moves X.Y.Z by it, which equals moving the last final by it. So `changes.bumped` (and so check-change-fragment's predicted floor at an RC head) needs no tag read and never int-splits the RC string. `release.compute` itself bases the target on the last final TAG plus the pending bump.

<!-- fr:journal kind=decision scope=plan id=p7-status-workflow-token created=2026-10-14T10:05:58+00:00 phase=7 -->
### p7-status-workflow-token · decision · release.yml reads what waits with the workflow token (pull-requests read), never the app's (phase 7)

Reading merged PRs needs pull-requests read. The app token is minted with contents and issues write only, and asking it for more fails the mint when the installation lacks the permission, which would stop every release. So the workflow gains `pull-requests: read` and passes `FR_RELEASE_STATUS_TOKEN: ${{ github.token }}`, which `_run_gh_read` puts in GH_TOKEN for the merged-PR `gh` read alone; every credential-free env strips it.

<!-- fr:journal kind=decision scope=plan id=p7-no-fragment-no-rc created=2026-10-14T10:05:58+00:00 phase=7 -->
### p7-no-fragment-no-rc · decision · With no pending fragment on a final head nothing is released and what waits is never asked (phase 7)

An RC previews the final the pending fragments make. With none pending and HEAD a final, there is nothing to preview or finalize, so compute returns before calling `fr release status`, which also keeps the forge read off every no-op push. `--version` stays an ungated final.

<!-- fr:journal kind=discovery scope=plan id=p7-release-notes-by-subject created=2026-10-14T10:05:58+00:00 phase=7 -->
### p7-release-notes-by-subject · discovery · release_notes now finds its commit by exact subject; -S<version> cannot see an RC to final commit (phase 7)

`git log -S5.27.0` finds commits that change the COUNT of `5.27.0`, and `5.27.0rc1` -> `5.27.0` changes no count, so the final's own commit was invisible and the lookup landed on the RC's (whose subject did not match, so the notes were empty). It now lists `--fixed-strings --grep` matches and keeps the one whose subject is exactly `release: v<semver>`.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p7-t1 created=2026-10-14T10:05:58+00:00 phase=7 -->
### no-refactor-p7-t1 · discovery · no-refactor-because P7.T1 (phase 7)

fr.release_status is one pure engine over a two-method forge protocol and an owed-rows callable; the command reuses gate_cmd.resolve_target and the ledger's gated_rows_at rather than a second reader, so nothing was duplicated to merge.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p7-t2 created=2026-10-14T10:05:58+00:00 phase=7 -->
### no-refactor-p7-t2 · discovery · no-refactor-because P7.T2 (phase 7)

The RC parsing went straight into one shared value (scripts/versions.py Version) that bump-version, version_surfaces, changes and floors call; version_floor.admits is one added branch; nothing left to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p7-t4 created=2026-10-14T10:05:58+00:00 phase=7 -->
### no-refactor-p7-t4 · discovery · no-refactor-because P7.T4 (phase 7)

One fr acceptance set-status call; nothing to clean.

<!-- fr:journal kind=finding scope=plan id=p7-r1 created=2026-10-14T10:34:24+00:00 phase=7 state=open review_scope=in -->
### p7-r1 · finding [open] (reviewer: in scope) · untagged RC at HEAD recomputes the same RC; every later run refuses (phase 7)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p7-r2 created=2026-10-14T10:34:24+00:00 phase=7 state=open review_scope=in -->
### p7-r2 · finding [open] (reviewer: in scope) · merged-PR read trusts the eventually consistent search index; no --base main (phase 7)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p7-r3 created=2026-10-14T10:34:24+00:00 phase=7 state=open review_scope=in -->
### p7-r3 · finding [open] (reviewer: in scope) · bump and lock-check inherit write tokens while the spec claims otherwise (phase 7)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p7-r4 created=2026-10-14T10:34:24+00:00 phase=7 state=open review_scope=in -->
### p7-r4 · finding [open] (reviewer: in scope) · FR_RELEASE_STATUS_TOKEN described as read-only but is the write-capable github.token (phase 7)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p7-r5 created=2026-10-14T10:34:24+00:00 phase=7 state=open review_scope=in -->
### p7-r5 · finding [open] (reviewer: in scope) · failed or capped gate read blocks RCs too (phase 7)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p7-r6 created=2026-10-14T10:34:24+00:00 phase=7 state=open review_scope=in -->
### p7-r6 · finding [open] (reviewer: in scope) · removed major fragment moves the version backwards (phase 7)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p7-r7 created=2026-10-14T10:34:24+00:00 phase=7 state=open review_scope=in -->
### p7-r7 · finding [open] (reviewer: in scope) · human fr release status truncates silently and reads unfetched tags (phase 7)

Reviewer tag: in.

<!-- fr:journal kind=finding scope=plan id=p7-r8 created=2026-10-14T10:34:24+00:00 phase=7 state=open review_scope=out -->
### p7-r8 · finding [open] (reviewer: out of scope) · fr.cloud._version_tuple cannot parse X.Y.ZrcN; the cloud doctor's fr-version check reports ok on an RC install (phase 7)

Reviewer tag: out.

<!-- fr:journal kind=review scope=plan id=p7-review-1 created=2026-10-14T10:34:24+00:00 phase=7 -->
### p7-review-1 · review · phase 7 independent review: 8 findings (7 in, 1 out) (phase 7)

Dispatched reviewer read 55036128..11ca630e against R20, R21, R25, R26 and AGENTS.md's release flow, ran probes with the World fixture; confirmed one Version object, credential-free fr decision, no RC loop, narrow floor admission; reproduced the untagged-RC wedge (p7-r1) and found the search-index gap (p7-r2). All 7 in-scope fixed in 4fdf1676; CI green.

<!-- fr:journal kind=finding scope=plan id=p7-r1-resolved created=2026-10-14T10:34:24+00:00 phase=7 state=fixed resolves=p7-r1 -->
### p7-r1-resolved · finding [fixed] · resolves p7-r1: untagged RC at HEAD recomputes the same RC; every later run refuses (phase 7)

test_p7_r1_an_untagged_rc_at_head_is_tagged_with_no_new_commit (4fdf1676, CI green)

<!-- fr:journal kind=finding scope=plan id=p7-r2-resolved created=2026-10-14T10:34:24+00:00 phase=7 state=fixed resolves=p7-r2 -->
### p7-r2-resolved · finding [fixed] · resolves p7-r2: merged-PR read trusts the eventually consistent search index; no --base main (phase 7)

cross-checked against git log PR numbers, --base main; test_p7_r2_a_pr_in_git_log_but_missing_from_the_read_is_unknown_never_a_final (4fdf1676, CI green)

<!-- fr:journal kind=finding scope=plan id=p7-r3-resolved created=2026-10-14T10:34:24+00:00 phase=7 state=fixed resolves=p7-r3 -->
### p7-r3-resolved · finding [fixed] · resolves p7-r3: bump and lock-check inherit write tokens while the spec claims otherwise (phase 7)

credential-free; test_p7_r3_bump_and_lock_check_run_with_no_forge_token (4fdf1676, CI green)

<!-- fr:journal kind=finding scope=plan id=p7-r4-resolved created=2026-10-14T10:34:24+00:00 phase=7 state=fixed resolves=p7-r4 -->
### p7-r4-resolved · finding [fixed] · resolves p7-r4: FR_RELEASE_STATUS_TOKEN described as read-only but is the write-capable github.token (phase 7)

wording fixed in release.yml and AGENTS.md; test_p7_r4_header_says_the_status_token_is_the_write_capable_workflow_token (4fdf1676, CI green)

<!-- fr:journal kind=finding scope=plan id=p7-r5-resolved created=2026-10-14T10:34:24+00:00 phase=7 state=fixed resolves=p7-r5 -->
### p7-r5-resolved · finding [fixed] · resolves p7-r5: failed or capped gate read blocks RCs too (phase 7)

unknown gate state cuts an RC naming the reason; test_p7_r5_a_failed_forge_read_cuts_an_rc_naming_the_reason (4fdf1676, CI green)

<!-- fr:journal kind=finding scope=plan id=p7-r6-resolved created=2026-10-14T10:34:24+00:00 phase=7 state=fixed resolves=p7-r6 -->
### p7-r6-resolved · finding [fixed] · resolves p7-r6: removed major fragment moves the version backwards (phase 7)

target <= head refused; test_p7_r6_a_removed_major_fragment_never_moves_the_version_backwards (4fdf1676, CI green)

<!-- fr:journal kind=finding scope=plan id=p7-r7-resolved created=2026-10-14T10:34:24+00:00 phase=7 state=fixed resolves=p7-r7 -->
### p7-r7-resolved · finding [fixed] · resolves p7-r7: human fr release status truncates silently and reads unfetched tags (phase 7)

warns at limit, fetches tags; test_p7_r7_a_read_at_its_limit_warns_and_an_unfetched_tag_is_said (4fdf1676, CI green)

<!-- fr:journal kind=finding scope=plan id=p7-r8-resolved created=2026-10-14T10:34:24+00:00 phase=7 state=open resolves=p7-r8 out_of_scope=true -->
### p7-r8-resolved · finding [out-of-scope] · resolves p7-r8: fr.cloud._version_tuple cannot parse X.Y.ZrcN; the cloud doctor's fr-version check reports ok on an RC install (phase 7)

fr cloud doctor's version parser predates RC versions and degrades to ok, harmless; not part of the release tooling R25 names.
