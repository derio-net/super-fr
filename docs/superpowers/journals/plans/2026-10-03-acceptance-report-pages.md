# Journal: 2026-10-03-acceptance-report-pages

<!-- fr:journal kind=discovery scope=plan id=p1-site-dir-test-pins-existing created=2026-10-03T18:10:51+00:00 phase=1 -->
### p1-site-dir-test-pins-existing · discovery · site_dir render test passed at once (phase 1)

The CLI already supports --out under a site dir with a SHA pin and stamp; test_report_out_under_site_dir_is_sha_pinned_and_stamped pins existing behaviour, no production change.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-03T18:10:51+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

Two one-line text insertions (index link, README badge); nothing to clean.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-03T18:13:27+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · The FR_SKIP_MIGRATION test checks only the render step's env (phase 1)

tests/unit/test_pages_workflow.py:65-68. A job-level or workflow-level env would slip past it.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-03T18:13:27+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · No test pins setup-uv to acceptance-report.yml's SHA or pins `uv tool install ./packages/fr` (phase 1)

Spec §A requires both. A future bump in one workflow would drift silently.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-03T18:13:27+00:00 phase=1 state=open review_scope=out -->
### p1-r3 · finding [open] (reviewer: out of scope) · The CLI-entry migration gate can fail the deploy, and cancel-in-progress applies (phase 1)

Spec §A accepts the gate on purpose; cancel-in-progress is existing pages.yml behaviour.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-03T18:13:27+00:00 phase=1 -->
### p1-review-1 · review · phase 1 code review: 3 findings (2 in, 1 out) (phase 1)

An independent reviewer checked pages.yml against spec §A, CI viability (depth-1 git log, repo root, absolute github links, PATH after uv tool install), whether the tests are meaningful, the index/README edits and the matrix rows. It raised p1-r1 and p1-r2 (in, test gaps) and p1-r3 (out).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-03T18:13:27+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: The FR_SKIP_MIGRATION test checks only the render step's env (phase 1)

test_render_does_not_skip_migration now asserts FR_SKIP_MIGRATION appears nowhere in pages.yml.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-03T18:13:27+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: No test pins setup-uv to acceptance-report.yml's SHA or pins `uv tool install ./packages/fr` (phase 1)

test_fr_is_installed_like_acceptance_report_installs_it asserts pages.yml's setup-uv uses string equals acceptance-report.yml's, plus the install step; a mutated SHA makes it fail (verified).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-03T18:13:27+00:00 phase=1 state=open resolves=p1-r3 out_of_scope=true -->
### p1-r3-resolved · finding [out-of-scope] · resolves p1-r3: The CLI-entry migration gate can fail the deploy, and cancel-in-progress applies (phase 1)

The migration-gate refusal is an accepted design decision (spec §A step 5); cancel-in-progress predates this change.
