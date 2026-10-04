# Journal: 2026-10-04-drive-scoped-collect

<!-- fr:journal kind=decision scope=plan id=d-prev-facts-scope-check created=2026-10-04T06:23:07+00:00 phase=1 -->
### d-prev-facts-scope-check · decision · previous facts are scope-checked for batch_prs too (phase 1)

_previous_facts replaces _previous_batch_prs; known_batch_prs now also comes only from a same-scope facts.json (it always did live in the scope dir, so no practical change).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-04T06:23:07+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

acceptance rows, change fragment and verification only; no production code to clean

<!-- fr:journal kind=finding scope=plan id=cr-r7-drive-test-not-tied-to-carry created=2026-10-04T06:27:37+00:00 phase=1 state=open review_scope=in -->
### cr-r7-drive-test-not-tied-to-carry · finding [open] (reviewer: in scope) · The R7 drive test would stay green if the carry were removed (phase 1)

test_a_merged_batch_stays_merged_after_its_members_are_carried injected the batch PR by hand and never asserted that the member was carried.

<!-- fr:journal kind=finding scope=plan id=cr-spec-d-cases-untested created=2026-10-04T06:27:37+00:00 phase=1 state=open review_scope=in -->
### cr-spec-d-cases-untested · finding [open] (reviewer: in scope) · No test for a carried key in a skipped repo, or for a previously-unviewed key at the command layer (phase 1)

Spec §D lists both cases. They hold by construction today (collect.py iterates collected repos only; carried is built from previous.issues only), but nothing pins them.

<!-- fr:journal kind=finding scope=plan id=cr-test-imports-private-helpers-from-test-module created=2026-10-04T06:27:37+00:00 phase=1 state=open review_scope=in -->
### cr-test-imports-private-helpers-from-test-module · finding [open] (reviewer: in scope) · The carry tests import _issue and _pr_closing from test_triage_collect (phase 1)

The shared home for these helpers is tests/unit/triage_fixtures.py.

<!-- fr:journal kind=finding scope=plan id=cr-previous-facts-scope-check-batch-prs created=2026-10-04T06:27:37+00:00 phase=1 state=open review_scope=in -->
### cr-previous-facts-scope-check-batch-prs · finding [open] (reviewer: in scope) · _previous_facts now scope-checks known_batch_prs too (phase 1)

This only matters when --dir is shared between scopes. It costs one extra head lookup per batch there; correctness is unaffected.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-10-04T06:27:37+00:00 phase=1 -->
### review-p1 · review · phase 1 code review: 4 findings, all in scope, none a correctness bug (phase 1)

The dispatched code reviewer read spec, plan and the changed files: collect.py (carry keyed by (repo.lower(), number), closed only, truncation guard, links recomputed, viewed counted before every view_issue), triage_cmd.py (collect_into carry=, _previous_facts parsed once and scope-checked), triage_batch_cmd.py (recollect carry=True and the collect line), and the tests. It found no correctness bugs. Findings: cr-r7-drive-test-not-tied-to-carry, cr-spec-d-cases-untested, cr-test-imports-private-helpers-from-test-module, cr-previous-facts-scope-check-batch-prs.

<!-- fr:journal kind=finding scope=plan id=cr-r7-drive-test-not-tied-to-carry-resolved created=2026-10-04T06:27:37+00:00 phase=1 state=fixed resolves=cr-r7-drive-test-not-tied-to-carry -->
### cr-r7-drive-test-not-tied-to-carry-resolved · finding [fixed] · resolves cr-r7-drive-test-not-tied-to-carry: The R7 drive test would stay green if the carry were removed (phase 1)

The merged PR now comes through FakeForge prs with a closing reference to #5. The test asserts a single view_issue across both passes (the member was carried), that the link was recomputed (issue.prs == [9]), and that batch_pr finds it, before asserting merged.

<!-- fr:journal kind=finding scope=plan id=cr-spec-d-cases-untested-resolved created=2026-10-04T06:27:37+00:00 phase=1 state=fixed resolves=cr-spec-d-cases-untested -->
### cr-spec-d-cases-untested-resolved · finding [fixed] · resolves cr-spec-d-cases-untested: No test for a carried key in a skipped repo, or for a previously-unviewed key at the command layer (phase 1)

Added test_a_carried_issue_in_a_skipped_repo_is_not_emitted (org scope, failing repo) and test_collect_into_with_carry_views_a_key_the_previous_pass_could_not_view (a ForgeError leaves #5 unviewed, and the next carry pass views it).

<!-- fr:journal kind=finding scope=plan id=cr-test-imports-private-helpers-from-test-module-resolved created=2026-10-04T06:27:37+00:00 phase=1 state=fixed resolves=cr-test-imports-private-helpers-from-test-module -->
### cr-test-imports-private-helpers-from-test-module-resolved · finding [fixed] · resolves cr-test-imports-private-helpers-from-test-module: The carry tests import _issue and _pr_closing from test_triage_collect (phase 1)

_issue, _pr_closing and _captured_pr_with_refs moved to tests/unit/triage_fixtures.py; test_triage_collect.py and test_triage_collect_carry.py import them from there.

<!-- fr:journal kind=finding scope=plan id=cr-previous-facts-scope-check-batch-prs-resolved created=2026-10-04T06:27:37+00:00 phase=1 state=refuted resolves=cr-previous-facts-scope-check-batch-prs -->
### cr-previous-facts-scope-check-batch-prs-resolved · finding [refuted] · resolves cr-previous-facts-scope-check-batch-prs: _previous_facts now scope-checks known_batch_prs too (phase 1)

Not a defect. The reviewer itself concludes it is harmless. state_dir is keyed by scope, so only a --dir shared across scopes sees it, and there reusing another scope's batch PRs was never meaningful. Reading facts.json once for both uses is what P1.T2.S3 asked for.
