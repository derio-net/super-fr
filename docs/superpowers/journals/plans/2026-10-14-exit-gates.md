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
