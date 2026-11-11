<!-- fr:journal-schema=3 -->
# Journal: 2026-11-11-docs-currency

<!-- fr:journal kind=decision scope=plan id=p1-no-skills-list-edit created=2026-11-11T14:40:12+00:00 phase=1 -->
### p1-no-skills-list-edit · decision · fr skills lists per-skill commands, not groups (phase 1)

The plan said to add an `fr docs` line where `fr skills` lists command groups if hand-kept. skills_cmd.py lists one row per skill with its commands, not command groups (debt, gate and release are absent too), so no line was added.

<!-- fr:journal kind=discovery scope=plan id=p1-acceptance-level-int created=2026-11-11T14:40:12+00:00 phase=1 -->
### p1-acceptance-level-int · discovery · Scenario test refs go under the int level (phase 1)

`fr acceptance set-status --level` accepts unit|api|int|ui only; the test_scenarios.py refs were recorded as `int`.

<!-- fr:journal kind=discovery scope=plan id=p1-suite-env-failures created=2026-11-11T14:40:12+00:00 phase=1 -->
### p1-suite-env-failures · discovery · Full suite: 7 environment failures, none in fr docs (phase 1)

14411 passed, 132 skipped, 7 failed in 2h01. The failures are test_artifact_atomic read-only-file, test_bindings_catalogue and test_bindings_probe write-failure tests and test_validate_artifacts unreadable-artifact (all rely on a permission-denied write, which root defeats), plus three test_isolation_container_verbs tests that expect devcontainer mode but run in host-worktree mode. None touches fr.docs. The baseline run was not completed to compare. The install.sh integration tests run a real `npm install -g @devcontainers/cli` over the proxy (their PATH hides the installed devcontainer), which makes the tail of the suite take about two hours.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-11T14:40:12+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

check.py was written once, pure and already split; nothing to clean beyond folding duplicate uncovered findings, done inline

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-11T14:40:12+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

load/render/command were written as separate small modules with no duplication; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-11T14:40:12+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

scenarios share one _docs_fixture.sh from the start; nothing to clean

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-11-11T14:42:29+00:00 phase=1 -->
### p1-review-1 · review · Phase 1 review: fr docs check/status (phase 1)

A separate reviewer read the phase 1 diff against R1-R8. Globs, front matter handling, read-only git, rename parsing, exit codes and the no-write property were verified. Three findings, all in scope, all fixed with tests.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-11T14:42:29+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · R6 not met with unpushed commits on the default branch (phase 1)

changed_paths only went structure-only when merge-base == HEAD, so local main ahead of origin/main ran the stale check.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-11T14:42:29+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Rename test proved only the old side (phase 1)

test_a_rename_counts_both_sides asserted the old path only; a rename into a covered path and a deleted covered file were untested.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-11T14:42:29+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · A config selecting no page passed silently (phase 1)

A pages glob matching no tracked file printed 0 page(s) current and exited 0.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-11T14:42:29+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: R6 not met with unpushed commits on the default branch (phase 1)

With no --base, HEAD on the default branch's local branch is structure only (load.on_default_branch); test_unpushed_commits_on_the_default_branch_are_structure_only. Spec R6 says pushed or not.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-11T14:42:29+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Rename test proved only the old side (phase 1)

Added test_a_rename_into_a_covered_path_counts_the_new_side and test_a_deleted_covered_file_makes_its_page_stale.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-11T14:42:29+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: A config selecting no page passed silently (phase 1)

fr docs check exits 2 when the config selects no page; test_a_config_that_selects_no_page_exits_2. Spec R1 states it.
