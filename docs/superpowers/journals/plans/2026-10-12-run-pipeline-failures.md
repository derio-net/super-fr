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
