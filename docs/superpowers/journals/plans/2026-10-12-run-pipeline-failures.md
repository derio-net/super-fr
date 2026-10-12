# Journal: 2026-10-12-run-pipeline-failures

<!-- fr:journal kind=discovery scope=plan id=p1-render-only-param created=2026-10-11T22:40:36+00:00 phase=1 -->
### p1-render-only-param · discovery · render_committed_set takes only= (phase 1)

P1.T3.S2 done: render_committed_set(matrix, root, only=...) filters at the source, so every caller passes tracked_reports(root) rather than filtering its output. The implementation was written before the tests this phase (not strict red-first); the tests were then verified red by stashing the source changes (2 of 9 unit, 6 of 6 integration failed) and green with them.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-11T22:52:46+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · unit tests (e), report --check exits-3 and (f) pass without the change (phase 1)

The ignored linked.md was fresh/absent and file names were not asserted, so a regression comparing ignored reports in mixed setups would pass.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-11T22:52:46+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · report --check success line starts with an empty list when every report is CI-built (phase 1)

acceptance_cmd.py report --check printed ' in sync with matrix.yaml' when expected was empty.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-11T22:52:46+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · fr acceptance init prints CI-built reports as 'exists ... (left untouched)' though they do not exist (phase 1)

CI-built reports were appended to InitOutcome.skipped.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-11T22:52:46+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · ci_built_reports bypasses fr.git.git_answer and is spawned 2-3 times per operation; init still renders CI-built reports (phase 1)

No timeout / C locale; repeated git calls in init, report --check and matrix_anchors._fn.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-11T22:52:46+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · acceptance row cites R3 and the record path but anchors neither test (phase 1)

Row acceptance-ci-built-reports anchored only a check test and a set-status test.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-11T22:52:46+00:00 phase=1 state=open review_scope=out -->
### p1-r6 · finding [open] (reviewer: out of scope) · pre-existing _committable runs its own git check-ignore instead of a shared helper (phase 1)

acceptance_cmd.py _committable predates this change and covers init's other written paths, not only reports.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-11T22:52:46+00:00 phase=1 -->
### p1-review-1 · review · phase 1 independent review: 6 findings (5 in, 1 out) (phase 1)

Read-only reviewer over diff 761a7a04..HEAD against spec §A / R1-R3: every REPORT_SET / render_committed_set caller honours R1-R3; ci_built_reports edge cases correct; tests verified to fail on the old behaviour (2/9 unit, 6/6 integration). Findings p1-r1..p1-r5 (in, all fixed in 'fix(acceptance): address phase-1 review'), p1-r6 (out).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-11T22:52:46+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: unit tests (e), report --check exits-3 and (f) pass without the change (phase 1)

Case (e) makes the ignored linked.md stale; exits-3 asserts LOCAL and linked.html named and linked.md not; (f) asserts every name; new test: stale ignored report beside fresh tracked ones exits 0 naming it skipped.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-11T22:52:46+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: report --check success line starts with an empty list when every report is CI-built (phase 1)

report --check prints 'no tracked reports to check (CI-built, skipped: ...)' when every report is CI-built; tested.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-11T22:52:46+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: fr acceptance init prints CI-built reports as 'exists ... (left untouched)' though they do not exist (phase 1)

InitOutcome.ci_built, printed 'skipped <rel> (gitignored — CI builds it)'; integration test asserts ci_built and not skipped.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-11T22:52:46+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: ci_built_reports bypasses fr.git.git_answer and is spawned 2-3 times per operation; init still renders CI-built reports (phase 1)

ci_built_reports uses git_answer(root, 'check-ignore', '--', *REPORT_SET) and returns empty on GitUnavailableError; tracked_reports takes a precomputed ci_built; init, report --check and matrix_anchors._fn ask git once; init renders tracked reports only.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-11T22:52:46+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: acceptance row cites R3 and the record path but anchors neither test (phase 1)

fr acceptance set-status added unit #test_report_deterministic_writes_ignored_reports and int #test_a_record_with_an_acceptance_row_commits_without_ignored_reports.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-11T22:52:46+00:00 phase=1 state=open resolves=p1-r6 out_of_scope=true -->
### p1-r6-resolved · finding [out-of-scope] · resolves p1-r6: pre-existing _committable runs its own git check-ignore instead of a shared helper (phase 1)

Pre-existing helper not touched by this change; it checks init's non-report paths too, so it is not a duplicate of ci_built_reports' job. Correct today.

<!-- fr:journal kind=discovery scope=plan id=p2-selfreview-fixture created=2026-10-11T23:40:05+00:00 phase=2 -->
### p2-selfreview-fixture · discovery · self-review verification tests needed an executable .fr/candidate-install (phase 2)

R5 makes an explicit `strategy: candidate` an error in a repo without the program, so test_plan_self_review_verification._setup now installs one by default (install=False for the R5 case). Tests were written red-first for the new module; implementation then written in one pass.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-11T23:40:05+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

install_problem was lifted out of walk._contract (the refactor itself); nothing further to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-11T23:40:05+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

unrunnable_strategies is a single new helper with two thin callers; nothing to clean

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-11T23:56:51+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · R5 tests never isolate the per-row-line and row-verify: sources; self-review covers only section strategy: (phase 2)

A section-only unrunnable_strategies passed every test.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-11T23:56:51+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · R5 fix advice cannot clear a row's own verify:, which outranks spec lines; message does not name the source row (phase 2)

effective_strategy lets verify: win; 'strategy: none' would not clear it.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-11T23:56:51+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · effective_shape_default bindings in plan_ops._verification_issues and run/visual.py are untested (phase 2)

Spec ## Tests asks that visual.py's binding agrees.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-11T23:56:51+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · brainstorm warning catches only SectionError/AcceptanceError/OSError; other errors escape after commit (phase 2)

UnicodeDecodeError would exit non-zero after the record committed and skip the advance.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-11T23:56:51+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · R5 warning fires only on resolve --record, not the flag form with --emitted spec= (phase 2)

R5 says the brainstorm resolve that emits the spec warns.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-10-11T23:56:51+00:00 phase=2 state=open review_scope=out -->
### p2-r6 · finding [open] (reviewer: out of scope) · explicit row verify: on a spec with no ## Verification section is never flagged though walk_owed still owes it (phase 2)

Spec-mandated exemption: a spec with no section passes unchanged.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-10-11T23:56:51+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · fr verification walk without the install program says 'names no strategy' once R4 drops the default (phase 2)

verification_cmd.py advice points the user at adding strategy: candidate, which then fails.

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-10-11T23:56:51+00:00 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · fr-brainstorming SKILL.md still says strategy defaults to the shape's without the R4 drop / R5 error (phase 2)

plugins/super-fr/skills/fr-brainstorming/SKILL.md:79.

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-10-11T23:56:51+00:00 phase=2 -->
### p2-review-1 · review · phase 2 independent review: 8 findings (7 in, 1 out) (phase 2)

Read-only reviewer over diff b93b7896..HEAD against spec §B / R4-R6: install_problem is the one rule; effective_shape_default at all three binding sites and nowhere else; walk_owed behaviour correct; brainstorm hook only warns; R6 message exact; fixture changes sound; the two never-red tests verified red by monkeypatching. Findings p2-r1..r5, r7, r8 (in) fixed in fa06614d (+ matrix 0f0c5b6d); p2-r6 (out).

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-11T23:56:51+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: R5 tests never isolate the per-row-line and row-verify: sources; self-review covers only section strategy: (phase 2)

fa06614d: test_p2_r1_a_per_row_line_alone_is_flagged_and_names_its_row, test_p2_r1_a_rows_verify_alone_is_flagged_and_names_the_row_and_the_fix (fail on old src), test_p2_r1_self_review_flags_a_per_row_line_with_no_strategy_line.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-11T23:56:51+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: R5 fix advice cannot clear a row's own verify:, which outranks spec lines; message does not name the source row (phase 2)

fa06614d: one message per strategy listing every source; a row verify: source names the row and gives `fr acceptance set-status ... --verify none`; spec R5/§B updated.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-11T23:56:51+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: effective_shape_default bindings in plan_ops._verification_issues and run/visual.py are untested (phase 2)

fa06614d: test_p2_r3_self_review_binds_the_shape_default_only_when_the_repo_can_run_it, test_p2_r3_visual_verification_binds_the_shape_default_like_self_review.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-11T23:56:51+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: brainstorm warning catches only SectionError/AcceptanceError/OSError; other errors escape after commit (phase 2)

fa06614d: _unrunnable_spec_warnings catches Exception (advisory, post-commit); test_p2_r4_a_non_utf8_spec_never_fails_the_resolve and ..._still_resolves_and_advances.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-11T23:56:51+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: R5 warning fires only on resolve --record, not the flag form with --emitted spec= (phase 2)

fa06614d: shared _print_unrunnable_warnings on the flag path; test_p2_r5_the_flag_form_resolve_prints_the_same_warning.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-10-11T23:56:51+00:00 phase=2 state=open resolves=p2-r6 out_of_scope=true -->
### p2-r6-resolved · finding [out-of-scope] · resolves p2-r6: explicit row verify: on a spec with no ## Verification section is never flagged though walk_owed still owes it (phase 2)

The spec deliberately exempts a spec with no ## Verification section (pre-strategies world passes unchanged); not caused by this change. Worth a follow-up if row-level verify: without a section should be flagged too.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-10-11T23:56:51+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: fr verification walk without the install program says 'names no strategy' once R4 drops the default (phase 2)

fa06614d: walk names the filtered default's install problem and suggests per-row none / strategy: none (raw_shape_default helper); test_p2_r7_a_default_the_repo_cannot_run_says_so_instead_of_naming_no_strategy.

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-10-11T23:56:51+00:00 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: fr-brainstorming SKILL.md still says strategy defaults to the shape's without the R4 drop / R5 error (phase 2)

fa06614d: SKILL.md line 79 amended in place (still 119 lines); sync-opencode.py and sync-hermes.py mirrors regenerated; mirror/validation guards green.

<!-- fr:journal kind=discovery scope=plan id=p3-merge-claim created=2026-10-12T00:20:17+00:00 phase=3 -->
### p3-merge-claim · discovery · one _merge_claim decides every claim (phase 3)

run_cmd._merge_claim is shared by claim, --open-unit and resolve's no-agent branch; fr-opencode-plugin claim.ts needed no change.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-12T00:20:17+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

_claimed_identity and _claim_identity's duplicated field handling collapsed into _merge_claim; nothing further to clean
